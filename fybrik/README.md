### Version compatibility matrix

| Fybrik | ABM    | Command                                                                         |
|--------|--------|---------------------------------------------------------------------------------|
| 0.7.x  | 0.1.x  | `https://github.com/fybrik/airbyte-module/releases/download/v0.1.0/module.yaml` |
| 1.0.x  | 0.2.x  | `https://github.com/fybrik/airbyte-module/releases/download/v0.2.0/module.yaml` |
| 1.1.x  | 0.2.x  | `https://github.com/fybrik/airbyte-module/releases/download/v0.2.0/module.yaml` |
| master | master | `https://raw.githubusercontent.com/fybrik/airbyte-module/master/module.yaml`    |

# Accessing a Dataset by a Fybrik Application

We explain how, using an Airbyte FybrikModule, a workload can access data stored in google-sheets, postgres, and other data stores supported by Airbyte connectors. To do so a FybrikApplication (i.e. the request) must be submitted indicating the desired data set(s). In this example, we use the `userdata` dataset, a Parquet file found in https://github.com/Teradata/kylo/blob/master/samples/sample-data/parquet/userdata2.parquet.

You will need a copy of the Fybrik repository (`git clone https://github.com/fybrik/fybrik.git`). Set the following environment variables: FYBRIK_DIR for the path of the `fybrik` directory, and AIRBYTE_MODULE_DIR for the path of the `airbyte-module` directory.

1. Install Fybrik Prerequisites. Follow the instruction in the Fybrik [Quick Start Guide](https://fybrik.io/dev/get-started/quickstart/). Stop before the "Install control plane" section.

1. Install Fybrik with a built-in catalog, called Katalog, as opposed to the Openmetadata catalog which is installed by default.

    ```bash
    cd $FYBRIK_DIR
    helm install fybrik-crd charts/fybrik-crd -n fybrik-system --wait
    helm install fybrik charts/fybrik --set coordinator.catalog=katalog --set global.tag=master --set global.imagePullPolicy=Always -n fybrik-system --wait
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

1. Create an asset (the `userdata` asset) and an application that requires this asset:
   ```bash
   kubectl apply -f $AIRBYTE_MODULE_DIR/fybrik/read-flow/asset.yaml -n fybrik-airbyte-sample
   kubectl apply -f $AIRBYTE_MODULE_DIR/fybrik/read-flow/application.yaml -n fybrik-airbyte-sample
   ```

1. After the application is created, the Fybrik manager attempts to create the data path for the application. Fybrik realizes that the Airbyte module can give the application access to the `userdata` dataset, and deploys it in the `fybrik-blueprints` namespace. To verify that the Airbyte module was indeed deployed, run:
   ```bash
   kubectl get pods -n fybrik-blueprints
   ```
   ---
   > _NOTE:_ If you are using OpenShift cluster you will see that the deployment fails because OpenShift doesn't allow `privileged: true` value in `securityContext` field by default. Thus, you should add the service account of the module's deployment to the `privileged SCC` using the following command:
   ```bash
   oc adm policy add-scc-to-user privileged system:serviceaccount:fybrik-blueprints:<SERVICE_ACCOUNT_NAME>
   ```
   > Then, the deployment will restart the failed pods and the pods in `fybrik-blueprints` namespace should start successfully.
   ---

1. To verify that the Airbyte module gives access to the `userdata` dataset, run:
   ```bash
   export CATALOGED_ASSET=fybrik-airbyte-sample/userdata
   export ENDPOINT_HOSTNAME=$(kubectl get fybrikapplication my-app-read -n fybrik-airbyte-sample -o "jsonpath={.status.assetStates.${CATALOGED_ASSET}.endpoint.fybrik-arrow-flight.hostname}")
   cd $AIRBYTE_MODULE_DIR/helm/client
   ./deploy_airbyte_module_client_pod.sh
   kubectl exec -it my-shell -n default -- python3 /root/client.py --host ${ENDPOINT_HOSTNAME} --port 80 --asset ${CATALOGED_ASSET}
   ```

# Writing Dataset with Fybrik Application

In this example, a small `userdata` dataset is written to a directory on the local filesystem on the host running Airbyte. To do so a FybrikApplication (i.e. the request) must be submitted indicating the desired data set(s) to be written.

As above, you will need a copy of the Fybrik repository (`git clone https://github.com/fybrik/fybrik.git`). Set the following environment variables: FYBRIK_DIR for the path of the `fybrik` directory, and AIRBYTE_MODULE_DIR for the path of the `airbyte-module` directory.

Repeat steps 1-5 above.

6. Create an asset (the `userdata` asset), the policy to access it (we use a policy that does not restrict access nor mandate any transformations), and an application that requires this asset:
   ```bash
   kubectl apply -f $AIRBYTE_MODULE_DIR/fybrik/write-flow/asset.yaml -n fybrik-airbyte-sample
   kubectl apply -f $AIRBYTE_MODULE_DIR/fybrik/write-flow/application.yaml -n fybrik-airbyte-sample
   ```

1. After the application is created, the Fybrik manager attempts to create the data path for the application. Fybrik realizes that the Airbyte module can give the application access to the `userdata` dataset, and deploys it in the `fybrik-blueprints` namespace. To verify that the Airbyte module was indeed deployed, run:
   ```bash
   kubectl get pods -n fybrik-blueprints
   ```

   > _NOTE:_ See the note in step 7 above.


1. To verify that the Airbyte module writes the dataset, run:
   ```bash
   export AIRBYTE_POD_NAME=$(kubectl get pods -n fybrik-blueprints | grep air |awk '{print $1}')
   cd $AIRBYTE_MODULE_DIR/helm/client
   ./deploy_airbyte_module_client_pod.sh
   export CATALOGED_ASSET=fybrik-airbyte-sample/userdata
   export ENDPOINT_HOSTNAME=$(kubectl get fybrikapplication my-app-write -n fybrik-airbyte-sample -o "jsonpath={.status.assetStates.${CATALOGED_ASSET}.endpoint.fybrik-arrow-flight.hostname}")
   kubectl exec -it my-shell -n default -- python3 /root/client.py --host ${ENDPOINT_HOSTNAME} --port 80 --asset ${CATALOGED_ASSET} --operation put
   kubectl exec $AIRBYTE_POD_NAME -n fybrik-blueprints -- bash -c "cat /local/airbyte_out/*"
   ```


# Cleanup

When you're finished experimenting with a sample, you may clean up as follows:

Delete the namespace created for this sample:

```bash
kubectl delete namespace fybrik-airbyte-sample
```

To experiment with a sample after the deletion of `fybrik-airbyte-sample` namespace,
re-create the namespace with the following commands and continue from step 6 in the chosen sample.

```bash
kubectl create namespace fybrik-airbyte-sample
kubectl config set-context --current --namespace=fybrik-airbyte-sample
```


