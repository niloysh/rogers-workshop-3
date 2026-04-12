#!/usr/bin/env python3
"""
Exercise 1 - Transport Slice Provisioning
==========================================
Topology:

    h1 --.
    h3 --+-- s1 --[10Mbps]-- s2 -- s3 -- h2
                              |     |
                             mb1   mb2

You have seen the slice demo provision a premium slice through mb1.
Your task: provision a slice that visits mb2 instead, with 6 Mbps guaranteed.

Both mb1 and mb2 loggers will be running before you provision.
Only one of them should light up when the slice is active -- which one?

Think about:
  - What does chain=[] mean vs chain=["mb1"] vs chain=["mb2"]?
  - What happens to mb1 even though it is connected to the topology?
  - After teardown, what do you expect to see in the iperf logs?

Usage:
    sudo python3 exercises/part1.py
"""

import sys
import time
from pathlib import Path
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI

LAB4_DIR = Path(__file__).resolve().parents[1]
if str(LAB4_DIR) not in sys.path:
    sys.path.insert(0, str(LAB4_DIR))

from slice_controller import SliceController, MB1_LOG, MB2_LOG

H1_PORT = 5201
H3_PORT = 5202


def build_topology(net):
    info("*** Adding hosts\n")
    h1  = net.addHost("h1",  ip="10.0.0.1/24", mac="00:00:00:00:00:01")
    h2  = net.addHost("h2",  ip="10.0.0.2/24", mac="00:00:00:00:00:02")
    h3  = net.addHost("h3",  ip="10.0.0.3/24", mac="00:00:00:00:00:03")
    mb1 = net.addHost("mb1", ip="10.0.0.4/24", mac="00:00:00:00:00:04")
    mb2 = net.addHost("mb2", ip="10.0.0.5/24", mac="00:00:00:00:00:05")

    info("*** Adding switches\n")
    s1 = net.addSwitch("s1", cls=OVSKernelSwitch, failMode="standalone")
    s2 = net.addSwitch("s2", cls=OVSKernelSwitch, failMode="standalone")
    s3 = net.addSwitch("s3", cls=OVSKernelSwitch, failMode="standalone")

    info("*** Adding links\n")
    net.addLink(h1,  s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h3,  s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(mb1, s2, cls=TCLink, bw=100, delay="1ms")
    net.addLink(mb2, s3, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h2,  s3, cls=TCLink, bw=100, delay="1ms")
    net.addLink(s1,  s2, cls=TCLink, bw=10,  delay="5ms")
    net.addLink(s2,  s3, cls=TCLink, bw=100, delay="5ms")

    return h1, h2, h3, mb1, mb2, s1, s2, s3


def main():
    setLogLevel("info")

    net = Mininet(controller=None, switch=OVSKernelSwitch,
                  link=TCLink, autoSetMacs=False)
    h1, h2, h3, mb1, mb2, s1, s2, s3 = build_topology(net)

    info("*** Starting network\n")
    net.start()

    try:
        # The controller needs to know where the bottleneck is.
        # Hint: traffic from h1 and h3 both enter at s1.
        sc = SliceController(net, ingress=s1, peer=s2, link_bw=10)

        # Configure SRv6 on all relevant hosts.
        # Hint: include every host that might be a source, destination,
        # or waypoint -- but not switches for this exercise.
        sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2")

        info("*** Testing connectivity\n")
        net.pingAll()
        sc.verify_srv6("h1", "h2", "mb1", "mb2")

        # Start iperf3 servers on h2
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)

        # Start both loggers so you can observe which one reacts
        # when the slice is provisioned.
        sc._start_mb1_logger(mb1)
        sc._start_mb2_logger(mb2)

        print(f"""
Both loggers running. Before provisioning, both should be silent.

    tail -F {MB1_LOG}    -> ?
    tail -F {MB2_LOG}  -> ?
        """)

        input("[ Press ENTER ] ▶  Provision your slice")
        print()

        # ── TODO ──────────────────────────────────────────────────────────────
        # Provision a slice named "premium" from h1 to h2.
        # Requirements:
        #   - traffic must visit mb2
        #   - h1 should get 6 Mbps guaranteed
        #
        # Hint: look at how sc.provision() was used in slice_demo.py.
        #       The chain parameter controls which waypoints are visited.
        #
        # sc.provision(???)
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

        # Start traffic
        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        time.sleep(0.5)
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print(f"""
Watch these and think about what you expect to see:

    tail -F /tmp/iperf_h1.log    -> ?
    tail -F /tmp/iperf_h3.log    -> ?
    tail -F {MB1_LOG}    -> ?
    tail -F {MB2_LOG}  -> ?
        """)

        input("[ Press ENTER ] ▶  Teardown slice")
        print()

        h1.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h3.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(1)

        # ── TODO ──────────────────────────────────────────────────────────────
        # Tear down the slice you provisioned.
        # Hint: sc.teardown() takes the slice name as an argument.
        #
        # sc.teardown(???)
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

        # Restart traffic to observe best-effort behaviour after teardown
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)
        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        time.sleep(0.5)
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print(f"""
Slice torn down. What do you observe now?

    tail -F /tmp/iperf_h1.log    -> ?
    tail -F /tmp/iperf_h3.log    -> ?
    tail -F {MB1_LOG}    -> ?
    tail -F {MB2_LOG}  -> ?

Why did the throughput change?
What happened to mb2?
        """)

        input("[ Press ENTER ] ▶  Open Mininet CLI (type 'exit' to finish)")
        CLI(net)

    finally:
        info("\n*** Cleaning up\n")
        for h in [h1, h2, h3, mb1, mb2]:
            h.cmd("pkill -f iperf3    2>/dev/null; true")
            h.cmd("pkill -f mb_logger 2>/dev/null; true")
        net.stop()


if __name__ == "__main__":
    main()
