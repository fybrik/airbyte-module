# Accessing a Dataset by a Fybrik Application

We explain how, using an Airbyte FybrikModule, a workload can access data stored in google-sheets, postgres, and other data stores supported by Airbyte connectors. To do so a FybrikApplication (i.e. the request) must be submitted indicating the desired data set(s). In this example, we use the `userdata` dataset, a Parquet file found in https://github.com/Teradata/kylo/blob/master/samples/sample-data/parquet/userdata2.parquet.

You will need a copy of the Fybrik repository (`git clone https://github.com/fybrik/fybrik.git`). Set the following environment variables: FYBRIK_DIR for the path of the `fybrik` directory, and AIRBYTE_MODULE_DIR for the path of the `airbyte-module` directory.

1. Install Fybrik Prerequisites. Follow the instruction in the Fybrik [Quick Start Guide](https://fybrik.io/dev/get-started/quickstart/). Stop before the "Install control plane" section.

1. Before installing the control plane, we need to customize the [Fybrik taxonomy](https://fybrik.io/dev/tasks/custom-taxonomy/), to define new connection and interface types. Run:
    ```bash
    cd $FYBRIK_DIR
    go run main.go taxonomy compile --out custom-taxonomy.json --base charts/fybrik/files/taxonomy/taxonomy.json $AIRBYTE_MODULE_DIR/fybrik/fybrik-taxonomy-customize.yaml
    helm install fybrik-crd charts/fybrik-crd -n fybrik-system --wait
    helm install fybrik charts/fybrik --set global.tag=master --set global.imagePullPolicy=Always -n fybrik-system --wait --set-file taxonomyOverride=custom-taxonomy.json
    ```

1. Install the Airbyte module:
    ```bash
    kubectl apply -f $AIRBYTE_MODULE_DIR/module.yaml -n fybrik-system
    ```

1. Create a new namespace for the application, and set it as default:
   ```bash
   kubectl create namespace fybrik-airbyte-sample
   kubectl config set-context --current --namespace=fybrik-airbyte-sample
   ```

1. Create an asset (the `userdata` asset), the policy to access it (we use a policy that does not restrict access nor mandate any transformations), and an application that requires this asset:
   ```bash
   kubectl apply -f $AIRBYTE_MODULE_DIR/fybrik/asset.yaml
   kubectl -n fybrik-system create configmap sample-policy --from-file=$AIRBYTE_MODULE_DIR/fybrik/sample-policy.rego
   kubectl -n fybrik-system label configmap sample-policy openpolicyagent.org/policy=rego
   while [[ $(kubectl get cm sample-policy -n fybrik-system -o 'jsonpath={.metadata.annotations.openpolicyagent\.org/policy-status}') != '{"status":"ok"}' ]]; do echo "waiting for policy to be applied" && sleep 5; done
   kubectl apply -f $AIRBYTE_MODULE_DIR/fybrik/application.yaml
   ```

1. After the application is created, the Fybrik manager attempts to create the data path for the application. Fybrik realizes that the Airbyte module can give the application access to the `userdata` dataset, and deploys it in the `fybrik-blueprints` namespace. To verify that the Airbyte module was indeed deployed, run:
   ```bash
   kubectl get pods -n fybrik-blueprints
   ```

1. To verify that the Airbyte module gives access to the `userdata` dataset, run:
   ```bash
   cd $AIRBYTE_MODULE_DIR/helm/client
   ./deploy_airbyte_module_client_pod.sh
   kubectl exec -it my-shell -n default -- python3 /root/client.py --host my-app-fybrik-airbyte-sample-airbyte-module.fybrik-blueprints --port 80 --asset fybrik-airbyte-sample/userdata
   ```
