#
# Copyright 2020 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import pyarrow.flight as fl
import pyarrow as pa
import json
from faker import Faker

def fake_dataset(num_entries):
        Faker.seed(1234)
        f = Faker()
        arrays = []
        column_names = []

        arr = []
        for i in range(num_entries):
           arr.append(f.date_of_birth())
        arrays.append(arr)
        column_names.append("DOB")

        arr = []
        for i in range(num_entries):
           arr.append(f.name())
        arrays.append(arr)
        column_names.append("Name")

        return arrays, column_names

# taken from https://github.com/apache/arrow/blob/master/python/pyarrow/tests/test_flight.py#L450
class HttpBasicClientAuthHandler(fl.ClientAuthHandler):
    """An example implementation of HTTP basic authentication."""

    def __init__(self, username, password):
        super().__init__()
        self.basic_auth = fl.BasicAuth(username, password)
        self.token = None

    def authenticate(self, outgoing, incoming):
        auth = self.basic_auth.serialize()
        outgoing.write(auth)
        self.token = incoming.read()

    def get_token(self):
        return self.token

request = {
    "asset": "write_test",
    "stream_name": "testing",
    "schema":  '{"streams": [{"sync_mode": "full_refresh",  "destination_sync_mode": "overwrite", "stream": {"supported_sync_modes": ["full_refresh"], "name": "testing", "json_schema": {"type": "object",  "properties": {"DOB": { "type": "string" },"Name": { "type": "string" }}}}}]}'
  }

def main(port):
    client = fl.connect("grpc://localhost:{}".format(port))
    arrays, names = fake_dataset(10)

    data = pa.Table.from_arrays(arrays, names=names)
    writer, _ = client.do_put(fl.FlightDescriptor.for_command(json.dumps(request)),
                              data.schema)
    writer.write_table(data, 1024)
    writer.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='airbyte-module sample')
    parser.add_argument(
        '--port', type=int, default=8081, help='Listening port')
    args = parser.parse_args()
    main(args.port)
