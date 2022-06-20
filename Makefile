include Makefile.env

DOCKER_HOSTNAME ?= ghcr.io
DOCKER_NAMESPACE ?= fybrik
DOCKER_TAG ?= 0.0.0
DOCKER_NAME ?= airbyte-module
DOCKER_CLIENT_NAME ?= airbyte-module-client

IMG := ${DOCKER_HOSTNAME}/${DOCKER_NAMESPACE}/${DOCKER_NAME}:${DOCKER_TAG}
CLIENT_IMG := ${DOCKER_HOSTNAME}/${DOCKER_NAMESPACE}/${DOCKER_CLIENT_NAME}:${DOCKER_TAG}

export HELM_EXPERIMENTAL_OCI=1

all: test build

.PHONY: test
test:
	pipenv run python -m unittest discover

.PHONY: build
build:
	pipenv lock -r | sed -n '/^#/,$$p' > requirements.txt
	docker build -f build/Dockerfile . -t ${IMG}
	rm requirements.txt

	cd helm/client
	docker build --tag ${CLIENT_IMG} .

.PHONY: docker-push
docker-push:
	docker push ${IMG}
	docker push ${CLIENT_IMG}

.PHONY: push-to-kind
push-to-kind:
	kind load docker-image ${IMG}

include hack/make-rules/helm.mk
include hack/make-rules/tools.mk
