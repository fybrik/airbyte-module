#!/bin/sh

kubectl run my-shell --image ghcr.io/fybrik/airbyte-module-client:0.0.0 --image-pull-policy=Always -n default --wait
kubectl wait pod --for=condition=ready my-shell -n default
