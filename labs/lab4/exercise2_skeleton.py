#!/usr/bin/env python3
"""
Exercise 2 - Service Chain Ordering
=====================================
Topology:

    h1 --.
    h3 --+-- s1 --[10Mbps]-- s2 -- s3 -- h2
                              |     |
                             mb1   mb2

Your task: provision a slice that visits BOTH mb1 and mb2.

The slice controller accepts any chain order you give it -- it has no
topology awareness. But the physical network does have an order, and
visiting waypoints in the wrong order forces the packet to backtrack
through the network.

Tasks:
  Step 1: Provision with chain=["mb2", "mb1"] (wrong order)
          - Both loggers will show traffic
          - Measure the round-trip time with ping
          - Think about why the RTT is what it is

  Step 2: Teardown and reprovision with chain=["mb1", "mb2"] (correct order)
          - Measure RTT again
          - Compare with Step 1

  Step 3: Explain the difference
          - Draw the actual packet path for each chain order
          - Which switches does the packet visit and how many times?
          - Why does the controller not catch this?

Think about:
  - mb1 is on s2, mb2 is on s3. What is the natural forwarding direction?
  - What does "backtracking" mean in terms of switches visited?
  - The controller builds segment lists from whatever order you pass in.
    What information would it need to detect an inefficient chain order?

Usage:
    sudo python3 exercise2_skeleton.py
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


def measure_rtt(h1, dst_ip, count=5):
    """Ping dst_ip from h1 and return the avg RTT string."""
    result = h1.cmd(f"ping -c {count} -q {dst_ip} 2>&1 | tail -1")
    return result.strip()


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

        # Start both loggers
        sc._start_mb1_logger(mb1)
        sc._start_mb2_logger(mb2)

        # Measure baseline RTT before any slice
        print("\nMeasuring baseline RTT (no slice, direct path)...")
        baseline = measure_rtt(h1, h2.IP())
        print(f"  Baseline RTT: {baseline}\n")

        input("[ Press ENTER ] ▶  Step 1: Provision with WRONG chain order")
        print()

        # ── TODO 1 ────────────────────────────────────────────────────────────
        # Provision a slice with chain=["mb2", "mb1"] -- mb2 first, then mb1.
        # Use 6 Mbps bandwidth.
        #
        # Hint: the controller will accept this without complaint.
        #       It has no idea whether this order makes topological sense.
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

        time.sleep(3)
        print("\nMeasuring RTT with wrong chain order [mb2, mb1]...")
        rtt_wrong = measure_rtt(h1, h2.IP())
        print(f"  RTT (wrong order): {rtt_wrong}")

        print(f"""
Both loggers should show traffic -- the packet visits both mb1 and mb2.
But look at the RTT compared to baseline. Is it what you expected?

    tail -F {MB1_LOG}    -> traffic
    tail -F {MB2_LOG}  -> traffic
    tail -F /tmp/iperf_h1.log    -> ?

Think about the actual path the packet takes:
  chain=["mb2", "mb1"] means segments: fc00::b2, fc00::b1, fc00::2
  Where is mb2? Where is mb1? Draw the path.
        """)

        input("[ Press ENTER ] ▶  Step 2: Teardown and reprovision with CORRECT order")
        print()

        # Stop traffic and teardown
        h1.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h3.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(1)

        # ── TODO 2 ────────────────────────────────────────────────────────────
        # Teardown the wrong-order slice.
        #
        # sc.teardown(???)
        # ─────────────────────────────────────────────────────────────────────

        # ── TODO 3 ────────────────────────────────────────────────────────────
        # Reprovision with the correct chain order.
        # Same bandwidth, same name, but fix the chain.
        #
        # Hint: mb1 is attached to s2, mb2 is attached to s3.
        #       Traffic naturally flows s1->s2->s3.
        #       Which waypoint should come first?
        #
        # sc.provision(???)
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

        # Restart traffic
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
        print("\nMeasuring RTT with correct chain order [mb1, mb2]...")
        rtt_correct = measure_rtt(h1, h2.IP())
        print(f"  RTT (correct order): {rtt_correct}")

        print(f"""
Compare the RTTs:
  Baseline (no slice):   {baseline}
  Wrong order [mb2,mb1]: {rtt_wrong}
  Correct order [mb1,mb2]: {rtt_correct}

    tail -F /tmp/iperf_h1.log    -> ?
    tail -F {MB1_LOG}    -> traffic
    tail -F {MB2_LOG}  -> traffic

Reflection:
  - What is the actual packet path for each chain order?
    Wrong:   h1 -> s1 -> s2 -> s3 -> mb2 -> s2 -> mb1 -> s2 -> s3 -> h2
    Correct: h1 -> s1 -> s2 -> mb1 -> s2 -> s3 -> mb2 -> s3 -> h2
  - How many times does each switch appear in each path?
  - The controller accepted both -- what would it need to know to
    detect and reject or warn about an inefficient chain order?
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