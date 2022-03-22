# Sample

This sample is for experimenting with the Airbyte Module (ABM) locally,
without Kubernetes.

The server is configured to obtain a CSV file from
https://people.sc.fsu.edu/~jburkardt/data/csv/letter_frequency.csv

The Airbyte server is both an HTTP server (on port 8080) and an
Arrow Flight server (on port 8081)

## Steps
1. Install python dependencies
    ```bash
    pipenv install
    ```
1. Run the server with
    ```bash
    pipenv run server --config sample/sample.yaml  --workdir /tmp
    ```
1. Read the letter_frequency dataset from HTTP server:
    ```bash
    curl localhost:8080/letter_frequency
    ```
1. Read the letter_frequency dataset from the arrow-flight server:
   ```bash
   pipenv run python sample/sample.py
    ```
