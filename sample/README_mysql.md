# Mysql Sample

This sample is for experimenting with the Airbyte Module (ABM) mysql connector.

The server is configured to read and write a mysql table.

It uses Kuberentes only for the mysql chart deployment, while the Airbyte Module (ABM) runs locally without Kubernetes.

## Before you begin

Ensure that you have the following:

- Helm 3.3 or greater must be installed and configured on your machine.
- Kubectl 1.20 or newer must be installed on your machine.
- Access to a Kubernetes cluster such as Kind as a cluster administrator. Kubernetes version support range is 1.24-1.22 although older versions may work well.
- yq tool

The tools can also be found in `hack/tools/bin` directory after executing `make install-tools` in the root folder.

## Steps
### Read example

1. Setup and initialize mysql for reading a dataset


    1. Create a new namespace for mysql depolyment, and set it as default:
      ```bash
      kubectl create namespace fybrik-airbyte-sample
      kubectl config set-context --current --namespace=fybrik-airbyte-sample
      ```

    2. Deploy [mysql](https://bitnami.com/stack/mysql/helm) helm chart in `fybrik-airbyte-sample` namespace.
      ```bash
      helm repo add bitnami https://charts.bitnami.com/bitnami
      helm install mysql bitnami/mysql -n fybrik-airbyte-sample
      kubectl wait pod --for=condition=ready mysql-0 --namespace fybrik-airbyte-sample --timeout 20m
      ```
    3. Use the instructions from the helm chart notes to run a pod that is used as a client and connects to the service:
      ```bash
      echo Username: root
      export MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace fybrik-airbyte-sample mysql -o jsonpath="{.data.mysql-root-password}" | base64 -d)
      kubectl run mysql-client --rm --tty -i --restart='Never' --image  docker.io/bitnami/mysql:8.0.32-debian-11-r0 --namespace fybrik-airbyte-sample --env MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD --command -- bash
      mysql -h mysql.fybrik-airbyte-sample.svc.cluster.local -uroot -p"$MYSQL_ROOT_PASSWORD"
      ```
   
    4. In a mysql client shell prompt insert the following commands to upload fake data into a new database called `fybrik`:
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

    5. exit the `mysql` prompt and `mysql-client` pod

    6. port forward mysql service:
      ```bash
      kubectl port-forward svc/mysql -n fybrik-airbyte-sample 3306:3306 &
      ```

1. Install python dependencies
    ```bash
    pipenv install
    ```
1. Update `password` field in the configuration
   ```bash
   yq  e -i '.data[0].connection.read_mysql.password=env(MYSQL_ROOT_PASSWORD)' sample/read_mysql.yaml
   ```

1. Run the server with
    ```bash
    pipenv run server --config sample/read_mysql.yaml  --workdir /tmp
    ```
1. Read the `userdata` dataset from the arrow-flight server:
   ```bash
   pipenv run python sample/sample.py
    ```

### Write example
1. Setup and initialize mysql for writing a dataset

    1. Create a new namespace for mysql depolyment, and set it as default:
      ```bash
      kubectl create namespace fybrik-airbyte-sample
      kubectl config set-context --current --namespace=fybrik-airbyte-sample
      ```

    2. Deploy [mysql](https://bitnami.com/stack/mysql/helm) helm chart in `fybrik-airbyte-sample` namespace:
      ```bash
      helm repo add bitnami https://charts.bitnami.com/bitnami
      helm install mysql bitnami/mysql -n fybrik-airbyte-sample
      kubectl wait pod --for=condition=ready mysql-0 --namespace fybrik-airbyte-sample --timeout 20m
      ```
    3. Use the instructions from the helm chart notes to run a pod that is used as a client and connects to the service:
      ```bash
      echo Username: root
      export MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace fybrik-airbyte-sample mysql -o jsonpath="{.data.mysql-root-password}" | base64 -d)
      kubectl run mysql-client --rm --tty -i --restart='Never' --image  docker.io/bitnami/mysql:8.0.32-debian-11-r0 --namespace fybrik-airbyte-sample --env MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD --command -- bash
      mysql -h mysql.fybrik-airbyte-sample.svc.cluster.local -uroot -p"$MYSQL_ROOT_PASSWORD"
      ```
   
    4. In a mysql client shell prompt insert the following commands to create a new database called `test`:
      ```bash
      create database test;
      ```

    5. exit the `mysql` prompt and `mysql-client` pod

    6. port forward mysql service:
      ```bash
      kubectl port-forward svc/mysql -n fybrik-airbyte-sample 3306:3306 &
      ```
1. Install python dependencies
    ```bash
    pipenv install
    ```

1. Update `password` field in the configuration
   ```bash
   yq  e -i '.data[0].connection.write_mysql.password=env(MYSQL_ROOT_PASSWORD)' sample/write_mysql.yaml
   ```

1. Run the server with
    ```bash
    pipenv run server --config sample/write_mysql.yaml  --workdir /tmp
    ```
1. Send the information to be written to the server using arrow-flight:
   ```bash
   pipenv run python sample/sample_put.py
   ```
1. To verify that the Airbyte module writes the dataset, run:
   ```bash
   kubectl run mysql-client --rm --tty -i --restart='Never' --image  docker.io/bitnami/mysql:8.0.32-debian-11-r0 --namespace fybrik-airbyte-sample --env MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD --command -- bash
   mysql -h mysql.fybrik-airbyte-sample.svc.cluster.local -uroot -p"$MYSQL_ROOT_PASSWORD"
   use test;
   show tables;
   select * from demo;
   ```
