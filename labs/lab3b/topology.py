#!/usr/bin/env python3
"""
topology.py
────────────────
Lab 3b topology — SRv6 Service Function Chaining with ONOS.

Two OpenFlow switches carry the baseline path between h1 and h2.
A dual-homed Linux host, r1, adds an alternate path between s1 and s2.
Unlike an OVS switch, r1 can be an SRv6 segment endpoint: it receives
packets addressed to its SID, processes the SRH in the Linux kernel, and
forwards to the next segment.

Link delays are asymmetric on purpose:
  - s1 ─[30ms]─ s2   direct path, intentionally slow
  - s1 ─[5ms]─ r1 ─[5ms]─ s2   alternate path, faster

Without SRv6 ONOS routes h1→h2 via the direct s1-s2 link (fewer hops).
SRv6 encap on h1 forces the outer packet through r1, taking the lower-
latency alternate path despite the extra hop.

Physical layout:

    h1 ── s1 ──[30ms]── s2 ── h2
           |   [5ms] [5ms]   ├── mb1  (waypoint 1)
           └──── r1 ─────────┘   └── mb2  (IDS)

    h1  : traffic source       (IPv4: 10.0.0.1,  SRv6 SID: fc00::1)
    h2  : traffic destination  (IPv4: 10.0.0.2,  SRv6 SID: fc00::2)
    mb1 : waypoint 1           (IPv4: 10.0.0.3,  SRv6 SID: fc00::b1)
    mb2 : IDS                  (IPv4: 10.0.0.4,  SRv6 SID: fc00::b2)
    r1  : SRv6 router          (IPv4: 10.0.0.5,  SRv6 SID: fc00::a1 / fc00::a2)
    s1  : OVS switch 1 (OpenFlow13, controlled by ONOS)
    s2  : OVS switch 2 (OpenFlow13, controlled by ONOS)

Baseline service chain:
    h1 → mb1 (waypoint 1) → mb2 (IDS) → h2

Latency-optimized path after adding r1 to the segment list:
    h1 → r1 → mb1 (waypoint 1) → mb2 (IDS) → h2

Usage:
    sudo python3 topology.py

Note:
    ONOS must be running before starting this topology.
    SRv6 is NOT configured at startup — you will do this in the lab.
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI


HOST_IPS = {
    'h1':  '10.0.0.1/24',
    'h2':  '10.0.0.2/24',
    'mb1': '10.0.0.3/24',
    'mb2': '10.0.0.4/24',
    'r1':  '10.0.0.5/24',
}

SRV6_SIDS = {
    'h1':  'fc00::1',
    'h2':  'fc00::2',
    'mb1': 'fc00::b1',
    'mb2': 'fc00::b2',
    'r1':  'fc00::a1 (eth0) / fc00::a2 (eth1)',
}

LINK_BW_MBPS   = 100
DIRECT_DELAY   = '30ms'   # s1 ── s2  (intentionally slow direct path)
ALT_DELAY      = '5ms'    # s1 ── r1, r1 ── s2  (faster alternate path)
ONOS_IP        = '127.0.0.1'
ONOS_PORT      = 6653


class Lab3bTopo(Topo):
    def build(self):
        h1  = self.addHost('h1',  ip=HOST_IPS['h1'])
        h2  = self.addHost('h2',  ip=HOST_IPS['h2'])
        mb1 = self.addHost('mb1', ip=HOST_IPS['mb1'])
        mb2 = self.addHost('mb2', ip=HOST_IPS['mb2'])
        r1  = self.addHost('r1',  ip=HOST_IPS['r1'])

        s1 = self.addSwitch('s1', cls=OVSSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSSwitch, protocols='OpenFlow13')

        # Host-facing links — no artificial delay
        self.addLink(h1,  s1,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h2,  s2,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb1, s2,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb2, s2,  cls=TCLink, bw=LINK_BW_MBPS)

        # Direct inter-switch link — high delay (default ONOS path)
        self.addLink(s1,  s2,  cls=TCLink, bw=LINK_BW_MBPS, delay=DIRECT_DELAY)

        # Alternate path through r1 — low delay (SRv6 steered path)
        # r1-eth0 → s1,  r1-eth1 → s2
        self.addLink(r1,  s1,  cls=TCLink, bw=LINK_BW_MBPS, delay=ALT_DELAY)
        self.addLink(r1,  s2,  cls=TCLink, bw=LINK_BW_MBPS, delay=ALT_DELAY)


def print_topology_info():
    print("\n" + "═" * 60)
    print("  Lab 3b — SRv6 Service Chaining with ONOS")
    print("═" * 60)
    print(f"""
    h1 ── s1 ──[{DIRECT_DELAY}]── s2 ── h2
           |                |   ├── mb1  (waypoint 1)
         [{ALT_DELAY}]            [{ALT_DELAY}] └── mb2  (IDS)
           └────── r1 ──────┘
    """)
    print(f"  {'Node':<8} {'IPv4':<16} {'SRv6 SID':<16} {'Role'}")
    print(f"  {'────':<8} {'────':<16} {'────────':<16} {'────'}")
    roles = {'h1': 'source', 'h2': 'destination',
             'mb1': 'waypoint 1', 'mb2': 'IDS', 'r1': 'SRv6 router'}
    for name in ['h1', 'h2', 'mb1', 'mb2', 'r1']:
        print(f"  {name:<8} {HOST_IPS[name]:<16} "
              f"{SRV6_SIDS[name]:<16} {roles[name]}")
    print()
    print(f"  Switches: s1, s2 (OpenFlow13, ONOS at {ONOS_IP}:{ONOS_PORT})")
    print(f"  Direct path s1-s2: {DIRECT_DELAY}  |  Alternate via r1: {ALT_DELAY} each leg")
    print("  SRv6 NOT configured — you will do this in the lab")
    print("═" * 60 + "\n")


def run():
    setLogLevel('info')

    print(f"[Controller] Connecting to ONOS at {ONOS_IP}:{ONOS_PORT}")
    controller = lambda name: RemoteController(name, ip=ONOS_IP, port=ONOS_PORT)

    net = Mininet(
        topo=Lab3bTopo(),
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


if __name__ == '__main__':
    run()
