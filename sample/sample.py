#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import pyarrow.flight as fl
import pyarrow as pa
import json

request = {
    "asset": "letter_frequency",
}

def main(port):
    client = fl.connect("grpc://localhost:{}".format(port))

    info = client.get_flight_info(
        fl.FlightDescriptor.for_command(json.dumps(request)))

    print("Schema: " + str(info.schema))
    endpoint = info.endpoints[0]
    result: fl.FlightStreamReader = client.do_get(endpoint.ticket)
    print(result.read_all().to_pandas())

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='airbyte-module sample')
    parser.add_argument(
        '--port', type=int, default=8081, help='Listening port')
    args = parser.parse_args()

    main(args.port)
