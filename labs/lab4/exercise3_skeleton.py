#!/usr/bin/env python3
"""
Exercise 3 — Admission Control
================================
The slice controller enforces admission control: it will reject a slice
if the requested bandwidth would exceed the available link capacity.

In this exercise you will:
    1. Deliberately trigger an AdmissionError
    2. Understand why it was rejected
    3. Fix it — either by reducing the requested bandwidth,
       or by tearing down an existing slice first

Starting state:
    premium slice: h1 → mb1 → h2   8 Mbps   (provisioned below)
    Link capacity: 10 Mbps
    Available:     2 Mbps

Your task:
    Try to provision a "greedy" slice for h3 at 9 Mbps.
    The controller will reject it with an AdmissionError.
    Read the error message, then fix it.

There are two valid fixes — try both and think about the tradeoff:
    Fix A: reduce the "greedy" slice bandwidth to fit in available capacity
    Fix B: teardown the premium slice first, then provision greedy at full rate

Which fix is more realistic in a production network? Why?
"""

import time
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI
from slice_controller import SliceController, AdmissionError, MB1_LOG

H1_PORT = 5201
H3_PORT = 5202


def build_topology(net):
    h1  = net.addHost("h1",  ip="10.0.0.1/24", mac="00:00:00:00:00:01")
    h2  = net.addHost("h2",  ip="10.0.0.2/24", mac="00:00:00:00:00:02")
    h3  = net.addHost("h3",  ip="10.0.0.3/24", mac="00:00:00:00:00:03")
    mb1 = net.addHost("mb1", ip="10.0.0.4/24", mac="00:00:00:00:00:04")
    s1 = net.addSwitch("s1", cls=OVSKernelSwitch, failMode="standalone")
    s2 = net.addSwitch("s2", cls=OVSKernelSwitch, failMode="standalone")
    net.addLink(h1,  s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h3,  s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h2,  s2, cls=TCLink, bw=100, delay="1ms")
    net.addLink(mb1, s2, cls=TCLink, bw=100, delay="1ms")
    net.addLink(s1,  s2, cls=TCLink, bw=10,  delay="5ms")
    return h1, h2, h3, mb1, s1, s2


def main():
    setLogLevel("info")
    net = Mininet(controller=None, switch=OVSKernelSwitch,
                  link=TCLink, autoSetMacs=False)
    h1, h2, h3, mb1, s1, s2 = build_topology(net)
    net.start()

    try:
        sc = SliceController(net, s1, s2, link_bw=10)
        sc.configure_srv6("h1", "h2", "h3", "mb1")
        net.pingAll()

        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)

        # Premium slice already provisioned
        sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
        sc.status()

        # ── TODO ──────────────────────────────────────────────────────────────
        # Step 1: Try to provision a greedy slice for h3 at 9 Mbps.
        #         Wrap it in a try/except AdmissionError and print the error.
        #
        # try:
        #     sc.provision("greedy", src="h3", dst="h2", chain=[], bw=???)
        # except AdmissionError as e:
        #     print(e)
        #
        # Step 2: Fix it. Choose one:
        #   Fix A — provision at a bandwidth that fits:
        #     sc.provision("greedy", src="h3", dst="h2", chain=[], bw=???)
        #
        #   Fix B — teardown premium first, then provision greedy:
        #     sc.teardown(???)
        #     sc.provision("greedy", src="h3", dst="h2", chain=[], bw=???)
        #
        # Hint: sc.status() tells you how much bandwidth is available.
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

        sc._start_mb1_logger(mb1)
        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 120 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 9M -t 120 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print("""
Open these in separate terminals:
    tail -F /tmp/iperf_h1.log
    tail -F /tmp/iperf_h3.log
        """)

        input("[ Press ENTER ] ▶  Open Mininet CLI")
        CLI(net)

    finally:
        for h in [h1, h2, h3, mb1]:
            h.cmd("pkill -f iperf3    2>/dev/null; true")
            h.cmd("pkill -f mb_logger 2>/dev/null; true")
        net.stop()


if __name__ == "__main__":
    main()