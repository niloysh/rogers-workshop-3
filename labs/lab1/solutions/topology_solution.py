#!/usr/bin/env python3
"""Reference topology for the Lab 1 challenge."""

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import OVSSwitch


def build_topology():
    net = Mininet()

    h1 = net.addHost("h1", ip="10.0.0.1/24")
    h2 = net.addHost("h2", ip="10.0.0.2/24")
    h3 = net.addHost("h3", ip="10.0.0.3/24")

    s1 = net.addSwitch("s1", cls=OVSSwitch, protocols="OpenFlow13")
    s2 = net.addSwitch("s2", cls=OVSSwitch, protocols="OpenFlow13")
    s3 = net.addSwitch("s3", cls=OVSSwitch, protocols="OpenFlow13")
    s4 = net.addSwitch("s4", cls=OVSSwitch, protocols="OpenFlow13")

    net.addLink(h1, s1, cls=TCLink, bw=10, delay="5ms")
    net.addLink(h2, s2, cls=TCLink, bw=10, delay="5ms")
    net.addLink(h3, s4, cls=TCLink, bw=10, delay="5ms")

    net.addLink(s1, s2, cls=TCLink, bw=10, delay="5ms")
    net.addLink(s1, s3, cls=TCLink, bw=10, delay="5ms")
    net.addLink(s2, s4, cls=TCLink, bw=10, delay="5ms")
    net.addLink(s3, s4, cls=TCLink, bw=10, delay="5ms")

    return net


def main():
    net = build_topology()
    net.start()
    net.staticArp()

    print("\nReference challenge topology started.")
    print("Install the reference rules with:")
    print("  sudo bash solutions/install_rules_solution.sh\n")

    CLI(net)
    net.stop()


if __name__ == "__main__":
    main()
