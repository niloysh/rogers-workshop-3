#!/usr/bin/env python3
"""
lab4_topology.py
────────────────
Revised Lab 4 topology — transport slicing over a small triangle core.

Physical layout:

               mb1
                |
 h1 ── r1 ───── r2 ── h2
        \\       /
         \\     /
          \\   /
            r3 ── h3
           /  \\
         mb2  mb3

    h1  : premium source        (10.0.0.1  / fc00::1)
    h2  : destination           (10.0.0.2  / fc00::2)
    h3  : secondary source      (10.0.0.3  / fc00::3)
    mb1 : throughput monitor    (10.0.0.11 / fc00::b1)
    mb2 : firewall policy       (10.0.0.12 / fc00::b2)
    mb3 : flow logger           (10.0.0.13 / fc00::b3)
    r1  : transport node 1
    r2  : transport node 2
    r3  : transport node 3

The triangle r1-r2-r3 provides more than one transport path.
This lets the controller realize low-latency and best-effort intents differently.
"""

from pathlib import Path
import time

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
    "mb1": "10.0.0.11/24",
    "mb2": "10.0.0.12/24",
    "mb3": "10.0.0.13/24",
}

SRV6_SIDS = {
    "h1": "fc00::1",
    "h2": "fc00::2",
    "h3": "fc00::3",
    "mb1": "fc00::b1",
    "mb2": "fc00::b2",
    "mb3": "fc00::b3",
}

LINK_BW_MBPS = 100

ARTIFACTS = [
    "/tmp/slice_controller_state.json",
    "/tmp/mb_monitor.json",
    "/tmp/mb_firewall.json",
    "/tmp/mb_logger.json",
    "/tmp/mb_monitor_config.json",
    "/tmp/mb_firewall_config.json",
    "/tmp/mb_logger_config.json",
    "/tmp/h2_http80.log",
    "/tmp/h2_http8080.log",
    "/tmp/h2_receiver5004.log",
    "/tmp/h2_receiver5005.log",
]


class Lab4Topo(Topo):
    def build(self):
        h1 = self.addHost("h1", ip=HOST_IPS["h1"])
        h2 = self.addHost("h2", ip=HOST_IPS["h2"])
        h3 = self.addHost("h3", ip=HOST_IPS["h3"])

        mb1 = self.addHost("mb1", ip=HOST_IPS["mb1"])
        mb2 = self.addHost("mb2", ip=HOST_IPS["mb2"])
        mb3 = self.addHost("mb3", ip=HOST_IPS["mb3"])

        r1 = self.addSwitch(
            "r1",
            cls=OVSSwitch,
            protocols="OpenFlow13",
            dpid="0000000000000001",
        )
        r2 = self.addSwitch(
            "r2",
            cls=OVSSwitch,
            protocols="OpenFlow13",
            dpid="0000000000000002",
        )
        r3 = self.addSwitch(
            "r3",
            cls=OVSSwitch,
            protocols="OpenFlow13",
            dpid="0000000000000003",
        )

        self.addLink(h1, r1, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h2, r2, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(h3, r3, cls=TCLink, bw=LINK_BW_MBPS)

        self.addLink(mb1, r2, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb2, r3, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(mb3, r3, cls=TCLink, bw=LINK_BW_MBPS)

        self.addLink(r1, r2, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(r2, r3, cls=TCLink, bw=LINK_BW_MBPS)
        self.addLink(r1, r3, cls=TCLink, bw=LINK_BW_MBPS)


def cleanup_artifacts():
    for artifact in ARTIFACTS:
        Path(artifact).unlink(missing_ok=True)


def configure_srv6(net):
    print("\n[SRv6] Configuring hosts and middleboxes...")
    for name, sid in SRV6_SIDS.items():
        host = net[name]
        iface = f"{name}-eth0"
        host.cmd("sysctl -w net.ipv6.conf.all.forwarding=1")
        host.cmd("sysctl -w net.ipv6.conf.all.seg6_enabled=1")
        host.cmd(f"sysctl -w net.ipv6.conf.{iface}.seg6_enabled=1")
        host.cmd(f"ip -6 addr add {sid}/128 dev {iface}")
        host.cmd(f"ip -6 route replace fc00::/64 dev {iface}")
        host.cmd("iptables -F")
        host.cmd("ip6tables -F")
        print(f"  {name}: SID={sid}")
    print("[SRv6] Done.\n")


def start_middlebox_services(net):
    print("[services] Starting middlebox services...")
    services = {
        "mb1": ("mb_monitor.py", "/tmp/mb_monitor.json"),
        "mb2": ("mb_firewall.py", "/tmp/mb_firewall.json"),
        "mb3": ("mb_logger.py", "/tmp/mb_logger.json"),
    }
    for host_name, (script, output_file) in services.items():
        net[host_name].cmd(f"python3 {script} > /tmp/{host_name}.log 2>&1 &")
        print(f"  {host_name}: {script} -> {output_file}")
    time.sleep(2)
    print("[services] Done.\n")


def start_h2_services(net):
    print("[h2] Starting HTTP and UDP services...")
    net["h2"].cmd("python3 -m http.server 80 > /tmp/h2_http80.log 2>&1 &")
    net["h2"].cmd("python3 -m http.server 8080 > /tmp/h2_http8080.log 2>&1 &")
    net["h2"].cmd(
        "stdbuf -oL -eL python3 receiver.py --port 5004 --label primary "
        "> /tmp/h2_receiver5004.log 2>&1 &"
    )
    net["h2"].cmd(
        "stdbuf -oL -eL python3 receiver.py --port 5005 --label secondary "
        "> /tmp/h2_receiver5005.log 2>&1 &"
    )
    print("  h2: HTTP on 80 and 8080")
    print("  h2: UDP demo receivers on 5004 and 5005")
    print("[h2] Done.\n")


def print_topology_info():
    print("\n" + "═" * 64)
    print("  Lab 4 — Revised Transport Slice Topology")
    print("═" * 64)
    print(
        """
               mb1
                |
 h1 ── r1 ───── r2 ── h2
        \\       /
         \\     /
          \\   /
            r3 ── h3
           /  \\
         mb2  mb3
        """
    )
    print(f"  {'Node':<8} {'IPv4':<16} {'SRv6 SID':<16} {'Role'}")
    print(f"  {'────':<8} {'────':<16} {'────────':<16} {'────'}")
    roles = {
        "h1": "premium source",
        "h2": "destination",
        "h3": "secondary source",
        "mb1": "throughput monitor",
        "mb2": "firewall policy",
        "mb3": "flow logger",
    }
    for name in ["h1", "h2", "h3", "mb1", "mb2", "mb3"]:
        print(f"  {name:<8} {HOST_IPS[name]:<16} {SRV6_SIDS[name]:<16} {roles[name]}")
    print()
    print("  Transport nodes: r1, r2, r3 (OpenFlow13, ONOS-controlled)")
    print("  Workshop rule: one active slice per ordered endpoint pair")
    print("═" * 64 + "\n")


def run():
    setLogLevel("info")
    cleanup_artifacts()

    print("[init] Connecting to ONOS at 127.0.0.1:6653...")
    net = Mininet(
        topo=Lab4Topo(),
        controller=lambda name: RemoteController(name, ip="127.0.0.1", port=6653),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        waitConnected=True,
    )

    net.start()
    configure_srv6(net)
    start_middlebox_services(net)
    start_h2_services(net)
    print_topology_info()
    CLI(net)
    net.stop()


if __name__ == "__main__":
    run()
