#!/usr/bin/env python3
"""
Exercise 1 — Solution
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

    net = Mininet(
        topo=Lab4bTopo(),
        controller=lambda name: RemoteController(name, ip=ONOS_IP, port=ONOS_PORT),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=False,
        waitConnected=True,
    )
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
        sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2", "r1")

        net.pingAll()
        sc.verify_srv6("h1", "h2", "mb1", "mb2")

        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)

        sc._start_mb1_logger(mb1)
        sc._start_mb2_logger(mb2)

        input("[ Press ENTER ] ▶  Provision slice through mb2")

        # Solution: chain=["mb2"] steers traffic through mb2, not mb1
        sc.provision("premium", src="h1", dst="h2", chain=["mb2"], bw=6)
        sc.status()

        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        time.sleep(0.5)
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        print(f"""
Expected:
    iperf_h1.log  → ~6 Mbps (guaranteed by queue)
    iperf_h3.log  → ~4 Mbps (best-effort, remaining capacity)
    {MB1_LOG}  → SILENT (chain goes to mb2, not mb1)
    {MB2_LOG} → SHOWS TRAFFIC
        """)

        input("[ Press ENTER ] ▶  Teardown")

        h1.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h3.cmd("pkill -f 'iperf3 -c' 2>/dev/null; true")
        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(1)

        # Teardown using the slice name
        sc.teardown("premium")
        sc.status()

        CLI(net)

    finally:
        for name in ['h1', 'h2', 'h3', 'mb1', 'mb2']:
            h = net.get(name)
            h.cmd("pkill -f iperf3    2>/dev/null; true")
            h.cmd("pkill -f mb_logger 2>/dev/null; true")
        net.stop()


if __name__ == "__main__":
    main()
