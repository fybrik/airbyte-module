#!/usr/bin/env bash

set -x
set -e

export WORKING_DIR=$PWD/tests/dataset
export TOOLBIN=$PWD/hack/tools/bin
export AIRBYTE_FYBRIK_TEST=$PWD/fybrik

export PATH=$TOOLBIN:$PATH

kubernetesVersion=$1
certManagerVersion=$2
moduleVersion=$3

if [ $kubernetesVersion == "kind19" ]
then
    kind delete cluster
    kind create cluster --image=kindest/node:v1.19.11@sha256:07db187ae84b4b7de440a73886f008cf903fcf5764ba8106a9fd5243d6f32729
elif [ $kubernetesVersion == "kind20" ]
then
    kind delete cluster
    kind create cluster --image=kindest/node:v1.20.7@sha256:cbeaf907fc78ac97ce7b625e4bf0de16e3ea725daf6b04f930bd14c67c671ff9
elif [ $kubernetesVersion == "kind21" ]
then
    kind delete cluster
    kind create cluster --image=kindest/node:v1.21.1@sha256:69860bda5563ac81e3c0057d654b5253219618a22ec3a346306239bba8cfa1a6
elif [ $kubernetesVersion == "kind22" ]
then
    kind delete cluster
    kind create cluster --image=kindest/node:v1.22.0@sha256:b8bda84bb3a190e6e028b1760d277454a72267a5454b57db34437c34a588d047
else
    echo "Unsupported kind version"
    exit 1
fi

# clone the fybrik repository
pushd /tmp
git clone https://github.com/fybrik/fybrik
popd

export FYBRIK_DIR=/tmp/fybrik

# deploy fybrik based on quick start
helm repo add jetstack https://charts.jetstack.io
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo add fybrik-charts https://fybrik.github.io/charts
helm repo update

helm install cert-manager jetstack/cert-manager \
    --namespace cert-manager \
    --version v$certManagerVersion \
    --create-namespace \
    --set installCRDs=true \
    --wait --timeout 400s

pushd $FYBRIK_DIR

# deploy vault
helm dependency update charts/vault
helm install vault charts/vault --create-namespace -n fybrik-system \
    --set "vault.injector.enabled=false" \
    --set "vault.server.dev.enabled=true" \
    --values charts/vault/env/dev/vault-single-cluster-values.yaml
kubectl wait --for=condition=ready --all pod -n fybrik-system --timeout=300s

# helm install fybrik-crd
helm install fybrik-crd charts/fybrik-crd -n fybrik-system --wait

# customize taxonomy to support the airbyte module
go run main.go taxonomy compile --out custom-taxonomy.json --base charts/fybrik/files/taxonomy/taxonomy.json $AIRBYTE_FYBRIK_TEST/fybrik-taxonomy-customize.yaml

# helm install fybrik
helm install fybrik charts/fybrik --set global.tag=master --set global.imagePullPolicy=Always -n fybrik-system --wait --set-file taxonomyOverride=custom-taxonomy.json

popd

# Related to https://github.com/cert-manager/cert-manager/issues/2908
# Fybrik webhook not really ready after "helm install --wait"
# A workaround is to loop until the module is applied as expected
CMD="kubectl apply -f https://github.com/fybrik/airbyte-module/releases/download/v$moduleVersion/module.yaml -n fybrik-system
"
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

# run an notebook-like example
kubectl create namespace fybrik-airbyte-sample
kubectl config set-context --current --namespace=fybrik-airbyte-sample

kubectl apply -f $AIRBYTE_FYBRIK_TEST/asset.yaml

kubectl -n fybrik-system create configmap sample-policy --from-file=$AIRBYTE_FYBRIK_TEST/sample-policy.rego
kubectl -n fybrik-system label configmap sample-policy openpolicyagent.org/policy=rego
while [[ $(kubectl get cm sample-policy -n fybrik-system -o 'jsonpath={.metadata.annotations.openpolicyagent\.org/policy-status}') != '{"status":"ok"}' ]]; do echo "waiting for policy to be applied" && sleep 5; done

kubectl apply -f $AIRBYTE_FYBRIK_TEST/application.yaml
CMD="kubectl wait --for=condition=ready --all pod -n fybrik-blueprints --timeout=300s
"
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

# create client pod in default namespace
pushd helm/client
./deploy_airbyte_module_client_pod.sh
popd

kubectl exec -it my-shell -n default -- python3 /root/client.py --host my-app-fybrik-airbyte-sample-airbyte-module.fybrik-blueprints --port 80 --asset fybrik-airbyte-sample/userdata > res.out
kubectl delete pod my-shell -n default

DIFF=$(diff -b $WORKING_DIR/expected.txt res.out)

# cleanup
/bin/rm res.out
kubectl delete namespace fybrik-airbyte-sample
kubectl -n fybrik-system delete configmap sample-policy
/bin/rm -Rf $FYBRIK_DIR

if [ "${DIFF}" == "" ]
then
    echo "test succeeded"
else
    echo "test failed"
    exit 1
fi
