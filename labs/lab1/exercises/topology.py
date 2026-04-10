#!/usr/bin/env python3
"""
topology.py
-----------
Lab 1 exercise topology: three hosts connected to one switch.

    h1 (10.0.0.1) ──┐
    h2 (10.0.0.2) ──┤  s1  (OpenFlow 1.3, no controller)
    h3 (10.0.0.3) ──┘

All links: 10 Mbps, 5 ms delay.

Run with:
    sudo python3 exercises/topology.py

After it starts, check port numbers with:
    sudo ovs-ofctl -O OpenFlow13 show s1
"""

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import OVSSwitch


def build_topology():
    """Build and return the topology (not yet started)."""
    net = Mininet()

    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")

    s1 = net.addSwitch("s1", cls=OVSSwitch, protocols="OpenFlow13")

    net.addLink(h1, s1, cls=TCLink, bw=10, delay="5ms")
    net.addLink(h2, s1, cls=TCLink, bw=10, delay="5ms")
    net.addLink(h3, s1, cls=TCLink, bw=10, delay="5ms")

    return net


def main():
    net = build_topology()
    net.start()
    net.staticArp()

    print("\nTopology started: h1, h2, h3 all connected to s1.")
    print("Run 'net' to see which host connects to which port.")
    print("Install rules from the second terminal, then test with pingall.\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    main()
