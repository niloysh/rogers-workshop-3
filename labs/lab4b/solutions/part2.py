#!/usr/bin/env python3
"""
Exercise 2 — Solution
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
        s1  = net.get('s1')
        s2  = net.get('s2')

        sc = SliceController(net, ingress=s1, peer=s2, link_bw=BOTTLENECK_BW)
        sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2", "r1")

        net.pingAll()
        sc.verify_srv6("h1", "h2", "mb1")

        h2.cmd("pkill -f iperf3 2>/dev/null; true")
        time.sleep(0.3)
        h2.cmd(f"iperf3 -s -p {H1_PORT} -D --forceflush")
        h2.cmd(f"iperf3 -s -p {H3_PORT} -D --forceflush")
        time.sleep(0.5)
        sc._start_mb1_logger(mb1)

        input("\n[ Press ENTER ] ▶  Step 1: Provision premium slice")

        # Step 1: premium slice for h1, 8 Mbps
        sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
        sc.status()

        h1.cmd(f"iperf3 -c {h2.IP()} -p {H1_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h1.log &")
        h3.cmd(f"iperf3 -c {h2.IP()} -p {H3_PORT} -b 8M -t 600 "
               f"--forceflush -i 1 2>&1 | tee /tmp/iperf_h3.log &")

        input("\n[ Press ENTER ] ▶  Step 2: Try to over-provision h3")

        # Step 2: request more than available (8 Mbps reserved, 10 Mbps total → 2 Mbps left)
        try:
            sc.provision("standard", src="h3", dst="h2", chain=[], bw=5)
        except AdmissionError as e:
            print(e)

        input("\n[ Press ENTER ] ▶  Step 3: Provision h3 within capacity")

        # Step 3: 2 Mbps is the maximum available
        sc.provision("standard", src="h3", dst="h2", chain=[], bw=2)
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

        print("""
Expected with both slices active:
    iperf_h1.log  → ~8 Mbps  (premium, guaranteed)
    iperf_h3.log  → ~2 Mbps  (standard, guaranteed minimum)
        """)

        input("[ Press ENTER ] ▶  Open Mininet CLI")
        CLI(net)

    finally:
        for name in ['h1', 'h2', 'h3', 'mb1', 'mb2']:
            h = net.get(name)
            h.cmd("pkill -f iperf3    2>/dev/null; true")
            h.cmd("pkill -f mb_logger 2>/dev/null; true")
        net.stop()


if __name__ == "__main__":
    main()
