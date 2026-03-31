#!/usr/bin/env python3
"""
topology_starter.py
-------------------
Participant starter for the Lab 1 challenge topology.

Complete the TODO sections, then run:

    sudo python3 topology_starter.py

In a second terminal, install your rules with:

    sudo bash install_rules.sh

You can then verify your work with:

    sudo python3 verify_challenge.py
"""

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import OVSSwitch


def validate_topology(net):
    """Fail early with a clear message if TODOs are still incomplete."""
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
            "The challenge topology is incomplete.\n"
            "Finish the TODO sections in topology_starter.py before starting Mininet.\n"
            f"{details}"
        )


def build_topology():
    """Create the Lab 1 challenge topology and return the Mininet object."""
    net = Mininet()

    # Hosts
    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")

    # Switches
    s1 = net.addSwitch("s1", cls=OVSSwitch, protocols="OpenFlow13")
    s2 = net.addSwitch("s2", cls=OVSSwitch, protocols="OpenFlow13")
    # TODO: add s3 and s4

    # Host links
    net.addLink(h1, s1, cls=TCLink, bw=10, delay="5ms")
    net.addLink(h2, s2, cls=TCLink, bw=10, delay="5ms")
    # TODO: connect h3 to the correct switch

    # Switch-to-switch links
    net.addLink(s1, s2, cls=TCLink, bw=10, delay="5ms")
    # TODO: add the remaining switch-to-switch links
    # Hint: the complete topology is a diamond with s1 at the left and s4 at the right.

    return net


def main():
    net = build_topology()
    try:
        validate_topology(net)
        net.start()
        net.staticArp()
    except RuntimeError as err:
        net.stop()
        print(f"\n[Topology error]\n{err}\n")
        return

    print("\nChallenge topology started.")
    print("Install your flow rules from a second terminal with 'sudo bash install_rules.sh'.")
    print("Use 'ovs-ofctl show <switch>' to confirm port numbers before adding rules.\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    main()
