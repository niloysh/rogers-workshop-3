#!/usr/bin/env python3
"""
Pre-flight checks for the Lab 2 independent challenge.

Usage:
    python3 preflight_check.py
    python3 preflight_check.py 10.0.0.1 10.0.0.2
"""

import sys
import requests

BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')
DEFAULT_SRC_IP = '10.0.0.1'
DEFAULT_DST_IP = '10.0.0.2'

PASS = '[ok]'
FAIL = '[fail]'


def api_get(endpoint):
    """GET from ONOS REST API and return parsed JSON."""
    response = requests.get(f'{BASE}/{endpoint}', auth=AUTH, timeout=5)
    response.raise_for_status()
    return response.json()


def print_check(name, passed, detail=''):
    """Print one pre-flight check result."""
    status = PASS if passed else FAIL
    print(f'{status} {name}')
    if detail:
        print(f'       {detail}')
    return passed


def find_host_by_ip(hosts, ip):
    """Return the first host object whose ipAddresses contains ip."""
    for host in hosts:
        if ip in host.get('ipAddresses', []):
            return host
    return None


def host_location(host):
    """Return the first location for a host, or None."""
    locations = host.get('locations', [])
    return locations[0] if locations else None


def main():
    src_ip = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC_IP
    dst_ip = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_DST_IP

    print('=' * 56)
    print('Lab 2 Challenge Pre-flight')
    print(f'Checking path: {src_ip} -> {dst_ip}')
    print('=' * 56)

    try:
        devices = api_get('devices').get('devices', [])
        links = api_get('links').get('links', [])
        hosts = api_get('hosts').get('hosts', [])
    except Exception as exc:
        print_check('ONOS REST API is reachable', False, str(exc))
        sys.exit(1)

    all_ok = True
    all_ok &= print_check('ONOS REST API is reachable', True)

    active_devices = [device for device in devices if device.get('available')]
    all_ok &= print_check(
        'Three switches discovered',
        len(active_devices) == 3,
        f'Found {len(active_devices)} active device(s).',
    )

    all_ok &= print_check(
        'Triangle links discovered',
        len(links) == 6,
        f'Found {len(links)} link(s).',
    )

    src_host = find_host_by_ip(hosts, src_ip)
    dst_host = find_host_by_ip(hosts, dst_ip)

    all_ok &= print_check(
        f'Host {src_ip} discovered with IP address',
        src_host is not None,
        'Run pingall in Mininet and recheck hosts.' if src_host is None else '',
    )
    all_ok &= print_check(
        f'Host {dst_ip} discovered with IP address',
        dst_host is not None,
        'Run pingall in Mininet and recheck hosts.' if dst_host is None else '',
    )

    if src_host and dst_host:
        src_location = host_location(src_host)
        dst_location = host_location(dst_host)

        all_ok &= print_check(
            'Hosts have attachment locations',
            src_location is not None and dst_location is not None,
            'Check ONOS host discovery if locations are missing.',
        )

        if src_location and dst_location:
            try:
                paths = api_get(
                    f"paths/{src_location['elementId']}/{dst_location['elementId']}"
                ).get('paths', [])
            except Exception as exc:
                paths = []

            all_ok &= print_check(
                'ONOS returns a path between the endpoint switches',
                len(paths) > 0,
                'If paths is empty, focus on links and ports before debugging your app.',
            )

    print('-' * 56)
    if all_ok:
        print('[ready] You can start lab2_skeleton.py now.')
    else:
        print('[not ready] Fix the failed checks above before running the challenge app.')
        sys.exit(1)


if __name__ == '__main__':
    main()
