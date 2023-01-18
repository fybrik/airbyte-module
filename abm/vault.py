#
# Copyright 2023 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#

from fybrik_python_vault import get_jwt_from_file, get_raw_secret_from_vault
from fybrik_python_logging import logger, DataSetID, ForUser


def get_secrets_from_vault(vault_credentials, datasetID, tls_min_version=None, verify=True, cert=None):
    """Get secrets from Vault

    Args:
        vault_credentials (dictonary): Properties used for getting secrets from Vault.
        datasetID (string): dataset ID.
        tls_min_version (string, optional): tls minimum version to use in the connection to Vault. Defaults to None.
        verify (optional): Either a boolean, in which case it controls whether we verify
        the Vault server's TLS certificate, or a string, in which case it must be a path
        to a CA bundle to use. Defaults to ``True``.
        cert (tuple, optional): the module ('cert', 'key') pair.

    Returns:
        dictionary of secrets returned by vault
    """
    jwt_file_path = vault_credentials.get('jwt_file_path', '/var/run/secrets/kubernetes.io/serviceaccount/token')
    jwt = get_jwt_from_file(jwt_file_path)
    vault_address = vault_credentials.get('address', 'https://localhost:8200')
    secret_path = vault_credentials.get('secretPath', '/v1/secret/data/cred')
    vault_auth = vault_credentials.get('authPath', '/v1/auth/kubernetes/login')
    role = vault_credentials.get('role', 'demo')

    return get_raw_secret_from_vault(jwt, secret_path, vault_address, vault_auth,
                                     role, datasetID, tls_min_version, verify, cert)
