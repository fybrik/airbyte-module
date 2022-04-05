#!/usr/bin/env bash

set -x
set -e

export WORKING_DIR=$PWD/tests/test_helm
export TOOLBIN=$PWD/hack/tools/bin

export PATH=$TOOLBIN:$PATH

kubernetesVersion=$1

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


helm install airbyte-module -f helm/abm/values.sample.yaml helm/abm -n default --wait

# create client pod
cd helm/client
./deploy_airbyte_module_client_pod.sh
cd -

kubectl exec -it my-shell -n default -- /root/do_get.sh > res.out
kubectl delete pod my-shell -n default


helm delete airbyte-module -n default

DIFF=$(diff -b $WORKING_DIR/expected.txt res.out)

/bin/rm res.out

RES=0
if [ "${DIFF}" == "" ]
then
    echo "test succeeded"
else
    RES=1
fi

if [ ${RES} == 1 ]
then
  echo "test failed"
  exit 1
fi
