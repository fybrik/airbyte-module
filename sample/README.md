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
2. Run the server with
    ```bash
    pipenv run server --config sample/sample.yaml  --workdir /tmp
    ```
3. Read the `userdata` dataset from HTTP server:
    ```bash
    curl localhost:8080/userdata
    ```
4. Read the `userdata` dataset from the arrow-flight server:
   ```bash
   pipenv run python sample/sample.py
    ```

### Write example
1. Run the server with
    ```bash
    pipenv run server --config sample/write_config.yaml  --workdir /tmp
2. Send the information to be written to the server
   sample/post.sh
3. Check the output in /tmp/airbyte_out

