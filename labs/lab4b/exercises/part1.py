#!/usr/bin/env python3
"""
Exercise 1 — Transport Slice Provisioning
==========================================

You have seen the direct-path demo provision a premium slice through mb1.
Your task: provision a slice that visits mb2 instead, with 6 Mbps guaranteed.

Both mb1 and mb2 loggers will be running — only one should light up.

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
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI

LAB4B_DIR = Path(__file__).resolve().parents[1]
if str(LAB4B_DIR) not in sys.path:
    sys.path.insert(0, str(LAB4B_DIR))

from topology import Lab4bTopo, ONOS_IP, ONOS_PORT, BOTTLENECK_BW
from slice_controller import SliceController, MB1_LOG, MB2_LOG

H1_PORT = 5201
H3_PORT = 5202


def main():
    setLogLevel("info")

    print(f"[Controller] Connecting to ONOS at {ONOS_IP}:{ONOS_PORT}")
    net = Mininet(
        topo=Lab4bTopo(),
        controller=lambda name: RemoteController(name, ip=ONOS_IP, port=ONOS_PORT),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        waitConnected=True,
    )

    info("*** Starting network\n")
    net.start()

    try:
        h1  = net.get('h1')
        h2  = net.get('h2')
        h3  = net.get('h3')
        mb1 = net.get('mb1')
        mb2 = net.get('mb2')
        s1  = net.get('s1')
        s2  = net.get('s2')

        sc = SliceController(net, ingress=s1, peer=s2, link_bw=BOTTLENECK_BW)

        info("*** Testing connectivity\n")
        net.pingAll()
        sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2", "r1")
        sc.warmup_ndp("h1", "h2", "h3", "mb1", "mb2")
        sc.verify_srv6("h1", "h2", "mb1", "mb2")

        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)

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
        #   - traffic must visit mb2 (not mb1)
        #   - h1 should get 6 Mbps guaranteed
        #
        # Hint: look at how sc.provision() was used in slice_demo.py.
        #       The chain parameter controls which waypoints are visited.
        #
        # sc.provision(???)
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

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
        #
        # sc.teardown(???)
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

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
        for name in ['h1', 'h2', 'h3', 'mb1', 'mb2']:
            h = net.get(name)
            h.cmd("pkill -f iperf3    2>/dev/null; true")
            h.cmd("pkill -f mb_logger 2>/dev/null; true")
        net.stop()


if __name__ == "__main__":
    main()
