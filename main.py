#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import argparse
from abm.server import ABMServer, ABMFlightServer
from fybrik_python_logging import logger
import threading

def init_ABMServer(args):
    ABMServer(args.config, args.port, args.loglevel.upper(), args.workdir)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ABM Server')
    parser.add_argument(
        '-p', '--port', type=int, default=8080, help='Listening port for HTTP Server')
    parser.add_argument(
        '-a', '--arrowport', type=int, default=8081, help='Listening port for Arrow Flight Server')
    parser.add_argument(
        '-c', '--config', type=str, default='/etc/conf/conf.yaml', help='Path to config file')
    parser.add_argument(
        '-l', '--loglevel', type=str, default='warning', help='logging level', 
        choices=['trace', 'info', 'debug', 'warning', 'error', 'critical'])
    parser.add_argument(
        '-w', '--workdir', type=str, default='/local', help='writable directory for temporary files')
    args = parser.parse_args()

    # start the HTTP server in a separate thread
    t = threading.Thread(target=init_ABMServer, args=(args,))
    t.start()

    # start Arrow Flight server
    server = ABMFlightServer(args.config, args.arrowport, args.workdir)
    logger.info('AFMFlightServer started')
    server.serve()

    t.join()
