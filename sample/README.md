# Sample

This sample is for experimenting with the Airbyte Module (ABM) locally,
without Kubernetes.

The server is configured to obtain a Parquet file from
https://github.com/Teradata/kylo/blob/master/samples/sample-data/parquet/userdata2.parquet

The Airbyte server is both an HTTP server (on port 8080) and an
Arrow Flight server (on port 8081)

## Steps
### Read example

1. Install python dependencies
    ```bash
    pipenv install
    ```
1. Run the server with
    ```bash
    pipenv run server --config sample/sample.yaml  --workdir /tmp
    ```
1. Read the `userdata` dataset from HTTP server:
    ```bash
    curl localhost:8080/userdata
    ```
1. Read the `userdata` dataset from the arrow-flight server:
   ```bash
   pipenv run python sample/sample.py
    ```

### Write example
1. Install python dependencies
    ```bash
    pipenv install
    ```
1. Run the server with
    ```bash
    pipenv run server --config sample/write_config.yaml  --workdir /tmp
    ```
1. Send the information to be written to the server:
   ```bash
   sample/post.sh
   ```
1. Check the output in /tmp/airbyte_out
1. Send the information to be written to the server using arrow-flight:
   ```bash
   pipenv run python sample/sample_put.py
   ```
1. Check the output in /tmp/airbyte_out
