#!/usr/bin/env python3
"""
Exercise 2 — Slice Admission Control
=====================================

The bottleneck link (s1→s2) has a capacity of 10 Mbps.

In this exercise you will deliberately try to provision more bandwidth
than the link can support, observe the controller reject it, and think
about what a smarter admission control policy might look like.

Background:
  The slice controller uses simple first-come-first-served admission:
    - Track total reserved bandwidth across all active slices
    - Reject any new slice that would exceed link capacity
    - No preemption, no negotiation, no dynamic reallocation

Tasks:
  1. Provision a premium slice for h1 (8 Mbps, chain=["mb1"])
  2. Try to provision a second slice for h3 that exceeds remaining capacity
  3. Read the AdmissionError — what does it tell you?
  4. Find a bandwidth value for h3's slice that the controller accepts
  5. Observe both slices running simultaneously

Think about:
  - What is the maximum bandwidth h3's slice can request?
  - What happens to h3's traffic while only the premium slice is active?
  - Is first-come-first-served always the right policy?

Further reading:
  M. Sulaiman et al., "Coordinated Slicing and Admission Control using
  Multi-Agent Deep Reinforcement Learning", IEEE TNSM, Vol. 20(2), 2023.

Usage:
    sudo python3 exercises/part2.py
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
from slice_controller import SliceController, AdmissionError, MB1_LOG

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
        autoSetMacs=False,
        waitConnected=True,
    )

    info("*** Starting network\n")
    net.start()

    try:
        h1  = net.get('h1')
        h2  = net.get('h2')
        h3  = net.get('h3')
        mb1 = net.get('mb1')
        s1  = net.get('s1')
        s2  = net.get('s2')

        sc = SliceController(net, ingress=s1, peer=s2, link_bw=BOTTLENECK_BW)
        sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2", "r1")

        info("*** Testing connectivity\n")
        net.pingAll()
        sc.verify_srv6("h1", "h2", "mb1")

        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)

        sc._start_mb1_logger(mb1)

        input(f"\n[ Press ENTER ] ▶  Step 1: Provision premium slice for h1")
        print()

        # ── TODO 1 ────────────────────────────────────────────────────────────
        # Provision a "premium" slice for h1.
        # Requirements: chain through mb1, 8 Mbps guaranteed.
        #
        # sc.provision(???)
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print(f"""
Premium slice active.

    tail -F /tmp/iperf_h1.log   → ~8 Mbps (guaranteed)
    tail -F /tmp/iperf_h3.log   → ~2 Mbps (best-effort, squeezed)
    tail -F {MB1_LOG}   → traffic

Notice h3 is getting very little bandwidth with no slice protection.
        """)

        input("\n[ Press ENTER ] ▶  Step 2: Try to provision a slice for h3")
        print()

        # ── TODO 2 ────────────────────────────────────────────────────────────
        # Try to provision a slice for h3 with more bandwidth than is available.
        # Wrap it in a try/except AdmissionError to catch the rejection.
        #
        # try:
        #     sc.provision("standard", src="h3", dst="h2", chain=[], bw=???)
        # except AdmissionError as e:
        #     print(e)
        # ─────────────────────────────────────────────────────────────────────

        input("\n[ Press ENTER ] ▶  Step 3: Provision h3 with a fitting bandwidth")
        print()

        # ── TODO 3 ────────────────────────────────────────────────────────────
        # Now provision a slice for h3 that the controller will accept.
        # How much bandwidth is actually available?
        #
        # sc.provision("standard", src="h3", dst="h2", chain=[], bw=???)
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

        h1.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h3.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(1)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)
        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        time.sleep(0.5)
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print(f"""
Both slices active. What do you observe?

    tail -F /tmp/iperf_h1.log   → ?
    tail -F /tmp/iperf_h3.log   → ?

Reflection questions:
  - What bandwidth did h3 actually get? Is it what you expected?
  - What happens if a third flow arrives and there is no capacity left?
  - Our controller uses first-come-first-served with no preemption.
    Can you think of a scenario where this policy is unfair or inefficient?
  - How might a smarter controller decide which slice to admit or preempt?
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
