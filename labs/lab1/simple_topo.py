#!/usr/bin/env python3
"""
simple_topo.py
--------------
Demo topology for the guided walkthrough: h1 and h2 connected to s1.

Run with:
    sudo python3 simple_topo.py

Then install rules from a second terminal:
    sudo ovs-ofctl -O OpenFlow13 show s1
    sudo ovs-ofctl -O OpenFlow13 add-flow s1 ...
"""

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import OVSSwitch


def build_topology():
    net = Mininet()

    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    s1 = net.addSwitch("s1", cls=OVSSwitch, protocols="OpenFlow13")

    net.addLink(h1, s1, cls=TCLink, bw=10, delay="5ms")
    net.addLink(h2, s1, cls=TCLink, bw=10, delay="5ms")

    return net


def main():
    net = build_topology()
    net.start()
    net.staticArp()

    print("\nDemo topology started: h1 and h2 connected to s1.")
    print("Run 'net' to see which host connects to which port.")
    print("Install rules from a second terminal.\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    main()
