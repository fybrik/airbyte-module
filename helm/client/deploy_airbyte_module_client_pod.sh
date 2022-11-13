#!/bin/sh

kubectl run my-shell --image ghcr.io/fybrik/airbyte-module-client:main --image-pull-policy=Always -n default
kubectl wait pod --for=condition=ready my-shell -n default --timeout 10m
