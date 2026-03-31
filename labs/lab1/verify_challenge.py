#!/usr/bin/env python3
"""
verify_challenge.py
-------------------
Run the Lab 1 challenge topology, apply a rules script, and verify behavior.

Usage:
    sudo python3 verify_challenge.py
    sudo python3 verify_challenge.py --topology topology_starter.py --rules install_rules.sh
    sudo python3 verify_challenge.py --topology solutions/topology_solution.py --rules solutions/install_rules_solution.sh
"""

import argparse
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path


LAB_DIR = Path(__file__).resolve().parent


def require_root():
    if os.geteuid() != 0:
        print("Please run this checker with sudo.")
        sys.exit(2)


def cleanup_mininet():
    subprocess.run(
        ["mn", "-c"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def load_topology_module(topology_path):
    spec = importlib.util.spec_from_file_location("lab1_topology", topology_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load topology file: {topology_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def create_network(module):
    if hasattr(module, "build_topology"):
        return module.build_topology()
    if hasattr(module, "build"):
        return module.build()
    raise RuntimeError("Topology file must define build_topology() or build()")


def validate_topology(net):
    """Fail early with a clear message if the topology is incomplete."""
    missing = []

    for host in net.hosts:
        if host.defaultIntf() is None:
            missing.append(f"{host.name} is missing a host link")

    for switch in net.switches:
        if len(switch.intfList()) <= 1:
            missing.append(f"{switch.name} has no data-plane links")

    if missing:
        details = "\n".join(f"  - {item}" for item in missing)
        raise RuntimeError(
            "The selected topology is incomplete.\n"
            "Finish the TODO sections, or point the checker at the reference solution.\n"
            "Example:\n"
            "  sudo python3 verify_challenge.py "
            "--topology solutions/topology_solution.py "
            "--rules solutions/install_rules_solution.sh\n"
            f"{details}"
        )


def run_rules_script(rules_path):
    result = subprocess.run(
        ["bash", str(rules_path)],
        text=True,
        capture_output=True,
        cwd=LAB_DIR,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Rules script failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def packet_loss(output):
    match = re.search(r"(\d+)% packet loss", output)
    if not match:
        raise RuntimeError(f"Could not parse ping output:\n{output}")
    return int(match.group(1))


def ping_ok(src, dst):
    output = src.cmd(f"ping -c 2 -W 1 {dst.IP()}")
    return packet_loss(output) == 0, output


def expect(label, condition, details):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}")
    if not condition:
        print(details.strip())
    return condition


def verify_topology_shape(net):
    expected_hosts = {"h1", "h2", "h3"}
    expected_switches = {"s1", "s2", "s3", "s4"}

    actual_hosts = {host.name for host in net.hosts}
    actual_switches = {switch.name for switch in net.switches}

    ok = True
    ok &= expect(
        "hosts present",
        actual_hosts == expected_hosts,
        f"Expected hosts {sorted(expected_hosts)}, found {sorted(actual_hosts)}",
    )
    ok &= expect(
        "switches present",
        actual_switches == expected_switches,
        f"Expected switches {sorted(expected_switches)}, found {sorted(actual_switches)}",
    )
    return ok


def verify_connectivity(net):
    h1, h2, h3 = net["h1"], net["h2"], net["h3"]
    ok = True

    success, output = ping_ok(h1, h2)
    ok &= expect("h1 can reach h2", success, output)

    success, output = ping_ok(h2, h1)
    ok &= expect("h2 can reach h1", success, output)

    success, output = ping_ok(h1, h3)
    ok &= expect("h1 can reach h3", success, output)

    success, output = ping_ok(h3, h1)
    ok &= expect("h3 can reach h1", success, output)

    success, output = ping_ok(h2, h3)
    ok &= expect("h2 cannot reach h3", not success, output)

    success, output = ping_ok(h3, h2)
    ok &= expect("h3 cannot reach h2", not success, output)

    return ok


def main():
    parser = argparse.ArgumentParser(description="Verify the Lab 1 challenge solution.")
    parser.add_argument(
        "--topology",
        default="topology_starter.py",
        help="Topology file to import",
    )
    parser.add_argument(
        "--rules",
        default="install_rules.sh",
        help="Rules script to execute after the topology starts",
    )
    args = parser.parse_args()

    require_root()

    topology_path = (LAB_DIR / args.topology).resolve()
    rules_path = (LAB_DIR / args.rules).resolve()

    if not topology_path.exists():
        print(f"Topology file not found: {topology_path}")
        sys.exit(2)
    if not rules_path.exists():
        print(f"Rules file not found: {rules_path}")
        sys.exit(2)

    cleanup_mininet()
    module = load_topology_module(topology_path)
    net = None

    try:
        net = create_network(module)
        validate_topology(net)
        net.start()
        net.staticArp()
        run_rules_script(rules_path)

        print("Verifying Lab 1 challenge...\n")
        ok = verify_topology_shape(net)
        ok &= verify_connectivity(net)
    except RuntimeError as err:
        print(f"\n[Verification error]\n{err}\n")
        ok = False
    finally:
        if net is not None:
            net.stop()
        cleanup_mininet()

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
