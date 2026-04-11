#!/usr/bin/env python3
"""
Exercise 2 - Solution
=====================
Usage:
    sudo python3 solutions/part2.py
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

from slice_controller import SliceController, AdmissionError, MB1_LOG

H1_PORT = 5201
H3_PORT = 5202


def build_topology(net):
    info("*** Adding hosts\n")
    h1  = net.addHost("h1",  ip="10.0.0.1/24", mac="00:00:00:00:00:01")
    h2  = net.addHost("h2",  ip="10.0.0.2/24", mac="00:00:00:00:00:02")
    h3  = net.addHost("h3",  ip="10.0.0.3/24", mac="00:00:00:00:00:03")
    mb1 = net.addHost("mb1", ip="10.0.0.4/24", mac="00:00:00:00:00:04")
    mb2 = net.addHost("mb2", ip="10.0.0.5/24", mac="00:00:00:00:00:05")
    s1 = net.addSwitch("s1", cls=OVSKernelSwitch, failMode="standalone")
    s2 = net.addSwitch("s2", cls=OVSKernelSwitch, failMode="standalone")
    s3 = net.addSwitch("s3", cls=OVSKernelSwitch, failMode="standalone")
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
    net.start()

    try:
        sc = SliceController(net, ingress=s1, peer=s2, link_bw=10)
        sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2")
        net.pingAll()
        sc.verify_srv6("h1", "h2", "mb1", "mb2")

        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)
        sc._start_mb1_logger(mb1)

        input("\n[ Press ENTER ] ▶  Step 1: Provision premium slice for h1")
        print()

        # SOLUTION 1: premium slice, 8 Mbps, chain through mb1
        sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
        sc.status()

        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print(f"""
Premium slice active.

    tail -F /tmp/iperf_h1.log    -> ~8 Mbps (guaranteed)
    tail -F /tmp/iperf_h3.log    -> ~2 Mbps (squeezed best-effort)
    tail -F {MB1_LOG}    -> traffic
        """)

        input("\n[ Press ENTER ] ▶  Step 2: Try to overprovision h3")
        print()

        # SOLUTION 2: deliberately try to exceed capacity
        # 10 Mbps link, 8 Mbps reserved = 2 Mbps available
        # Requesting 5 Mbps should be rejected
        print("--- Attempting to provision 5 Mbps for h3 (should fail) ---\n")
        try:
            sc.provision("standard", src="h3", dst="h2", chain=[], bw=5)
        except AdmissionError as e:
            print(e)

        # The error message tells you exactly what went wrong:
        #   Requested : 5 Mbps
        #   Available : 2 Mbps  (10 - 8 = 2)
        #   Reserved  : 8 Mbps
        # This is what admission control looks like -- a hard reject
        # with a clear explanation of why.

        input("\n[ Press ENTER ] ▶  Step 3: Provision h3 within capacity")
        print()

        # SOLUTION 3: 2 Mbps is exactly what's available
        sc.provision("standard", src="h3", dst="h2", chain=[], bw=2)
        sc.status()

        # Restart traffic
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
Both slices active.

    tail -F /tmp/iperf_h1.log    -> ~8 Mbps (premium guaranteed)
    tail -F /tmp/iperf_h3.log    -> ~2 Mbps (standard guaranteed)

h3 is now protected -- it holds 2 Mbps even under contention.
Before the slice it was getting ~2 Mbps anyway as best-effort,
but that was coincidental. With the slice it is a contract.

Limitations of first-come-first-served admission control:
  - The link is now fully allocated: 8 + 2 = 10 Mbps
  - Any new slice request will be rejected regardless of priority
  - A high-priority emergency slice cannot preempt the standard slice
  - The controller has no concept of slice priority or time-of-day demand

This is why real network slicing systems need smarter policies.
See: Sulaiman et al., "Coordinated Slicing and Admission Control using
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
