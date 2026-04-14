#!/usr/bin/env python3
"""
triangle_topology.py
--------------------
Defines the Mininet topology used in Lab 2.

Physical layout:

    h1 ── s1 ────────── s2 ── h2
           |             |
           s3 ───────────┘
           |
          h3

This is the smallest topology in the workshop that still shows:
  - ONOS device and link discovery
  - host discovery after traffic appears
  - automatic forwarding
  - rerouting after the s1-s2 link fails

Usage:
    sudo python3 triangle_topology.py
"""

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.topo import Topo


HOST_IPS = {
    "h1": "10.0.0.1/24",
    "h2": "10.0.0.2/24",
    "h3": "10.0.0.3/24",
}

LINK_BW_MBPS = 100


class TriangleTopo(Topo):
    """Three switches in a triangle, with one host on each edge switch."""

    def build(self):
        h1 = self.addHost("h1", ip=HOST_IPS["h1"])
        h2 = self.addHost("h2", ip=HOST_IPS["h2"])
        h3 = self.addHost("h3", ip=HOST_IPS["h3"])

        s1 = self.addSwitch("s1", cls=OVSSwitch, protocols="OpenFlow13")
        s2 = self.addSwitch("s2", cls=OVSSwitch, protocols="OpenFlow13")
        s3 = self.addSwitch("s3", cls=OVSSwitch, protocols="OpenFlow13")

        self.addLink(h1, s1, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h2, s2, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h3, s3, cls=TCLink, bw=LINK_BW_MBPS)

        self.addLink(s1, s2, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(s2, s3, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(s1, s3, cls=TCLink, bw=LINK_BW_MBPS)


def print_topology_info():
    """Print a summary of the running topology."""
    print("\n" + "═" * 60)
    print("  Triangle Topology")
    print("═" * 60)
    print(
        """
    h1 ── s1 ────────── s2 ── h2
           |             |
           s3 ───────────┘
           |
          h3
    """
    )
    print(f"  {'Node':<8} {'IPv4'}")
    print(f"  {'────':<8} {'────'}")
    for name in ["h1", "h2", "h3"]:
        print(f"  {name:<8} {HOST_IPS[name]}")
    print()
    print("  Switches: s1, s2, s3 (OpenFlow13)")
    print("  Links:    100Mbps, TCLink")
    print("═" * 60 + "\n")


def run():
    setLogLevel("info")

    print("[Controller] Connecting to ONOS at 127.0.0.1:6653")
    controller = lambda name: RemoteController(name, ip="127.0.0.1", port=6653)

    net = Mininet(
        topo=TriangleTopo(),
        controller=controller,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        waitConnected=True,
    )

    net.start()
    print_topology_info()
    CLI(net)
    net.stop()


if __name__ == "__main__":
    run()
