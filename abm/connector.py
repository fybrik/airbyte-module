#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import docker
import json
import tempfile
import pyarrow as pa
from pyarrow import json as pa_json

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
        self.client = docker.from_env()
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
    For instance, it the path is '/tmp/tmp12345', return '/json/tmp12345'.
    '''
    def name_in_container(self, path):
        return path.replace(self.workdir, '/tmp', 1)

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
    def filter_reply(self, lines):
        ret = []
        for line in lines:
            try:
               line_dict = json.loads(line)
               if 'type' in line_dict:
                   if line_dict['type'] == 'CATALOG':
                       ret.append(line)
                   elif line_dict['type'] == 'RECORD':
                       ret.append(self.extract_data(line_dict))
            finally:
               continue
        return ret

    '''
    ***** TODO: have the mount point defined somewhere
    Run a docker container from the connector image.
    Mount the workdir on /tmp. Remove the container after done.
    '''
    def run_container(self, command):
        self.logger.debug("running command: " + command)
        try:
            reply = self.client.containers.run(self.connector, command,
                volumes=[self.workdir + ':/tmp'], network_mode='host', remove=True)
            return self.filter_reply(reply.splitlines())
        except docker.errors.DockerException as e:
            self.logger.error('Running of docker container failed',
                              extra={'error': str(e)})
            return None

    # Given configuration, obtain the Airbyte Catalog, which includes list of datasets
    def get_catalog(self):
        return self.run_container('discover --config ' + self.name_in_container(self.conf_file.name))

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
        return self.run_container('read --config ' + self.name_in_container(self.conf_file.name) +
                            ' --catalog ' + self.name_in_container(catalog_file.name))


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

    '''
    Creates a template catalog for write connectors
    '''
    def create_write_catalog(self):
        template = '{ \
        "streams": [{ \
                "sync_mode": "full_refresh", \
                "destination_sync_mode": "overwrite", \
                "stream": { \
                        "name": "testing", \
                        "json_schema": { \
                                "$schema": "http://json-schema.org/draft-07/schema#", \
                                "type": "object", \
                                "properties": { \
                                } \
                        }, \
                        "supported_sync_modes": [ \
                                "full_refresh" \
                        ] \
                } \
        }] \
        }'

        tmp_catalog = tempfile.NamedTemporaryFile(dir=self.workdir)
        tmp_catalog.write(json.dumps(template).encode('utf-8'))
        tmp_catalog.flush()
        return tmp_catalog

    def write_dataset(self, payload):
        self.logger.info('write requested')
# The catalog to be provided to the write command is from a template - there is no discover on the write
        tmp_catalog = self.create_write_catalog()

 # eg echo payload | docker run -v /Users/eliot/temp:/local -i airbyte/destination-local-json write --catalog /local/airbyte_catalog.txt --config /local/airbyte_write1.json
        self.run_container('write --config ' + self.name_in_container(self.conf_file.name) + ' --catalog ' + self.name_in_container(tmp_catalog.name))
        tmp_catalog.close()

    def get_dataset_table(self, schema):
        dataset = self.get_dataset()
        with tempfile.NamedTemporaryFile(dir=self.workdir) as dataset_file:
            for line in dataset:
                dataset_file.write(line)
            dataset_file.flush()
            return pa_json.read_json(dataset_file.name,
                                      parse_options=pa_json.ParseOptions(schema))
