#
# Copyright 2022 IBM Corp.
# SPDX-License-Identifier: Apache-2.0
#
import json

'''
An Airbyte Module ticket contains a single field: the asset_name
'''
class ABMTicket:
    def __init__(self, asset_name):
        self._asset_name = asset_name

    @staticmethod
    def fromJSON(raw):
        return ABMTicket(**json.loads(raw))

    def toJSON(self):
        return json.dumps({
            "asset_name": self.asset_name,
        })

    @property
    def asset_name(self) -> str:
        return self._asset_name
