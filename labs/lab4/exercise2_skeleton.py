#!/usr/bin/env python3
"""
Exercise 2 — Extend the Chain to Include mb2
==============================================
The premium slice currently chains: h1 → mb1 → h2
Your task: extend it to:            h1 → mb1 → mb2 → h2

mb2 is a packet counter — it logs how many packets per second it sees.
When the extended chain is working you should see both mb1 and mb2 light up.

What you need to do:
    1. Add mb2 to the topology          (see build_topology — mb2 is already
                                         added for you, just needs linking)
    2. Configure SRv6 on mb2            (add "mb2" to configure_srv6 call)
    3. Update the slice chain           (add "mb2" to the chain list)
    4. Watch both loggers light up

    tail -F /tmp/mb1_bandwidth.log    → mb1 sees traffic
    tail -F /tmp/mb2_packets.log      → mb2 sees traffic   ← new

Think about:
    - The segment list will be: fc00::b1, fc00::b2, fc00::2
      Why must fc00::b1 (mb1) come before fc00::b2 (mb2)?
    - What would happen if mb2 didn't have a static neighbour entry for fc00::2?
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
    h1  = net.addHost("h1",  ip="10.0.0.1/24", mac="00:00:00:00:00:01")
    h2  = net.addHost("h2",  ip="10.0.0.2/24", mac="00:00:00:00:00:02")
    h3  = net.addHost("h3",  ip="10.0.0.3/24", mac="00:00:00:00:00:03")
    mb1 = net.addHost("mb1", ip="10.0.0.4/24", mac="00:00:00:00:00:04")
    mb2 = net.addHost("mb2", ip="10.0.0.5/24", mac="00:00:00:00:00:05")

    s1 = net.addSwitch("s1", cls=OVSKernelSwitch, failMode="standalone")
    s2 = net.addSwitch("s2", cls=OVSKernelSwitch, failMode="standalone")

    net.addLink(h1,  s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h3,  s1, cls=TCLink, bw=100, delay="1ms")
    net.addLink(h2,  s2, cls=TCLink, bw=100, delay="1ms")
    net.addLink(mb1, s2, cls=TCLink, bw=100, delay="1ms")

    # ── TODO 1 ────────────────────────────────────────────────────────────────
    # Connect mb2 to s2.
    # Hint: same pattern as mb1 above.
    # net.addLink(???)
    # ─────────────────────────────────────────────────────────────────────────

    net.addLink(s1, s2, cls=TCLink, bw=10, delay="5ms")
    return h1, h2, h3, mb1, mb2, s1, s2


def main():
    setLogLevel("info")
    net = Mininet(controller=None, switch=OVSKernelSwitch,
                  link=TCLink, autoSetMacs=False)
    h1, h2, h3, mb1, mb2, s1, s2 = build_topology(net)
    net.start()

    try:
        sc = SliceController(net, s1, s2, link_bw=10)

        # ── TODO 2 ────────────────────────────────────────────────────────────
        # Add "mb2" to the configure_srv6 call so it gets its SID and
        # static neighbour entries.
        # Hint: fc00::b2 is already in the SID table in slice_controller.py
        sc.configure_srv6("h1", "h2", "h3", "mb1")  # ← add "mb2" here
        # ─────────────────────────────────────────────────────────────────────

        net.pingAll()
        sc.verify_srv6("h1", "h2", "mb1")

        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)

        # ── TODO 3 ────────────────────────────────────────────────────────────
        # Extend the chain to include mb2.
        # Current:  chain=["mb1"]
        # Extended: chain=["mb1", "mb2"]
        sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
        #                                                   ^^^^ add "mb2"
        # ─────────────────────────────────────────────────────────────────────

        sc.status()

        sc._start_mb1_logger(mb1)
        sc._start_mb2_logger(mb2)

        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 120 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 120 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print(f"""
Open these in separate terminals:
    tail -F /tmp/iperf_h1.log     → ~8 Mbps
    tail -F {MB1_LOG} → mb1 should show traffic
    tail -F {MB2_LOG} → mb2 should show traffic  ← new
        """)

        input("[ Press ENTER ] ▶  Open Mininet CLI")
        CLI(net)

    finally:
        for h in [h1, h2, h3, mb1, mb2]:
            h.cmd("pkill -f iperf3    2>/dev/null; true")
            h.cmd("pkill -f mb_logger 2>/dev/null; true")
        net.stop()


if __name__ == "__main__":
    main()