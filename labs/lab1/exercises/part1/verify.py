#!/usr/bin/env python3
"""
verify.py — Part 1
------------------
Run against a live topology. Start it first in another terminal:
    sudo python3 exercises/topology.py

Then verify:
    sudo python3 exercises/part1/verify.py
"""

import os
import re
import subprocess
import sys


def require_root():
    if os.geteuid() != 0:
        print("Please run with sudo.")
        sys.exit(2)


def get_host_pid(host):
    result = subprocess.run(
        ["pgrep", "-f", f"mininet:{host}"],
        capture_output=True, text=True,
    )
    pids = result.stdout.strip().split()
    return pids[0] if pids else None


def require_topology():
    if not get_host_pid("h1"):
        print("Topology is not running — start it first:")
        print("  sudo python3 exercises/topology.py")
        sys.exit(1)


def run_in_host(host, cmd):
    pid = get_host_pid(host)
    result = subprocess.run(
        ["sudo", "mnexec", "-a", pid, *cmd],
        capture_output=True, text=True,
    )
    return result.stdout


def get_flows():
    result = subprocess.run(
        ["sudo", "ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"],
        capture_output=True, text=True,
    )
    return result.stdout


def packet_loss(ping_output):
    match = re.search(r"(\d+)% packet loss", ping_output)
    return int(match.group(1)) if match else 100


def check(label, condition, detail=""):
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")
    if not condition and detail:
        print(f"      {detail.strip()}")
    return condition


def main():
    require_root()
    require_topology()

    print("\nVerifying Part 1...\n")
    ok = True

    flows = get_flows()
    ok &= check(
        "flow rules installed on s1",
        "actions=" in flows,
        "No rules found — fill in and run: sudo bash exercises/part1/add_rules.sh",
    )

    out = run_in_host("h1", ["ping", "-c", "2", "-W", "1", "10.0.0.2"])
    ok &= check("h1 can reach h2", packet_loss(out) == 0, out)

    out = run_in_host("h2", ["ping", "-c", "2", "-W", "1", "10.0.0.1"])
    ok &= check("h2 can reach h1", packet_loss(out) == 0, out)

    print()
    print("All checks passed." if ok else "Some checks failed — re-read the hints and try again.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
