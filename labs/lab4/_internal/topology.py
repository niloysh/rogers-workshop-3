#!/usr/bin/env python3
"""
topology.py
────────────────
Lab 4 topology — Transport Slicing with ONOS.

Builds on the earlier labs with:
  - ONOS remote controller (OpenFlow13) instead of standalone OVS
  - r1: dual-homed Linux SRv6 router on the alternate path
  - Asymmetric delays: s1-s2 = 30 ms (slow), s1-r1 / r1-s2 = 5 ms (fast)
  - 10 Mbps bottleneck on the direct s1-s2 link
  - h3: contending flow host on s1

Physical layout:

                               mb1   mb2
                                │     │
                                └──┬──┘
    h1 ──┐                         │
         ├── s1 ──[30ms, 10Mbps]─── s2 ── h2
    h3 ──┘   │                      │
             └──────[5ms]── r1 ──[5ms]

SRv6 SIDs:
    h1  : fc00::1
    h2  : fc00::2
    h3  : fc00::3
    mb1 : fc00::b1
    mb2 : fc00::b2
    r1  : fc00::a1 (eth0, s1-facing) / fc00::a2 (eth1, s2-facing)

Usage:
    sudo python3 topology.py

Note:
    ONOS must be running before starting this topology.
    SRv6 is NOT configured at startup — the demo/exercises handle that.
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
    'h3':  '10.0.0.3/24',
    'mb1': '10.0.0.4/24',
    'mb2': '10.0.0.5/24',
    'r1':  '10.0.0.6/24',
}

SRV6_SIDS = {
    'h1':  'fc00::1',
    'h2':  'fc00::2',
    'h3':  'fc00::3',
    'mb1': 'fc00::b1',
    'mb2': 'fc00::b2',
    'r1':  'fc00::a1 (eth0) / fc00::a2 (eth1)',
}

LINK_BW_MBPS     = 100
BOTTLENECK_BW    = 10     # Mbps — s1-s2 direct link (the shared constraint)
BOTTLENECK_DELAY = '30ms'
ALT_DELAY        = '5ms'  # s1-r1 and r1-s2
ONOS_IP          = '127.0.0.1'
ONOS_PORT        = 6653


class Lab4Topo(Topo):
    def build(self):
        h1  = self.addHost('h1',  ip=HOST_IPS['h1'])
        h2  = self.addHost('h2',  ip=HOST_IPS['h2'])
        h3  = self.addHost('h3',  ip=HOST_IPS['h3'])
        mb1 = self.addHost('mb1', ip=HOST_IPS['mb1'])
        mb2 = self.addHost('mb2', ip=HOST_IPS['mb2'])
        r1  = self.addHost('r1',  ip=HOST_IPS['r1'])

        s1 = self.addSwitch('s1', cls=OVSSwitch, protocols='OpenFlow13')
        s2 = self.addSwitch('s2', cls=OVSSwitch, protocols='OpenFlow13')

        # Host-facing links — no artificial delay
        self.addLink(h1,  s1, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h3,  s1, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h2,  s2, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb1, s2, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb2, s2, cls=TCLink, bw=LINK_BW_MBPS)

        # Direct bottleneck — slow and bandwidth-limited (default ONOS path)
        self.addLink(s1, s2, cls=TCLink, bw=BOTTLENECK_BW, delay=BOTTLENECK_DELAY)

        # Alternate path via r1 — fast, high bandwidth (SRv6-steered path)
        # r1-eth0 → s1,  r1-eth1 → s2
        self.addLink(r1, s1, cls=TCLink, bw=LINK_BW_MBPS, delay=ALT_DELAY)
        self.addLink(r1, s2, cls=TCLink, bw=LINK_BW_MBPS, delay=ALT_DELAY)


def get_topology_diagram():
    return "\n".join([
        "                               mb1   mb2",
        "                                │     │",
        "                                └──┬──┘",
        "    h1 ──┐                         │",
        f"         ├── s1 ──[{BOTTLENECK_DELAY},{BOTTLENECK_BW}Mbps]─── s2 ── h2",
        "    h3 ──┘   │                      │",
        f"             └──────────[{ALT_DELAY}]── r1 ──[{ALT_DELAY}]──┤",
    ])


def print_topology_info(include_details=True):
    print("\n" + "═" * 62)
    print("  Lab 4 — Transport Slicing with ONOS")
    print("═" * 62)
    print(get_topology_diagram())
    if not include_details:
        print("═" * 62 + "\n")
        return

    print()
    print(f"  {'Node':<8} {'IPv4':<16} {'SRv6 SID':<34} {'Role'}")
    print(f"  {'────':<8} {'────':<16} {'────────':<34} {'────'}")
    roles = {
        'h1':  'slice source',
        'h2':  'slice destination',
        'h3':  'contending flow',
        'mb1': 'telemetry monitor',
        'mb2': 'security inspector / IDS',
        'r1':  'SRv6 router',
    }
    for name in ['h1', 'h2', 'h3', 'mb1', 'mb2', 'r1']:
        print(f"  {name:<8} {HOST_IPS[name]:<16} "
              f"{SRV6_SIDS[name]:<34} {roles[name]}")
    print()
    print(f"  Switches: s1, s2 (OpenFlow13, ONOS at {ONOS_IP}:{ONOS_PORT})")
    print(f"  Bottleneck s1-s2: {BOTTLENECK_DELAY} / {BOTTLENECK_BW} Mbps")
    print(f"  Alternate via r1: {ALT_DELAY} each leg / {LINK_BW_MBPS} Mbps")
    print("═" * 62 + "\n")


def run():
    setLogLevel('info')

    print(f"[Controller] Connecting to ONOS at {ONOS_IP}:{ONOS_PORT}")
    controller = lambda name: RemoteController(name, ip=ONOS_IP, port=ONOS_PORT)

    net = Mininet(
        topo=Lab4Topo(),
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
