#!/usr/bin/env python3
"""
topology.py
────────────────
Lab 3 topology — SRv6 Service Function Chaining.

Physical layout:

    h1 ── s1 ── s2 ── h2
                ├── mb1  (waypoint 1)
                └── mb2  (IDS)

    h1  : traffic source       (IPv4: 10.0.0.1,  SRv6 SID: fc00::1)
    h2  : traffic destination  (IPv4: 10.0.0.2,  SRv6 SID: fc00::2)
    mb1 : waypoint 1           (IPv4: 10.0.0.3,  SRv6 SID: fc00::b1)
    mb2 : IDS                  (IPv4: 10.0.0.4,  SRv6 SID: fc00::b2)
    s1  : OVS switch 1
    s2  : OVS switch 2

Service chain:
    h1 → mb1 (waypoint 1) → mb2 (IDS) → h2

    mb1 is the first service waypoint
    mb2 inspects tunneled HTTP payloads and alerts on suspicious patterns

Why this topology?
    The direct path h1→s1→s2→h2 bypasses both service functions.
    SRv6 forces traffic through mb1 then mb2 before reaching h2.

    Without SRv6:
      - curl requests reach h2 unfiltered and unmonitored
      - malicious requests go undetected

    With SRv6:
      - the outer SRv6 packet is forced through mb1 then mb2
      - mb2 inspects tunneled HTTP payloads and alerts on suspicious patterns
      - malicious requests are detected even though they still reach h2

Usage:
    sudo python3 topology.py

Note:
    SRv6 is NOT configured at startup.
    You will configure it manually during the lab.
"""

from mininet.topo import Topo
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.cli import CLI


HOST_IPS = {
    'h1':  '10.0.0.1/24',
    'h2':  '10.0.0.2/24',
    'mb1': '10.0.0.3/24',
    'mb2': '10.0.0.4/24',
}

SRV6_SIDS = {
    'h1':  'fc00::1',
    'h2':  'fc00::2',
    'mb1': 'fc00::b1',
    'mb2': 'fc00::b2',
}

LINK_BW_MBPS = 100


class Lab3Topo(Topo):
    def build(self):
        h1  = self.addHost('h1',  ip=HOST_IPS['h1'])
        h2  = self.addHost('h2',  ip=HOST_IPS['h2'])
        mb1 = self.addHost('mb1', ip=HOST_IPS['mb1'])
        mb2 = self.addHost('mb2', ip=HOST_IPS['mb2'])

        s1 = self.addSwitch('s1', cls=OVSSwitch, failMode='standalone')
        s2 = self.addSwitch('s2', cls=OVSSwitch, failMode='standalone')

        self.addLink(h1,  s1,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h2,  s2,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb1, s2,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb2, s2,  cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(s1,  s2,  cls=TCLink, bw=LINK_BW_MBPS)


def print_topology_info():
    print("\n" + "═" * 60)
    print("  Lab 3 — SRv6 Service Function Chaining")
    print("═" * 60)
    print("""
    h1 ── s1 ── s2 ── h2
                |
               ├── mb1  (waypoint 1)
               └── mb2  (IDS — inspects tunneled HTTP)
    """)
    print(f"  {'Node':<8} {'IPv4':<16} {'SRv6 SID':<16} {'Role'}")
    print(f"  {'────':<8} {'────':<16} {'────────':<16} {'────'}")
    roles = {'h1': 'source', 'h2': 'destination',
             'mb1': 'waypoint 1', 'mb2': 'IDS'}
    for name in ['h1', 'h2', 'mb1', 'mb2']:
        print(f"  {name:<8} {HOST_IPS[name]:<16} "
              f"{SRV6_SIDS[name]:<16} {roles[name]}")
    print()
    print("  SRv6 NOT configured — you will do this in the lab")
    print("  Direct path h1→h2 bypasses mb1 and mb2")
    print("  Switches run in standalone learning mode — no ONOS needed")
    print("═" * 60 + "\n")


def run():
    setLogLevel('info')
    net = Mininet(
        topo=Lab3Topo(),
        controller=None,
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
