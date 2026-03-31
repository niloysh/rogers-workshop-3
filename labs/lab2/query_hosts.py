#!/usr/bin/env python3
"""Query ONOS for discovered links and hosts."""

import requests

# Base URL and credentials for the local ONOS REST API.
BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')


def main():
    # First show how many links ONOS currently knows about.
    links = requests.get(f'{BASE}/links', auth=AUTH)
    links.raise_for_status()
    link_data = links.json()['links']
    print(f"{len(link_data)} links")

    # Then print each discovered host with:
    # host ID, IP addresses, and the switch it attaches to.
    hosts = requests.get(f'{BASE}/hosts', auth=AUTH)
    hosts.raise_for_status()
    host_data = hosts.json()['hosts']
    for host in host_data:
        locations = host.get('locations', [])
        if locations:
            print(host['id'], host['ipAddresses'], locations[0]['elementId'])
        else:
            print(host['id'], host['ipAddresses'], '(no location)')


if __name__ == '__main__':
    main()
