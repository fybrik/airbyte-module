#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#

from fybrik_python_logging import init_logger, logger, DataSetID, ForUser
from .config import Config
from .connector import GenericConnector
from .ticket import ABMTicket
import http.server
import json
import os
import socketserver
from http import HTTPStatus
import pyarrow.flight as fl

class ABMHttpHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self.config_path = server.config_path
        self.workdir = server.workdir
        socketserver.BaseRequestHandler.__init__(self, request, client_address, server)

    '''
    do_GET() gets the asset name from the URL.
    for instance, if the URL is localhost:8080/userdata
    then the asset name is userdata.
    Obtain the dataset associated with the asset name, and
    return it to client.
    '''
    def do_GET(self):
        with Config(self.config_path) as config:
            asset_name = self.path.lstrip('/')
            try:
                asset_conf = config.for_asset(asset_name)
                connector = GenericConnector(asset_conf, logger, self.workdir)
            except ValueError:
                logger.error('asset not found or malformed configuration')
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                return

            batches = connector.get_dataset()
            if batches:
                self.send_response(HTTPStatus.OK)
                self.end_headers()
                for batch in batches:
                    for line in batch:
                        self.wfile.write(line + b'\n')
            else:
                self.send_response(HTTPStatus.BAD_REQUEST)
                self.end_headers()

# Have the same routine for PUT and POST
    def do_WRITE(self):
        logger.info('write requested')
        with Config(self.config_path) as config:
            asset_name = self.path.lstrip('/')
            try:
                asset_conf = config.for_asset(asset_name)
                connector = GenericConnector(asset_conf, logger, self.workdir)
            except ValueError:
                logger.error('asset ' + asset_name + ' not found or malformed configuration')
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                return
            # Change to allow for streaming reads
            read_length = self.headers.get('Content-Length')
            if connector.write_dataset(self.rfile, int(read_length)):
                self.send_response(HTTPStatus.OK)
            else:
                self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()

    def do_PUT(self):
        self.do_WRITE()

    def do_POST(self):
        self.do_WRITE()

class ABMHttpServer(socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass,
                 config_path, workdir):
        self.config_path = config_path
        self.workdir = workdir
        socketserver.TCPServer.__init__(self, server_address,
                                        RequestHandlerClass)

class ABMFlightServer(fl.FlightServerBase):
    def __init__(self, config_path: str, port: int, workdir: str, *args, **kwargs):
        super(ABMFlightServer, self).__init__(
                "grpc://0.0.0.0:{}".format(port), *args, **kwargs)
        self.config_path = config_path
        self.workdir = workdir

    '''
    Return a list of locations which can serve a client
    request for a dataset, given a flight ticket.
    The location list may be empty to indicate that the client
    should contact the same server that server its
    get_flight_info() request.
    '''
    def _get_locations(self):
        locations = []
        local_address = os.getenv("MY_POD_IP")
        if local_address:
            locations += "grpc://{}:{}".format(local_address, self.port)
        return locations

    '''
    Given a list of tickets and a list of locations,
    return a list of endpoints returned by get_flight_info.
    '''
    def _get_endpoints(self, tickets, locations):
        endpoints = []
        i = 0
        for ticket in tickets:
            if locations:
                endpoints.append(fl.FlightEndpoint(ticket.toJSON(), [locations[i]]))
                i = (i + 1) % len(locations)
            else:
                endpoints.append(fl.FlightEndpoint(ticket.toJSON(), []))
        return endpoints

    '''
    Serve arrow flight do_get requests
    '''
    def do_get(self, context, ticket: fl.Ticket):
        ticket_info: ABMTicket = ABMTicket.fromJSON(ticket.ticket)

        logger.info('retrieving dataset',
            extra={'ticket': ticket.ticket,
                   DataSetID: ticket_info.asset_name,
                   ForUser: True})

        with Config(self.config_path) as config:
            asset_conf = config.for_asset(ticket_info.asset_name)

        connector = GenericConnector(asset_conf, logger, self.workdir)
        # determine schema using the Airbyte 'discover' operation
        schema = connector.get_schema()

        # read dataset using the Airbyte 'read' operation
        batches = connector.get_dataset_batches(schema)

        # return dataset as arrow flight record batches
        return fl.GeneratorStream(schema, batches)

    '''
    Serve arrow flight do_put requests
    '''
    def do_put(self, context, descriptor, reader, writer):
        asset_name = json.loads(descriptor.command)['asset']
        logger.info('getting flight information',
            extra={'command': descriptor.command,
                   DataSetID: asset_name,
                   ForUser: True})
        with Config(self.config_path) as config:
            df_bytes = []
            asset_conf = config.for_asset(asset_name)
            connector = GenericConnector(asset_conf, logger, self.workdir)
            batches = reader.read_all().combine_chunks().to_batches(max_chunksize=1)
            for batch in batches:
                df_bytes.append(batch.to_pandas().to_json(orient='records').encode())
            connector.write_dataset_bytes(df_bytes, True)

    '''
    Serve arrow-flight get_flight_info requests.
    Determine dataset schema.
    Return flight info with single ticket for entire dataset.
    '''
    def get_flight_info(self, context, descriptor):
        asset_name = json.loads(descriptor.command)['asset']
        logger.info('getting flight information',
            extra={'command': descriptor.command,
                   DataSetID: asset_name,
                   ForUser: True})

        with Config(self.config_path) as config:
            asset_conf = config.for_asset(asset_name)
            # given the asset configuration, let us determine the schema
            connector = GenericConnector(asset_conf, logger, self.workdir)
            schema = connector.get_schema()

        locations = self._get_locations()

        tickets = [ABMTicket(asset_name)]

        endpoints = self._get_endpoints(tickets, locations)
        return fl.FlightInfo(schema, descriptor, endpoints, -1, -1)

class ABMServer():
    def __init__(self, config_path: str, port: int, loglevel: str, workdir: str, *args, **kwargs):
        with Config(config_path) as config:
            init_logger(loglevel, config.app_uuid, 'airbyte-module')

        server = ABMHttpServer(("0.0.0.0", port), ABMHttpHandler,
                               config_path, workdir)
        server.serve_forever()
