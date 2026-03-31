#!/usr/bin/env python3
"""
workshop_topology.py
────────────────────
Defines the Mininet topology used across all workshop labs.

Physical layout:

    h1 ── s1 ────────── s2 ── h2
           |             |
           s3 ───────────┘
           |
          mb1
           |
          h3

    h1  : traffic source        (IPv4: 10.0.0.1,  SRv6 SID: fc00::1)
    h2  : traffic destination   (IPv4: 10.0.0.2,  SRv6 SID: fc00::2)
    h3  : additional host       (IPv4: 10.0.0.3,  SRv6 SID: fc00::3)
    mb1 : middlebox             (IPv4: 10.0.0.4,  SRv6 SID: fc00::b1)
    s1  : OVS switch 1
    s2  : OVS switch 2
    s3  : OVS switch 3 (connects to middlebox)

Why this topology?

    Lab 1 — Flow rules:
        Multiple switches give participants meaningful rule installation.
        h1↔h2 requires rules on s1 and s2.
        h1↔h3 requires rules on s1 and s3.
        h2↔h3 isolation is non-trivial to enforce.

    Lab 2 — ONOS + link failure:
        The s1-s2-s3 triangle loop means ONOS can reroute traffic via s3
        when the s1-s2 link goes down. Without a loop, rerouting is impossible.

    Lab 3 — SRv6 path steering:
        A direct path h1→s1→s2→h2 exists.
        SRv6 forces the longer path h1→s1→s3→mb1→s3→s1→s2→h2.
        This demonstrates that SRv6 is actually doing path control —
        traffic takes the longer route only because the packet says so.

    Lab 4 — Transport slice controller:
        Same as Lab 3 with ONOS for topology discovery and flow rules.

Usage:
    sudo python3 workshop_topology.py
    sudo python3 workshop_topology.py --onos      # connect to ONOS (Lab 2, 4)
    sudo python3 workshop_topology.py --srv6      # enable SRv6 (Lab 3)
    sudo python3 workshop_topology.py --onos --srv6  # full stack (Lab 4)
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController, DefaultController
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
import argparse


# ─── IPv4 addresses ───────────────────────────────────────────────────────────

HOST_IPS = {
    'h1':  '10.0.0.1/24',
    'h2':  '10.0.0.2/24',
    'h3':  '10.0.0.3/24',
    'mb1': '10.0.0.4/24',
}

# ─── SRv6 Segment IDs (SIDs) ──────────────────────────────────────────────────
#
# Each node that participates in SRv6 gets a unique IPv6 SID.
# These are the addresses that appear in the Segment Routing Header (SRH).
# Think of them as "waypoint labels" — the packet carries a list of these,
# and each node processes the SRH when it sees its own SID as the destination.

SRV6_SIDS = {
    'h1':  'fc00::1',
    'h2':  'fc00::2',
    'h3':  'fc00::3',
    'mb1': 'fc00::b1',
}

# ─── Link bandwidth limits ────────────────────────────────────────────────────
#
# TCLink lets us set bandwidth, delay, and loss on each link.
# These limits make the QoS queuing exercise meaningful — without a cap,
# a 10Mbps guarantee on an unconstrained link is hard to observe.

LINK_BW_MBPS = 100   # 100Mbps per link — enough headroom for slicing demo


class WorkshopTopo(Topo):
    """
    The topology used across all 4 workshop labs.

    Mininet calls build() automatically when the topology is instantiated.
    """

    def build(self):
        # ── Hosts ──────────────────────────────────────────────────────────────

        h1  = self.addHost('h1',  ip=HOST_IPS['h1'])
        h2  = self.addHost('h2',  ip=HOST_IPS['h2'])
        h3  = self.addHost('h3',  ip=HOST_IPS['h3'])

        # The middlebox simulates a service function (firewall, DPI, NAT, etc.).
        # It sits on s3 — off the direct h1→h2 path — so SRv6 is needed
        # to force traffic through it.
        mb1 = self.addHost('mb1', ip=HOST_IPS['mb1'])

        # ── Switches ───────────────────────────────────────────────────────────

        s1 = self.addSwitch('s1', cls=OVSSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSSwitch, protocols='OpenFlow13')
        s3 = self.addSwitch('s3', cls=OVSSwitch, protocols='OpenFlow13')

        # ── Links ──────────────────────────────────────────────────────────────
        #
        # Host links
        self.addLink(h1,  s1, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h2,  s2, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h3,  s3, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb1, s3, cls=TCLink, bw=LINK_BW_MBPS)

        # Switch links — s1-s2-s3 triangle provides loop for rerouting (Lab 2)
        # and an alternate path bypassing mb1 (Labs 3, 4)
        self.addLink(s1, s2, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(s2, s3, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(s1, s3, cls=TCLink, bw=LINK_BW_MBPS)


def configure_srv6(net):
    """
    Assign SRv6 SIDs to each host and enable SRv6 in the kernel.

    Called automatically with --srv6 flag. Not needed for Labs 1 and 2.

    What this does on each host:
      - Assigns the SRv6 SID as a /128 address on the host interface
      - Enables IPv6 forwarding
      - Enables SRv6 header processing (seg6_enabled)
    """
    print("\n[SRv6] Assigning SIDs and enabling SRv6 on all hosts...")

    for name, sid in SRV6_SIDS.items():
        host = net[name]
        iface = f"{name}-eth0"

        # Assign the SID as a /128 address — like a loopback, this exact
        # address belongs to this node and is used as its segment identifier.
        host.cmd(f'ip -6 addr add {sid}/128 dev {iface}')

        # Enable IPv6 forwarding and SRv6 header processing
        host.cmd('sysctl -w net.ipv6.conf.all.forwarding=1')
        host.cmd('sysctl -w net.ipv6.conf.all.seg6_enabled=1')
        host.cmd(f'sysctl -w net.ipv6.conf.{iface}.seg6_enabled=1')

        print(f"  {name}: SID={sid}, iface={iface}")

    print("[SRv6] Done.\n")


def print_topology_info(net):
    """Print a summary of the running topology."""
    print("\n" + "═" * 60)
    print("  Workshop Topology")
    print("═" * 60)
    print("""
    h1 ── s1 ────────── s2 ── h2
           |             |
           s3 ───────────┘
           |
          mb1
           |
          h3
    """)
    print(f"  {'Node':<8} {'IPv4':<16} {'SRv6 SID'}")
    print(f"  {'────':<8} {'────':<16} {'────────'}")
    for name in ['h1', 'h2', 'h3', 'mb1']:
        print(f"  {name:<8} {HOST_IPS[name]:<16} {SRV6_SIDS[name]}")
    print()
    print("  Switches: s1, s2, s3 (OpenFlow13) — triangle topology")
    print("  Links:    100Mbps, TCLink")
    print("═" * 60 + "\n")


def run(use_onos=False, enable_srv6=False):
    setLogLevel('info')

    if use_onos:
        print("[Controller] Connecting to ONOS at 127.0.0.1:6653")
        controller = lambda name: RemoteController(
            name, ip='127.0.0.1', port=6653
        )
    else:
        print("[Controller] Using OVS default controller (no ONOS)")
        controller = DefaultController

    net = Mininet(
        topo=WorkshopTopo(),
        controller=controller,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        waitConnected=True,
    )

    net.start()

    if enable_srv6:
        configure_srv6(net)

    print_topology_info(net)

    CLI(net)

    net.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Workshop Mininet topology')
    parser.add_argument(
        '--onos',
        action='store_true',
        help='Connect switches to ONOS controller (Labs 2 and 4)'
    )
    parser.add_argument(
        '--srv6',
        action='store_true',
        help='Assign SRv6 SIDs and enable SRv6 on all hosts (Labs 3 and 4)'
    )
    args = parser.parse_args()

    run(use_onos=args.onos, enable_srv6=args.srv6)