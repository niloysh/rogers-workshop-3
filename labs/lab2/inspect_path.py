#!/usr/bin/env python3
"""Query ONOS for the path between two switches."""

import sys
import requests

# Base URL and credentials for the local ONOS REST API.
BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')


def main():
    if len(sys.argv) != 3:
        print(f"Usage: python3 {sys.argv[0]} <src_device_id> <dst_device_id>")
        sys.exit(1)

    src_device, dst_device = sys.argv[1], sys.argv[2]
    # Ask ONOS for the current shortest path between the two switches.
    response = requests.get(f'{BASE}/paths/{src_device}/{dst_device}', auth=AUTH)
    response.raise_for_status()
    paths = response.json()['paths']

    if not paths:
        print("No path found.")
        return

    # Print the first path as a device-and-port sequence.
    for link in paths[0]['links']:
        print(
            link['src']['device'],
            link['src']['port'],
            '->',
            link['dst']['device'],
            link['dst']['port'],
        )


if __name__ == '__main__':
    main()
