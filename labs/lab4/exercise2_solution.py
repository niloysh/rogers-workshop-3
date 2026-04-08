#!/usr/bin/env python3
"""
Exercise 2 - Solution
=====================
Usage:
    sudo python3 exercise2_solution.py
"""

import time
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI

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


def measure_rtt(h1, dst_ip, count=5):
    result = h1.cmd(f"ping -c {count} -q {dst_ip} 2>&1 | tail -1")
    return result.strip()


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
        sc._start_mb2_logger(mb2)

        print("\nMeasuring baseline RTT (no slice)...")
        baseline = measure_rtt(h1, h2.IP())
        print(f"  Baseline: {baseline}\n")

        input("[ Press ENTER ] ▶  Step 1: Wrong chain order [mb2, mb1]")
        print()

        # SOLUTION 1: wrong order -- controller accepts, path backtracks
        # Path: h1->s1->s2->s3->mb2->s2->mb1->s2->s3->h2
        # s2 visited 3 times, s3 visited twice
        sc.provision("test", src="h1", dst="h2", chain=["mb2", "mb1"], bw=6)
        sc.status()

        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        time.sleep(0.5)
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        time.sleep(3)
        print("\nMeasuring RTT with wrong order [mb2, mb1]...")
        rtt_wrong = measure_rtt(h1, h2.IP())
        print(f"  RTT (wrong order): {rtt_wrong}")

        print(f"""
Path with chain=["mb2", "mb1"]:
  h1 -> s1 -> s2 -> s3 -> mb2 -> s2 -> mb1 -> s2 -> s3 -> h2
                                   ^--- backtrack! s2 visited 3x, s3 visited 2x

Both loggers show traffic -- the chain IS being enforced.
But the extra hops add latency.
        """)

        input("[ Press ENTER ] ▶  Step 2: Teardown and fix the chain order")
        print()

        h1.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h3.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(1)

        # SOLUTION 2: teardown wrong-order slice
        sc.teardown("test")

        # SOLUTION 3: correct order -- mb1 is on s2, mb2 is on s3
        # Efficient path: h1->s1->s2->mb1->s2->s3->mb2->s3->h2
        # Each switch visited at most twice
        sc.provision("test", src="h1", dst="h2", chain=["mb1", "mb2"], bw=6)
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

        time.sleep(3)
        print("\nMeasuring RTT with correct order [mb1, mb2]...")
        rtt_correct = measure_rtt(h1, h2.IP())
        print(f"  RTT (correct order): {rtt_correct}")

        print(f"""
RTT comparison:
  Baseline (no slice):     {baseline}
  Wrong order  [mb2,mb1]:  {rtt_wrong}
  Correct order [mb1,mb2]: {rtt_correct}

Path with chain=["mb1", "mb2"]:
  h1 -> s1 -> s2 -> mb1 -> s2 -> s3 -> mb2 -> s3 -> h2
  Each switch visited at most twice. No backtracking.

Key insight:
  The controller accepted both chain orders without complaint.
  It has no topology awareness -- it just maps names to SIDs.
  A smarter controller would know the physical location of each
  waypoint and warn or reject inefficient orderings.
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