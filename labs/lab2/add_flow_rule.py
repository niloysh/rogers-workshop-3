#!/usr/bin/env python3
"""Add one flow rule to an ONOS device using the REST API."""

import json
import requests

# Base URL and credentials for the local ONOS REST API.
BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')
DEVICE_ID = 'of:0000000000000001'
TEMPLATE_PATH = 'flow_rule_template.json'


def main():
    # Load the example flow rule JSON from the lab folder.
    with open(TEMPLATE_PATH, 'r', encoding='utf-8') as handle:
        flow_rule = json.load(handle)

    # POST the rule to /flows/<deviceId>.
    response = requests.post(
        f'{BASE}/flows/{DEVICE_ID}',
        auth=AUTH,
        json=flow_rule,
    )
    response.raise_for_status()
    print(f"Installed flow rule on {DEVICE_ID}")


if __name__ == '__main__':
    main()
