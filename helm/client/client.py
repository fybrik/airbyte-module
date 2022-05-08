#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import pyarrow.flight as fl
import json

def read_from_endpoint(endpoint):
    client = fl.connect("grpc://{}:{}".format(args.host, args.port))
    result: fl.FlightStreamReader = client.do_get(endpoint.ticket)
    print(result.read_pandas())

def read_dataset():
    threads = []
    for endpoint in info.endpoints:
        read_from_endpoint(endpoint)

def main(host, port, asset):
    request = {
       "asset": asset,
    }
    global client, info
    client = fl.connect("grpc://{}:{}".format(host, port))
    info = client.get_flight_info(
        fl.FlightDescriptor.for_command(json.dumps(request)))

    read_dataset()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='arrow-flight-module sample')
    parser.add_argument(
        '--host', type=str, default='localhost', help='abm hostname')
    parser.add_argument(
        '--port', type=int, default=8080, help='Listening port')
    parser.add_argument(
        '--asset', type=str, default='userdata', help='name of requested asset')
    args = parser.parse_args()

    main(args.host, args.port, args.asset)
