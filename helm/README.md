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

    Now that the client pod is deployed, you can obtain the `userdata` dataset from the airbyte-module server by running:
    ```bash
    kubectl exec -it my-shell -n default -- /root/do_get.sh
    ```
    The 'userdata' dataset is a Parquet file found in https://github.com/Teradata/kylo/blob/master/samples/sample-data/parquet/userdata2.parquet. The helm configuration in `abm/values.sample.yaml` contains the URL for the dataset, as well the name of the docker image used as a connector to obtain this dataset (`airbyte/source-file`).

    Alternatively, you can obtain the same dataset through a REST GET request. This can be done by using the 'curl' utility. First you need to install it. Simply run the following commands:
    ```bash
    kubectl exec -it my-shell -n default -- apt-get install -y curl
    kubectl exec -it my-shell -n default -- curl my-app-fybrik-airbyte-sample-airbyte-module.fybrik-blueprints:79/fybrik-airbyte-sample/userdata
    ```
