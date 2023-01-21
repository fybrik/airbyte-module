#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import pyarrow.flight as fl
import pyarrow as pa
from faker import Faker
import json

def read_from_endpoint(endpoint):
    client = fl.connect("grpc://{}:{}".format(args.host, args.port))
    result: fl.FlightStreamReader = client.do_get(endpoint.ticket)
    print(result.read_pandas())

def read_dataset():
    threads = []
    for endpoint in info.endpoints:
        read_from_endpoint(endpoint)

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

def main(host, port, asset, operation):
    global client
    client = fl.connect("grpc://{}:{}".format(host, port))
    if operation == "get":
      request = {
        "asset": asset,
      }
      global info
      info = client.get_flight_info(
          fl.FlightDescriptor.for_command(json.dumps(request)))

      read_dataset()
    elif operation == "put":
      request = {
        "asset": asset,
        # The request must contain the json_schema of the written data.
        "json_schema": '{"$schema": "http://json-schema.org/draft-07/schema#", "type": "object",  "properties": {"Name": { "type": "string" }, "DOB": { "type": "string" } }}'
      }
       
      arrays, names = fake_dataset(10)

      data = pa.Table.from_arrays(arrays, names=names)
      writer, _ = client.do_put(fl.FlightDescriptor.for_command(json.dumps(request)),
                                data.schema)
      writer.write_table(data, 1024)
      writer.close()
    else:
      print("Unsupported operation. should be get or put")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='arrow-flight-module sample')
    parser.add_argument(
        '--host', type=str, default='localhost', help='abm hostname')
    parser.add_argument(
        '--port', type=int, default=8080, help='Listening port')
    parser.add_argument(
        '--asset', type=str, default='userdata', help='name of requested asset')
    parser.add_argument(
        '--operation', type=str, default='get', help='type of operation. can be get or put')
    args = parser.parse_args()

    main(args.host, args.port, args.asset, args.operation)
