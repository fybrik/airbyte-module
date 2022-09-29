[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# airbyte-module

The airbyte-module (ABM) for [Fybrik](https://github.com/fybrik/fybrik) is a [`FybrikModule`](https://fybrik.io/dev/concepts/modules/) which makes use of [Airbyte](https://airbyte.com/) [connectors](https://docs.airbyte.com/integrations).

ABM is both an [Apache Arrow](https://arrow.apache.org/) [Flight](https://arrow.apache.org/docs/format/Flight.html) and an HTTP server.

## What is Airbyte?
[Airbyte](https://airbyte.com/) is a data integration tool that focuses on extracting and loading data.

Airbyte has a vast catalog of [connectors](https://docs.airbyte.com/integrations) that support dozens of data sources and data destinations. These Airbyte connectors run in docker containers and are built in accordance with the Airbyte [specification](https://docs.airbyte.com/understanding-airbyte/airbyte-specification).

## What is the Airbyte Module?

ABM is an arrow-flight server that enables applications to consume tabular data from a wide range of data sources.

Since Airbyte connectors are implemented as docker images and run as docker containers, the Airbyte Module does not require Airbyte as a prerequisite. To run the Airbyte Module, only docker is required.

## How to run the Airbyte Module server locally

Follow the instructions in the [sample folder](sample/README.md).

## How to deploy the Airbyte Module to kubernetes using helm

Follow the instructions in the [helm folder](helm/README.md).

## How a Fybrik Application can access a dataset, using an Airbyte FybrikModule
If you would like to run a use case where the application has unrestricted access to a dataset,
follow the instructions [here](fybrik/README.md).

However, if you are interested in a use case where the governance policies mandate that some of the dataset
columns must be redacted, follow the instructions [here](fybrik/README_Chaining.md). In this scenario, both the airbyte module and the [arrow-flight-module](https://github.com/fybrik/arrow-flight-module) are deployed. The airbyte
module reads the dataset, whereas the arrow-flight-module transforms the dataset based on the governance policies.
