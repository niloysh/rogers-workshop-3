#!/usr/bin/env python3
"""
Exercise 1 — Add a Standard Slice for h3
==========================================
The demo showed a single premium slice for h1.
Your task: add a second slice for h3 so both flows have explicit allocations.

Target state:
    premium:  h1 → mb1 → h2   8 Mbps   (already provisioned below)
    standard: h3 →       h2   4 Mbps   ← YOU provision this

Expected outcome:
    tail -F /tmp/iperf_h1.log  → ~8 Mbps  (premium slice protected)
    tail -F /tmp/iperf_h3.log  → ~4 Mbps  (standard slice protected)

Think about:
    - Total reserved = 8 + 4 = 12 Mbps on a 10 Mbps link.
      What do you expect to actually see? Why?
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
        sc.verify_srv6("h1", "h2", "mb1")

        # Start iperf3 servers
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)

        # Provision the premium slice (already done for you)
        sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)

        # ── TODO ──────────────────────────────────────────────────────────────
        # Provision a "standard" slice for h3.
        # It should go directly to h2 (no chain) with 4 Mbps guaranteed.
        #
        # sc.provision(???)
        #
        # Hint: look at the premium provision call above.
        #       chain=[] means no waypoints — direct path.
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

        # Start traffic
        sc._start_mb1_logger(mb1)
        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 120 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 120 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print(f"""
Open these in separate terminals:
    tail -F /tmp/iperf_h1.log     → should be ~8 Mbps
    tail -F /tmp/iperf_h3.log     → should be ~4 Mbps (once you add the slice)
    tail -F {MB1_LOG} → mb1 traffic logger
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