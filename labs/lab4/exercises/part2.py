#!/usr/bin/env python3
"""
Exercise 2 - Slice Admission Control
=====================================
Topology:

    h1 --.
    h3 --+-- s1 --[10Mbps]-- s2 -- s3 -- h2
                              |     |
                             mb1   mb2

The bottleneck link (s1->s2) has a capacity of 10 Mbps.

In this exercise you will deliberately try to provision more bandwidth
than the link can support, observe the controller reject it, and think
about what a smarter admission control policy might look like.

Background:
  The slice controller uses a simple first-come-first-served policy:
    - Track total reserved bandwidth across all active slices
    - Reject any new slice that would exceed link capacity
    - No preemption, no negotiation, no dynamic reallocation

  This is the simplest possible admission control strategy.
  It works, but it has clear limitations -- which you will discover.

Tasks:
  1. Provision a premium slice for h1 (8 Mbps, chain=[mb1])
  2. Try to provision a second slice for h3 that exceeds remaining capacity
  3. Read the AdmissionError -- what does it tell you?
  4. Find a bandwidth value for h3's slice that the controller accepts
  5. Observe both slices running simultaneously

Think about:
  - What is the maximum bandwidth h3's slice can request?
  - What happens to h3's traffic while only the premium slice is active?
  - Is first-come-first-served always the right policy? When might it fail?

Further reading:
  Our simple controller makes a binary accept/reject decision with no
  intelligence about priorities, traffic patterns, or future demand.
  For a more sophisticated approach using multi-agent deep reinforcement
  learning to coordinate slicing and admission control, see:

  M. Sulaiman, A. Moyyedi, M. Ahmadi, M. A. Salahuddin, R. Boutaba and
  A. Saleh. "Coordinated Slicing and Admission Control using Multi-Agent
  Deep Reinforcement Learning." IEEE Transactions on Network and Service
  Management, Vol. 20(2), pp. 1110-1124, June 2023.

Usage:
    sudo python3 exercises/part2.py
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

from slice_controller import SliceController, AdmissionError, MB1_LOG, MB2_LOG

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
        sc = SliceController(net, ingress=s1, peer=s2, link_bw=10)
        sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2")

        info("*** Testing connectivity\n")
        net.pingAll()
        sc.verify_srv6("h1", "h2", "mb1", "mb2")

        # Start iperf3 servers
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)

        sc._start_mb1_logger(mb1)

        input("\n[ Press ENTER ] ▶  Step 1: Provision premium slice for h1")
        print()

        # ── TODO 1 ────────────────────────────────────────────────────────────
        # Provision a "premium" slice for h1.
        # Requirements: chain through mb1, 8 Mbps guaranteed.
        #
        # Hint: you have done this before in exercise 1.
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

    tail -F /tmp/iperf_h1.log    -> ~8 Mbps (guaranteed)
    tail -F /tmp/iperf_h3.log    -> ~2 Mbps (best-effort, squeezed)
    tail -F {MB1_LOG}    -> traffic

Notice h3 is getting very little bandwidth with no slice protection.
        """)

        input("\n[ Press ENTER ] ▶  Step 2: Try to provision a slice for h3")
        print()

        # ── TODO 2 ────────────────────────────────────────────────────────────
        # Try to provision a slice for h3 with more bandwidth than is available.
        # Wrap it in a try/except AdmissionError to catch the rejection.
        #
        # The controller tracks how much bandwidth is already reserved.
        # Hint: sc.status() shows you available capacity.
        #       Pick a bandwidth that you think will be rejected.
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
        # Hint: link capacity is 10 Mbps, premium slice reserved 8 Mbps.
        #       What is the maximum h3 can request?
        #
        # sc.provision("standard", src="h3", dst="h2", chain=[], bw=???)
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

        # Restart traffic to pick up new queue assignments
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

    tail -F /tmp/iperf_h1.log    -> ?
    tail -F /tmp/iperf_h3.log    -> ?

Reflection questions:
  - What bandwidth did h3 actually get? Is it what you expected?
  - What happens if a third flow arrives and there is no capacity left?
  - Our controller uses first-come-first-served with no preemption.
    Can you think of a scenario where this policy is unfair or inefficient?
  - How might a smarter controller decide which slice to admit or preempt?

Further reading:
  For a deep reinforcement learning approach to this problem, see:
  Sulaiman et al., "Coordinated Slicing and Admission Control using
  Multi-Agent Deep Reinforcement Learning", IEEE TNSM, Vol. 20(2), 2023.
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
