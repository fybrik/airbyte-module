#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import docker
import tempfile
from .container import Container

MOUNTDIR = '/local'

class NormalizationContainer(Container):
    def __init__(self, config, logger, workdir, asset_name=""):
        if 'image' not in config['normalization']:
           raise ValueError("'image' field missing from normalization section in configuration")
        self.normalization_image = config['normalization']['image']
        if 'integrationType'  not in config['normalization']:
           raise ValueError("'integrationType' field missing from normalization section in configuration")
        self.integration_type = config['normalization']['integrationType']
        if 'airbyteVersion'  not in config['normalization']:
           raise ValueError("'airbyteVersion' field missing from normalization section in configuration")
        self.airbyte_version = config['normalization']['airbyteVersion']
        super().__init__(logger, workdir, MOUNTDIR)

    '''
    Run a docker container from the connector image.
    Mount the workdir on /local. Remove the container after done.
    '''
    def run_container(self, command):
        volumes=[self.workdir + ':' + MOUNTDIR]
        # The normalization image is tied to and released along with a specific Airbyte version.
        # ref: https://github.com/airbytehq/airbyte/blob/master/docs/understanding-airbyte/basic-normalization.md#airbyte-integrationbasesbase-normalization
        environment=["WORKER_ENVIRONMENT=DOCKER", "AIRBYTE_VERSION=" + self.airbyte_version]
        super().run_container(command, self.normalization_image, volumes, environment, remove=True, stream=True, init=True)

    '''
    Creates a normalization command
    '''
    def create_normalization_command(self, catalog, config):
        command = 'run --config ' + self.name_in_container(config.name) + \
                  ' --catalog ' + self.name_in_container(catalog.name) + ' --integration-type ' + \
                  self.integration_type

        return command
