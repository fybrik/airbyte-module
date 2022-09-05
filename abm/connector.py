#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import docker
import json
import tempfile
import pyarrow as pa
from pyarrow import json as pa_json

MOUNTDIR = '/local'
CHUNKSIZE = 1024
CTRLD = '\x04'.encode()

class GenericConnector:
    def __init__(self, config, logger, workdir):
        if 'connection' not in config:
            raise ValueError("'connection' field missing from configuration")

        if 'name' not in config['connection']:
            raise ValueError("the name of the connection is missing")
        connection_name = config['connection']['name'] # e.g. postgres, google-sheets, us-census

        self.config = config['connection'][connection_name]
        if 'connector' not in self.config:
            raise ValueError("'connector' field missing from configuration")

        self.workdir = workdir
    # Potentially the fybrik-blueprint pod for the airbyte module can start before the docker daemon pod, causing
    # docker.from_env() to fail
        retryLoop = 0
        while retryLoop < 10:
            try:
                self.client = docker.from_env()
            except Exception as e:
                print('error on docker.from_env() ' + str(e) + ' sleep and retry.  Retry count = ' + str(retryLoop))
                time.sleep(1)
                retryLoop += 1
            else:
                retryLoop = 10

        self.connector = self.config['connector']

        # The content of self.config will be written to a temporary json file,
        # and sent to the connector. First, we must remove the 'connector' entry,
        # since the Airbyte connectors do not recognize this field
        del self.config['connector']

        self.logger = logger

        # if the port field is a string, cast it to integer
        if 'port' in self.config and type(self.config['port']) == str:
            self.config['port'] = int(self.config['port'])

        self.catalog_dict = None

        # create the temporary json file for configuration
        self.conf_file = tempfile.NamedTemporaryFile(dir=self.workdir)
        self.conf_file.write(json.dumps(self.config).encode('utf-8'))
        self.conf_file.flush()

    def __del__(self):
        self.conf_file.close()

    '''
    Translate the name of the temporary file in the host to the name of the same file
    in the container.
    For instance, it the path is '/tmp/tmp12345', return '/local/tmp12345'.
    '''
    def name_in_container(self, path):
        return path.replace(self.workdir, MOUNTDIR, 1)

    '''
    Extract only the relevant data in "RECORD" lines returned by an Airbyte read operation.
    For instance, if a line is:
       {"type":"RECORD","record":{"stream":"users","data":{"id":1,"col1":"record1"},"emitted_at":"1644416403239","namespace":"public"}}
    extract:
       {"id":1,"col1":"record1"}
    '''
    def extract_data(self, line_dict):
        return json.dumps(line_dict['record']['data']).encode('utf-8')

    '''
    Filter out all irrelevant lines, such as log lines.
    Relevant lines are JSON-formatted, and have a 'type' field which is
    either 'CATALOG' or 'RECORD'
    '''
    def filter_reply(self, lines, batch_size=100):
        count = 0
        for line in lines:
            if count == 0:
                ret = []
            try:
               line_dict = json.loads(line)
               if 'type' in line_dict:
                   if line_dict['type'] == 'LOG':
                       continue
                   if line_dict['type'] == 'CATALOG':
                       ret.append(line)
                   elif line_dict['type'] == 'RECORD':
                       ret.append(self.extract_data(line_dict))
                   count = count + 1
               if count == batch_size:
                   count = 0
                   yield ret
            finally:
               continue
        if count == 0:
            yield []
        else:
            yield ret

    '''
    Run a docker container from the connector image.
    Mount the workdir on /local. Remove the container after done.
    '''
    def run_container(self, command):
        self.logger.debug("running command: " + command)
        try:
            reply = self.client.containers.run(self.connector, command,
                volumes=[self.workdir + ':' + MOUNTDIR], network_mode='host',
                remove=True, stream=True)
            return self.filter_reply(reply)
        except docker.errors.DockerException as e:
            self.logger.error('Running of docker container failed',
                              extra={'error': str(e)})
            return None

    def open_socket_to_container(self, command):
        container = self.client.containers.run(self.connector, detach=True,
                             tty=True, stdin_open=True,
                             volumes=[self.workdir + ':' + MOUNTDIR],
                             command=command, remove=True)
        # attach to the container stdin socket
        s = container.attach_socket(params={'stdin': 1, 'stream': 1, 'stdout': 1, 'stderr': 1})
        s._sock.setblocking(True)
        return s, container

    def close_socket_to_container(self, s, container):
        s._sock.sendall(CTRLD)  # ctrl d to finish things up
        s._sock.close()
        container.stop()
        self.client.close()

    def write_to_socket_to_container(self, s, binary_textline):
        s._sock.sendall(binary_textline)
        s.flush()

    # Given configuration, obtain the Airbyte Catalog, which includes list of datasets
    def get_catalog(self):
        ret = []
        for lines in self.run_container('discover --config ' + self.name_in_container(self.conf_file.name)):
            ret = ret + lines
        return ret

    translate = {
        'number': 'DOUBLE', # Number may be an integer or a double. We play it safe
        'string': 'STRING',
    }

    '''
    Return the schema of the first dataset in the catalog.
    Used by arrow-flight server for both the get_flight_info() and do_get().
    Not needed for the Airbyte http server.
    '''
    def get_schema(self):
        self.get_catalog_dict()
        if self.catalog_dict == None:
            return None

        schema = pa.schema({})
        properties = self.catalog_dict['catalog']['streams'][0]['json_schema']['properties']
        for field in properties:
            type_field = properties[field]['type']
            if type(type_field) is list:
                t = type_field[0]
            else:
                t = type_field
            schema = schema.append(pa.field(field, self.translate[t]))
        return schema

    '''
    run the Airbyte read operation to obtain all datasets
    '''
    def read_stream(self, catalog_file):
        # step 1: construct the ConfiguredAirbyteCatalog structure,
        #         for an Airbyte read operation
        streams = []
        for stream in self.catalog_dict['catalog']['streams']:
            stream_dict = {}
            stream_dict['sync_mode'] = 'full_refresh'
            stream_dict['destination_sync_mode'] = 'overwrite'
            stream_dict['stream'] = {}
            stream_dict['stream']['source_defined_cursor'] = False
            stream_dict['stream']['name'] = stream['name']
            if 'namespace' in stream:
                stream_dict['stream']['namespace'] = stream['namespace']
            stream_dict['stream']['supported_sync_modes'] = \
                stream['supported_sync_modes']
            stream_dict['stream']['json_schema'] = stream['json_schema']
            streams.append(stream_dict)

        # step 2: write the ConfiguredAirbyteCatalog structure to file
        catalog_file.write(json.dumps({'streams': streams}).encode('utf-8'))
        catalog_file.flush()

        # step 3: Run the Airbyte read operation to read the datasets
        return self.run_container('read --config '
                      + self.name_in_container(self.conf_file.name)
                      + ' --catalog '
                      + self.name_in_container(catalog_file.name))

    '''
    Obtain an AirbyteCatalog json structure, and translate it to a dictionary.
    Store this dictionary in self.catalog_dict
    '''
    def get_catalog_dict(self):
        # if self.catalog_dict is already populated, no need to do anything
        if self.catalog_dict:
            return

        airbyte_catalog = self.get_catalog()

        if not airbyte_catalog:
            return

        if len(airbyte_catalog) != 1:
            self.logger.error('Received more than a single response line from connector.')
            return

        try:
            self.catalog_dict = json.loads(airbyte_catalog[0])
        except ValueError as err:
            self.logger.error('Failed to parse AirByte Catalog JSON',
                              extra={'error': str(err)})

    '''
    To obtain a dataset, obtain an AirbyteCatalog json structure,
    and use it to for an Airbyte read operation.
    '''
    def get_dataset(self):
        # step 1: obtain an AirbyteCatalog json structure
        self.get_catalog_dict()
        if self.catalog_dict == None:
            return None

        # step 2: call read_stream() to run Airbyte read operation
        with tempfile.NamedTemporaryFile(dir=self.workdir) as tmp_configured_catalog:
            return self.read_stream(tmp_configured_catalog)

    '''
    Call self.get_dataset() to obtain an array of JSON structures.
    Transform this array into a pyarrow Table. In order to do that,
    temporarily write the JSON lines to file.
    '''
    def get_dataset_batches(self, schema):
        batches = self.get_dataset()
        for batch in batches:
            if batch:
                with tempfile.NamedTemporaryFile(dir=self.workdir) as dataset_file:
                    for line in batch:
                        dataset_file.write(line)
                    dataset_file.flush()
                    yield pa_json.read_json(dataset_file.name,
                                      parse_options=pa_json.ParseOptions(schema))

    '''
    Creates a template catalog for write connectors
    '''
    def create_write_catalog(self, schema):
        tmp_catalog = tempfile.NamedTemporaryFile(dir=self.workdir, mode='w+t')
        tmp_catalog.writelines(schema)
        tmp_catalog.flush()
        return tmp_catalog

    '''
    Write dataset passed as list of bytes.
    '''
    def write_dataset_bytes(self, bytes, schema: str, reformat=False):
        self.logger.debug('write bytes requested')
        # The catalog to be provided to the write command is from a template -
        # there is no discover on the write
        tmp_catalog = create_write_catalog(schema)

        command = 'write --config ' + self.name_in_container(self.conf_file.name) + \
                  ' --catalog ' + self.name_in_container(tmp_catalog.name)
        s, container = self.open_socket_to_container(command)

        for record in bytes:
            if reformat:
                record = record[1:-1] + b'\n'
            self.write_to_socket_to_container(s, record)

        self.close_socket_to_container(s, container)
        tmp_catalog.close()
        # TODO: Need to figure out how to handle error return
        return True

    '''
    Write dataset passed as JSON structure.
    '''
    def write_dataset_json(self, data, schema: str):
        # eg echo payload | docker run -v /Users/eliot/temp:/local -i airbyte/destination-local-json write --catalog /local/airbyte_catalog.txt --config /local/airbyte_write1.json
        tmp_catalog = create_write_catalog(schema)
        command = 'write --config ' + self.name_in_container(self.conf_file.name) + \
                  ' --catalog ' + self.name_in_container(tmp_catalog.name)
        s, container = self.open_socket_to_container(command)
        bytes = data.encode()
        bytes = bytes + b'\n'
        self.write_to_socket_to_container(s,  bytes)
        self.close_socket_to_container(s, container)
        tmp_catalog.close()
        # TODO: Need to figure out how to handle error return
        return True
