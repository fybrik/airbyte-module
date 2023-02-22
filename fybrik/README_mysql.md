# Reading a Dataset by a Fybrik Application

We explain how, using an Airbyte FybrikModule, a workload can access data stored in google-sheets, postgres, and other data stores supported by Airbyte connectors. To do so a FybrikApplication (i.e. the request) must be submitted indicating the desired data set(s). In this example, we use a dataset stored in mysql database.

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

1. Create a policy to allow access to any asset (we use a policy that does not restrict access nor mandate any transformations):
   ```bash
   kubectl -n fybrik-system create configmap sample-policy --from-file=$AIRBYTE_MODULE_DIR/fybrik/sample-policy.rego
   kubectl -n fybrik-system label configmap sample-policy openpolicyagent.org/policy=rego
   while [[ $(kubectl get cm sample-policy -n fybrik-system -o 'jsonpath={.metadata.annotations.openpolicyagent\.org/policy-status}') != '{"status":"ok"}' ]]; do echo "waiting for policy to be applied" && sleep 5; done
   ```

1. Setup and initialize mysql for reading a dataset

    1. Deploy [mysql](https://bitnami.com/stack/mysql/helm) helm chart in `fybrik-airbyte-sample` namespace.
      ```bash
      helm repo add bitnami https://charts.bitnami.com/bitnami
      helm install mysql bitnami/mysql -n fybrik-airbyte-sample
      kubectl wait pod --for=condition=ready mysql-0 --namespace fybrik-airbyte-sample --timeout 20m
      ```
    2. Use the instructions from the helm chart notes to run a pod that is use as a client and connect to the service:
      ```bash
      echo Username: root
      MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace fybrik-airbyte-sample mysql -o jsonpath="{.data.mysql-root-password}" | base64 -d)
      kubectl run mysql-client --rm --tty -i --restart='Never' --image  docker.io/bitnami/mysql:8.0.32-debian-11-r0 --namespace fybrik-airbyte-sample --env MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD --command -- bash
      mysql -h mysql.fybrik-airbyte-sample.svc.cluster.local -uroot -p"$MYSQL_ROOT_PASSWORD"
      ```
   
    3. In a mysql client shell prompt insert the following commands to upload fake data into a new database called `fybrik`:
      ```bash
      create database fybrik;
      create table fybrik.PS_20174392719_1491204439457_log ( step int, type varchar(255), amount varchar(255), nameOrig varchar(255), oldbalanceOrg varchar(255), newbalanceOrig varchar(255), nameDest varchar(255), oldbalanceDest varchar(255), newbalanceDest varchar(255), isFraud int, isFlaggedFraud int );
      insert into fybrik.PS_20174392719_1491204439457_log values
      (1,'PAYMENT','9839.64','C1231006815','170136','160296.36','M1979787155','0','0',0,0),
      (1,'PAYMENT','1864.28','C1666544295','21249','19384.72','M2044282225','0','0',0,0),
      (1,'TRANSFER','181','C1305486145','181','0','C553264065','0','0',1,0),
      (1,'CASH_OUT','181','C840083671','181','0','C38997010','21182','0',1,0),
      (1,'PAYMENT','11668.14','C2048537720','41554','29885.86','M1230701703','0','0',0,0),
      (1,'PAYMENT','7817.71','C90045638','53860','46042.29','M573487274','0','0',0,0);
      ```
      press `exit` to exit mysql shell prompt and then press `exit` again to exit mysql-client pod.

1. Register the credentials required for accessing the dataset as a kubernetes secret. Replace the value for MYSQL_ROOT_PASSWORD with the mysql service password as described in the section above:

    ```bash
    cat << EOF | kubectl apply -f -
    apiVersion: v1
    kind: Secret
    metadata:
      name: userdata
      namespace: fybrik-airbyte-sample
    type: Opaque
    stringData:
      username: root
      password: "${MYSQL_ROOT_PASSWORD}"
    EOF
      ```

1. Create an asset (the `userdata` asset) and an application that requires this asset:
   ```bash
   kubectl apply -f $AIRBYTE_MODULE_DIR/fybrik/read-flow/asset-mysql.yaml -n fybrik-airbyte-sample
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
   cd $AIRBYTE_MODULE_DIR/helm/client
   ./deploy_airbyte_module_client_pod.sh
   kubectl exec -it my-shell -n default -- python3 /root/client.py --host my-app-read-fybrik-airbyte-sample-airbyte-module.fybrik-blueprints --port 80 --asset fybrik-airbyte-sample/userdata
   ```

# Writing Dataset with Fybrik Application

In this example, a small dataset is written to mysql table. To do so a FybrikApplication (i.e. the request) must be submitted indicating the desired data set(s) to be written.

As above, you will need a copy of the Fybrik repository (`git clone https://github.com/fybrik/fybrik.git`). Set the following environment variables: FYBRIK_DIR for the path of the `fybrik` directory, and AIRBYTE_MODULE_DIR for the path of the `airbyte-module` directory.

Repeat steps 1-5 above.

6. Setup and initialize mysql for writing a dataset

    1. Deploy [mysql](https://bitnami.com/stack/mysql/helm) helm chart in `fybrik-airbyte-sample` namespace:
      ```bash
      helm repo add bitnami https://charts.bitnami.com/bitnami
      helm install mysql bitnami/mysql -n fybrik-airbyte-sample
      kubectl wait pod --for=condition=ready mysql-0 --namespace fybrik-airbyte-sample --timeout 20m
      ```
    2. Use the instructions from the helm chart notes to run a pod that is use as a client and connect to the service:
      ```bash
      echo Username: root
      MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace fybrik-airbyte-sample mysql -o jsonpath="{.data.mysql-root-password}" | base64 -d)
      kubectl run mysql-client --rm --tty -i --restart='Never' --image  docker.io/bitnami/mysql:8.0.32-debian-11-r0 --namespace fybrik-airbyte-sample --env MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD --command -- bash
      mysql -h mysql.fybrik-airbyte-sample.svc.cluster.local -uroot -p"$MYSQL_ROOT_PASSWORD"
      ```
   
    3. In a mysql client shell prompt insert the following commands to create a new database called `test`:
      ```bash
      create database test;
      ```
      press `exit` to exit mysql shell prompt and then press `exit` again to exit mysql-client pod.

1. Register the credentials required for accessing the dataset as a kubernetes secret. Replace the value for MYSQL_ROOT_PASSWORD with the mysql service password as described in the section above:

      ```bash
      cat << EOF | kubectl apply -f -
      apiVersion: v1
      kind: Secret
      metadata:
        name: userdata
        namespace: fybrik-airbyte-sample
      type: Opaque
      stringData:
        username: root
        password: "${MYSQL_ROOT_PASSWORD}"
      EOF
      ```

1. Create an asset (the `userdata` asset), the policy to access it (we use a policy that does not restrict access nor mandate any transformations), and an application that requires this asset:
   ```bash
   kubectl apply -f $AIRBYTE_MODULE_DIR/fybrik/write-flow/asset-mysql.yaml -n fybrik-airbyte-sample
   kubectl apply -f $AIRBYTE_MODULE_DIR/fybrik/write-flow/application.yaml -n fybrik-airbyte-sample
   ```

1. After the application is created, the Fybrik manager attempts to create the data path for the application. Fybrik realizes that the Airbyte module can give the application access to the `userdata` dataset, and deploys it in the `fybrik-blueprints` namespace. To verify that the Airbyte module was indeed deployed, run:
   ```bash
   kubectl get pods -n fybrik-blueprints
   ```
    > _NOTE:_ See the note in step 9 above.

1. Run the following commands to exceute a write command:
   ```bash
   export AIRBYTE_POD_NAME=$(kubectl get pods -n fybrik-blueprints | grep airbyte |awk '{print $1}')
   cd $AIRBYTE_MODULE_DIR/helm/client
   ./deploy_airbyte_module_client_pod.sh
   kubectl exec -it my-shell -n default -- python3 /root/client.py --host my-app-write-fybrik-airbyte-sample-airbyte-module.fybrik-blueprints --port 80 --asset fybrik-airbyte-sample/userdata --operation put
   ```

1. To verify that the Airbyte module writes the dataset, run:
   ```bash
   kubectl run mysql-client --rm --tty -i --restart='Never' --image  docker.io/bitnami/mysql:8.0.32-debian-11-r0 --namespace fybrik-airbyte-sample --env MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD --command -- bash
   mysql -h mysql.fybrik-airbyte-sample.svc.cluster.local -uroot -p"$MYSQL_ROOT_PASSWORD"
   ```

1. In a mysql client shell prompt insert the following commands to show the newly created dataset:
   ```bash
   use test;
   show tables;
   select * from demo;
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


