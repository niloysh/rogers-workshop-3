#!/usr/bin/env python3
"""
Shared runners for learner-facing Lab 4 exercises.
"""

import importlib.util
import time
from pathlib import Path
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.cli import CLI

from .topology import Lab4Topo, ONOS_IP, ONOS_PORT, BOTTLENECK_BW, print_topology_info
from .controller import SliceController, AdmissionError
from .demo_common import H1_PORT, H3_PORT, start_servers, start_client, stop_all, cleanup_demo_hosts
from .slice_request import (
    apply_slice_request,
    format_slice_realization,
    format_slice_request,
    realize_slice_request,
    teardown_slice_request,
)

LAB4_DIR = Path(__file__).resolve().parents[1]


def _build_network():
    print(f"[Controller] Connecting to ONOS at {ONOS_IP}:{ONOS_PORT}")
    net = Mininet(
        topo=Lab4Topo(),
        controller=lambda name: RemoteController(name, ip=ONOS_IP, port=ONOS_PORT),
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        waitConnected=True,
    )
    info("*** Starting network\n")
    net.start()
    return net


def _prepare_lab(net, sc, verify_waypoints):
    info("*** Testing IPv4 connectivity (populates ONOS MAC table)\n")
    net.pingAll()
    sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2", "r1")
    sc.warmup_ndp("h1", "h2", "h3", "mb1", "mb2")
    sc.verify_srv6("h1", "h2", *verify_waypoints)


def _start_waypoint_loggers(sc, waypoints):
    for waypoint in dict.fromkeys(waypoints):
        if waypoint in ("r1", "r1b"):
            continue
        sc._start_logger(waypoint)


def _print_request_block(slice_request):
    print(format_slice_request(slice_request))
    print(format_slice_realization(slice_request))
    print()


def _display_path(path):
    path = Path(path).resolve()
    try:
        return str(path.relative_to(LAB4_DIR))
    except ValueError:
        return str(path)


def _load_slice_request(request_path):
    request_path = Path(request_path).resolve()
    module_name = f"lab4_request_{request_path.stem}_{request_path.stat().st_mtime_ns}"
    spec = importlib.util.spec_from_file_location(module_name, request_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Could not load request file: {request_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "SLICE_REQUEST"):
        raise ValueError("Request file must define SLICE_REQUEST")

    slice_request = module.SLICE_REQUEST
    if not isinstance(slice_request, dict):
        raise ValueError("SLICE_REQUEST must be a dictionary")
    return slice_request


def _prompt_for_request(request_path, *, prompt_text):
    display_path = _display_path(request_path)
    print(prompt_text)
    print()
    print("Edit this file now:")
    print(f"  {display_path}")
    print()
    print("Change only the SLICE_REQUEST block, then come back here and press ENTER.\n")

    while True:
        input("[ Press ENTER ] ▶  Load the request from disk")
        print()
        try:
            slice_request = _load_slice_request(request_path)
            realize_slice_request(slice_request)
        except Exception as err:
            print(f"[request error] {err}")
            print(f"Edit {display_path} and press ENTER to try again.\n")
            continue

        print(f"[loaded] {display_path}\n")
        _print_request_block(slice_request)
        return slice_request


def run_single_slice_exercise(
    *,
    title,
    intro,
    request_path,
    logger_waypoints,
    tail_paths,
    after_apply_text,
    after_teardown_text,
    verify_waypoints=("mb1",),
    use_contention=True,
):
    """Run a learner-facing exercise centered on one slice request."""
    setLogLevel("info")

    net = _build_network()
    try:
        h1 = net.get("h1")
        h2 = net.get("h2")
        h3 = net.get("h3")
        s1 = net.get("s1")
        s2 = net.get("s2")

        sc = SliceController(net, ingress=s1, peer=s2, link_bw=BOTTLENECK_BW)

        print_topology_info(include_details=True)
        print(f"  {title}")
        slice_request = _prompt_for_request(
            request_path,
            prompt_text=intro,
        )

        _prepare_lab(net, sc, verify_waypoints)
        start_servers(h2)
        _start_waypoint_loggers(sc, logger_waypoints)

        print("Logs to watch:")
        for path in tail_paths:
            print(f"  tail -F {path}")
        print()

        input("[ Press ENTER ] ▶  Apply the slice request")
        print()
        apply_slice_request(sc, slice_request)
        sc.status()

        start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
        if use_contention:
            time.sleep(0.5)
            start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")

        print(after_apply_text)

        input("[ Press ENTER ] ▶  Teardown the slice")
        print()
        stop_all(h1, h3, h2)
        teardown_slice_request(sc, slice_request)
        sc.status()

        start_servers(h2)
        start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
        if use_contention:
            time.sleep(0.5)
            start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")

        print(after_teardown_text)

        input("[ Press ENTER ] ▶  Open Mininet CLI (type 'exit' to finish)")
        CLI(net)

    finally:
        info("\n*** Cleaning up\n")
        cleanup_demo_hosts(net)
        net.stop()


def run_admission_control_exercise(
    *,
    title,
    intro,
    baseline_request,
    request_path,
    tail_paths,
    verify_waypoints=("mb1",),
):
    """Run the admission-control exercise with one fixed slice and one learner request."""
    setLogLevel("info")

    realize_slice_request(baseline_request)

    net = _build_network()
    try:
        h1 = net.get("h1")
        h2 = net.get("h2")
        h3 = net.get("h3")
        s1 = net.get("s1")
        s2 = net.get("s2")

        sc = SliceController(net, ingress=s1, peer=s2, link_bw=BOTTLENECK_BW)

        print_topology_info(include_details=True)
        print(f"  {title}")
        print(intro)
        print()
        print("The baseline request is fixed:")
        print()
        print("Baseline Slice:")
        print(format_slice_request(baseline_request, heading="Baseline Request"))
        print(format_slice_realization(baseline_request))
        print()
        slice_request = _prompt_for_request(
            request_path,
            prompt_text="Use the topology roles above to reason about your competing request.",
        )

        _prepare_lab(net, sc, verify_waypoints)
        start_servers(h2)
        _start_waypoint_loggers(sc, ["mb1"])

        print("Logs to watch:")
        for path in tail_paths:
            print(f"  tail -F {path}")
        print()

        input("[ Press ENTER ] ▶  Provision the baseline premium slice")
        print()
        apply_slice_request(sc, baseline_request)
        sc.status()
        start_client(h1, h2.IP(), mbps=8, port=H1_PORT, tag="h1")
        time.sleep(0.5)
        start_client(h3, h2.IP(), mbps=8, port=H3_PORT, tag="h3")
        print("""
Baseline slice active.

  h1 has an 8 Mbps guarantee on the direct path through mb1.
  h3 is still best-effort and competes for the remaining capacity.
""")

        input("[ Press ENTER ] ▶  Try to provision your competing slice request")
        print()

        try:
            apply_slice_request(sc, slice_request)
            print("[result] Your request was admitted.\n")
        except AdmissionError as err:
            print(err)
            print("\n[result] Request rejected. Adjust only SLICE_REQUEST and rerun the exercise.\n")

        sc.status()

        input("[ Press ENTER ] ▶  Open Mininet CLI (type 'exit' to finish)")
        CLI(net)

    finally:
        info("\n*** Cleaning up\n")
        cleanup_demo_hosts(net)
        net.stop()
