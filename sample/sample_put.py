#
# Copyright 2020 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import pyarrow.flight as fl
import pyarrow as pa
import json

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
    "asset": "userdata",
    "schema": '{ \
        "streams": [{ \
                "sync_mode": "full_refresh", \
                "destination_sync_mode": "overwrite", \
                "stream": { \
                        "name": "revital76", \
                        "json_schema": { \
                            "$schema": "http://json-schema.org/draft-07/schema#", \
                            "type": "object", \
                            "properties": { \
                                "DOB": { \
                                    "type": "string" \
                                }, \
                                "FirstName": { \
                                    "type": "string" \
                                }, \
                                "LastNAME": { \
                                    "type": "string" \
                                } \
                            } \
                        }, \
                        "supported_sync_modes": [ \
                                "full_refresh" \
                        ] \
                } \
            }] \
        }'
}

def main(port):
    client = fl.connect("grpc://localhost:{}".format(port))
    arrays = [["RECORD", "RECORD", "RECORD"], [{"stream": "testing","data": {"DOB": "01/02/1992", "FirstName": "John", "LastNAME":"Jones"}, "emitted_at": 0},
                                     {"stream": "testing","data": {"DOB": "01/02/1994", "FirstName": "Ludwig", "LastNAME":"Beethoven"}, "emitted_at": 0},
                                     {"stream": "testing","data": {"DOB": "01/02/1995", "FirstName": "Frank", "LastNAME":"Sinatra"}, "emitted_at": 0}]]
    names = ["type", "record"]
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
