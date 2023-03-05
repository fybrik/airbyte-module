#!/usr/bin/env bash
# This script tests writing and reading to mysql using the airbyte module with Fybrik
# it does the following:
# 1) create fybrikapplication for writing a mysql table
# 2) write a dataset using the deployed airbyte module
# 3) create fybrikapplication for reading a mysql table
# 4) read a dataset using the deployed airbyte module
# 5) it compares the result of reading the newly written table using the airbyte module to reading it using a mysql client.


set -x
set -e


export WORKING_DIR=test-script
export ACCESS_KEY=1234
export SECRET_KEY=1234
export TOOLBIN=tools/bin

kubernetesVersion=$1
fybrikVersion=$2
moduleVersion=$3
certManagerVersion=$4

if [ $moduleVersion != 'master' ]
then
    git checkout tags/v$moduleVersion
fi

if [ $kubernetesVersion == "kind23" ]
then
    ${TOOLBIN}/kind delete cluster
    ${TOOLBIN}/kind create cluster --image=kindest/node:v1.23.13@sha256:ef453bb7c79f0e3caba88d2067d4196f427794086a7d0df8df4f019d5e336b61
elif [ $kubernetesVersion == "kind24" ]
then
    ${TOOLBIN}/kind delete cluster
    ${TOOLBIN}/kind create cluster --image=kindest/node:v1.24.7@sha256:577c630ce8e509131eab1aea12c022190978dd2f745aac5eb1fe65c0807eb315
elif [ $kubernetesVersion == "kind25" ]
then
    ${TOOLBIN}/kind delete cluster
    ${TOOLBIN}/kind create cluster --image=kindest/node:v1.25.3@sha256:f52781bc0d7a19fb6c405c2af83abfeb311f130707a0e219175677e366cc45d1
else
    echo "Unsupported kind version"
    exit 1
fi


# starting with write operation

${TOOLBIN}/helm repo add jetstack https://charts.jetstack.io
${TOOLBIN}/helm repo add hashicorp https://helm.releases.hashicorp.com
${TOOLBIN}/helm repo add fybrik-charts https://fybrik.github.io/charts
${TOOLBIN}/helm repo update


${TOOLBIN}/helm install cert-manager jetstack/cert-manager \
    --namespace cert-manager \
    --version v$certManagerVersion \
    --create-namespace \
    --set installCRDs=true \
    --wait --timeout 400s

if [ $fybrikVersion == "master" ]
then
	rm -rf fybrik
	git clone https://github.com/fybrik/fybrik.git
	cd fybrik
	../${TOOLBIN}/helm dependency update charts/vault
	../${TOOLBIN}/helm install vault charts/vault --create-namespace -n fybrik-system \
	    --set "vault.injector.enabled=false" \
	    --set "vault.server.dev.enabled=true" \
	    --values charts/vault/env/dev/vault-single-cluster-values.yaml
	../${TOOLBIN}/kubectl wait --for=condition=ready --all pod -n fybrik-system --timeout=120s
	../${TOOLBIN}/helm install fybrik-crd charts/fybrik-crd -n fybrik-system --wait
	../${TOOLBIN}/helm install fybrik charts/fybrik --set "coordinator.catalog=katalog" --set global.tag=master -n fybrik-system --wait
	cd -
	rm -rf fybrik
else
	${TOOLBIN}/helm install vault fybrik-charts/vault --create-namespace -n fybrik-system \
        --set "vault.injector.enabled=false" \
        --set "vault.server.dev.enabled=true" \
        --values https://raw.githubusercontent.com/fybrik/fybrik/v$fybrikVersion/charts/vault/env/dev/vault-single-cluster-values.yaml
    ${TOOLBIN}/kubectl wait --for=condition=ready --all pod -n fybrik-system --timeout=400s

	${TOOLBIN}/helm install fybrik-crd fybrik-charts/fybrik-crd -n fybrik-system --version v$fybrikVersion --wait
	${TOOLBIN}/helm install fybrik fybrik-charts/fybrik --set "coordinator.catalog=katalog" -n fybrik-system --version v$fybrikVersion --wait
fi

# apply modules

# Related to https://github.com/cert-manager/cert-manager/issues/2908
# Fybrik webhook not really ready after "helm install --wait"
# A workaround is to loop until the module is applied as expected
if [ $moduleVersion == "master" ]
then
	CMD="${TOOLBIN}/kubectl apply -f ../module.yaml -n fybrik-system"
else
	CMD="${TOOLBIN}/kubectl apply -f https://github.com/fybrik/airbyte-module/releases/download/v$moduleVersion/module.yaml -n fybrik-system"
fi

count=0
until $CMD
do
  if [[ $count -eq 10 ]]
  then
    break
  fi
  sleep 1
  ((count=count+1))
done

tmp_dir=$(mktemp -d)

# Notebook sample
${TOOLBIN}/kubectl create namespace fybrik-airbyte-sample
${TOOLBIN}/kubectl config set-context --current --namespace=fybrik-airbyte-sample

# deploy mysql chart
${TOOLBIN}/helm repo add bitnami https://charts.bitnami.com/bitnami
${TOOLBIN}/helm install mysql bitnami/mysql -n fybrik-airbyte-sample
${TOOLBIN}/kubectl wait pod --for=condition=ready mysql-0 --namespace fybrik-airbyte-sample --timeout 20m

# create an empty database in mysql
echo Username: root
export MYSQL_ROOT_PASSWORD=$(kubectl get secret --namespace fybrik-airbyte-sample mysql -o jsonpath="{.data.mysql-root-password}" | base64 -d)

${TOOLBIN}/kubectl run mysql-client --image docker.io/bitnami/mysql:8.0.32-debian-11-r0 --env MYSQL_ROOT_PASSWORD=$MYSQL_ROOT_PASSWORD --namespace fybrik-airbyte-sample
${TOOLBIN}/kubectl wait pod --for=condition=ready mysql-client --namespace fybrik-airbyte-sample --timeout 10m
echo "mysql -h mysql.fybrik-airbyte-sample.svc.cluster.local -uroot -p${MYSQL_ROOT_PASSWORD} -e \"create database test\"" > ${tmp_dir}/mysql-command

${TOOLBIN}/kubectl cp ${tmp_dir}/mysql-command mysql-client:/tmp/ -n fybrik-airbyte-sample
${TOOLBIN}/kubectl exec -i mysql-client -n fybrik-airbyte-sample -- bash /tmp/mysql-command >& ${tmp_dir}/out.txt
# check that the creation of the databse succeeded
DIFF=$(diff -b $WORKING_DIR/mysql_out_create.txt ${tmp_dir}/out.txt)
RES=0
if [ "${DIFF}" != "" ]
then
    echo "test database already exists in mysql"
    exit 1
fi


cat << EOF | ${TOOLBIN}/kubectl apply -f -
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


${TOOLBIN}/kubectl apply -f $WORKING_DIR/asset.yaml -n fybrik-airbyte-sample

${TOOLBIN}/kubectl describe asset userdata -n fybrik-airbyte-sample


kubectl -n fybrik-system create configmap sample-policy --from-file=$WORKING_DIR/sample-policy.rego
kubectl -n fybrik-system label configmap sample-policy openpolicyagent.org/policy=rego
while [[ $(kubectl get cm sample-policy -n fybrik-system -o 'jsonpath={.metadata.annotations.openpolicyagent\.org/policy-status}') != '{"status":"ok"}' ]]; do echo "waiting for policy to be applied" && sleep 5; done


c=0
while [[ $(${TOOLBIN}/kubectl get cm sample-policy -n fybrik-system -o 'jsonpath={.metadata.annotations.openpolicyagent\.org/policy-status}') != '{"status":"ok"}' ]]
do
    echo "waiting"
    ((c++)) && ((c==25)) && break
    sleep 1
done


# apply fybrik application for writing
${TOOLBIN}/kubectl apply -f $WORKING_DIR/write-fybrikapplication.yaml -n fybrik-airbyte-sample

c=0
while [[ $(${TOOLBIN}/kubectl get fybrikapplication my-app-write -n fybrik-airbyte-sample -o 'jsonpath={.status.ready}') != "true" ]]
do
    echo "waiting"
    ((c++)) && ((c==30)) && break
    sleep 1
done

kubectl wait --for=condition=ready --all pod -n fybrik-blueprints --timeout=120s
# do the writing using airbyte module
kubectl run my-shell --image ghcr.io/fybrik/airbyte-module-client:main --image-pull-policy=Always -n default
export CATALOGED_ASSET=fybrik-airbyte-sample/userdata
export ENDPOINT_HOSTNAME=$(kubectl get fybrikapplication my-app-write -n fybrik-airbyte-sample -o "jsonpath={.status.assetStates.${CATALOGED_ASSET}.endpoint.fybrik-arrow-flight.hostname}")
kubectl wait pod --for=condition=ready my-shell -n default --timeout 20m
kubectl exec -it my-shell -n default -- python3 /root/client.py --host ${ENDPOINT_HOSTNAME} --port 80 --asset ${CATALOGED_ASSET} --operation put

# check the newly written dataset by executing commands using mysql client
echo "mysql -h mysql.fybrik-airbyte-sample.svc.cluster.local -uroot -p${MYSQL_ROOT_PASSWORD} test -e \"select dob, name from demo\"" > ${tmp_dir}/mysql-command
${TOOLBIN}/kubectl cp ${tmp_dir}/mysql-command mysql-client:/tmp/ -n fybrik-airbyte-sample
${TOOLBIN}/kubectl exec -i mysql-client -n fybrik-airbyte-sample -- bash /tmp/mysql-command > ${tmp_dir}/out_fybrik_write.txt

# apply fybrik application for reading
${TOOLBIN}/kubectl apply -f $WORKING_DIR/read-fybrikapplication.yaml -n fybrik-airbyte-sample

c=0
while [[ $(${TOOLBIN}/kubectl get fybrikapplication my-app-read -n fybrik-airbyte-sample -o 'jsonpath={.status.ready}') != "true" ]]
do
    echo "waiting"
    ((c++)) && ((c==30)) && break
    sleep 1
done

kubectl wait --for=condition=ready --all pod -n fybrik-blueprints --timeout=120s
export CATALOGED_ASSET=fybrik-airbyte-sample/userdata
export ENDPOINT_HOSTNAME=$(kubectl get fybrikapplication my-app-read -n fybrik-airbyte-sample -o "jsonpath={.status.assetStates.${CATALOGED_ASSET}.endpoint.fybrik-arrow-flight.hostname}")
# do the reading using airbyte module
kubectl exec -it my-shell -n default -- python3 /root/client.py --host ${ENDPOINT_HOSTNAME} --port 80 --asset ${CATALOGED_ASSET} > ${tmp_dir}/out_fybrik_read.txt

# check that what was written using airbyte module is identical to what was read using airbyte module.
# skip first column from what was read as its the index.
awk '(NR>1)' ${tmp_dir}/out_fybrik_write.txt | awk {'print $1,$2,$3'} > ${tmp_dir}/fybrik_write.txt
awk '(NR>1)' ${tmp_dir}/out_fybrik_read.txt | awk {'print $2,$3,$4'} > ${tmp_dir}/fybrik_read.txt
DIFF=$(diff -b ${tmp_dir}/fybrik_read.txt ${tmp_dir}/fybrik_write.txt)
RES=0
if [ "${DIFF}" == "" ]
then
    echo "test succeeded"
else
    RES=1
fi

${TOOLBIN}/kubectl get cm -o yaml -n fybrik-blueprints

rm -rf ${tmp_dir}
${TOOLBIN}/kubectl delete namespace fybrik-airbyte-sample
${TOOLBIN}/kubectl -n fybrik-system delete configmap sample-policy

if [ ${RES} == 1 ]
then
  echo "test failed"
  exit 1
fi
