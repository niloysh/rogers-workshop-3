#!/usr/bin/env python3
"""
Exercise 1 - Solution
=====================
Topology:

    h1 --.
    h3 --+-- s1 --[10Mbps]-- s2 -- s3 -- h2
                              |     |
                             mb1   mb2

Provision a single transport slice:
    src=h1, dst=h2, chain=[mb2], bw=6 Mbps

Expected outcome:
    mb1 logger -> SILENT  (not in chain)
    mb2 logger -> TRAFFIC (in chain)
    h1         -> ~6 Mbps guaranteed
    h3         -> ~4 Mbps best-effort remainder

Usage:
    sudo python3 exercise1_solution.py
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
    # Bottleneck
    net.addLink(s1, s2, cls=TCLink, bw=10,  delay="5ms")
    # s2 to s3
    net.addLink(s2, s3, cls=TCLink, bw=100, delay="5ms")

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

        # Start both loggers before provisioning so participants
        # can observe which one lights up when the slice is provisioned
        sc._start_mb1_logger(mb1)
        sc._start_mb2_logger(mb2)

        print(f"""
Both loggers running. Before provisioning both should be silent.

    tail -F {MB1_LOG}    -> SILENT
    tail -F {MB2_LOG}  -> SILENT
        """)

        input("[ Press ENTER ] ▶  Provision the slice")
        print()

        sc.provision("premium", src="h1", dst="h2", chain=["mb2"], bw=6)
        sc.status()

        # Start traffic
        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        time.sleep(0.5)
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print(f"""
Slice active. Watch:

    tail -F /tmp/iperf_h1.log    -> ~6 Mbps  (guaranteed)
    tail -F /tmp/iperf_h3.log    -> ~4 Mbps  (best-effort remainder)
    tail -F {MB1_LOG}    -> SILENT  (mb1 not in chain)
    tail -F {MB2_LOG}  -> TRAFFIC (mb2 is in chain)

Notice:
  mb1 stays silent even though it is connected to the topology.
  SRv6 only visits the waypoints explicitly listed in chain=[].
  The slice contract is exact -- nothing more, nothing less.
        """)

        input("[ Press ENTER ] ▶  Teardown slice")
        print()

        h1.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h3.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(1)

        sc.teardown("premium")
        sc.status()

        # Restart servers and clients to show best-effort behaviour
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
Slice torn down. Traffic restarted as best-effort.

    tail -F /tmp/iperf_h1.log    -> drops to ~5 Mbps (fair share)
    tail -F /tmp/iperf_h3.log    -> ~5 Mbps (fair share)
    tail -F {MB1_LOG}    -> SILENT
    tail -F {MB2_LOG}  -> SILENT

Both loggers quiet -- traffic no longer visiting mb2.
Without the slice: no bandwidth protection, no path enforcement.
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