#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import docker
import time

CTRLD = '\x04'.encode()

class Container:
    def __init__(self, logger, workdir):
        self.logger = logger
        self.workdir = workdir
        # Potentially the fybrik-blueprint pod for the airbyte module can start before the docker daemon pod, causing
        # docker.from_env() to fail
        retryLoop = 0
        while retryLoop < 10:
            try:
                self.client = docker.from_env()
            except Exception as e:
                print('error on docker.from_env() ' + str(e) + ' sleep and retry.  Retry count = ' + str(retryLoop))
                time.sleep(1)
                retryLoop += 1
            else:
                retryLoop = 10
        
    '''
    Translate the name of the temporary file in the host to the name of the same file
    in the container.
    For instance, it the path is '/tmp/tmp12345', return '/local/tmp12345'.
    '''
    def name_in_container(self, path, mountdir):
        return path.replace(self.workdir, mountdir, 1)

    '''
    Run a docker container from the connector image.
    Mount the workdir on /local. Remove the container after done.
    '''
    def run_container(self, command, image, volumes, environment=None, remove=True, detach=True, stream=True, init=False):
        self.logger.debug("running command: " + command)
        try:
            _ = self.client.containers.run(image, volumes=volumes, network_mode='host',
                                        environment=environment,
                                        command=command, init=init, stream=stream, remove=remove, detach=detach)
        except docker.errors.DockerException as e:
            self.logger.error('Running of docker container failed',
                              extra={'error': str(e)})
            return None
        
    def open_socket_to_container(self, command, image, volumes, detach=True, tty=True, stdin_open=True, remove=True):
        container = self.client.containers.run(image, detach=detach,
                             tty=tty, stdin_open=stdin_open,
                             volumes=volumes, network_mode='host',
                             command=command, remove=remove)
        # attach to the container stdin socket
        s = container.attach_socket(params={'stdin': 1, 'stream': 1, 'stdout': 1, 'stderr': 1})
        s._sock.setblocking(True)
        return s, container

    def close_socket_to_container(self, s, container):
        s._sock.sendall(CTRLD)  # ctrl d to finish things up
        s._sock.close()
        container.stop()
        self.client.close()

    def write_to_socket_to_container(self, s, binary_textline):
        s._sock.sendall(binary_textline)
        s.flush()