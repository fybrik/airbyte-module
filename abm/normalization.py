#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import docker
import tempfile

MOUNTDIR = '/local'
CONTAINER_WORKDIR = "/data/1/0/normalize"

class NormalizationConnector:
    def __init__(self, config, logger, workdir, asset_name=""):
        if 'connector' not in config['normalization']:
           raise ValueError("'connector' field missing from normalization section in configuration")
        self.normalization_connector = config['normalization']['connector']
        if 'integrationType'  not in config['normalization']:
           raise ValueError("'integrationType' field missing from normalization section in configuration")
        self.integration_type = config['normalization']['integrationType']
        if 'airbyteVersion'  not in config['normalization']:
           raise ValueError("'airbyteVersion' field missing from normalization section in configuration")
        self.airbyte_version = config['normalization']['airbyteVersion']
        
        self.workdir = workdir
        self.client = docker.from_env()
        self.logger = logger
        self.tmp_dir = tempfile.TemporaryDirectory(prefix=self.workdir + '/')
        

    '''
    Translate the name of the temporary file in the host to the name of the same file
    in the container.
    For instance, it the path is '/tmp/tmp12345', return '/local/tmp12345'.
    '''
    def name_in_container(self, path):
        return path.replace(self.workdir, MOUNTDIR, 1)


    '''
    Run a docker container from the connector image.
    Mount the workdir on CONTAINER_WORKDIR. Remove the container after done.
    '''
    def run_container(self, command):
        self.logger.debug("running command: " + command)
        try:
            _ = self.client.containers.run(self.normalization_connector, volumes=[self.tmp_dir.name + ':' + "/data", self.workdir + ':' + MOUNTDIR], network_mode='host',
                                        environment=["DEPLOYMENT_MODE=OSS", "AIRBYTE_ROLE=", "WORKER_ENVIRONMENT=DOCKER", "AIRBYTE_VERSION="+self.airbyte_version],
                                        remove=True, detach=True, command=command, init=True, working_dir=CONTAINER_WORKDIR, stream=True)
        except docker.errors.DockerException as e:
            self.logger.error('Running of docker container failed',
                              extra={'error': str(e)})
            return None

    '''
    Creates a normalization command
    '''
    def create_normalization_command(self, catalog, config):
        command = 'run --config ' + self.name_in_container(config.name) + \
                  ' --catalog ' + self.name_in_container(catalog.name) + ' --integration-type ' + \
                  self.integration_type
        print(command)

        return command
