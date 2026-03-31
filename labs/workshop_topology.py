#!/usr/bin/env python3
"""
workshop_topology.py
────────────────────
Defines the Mininet topology used across all 4 workshop exercises.

Physical layout:

    h1 ── s1 ── mb1 ── s2 ── h2
                │
            (middlebox)

    h1  : traffic source        (IPv4: 10.0.0.1,  SRv6 SID: fc00::1)
    h2  : traffic destination   (IPv4: 10.0.0.2,  SRv6 SID: fc00::2)
    mb1 : middlebox             (IPv4: 10.0.0.3,  SRv6 SID: fc00::b1)
    s1  : OVS switch 1
    s2  : OVS switch 2

The middlebox simulates a service function (firewall, DPI, NAT, etc.).
In the slicing exercise, video traffic is forced through mb1 before
reaching h2. Bulk traffic takes the direct path s1 → s2 → h2.

Usage:
    sudo python3 workshop_topology.py
    sudo python3 workshop_topology.py --onos   # connect to ONOS controller
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController, DefaultController
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI
import argparse


# ─── IPv4 addresses ───────────────────────────────────────────────────────────
#
# These are the standard Mininet IPv4 addresses used in Exercises 1 and 2.
# In Exercise 3 and 4 we add IPv6/SRv6 addresses on top of these.

HOST_IPS = {
    'h1':  '10.0.0.1/24',
    'h2':  '10.0.0.2/24',
    'mb1': '10.0.0.3/24',
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
    The single topology used across all 4 workshop exercises.

    Mininet calls build() automatically when the topology is instantiated.
    You should not need to modify this class — the topology is intentionally
    simple so you can focus on the networking concepts, not the plumbing.
    """

    def build(self):
        # ── Hosts ──────────────────────────────────────────────────────────────
        #
        # addHost() creates a network namespace with a virtual ethernet interface.
        # The 'ip' parameter sets the IPv4 address assigned at startup.

        h1  = self.addHost('h1',  ip=HOST_IPS['h1'])
        h2  = self.addHost('h2',  ip=HOST_IPS['h2'])

        # The middlebox is just another host in Mininet — it has a network
        # namespace and we can run arbitrary processes inside it.
        # In a real network this would be a dedicated appliance (firewall, DPI box).
        mb1 = self.addHost('mb1', ip=HOST_IPS['mb1'])

        # ── Switches ───────────────────────────────────────────────────────────
        #
        # OVS switches are the data plane. In Exercise 1 you program them
        # manually with ovs-vsctl. In Exercise 2, ONOS takes over via OpenFlow.

        s1 = self.addSwitch('s1', cls=OVSSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSSwitch, protocols='OpenFlow13')

        # ── Links ──────────────────────────────────────────────────────────────
        #
        # TCLink gives us bandwidth control. All links share the same cap
        # so the topology is symmetric and easy to reason about.

        self.addLink(h1,  s1,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h2,  s2,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb1, s1,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(s1,  s2,  cls=TCLink, bw=LINK_BW_MBPS)


def configure_srv6(net):
    """
    Assign SRv6 SIDs to each host and enable SRv6 in the kernel.

    This is called automatically when you run the topology in Exercise 3+.
    In Exercise 1 and 2 you can skip this — it's not needed for basic
    OpenFlow / intent exercises.

    What this does on each host:
      - Assigns the SRv6 SID as a /128 loopback-style address
      - Enables IPv6 forwarding
      - Enables SRv6 header processing (seg6_enabled)
    """
    print("\n[SRv6] Assigning SIDs and enabling SRv6 on all hosts...")

    for name, sid in SRV6_SIDS.items():
        host = net[name]

        # Assign the SID as a /128 address on the host's interface.
        # /128 means "this exact address belongs to me" — like a loopback.
        iface = f"{name}-eth0"
        host.cmd(f'ip -6 addr add {sid}/128 dev {iface}')

        # Enable IPv6 forwarding — needed for transit and endpoint behaviour
        host.cmd('sysctl -w net.ipv6.conf.all.forwarding=1')

        # Enable SRv6 header processing.
        # Without this the kernel ignores the SRH and drops the packet.
        host.cmd('sysctl -w net.ipv6.conf.all.seg6_enabled=1')
        host.cmd(f'sysctl -w net.ipv6.conf.{iface}.seg6_enabled=1')

        print(f"  {name}: SID={sid}, iface={iface}")

    print("[SRv6] Done.\n")


def print_topology_info(net):
    """Print a summary of the running topology for participants."""
    print("\n" + "═" * 60)
    print("  Workshop Topology")
    print("═" * 60)
    print("""
    h1 ── s1 ── mb1 ── s2 ── h2
                │
            (middlebox)
    """)
    print(f"  {'Node':<8} {'IPv4':<16} {'SRv6 SID'}")
    print(f"  {'────':<8} {'────':<16} {'────────'}")
    for name in ['h1', 'h2', 'mb1']:
        host = net[name]
        print(f"  {name:<8} {HOST_IPS[name]:<16} {SRV6_SIDS[name]}")
    print()
    print("  Switches: s1 (OpenFlow13), s2 (OpenFlow13)")
    print("  Links:    100Mbps, TCLink")
    print("═" * 60 + "\n")


def run(use_onos=False, enable_srv6=False):
    setLogLevel('info')

    # ── Choose controller ──────────────────────────────────────────────────────
    #
    # Exercise 1: DefaultController (OVS internal) — no external controller
    # Exercise 2: RemoteController  — ONOS running in Docker on port 6653
    # Exercise 3: DefaultController — SRv6 is host-based, no controller needed
    # Exercise 4: RemoteController  — ONOS for topology + flow rules

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
        autoSetMacs=True,    # assign readable MAC addresses (00:00:00:00:00:01 etc)
        waitConnected=True,  # wait for switches to connect to controller
    )

    net.start()

    if enable_srv6:
        configure_srv6(net)

    print_topology_info(net)

    # Drop into the Mininet CLI so participants can run commands interactively
    CLI(net)

    net.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Workshop Mininet topology')
    parser.add_argument(
        '--onos',
        action='store_true',
        help='Connect switches to ONOS controller (use in Ex2 and Ex4)'
    )
    parser.add_argument(
        '--srv6',
        action='store_true',
        help='Assign SRv6 SIDs and enable SRv6 on all hosts (use in Ex3 and Ex4)'
    )
    args = parser.parse_args()

    run(use_onos=args.onos, enable_srv6=args.srv6)