#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import docker
import json
import tempfile
import pyarrow as pa
from pyarrow import json as pa_json
from .vault import get_secrets_from_vault
from .container import Container

MOUNTDIR = '/local'
CHUNKSIZE = 1024

class GenericConnector(Container):
    def __init__(self, config, logger, workdir, asset_name=""):
        if 'connection' not in config:
            raise ValueError("'connection' field missing from configuration")

        if 'name' not in config['connection']:
            raise ValueError("the name of the connection is missing")
        connection_name = config['connection']['name'] # e.g. postgres, google-sheets, us-census

        self.config = config['connection'][connection_name]
        if 'connector' not in self.config:
            raise ValueError("'connector' field missing from configuration")

        if 'vault_credentials' in config:
            vault_credentials = config['vault_credentials']
            secrets = get_secrets_from_vault(vault_credentials=vault_credentials, datasetID=asset_name)
            if secrets:
               # if the secret has nested structure then it is saved as a json object
               for key, value in secrets.items():
                 try:
                   secrets[key] = json.loads(value)
                 except BaseException:
                   continue
               # merge config with secrets returned by vault
               self.config = dict(self.config, **secrets)
            else:
                logger.info("no secrets returned by vault")

        super().__init__(logger, workdir, MOUNTDIR)

        self.connector = self.config['connector']

        # The content of self.config will be written to a temporary json file,
        # and sent to the connector. First, we must remove the 'connector' entry,
        # since the Airbyte connectors do not recognize this field
        del self.config['connector']

        # if the port field is a string, cast it to integer
        if 'port' in self.config and type(self.config['port']) == str:
            self.config['port'] = int(self.config['port'])

        self.catalog_dict = None
        # json_schema holds the json schema of the stream (table) to read if such stream is provided.
        # otherwise it cobtains the json schema of the first stream in the catalog.
        self.json_schema = None

        # create the temporary json file for configuration
        self.conf_file = tempfile.NamedTemporaryFile(dir=self.workdir)
        self.conf_file.write(json.dumps(self.config).encode('utf-8'))
        self.conf_file.flush()


    '''
    Return the stream name if such provided. Otherwise return an empty string.
    '''
    def get_stream_name(self):
        if "table" in self.config:
            # The database table is the stream name if exists
            return self.config["table"]
        return ""

    def __del__(self):
        self.conf_file.close()

    '''
    Remove metadata columns, if such exists, from "CATALOG" lines returned by an Airbyte read operation.
    For instance, if a line is:
        {'name': 'stream_name', 'json_schema': {'type': 'object', 'properties': {'_airbyte_stream_name_hashid': {'type': 'string'}, '_airbyte_ab_id': {'type': 'string'},
        'dob': {'type': 'string'}, '_airbyte_normalized_at': {'type': 'string', 'format': 'date-time', 'airbyte_type': 'timestamp_without_timezone'},
         'name': {'type': 'string'}, '_airbyte_emitted_at': {'type': 'string', 'format': 'date-time', 'airbyte_type': 'timestamp_with_timezone'}}}}
    extract:
        {'name': 'stream_name', 'json_schema': {'type': 'object', 'properties': {'dob': {'type': 'string'},'name': {'type': 'string'}}}}

    These metadata columns are added in the normalization process.
    ref:  https://docs.airbyte.com/understanding-airbyte/basic-normalization
    '''
    def remove_metadata_columns(self, line_dict):
        catalog_streams = line_dict['catalog']['streams']
        stream_name = self.get_stream_name()
        # get the stream: if a stream (table) is provided
        # then find it otherwise use the first stream in
        # streams list.
        if stream_name == "":
            # no specific stream was provided then take the first item
            # in the list
            the_stream = catalog_streams[0]
        else:
            for stream in catalog_streams:
                if stream['name'] == stream_name:
                   the_stream = stream
                   break
        # remove metadata columns
        properties = the_stream['json_schema']['properties']
        for key in list(properties.keys()):
            if key.startswith('_airbyte_'):
                del properties[key]
        # set the json_schema for later use
        self.json_schema = the_stream['json_schema']
        line_dict['catalog']['streams'] = [the_stream]
        return json.dumps(line_dict).encode()

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
                       ret.append(self.remove_metadata_columns(line_dict))
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
        volumes=[self.workdir + ':' + MOUNTDIR]
        return super().run_container(command, self.connector, volumes=volumes, remove=True, detach=False, stream=True)

    def open_socket_to_container(self, command):
        volumes=[self.workdir + ':' + MOUNTDIR]
        return super().open_socket_to_container(command, self.connector, volumes)

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
        properties = self.json_schema['properties']
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
        stream_name = self.get_stream_name()
        for stream in self.catalog_dict['catalog']['streams']:
            if 'name' in stream:
                if stream_name != "" and stream['name'] != stream_name:
                    continue
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
        with tempfile.NamedTemporaryFile(dir=self.workdir,delete=False) as tmp_configured_catalog:
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
                with tempfile.NamedTemporaryFile(dir=self.workdir,delete=False) as dataset_file:
                    for line in batch:
                        dataset_file.write(line)
                    dataset_file.flush()
                    yield pa_json.read_json(dataset_file.name,
                                      parse_options=pa_json.ParseOptions(schema))

    '''
    Creates a template catalog for write connectors
    '''
    def create_write_catalog(self, schema):
        tmp_catalog = tempfile.NamedTemporaryFile(dir=self.workdir, mode='w+t',delete=False)
        tmp_catalog.writelines(schema)
        tmp_catalog.flush()
        return tmp_catalog

    '''
    Creates a write command
    '''
    def create_write_command(self, schema):
        # The catalog to be provided to the write command is from an input schema -
        # there is no discover on the write
        tmp_catalog = self.create_write_catalog(schema)

        command = 'write --config ' + self.name_in_container(self.conf_file.name) + \
                  ' --catalog ' + self.name_in_container(tmp_catalog.name)
        return command, tmp_catalog

    '''
    Write dataset passed as file
    '''
    def write_dataset(self, schema, fptr, length):
        self.logger.debug('write requested')
        # The catalog to be provided to the write command is from an input schema -
        # there is no discover on the write
        tmp_catalog = self.create_write_catalog(schema)
        command = 'write --config ' + self.name_in_container(self.conf_file.name) + \
                  ' --catalog ' + self.name_in_container(tmp_catalog.name)
        s, container = self.open_socket_to_container(command)

        bytesToWrite = length
        while bytesToWrite > 0:
            readSize = CHUNKSIZE if (bytesToWrite - CHUNKSIZE) >= 0 else bytesToWrite
            bytesToWrite -= readSize
            payload = fptr.read(int(readSize))
            self.write_to_socket_to_container(s, payload)
        self.close_socket_to_container(s, container)
        tmp_catalog.close()
        # TODO: Need to figure out how to handle error return
        return True
    '''
    Write dataset passed as bytes
    '''
    def write_dataset_bytes(self, socket, bytes):
        self.logger.debug('write bytes requested')
        record = bytes + b'\n'
        self.write_to_socket_to_container(socket, record)
        # TODO: Need to figure out how to handle error return
        return True

