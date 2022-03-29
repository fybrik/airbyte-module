#!/bin/sh

docker build --tag airbyte_module_client:latest .
kind load docker-image airbyte_module_client:latest
kubectl run my-shell --rm -i --tty --image airbyte_module_client:latest --image-pull-policy=IfNotPresent -- bash
