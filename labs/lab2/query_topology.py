#!/usr/bin/env python3
"""Query ONOS for discovered devices."""

import requests

# Base URL and credentials for the local ONOS REST API.
BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')


def main():
    # Ask ONOS for the list of discovered devices (switches).
    response = requests.get(f'{BASE}/devices', auth=AUTH)
    response.raise_for_status()
    devices = response.json()['devices']

    # Print the most useful fields for the lab:
    # device ID, type, and whether ONOS sees it as available.
    for device in devices:
        print(device['id'], device['type'], device['available'])


if __name__ == '__main__':
    main()
