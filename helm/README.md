# Deploying the Airbyte Module using Helm

1. From the `helm` directory of the Airbyte Module, run:
    ```bash
    helm install airbyte-module -f abm/values.sample.yaml abm -n default
    ```

    This command deploys an airbyte-module pod in the `default` namespace, and creates an 'airbyte-module' service.


1. To test it, go to the `client` directory, and run:
    ```bash
    ./deploy_airbyte_module_client_pod.sh
    ```

    Now that the client pod is deployed, you can obtain the `letter_frequency` dataset from the airbyte-module server by running:
    ```bash
    kubectl exec -it my-shell -n default -- /root/do_get.sh
    ```
    The 'letter_frequency' dataset is a CSV file found in https://people.sc.fsu.edu/~jburkardt/data/csv/letter_frequency.csv. It contains a table with the frequency of each of the 26 English letters. The helm configuration in `abm/values.sample.yaml` contains the URL for the dataset, as well the name of the docker image used as a connector to obtain this dataset (`airbyte/source-file`).
