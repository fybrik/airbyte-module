# Deploying the Airbyte Module using Helm

From the `helm` directory of the Airbyte Module, run:
    ```bash
    helm install airbyte-module -f abm/values.sample.yaml abm -n default
    ```

This command deploys an airbyte-module pod in the `default` namespace, and creates an 'airbyte-module' service.

To test it, go to the `client directory`, and run:
    ```bash
    ./deploy_airbyte_module_client_pod.sh
    ```

This command deploys a client pod. You get a `bash` prompt, from which you can run:
    ```bash
    # /root/do_get.sh
    ```
to obtain the `letter_frequency` dataset.
