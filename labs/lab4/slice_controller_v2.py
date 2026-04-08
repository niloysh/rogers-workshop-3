#!/usr/bin/env python3
"""
slice_controller_v2.py
──────────────────────
Topology-aware transport slice controller for the revised Lab 4.

Workshop simplification:
  - one active slice per ordered endpoint pair (src, dst)
  - slice traffic is identified by endpoint pair
  - queue classification matches the outer SRv6 IPv6 traffic

This keeps the lab focused on combining:
  - topology discovery from ONOS
  - path selection by intent
  - SRv6 service-chain realization
  - queue-based bandwidth treatment
"""

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path

import requests


ONOS_BASE = "http://localhost:8181/onos/v1"
ONOS_AUTH = ("onos", "rocks")
APP_ID = "org.onosproject.cli"
STATE_FILE = "/tmp/slice_controller_state.json"

LINK_CAPACITY_MBPS = 100
HEADROOM_MBPS = 10

HOST_IPS = {
    "h1": "10.0.0.1",
    "h2": "10.0.0.2",
    "h3": "10.0.0.3",
    "mb1": "10.0.0.11",
    "mb2": "10.0.0.12",
    "mb3": "10.0.0.13",
}

ENDPOINT_SIDS = {
    "h1": "fc00::1",
    "h2": "fc00::2",
    "h3": "fc00::3",
    "mb1": "fc00::b1",
    "mb2": "fc00::b2",
    "mb3": "fc00::b3",
}

DEVICE_SIDS = {
    "of:0000000000000001": "fc00::101",
    "of:0000000000000002": "fc00::102",
    "of:0000000000000003": "fc00::103",
}

SWITCH_NAMES = {
    "of:0000000000000001": "r1",
    "of:0000000000000002": "r2",
    "of:0000000000000003": "r3",
}

MB_DESCRIPTIONS = {
    "mb1": "throughput monitor",
    "mb2": "firewall policy",
    "mb3": "flow logger",
}

HOST_CHOICES = ["h1", "h2", "h3"]


def load_state():
    try:
        return json.loads(Path(STATE_FILE).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"slices": {}}


def save_state(state):
    Path(STATE_FILE).write_text(json.dumps(state, indent=2))


def onos_get(endpoint):
    response = requests.get(f"{ONOS_BASE}/{endpoint}", auth=ONOS_AUTH, timeout=5)
    response.raise_for_status()
    return response.json()


def onos_post(endpoint, data):
    return requests.post(
        f"{ONOS_BASE}/{endpoint}",
        auth=ONOS_AUTH,
        json=data,
        timeout=5,
    )


def onos_delete(endpoint):
    return requests.delete(
        f"{ONOS_BASE}/{endpoint}",
        auth=ONOS_AUTH,
        timeout=5,
    )


def mn_run(host, cmd):
    full = (
        "sudo mnexec -a "
        f"$(pgrep -f 'mininet:{host}' | head -1) sh -lc {json.dumps(cmd)}"
    )
    result = subprocess.run(full, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_host_info(ip):
    hosts = onos_get("hosts").get("hosts", [])
    for host in hosts:
        if ip in host.get("ipAddresses", []):
            locations = host.get("locations") or []
            if not locations:
                continue
            return {
                "host_id": host["id"],
                "device": locations[0]["elementId"],
                "port": str(locations[0]["port"]),
            }
    return None


def build_topology_from_onos():
    graph = defaultdict(set)
    link_ports = {}

    for link in onos_get("links").get("links", []):
        src = link["src"]["device"]
        dst = link["dst"]["device"]
        src_port = str(link["src"]["port"])

        graph[src].add(dst)
        graph[dst].add(src)
        link_ports[(src, dst)] = src_port

    return {node: sorted(neighbors) for node, neighbors in graph.items()}, link_ports


def build_attachment_map(endpoint_names):
    attachments = {}
    for name in endpoint_names:
        info = get_host_info(HOST_IPS[name])
        if info:
            attachments[name] = info
    return attachments


def shortest_path(graph, src, dst):
    if src == dst:
        return [src]

    queue = deque([(src, [src])])
    visited = {src}

    while queue:
        node, path = queue.popleft()
        for neighbor in graph.get(node, []):
            if neighbor in visited:
                continue
            if neighbor == dst:
                return path + [neighbor]
            visited.add(neighbor)
            queue.append((neighbor, path + [neighbor]))

    return None


def all_simple_paths(graph, src, dst, max_depth=8):
    results = []

    def dfs(node, target, visited, path):
        if len(path) > max_depth:
            return
        if node == target:
            results.append(path[:])
            return
        for neighbor in graph.get(node, []):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            path.append(neighbor)
            dfs(neighbor, target, visited, path)
            path.pop()
            visited.remove(neighbor)

    dfs(src, dst, {src}, [src])
    results.sort(key=lambda item: (len(item), item))
    return results


def select_path(graph, src_dev, dst_dev, intent):
    if src_dev == dst_dev:
        return [src_dev]

    shortest = shortest_path(graph, src_dev, dst_dev)
    if not shortest:
        return None

    if intent == "low-latency":
        return shortest

    for candidate in all_simple_paths(graph, src_dev, dst_dev):
        if len(candidate) > len(shortest):
            return candidate
    return shortest


def compute_realized_transport(service_nodes, graph, attachments, intent):
    realized = []
    for src_name, dst_name in zip(service_nodes[:-1], service_nodes[1:]):
        if src_name not in attachments:
            raise RuntimeError(f"Endpoint '{src_name}' is not discovered in ONOS.")
        if dst_name not in attachments:
            raise RuntimeError(f"Endpoint '{dst_name}' is not discovered in ONOS.")

        src_dev = attachments[src_name]["device"]
        dst_dev = attachments[dst_name]["device"]
        path = select_path(graph, src_dev, dst_dev, intent)
        if not path:
            raise RuntimeError(f"No path found between {src_name} and {dst_name}.")

        realized.append(
            {
                "from": src_name,
                "to": dst_name,
                "src_dev": src_dev,
                "dst_dev": dst_dev,
                "path": path,
            }
        )

    return realized


def build_srv6_segments(service_nodes, realized_hops):
    segments = []

    for hop in realized_hops:
        for device in hop["path"][1:]:
            sid = DEVICE_SIDS.get(device)
            if not sid:
                raise RuntimeError(f"No transport SID configured for device '{device}'.")
            segments.append(sid)

        destination = hop["to"]
        if destination.startswith("mb"):
            endpoint_sid = ENDPOINT_SIDS.get(destination)
            if not endpoint_sid:
                raise RuntimeError(f"No endpoint SID configured for '{destination}'.")
            segments.append(endpoint_sid)

    final_dst = service_nodes[-1]
    segments.append(ENDPOINT_SIDS[final_dst])
    return segments


def allocate_queue_id(state):
    used = {int(item.get("queue_id", 0)) for item in state.get("slices", {}).values()}
    queue_id = 1
    while queue_id in used:
        queue_id += 1
    return queue_id


def find_interface_name(bridge, ofport):
    result = subprocess.run(
        ["sudo", "ovs-ofctl", "-O", "OpenFlow13", "show", bridge],
        capture_output=True,
        text=True,
        check=False,
    )
    pattern = re.compile(r"^\s*(\d+)\(([^)]+)\):")
    for line in result.stdout.splitlines():
        match = pattern.match(line)
        if match and match.group(1) == str(ofport):
            return match.group(2)
    return None


def ensure_qos_on_port(interface_name):
    current = subprocess.run(
        ["sudo", "ovs-vsctl", "get", "port", interface_name, "qos"],
        capture_output=True,
        text=True,
        check=False,
    )
    if current.stdout.strip() not in ("[]", ""):
        return

    subprocess.run(
        [
            "sudo",
            "ovs-vsctl",
            "set",
            "port",
            interface_name,
            "qos=@newqos",
            "--",
            "--id=@newqos",
            "create",
            "qos",
            "type=linux-htb",
            "other-config:max-rate=100000000",
            "queues:0=@q0",
            "--",
            "--id=@q0",
            "create",
            "queue",
            "other-config:min-rate=0",
            "other-config:max-rate=100000000",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def install_ovs_queue(device_id, ofport, queue_id, bandwidth_mbps):
    bridge = SWITCH_NAMES[device_id]
    interface_name = find_interface_name(bridge, ofport)
    if not interface_name:
        raise RuntimeError(f"Could not map ofport {ofport} on {bridge} to an interface.")

    ensure_qos_on_port(interface_name)
    qos_result = subprocess.run(
        ["sudo", "ovs-vsctl", "get", "port", interface_name, "qos"],
        capture_output=True,
        text=True,
        check=False,
    )
    qos_uuid = qos_result.stdout.strip()
    bw_bps = int(bandwidth_mbps * 1_000_000)

    result = subprocess.run(
        [
            "sudo",
            "ovs-vsctl",
            "--",
            "--id=@q",
            "create",
            "queue",
            f"other-config:min-rate={bw_bps}",
            f"other-config:max-rate={bw_bps}",
            "--",
            "set",
            "qos",
            qos_uuid,
            f"queues:{queue_id}=@q",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "OVS queue creation failed")

    print(
        f"  [OVS] Queue {queue_id} on {bridge} port {ofport}: "
        f"{bandwidth_mbps} Mbps reserved"
    )
    return bridge, interface_name


def remove_ovs_queue(interface_name, queue_id):
    result = subprocess.run(
        ["sudo", "ovs-vsctl", "get", "port", interface_name, "qos"],
        capture_output=True,
        text=True,
        check=False,
    )
    qos_uuid = result.stdout.strip()
    if qos_uuid and qos_uuid != "[]":
        subprocess.run(
            ["sudo", "ovs-vsctl", "remove", "qos", qos_uuid, "queues", str(queue_id)],
            capture_output=True,
            text=True,
            check=False,
        )
        print(f"  [OVS] Queue {queue_id} removed from {interface_name}")


def build_ipv6_selector(src_host, first_segment):
    return {
        "criteria": [
            {"type": "ETH_TYPE", "ethType": "0x86DD"},
            {"type": "IPV6_SRC", "ip": f"{ENDPOINT_SIDS[src_host]}/128"},
            {"type": "IPV6_DST", "ip": f"{first_segment}/128"},
        ]
    }


def install_queue_flow_rule(src_host, device_id, first_segment, output_port, queue_id):
    rule = {
        "priority": 50000,
        "timeout": 0,
        "isPermanent": True,
        "appId": APP_ID,
        "treatment": {
            "instructions": [
                {"type": "QUEUE", "queueId": queue_id},
                {"type": "OUTPUT", "port": str(output_port)},
            ]
        },
        "selector": build_ipv6_selector(src_host, first_segment),
    }

    response = onos_post(f"flows/{device_id}", rule)
    if response.status_code not in (200, 201):
        raise RuntimeError(f"Flow rule returned HTTP {response.status_code}")

    print(f"  [ONOS] Queue classifier installed on {device_id} -> port {output_port}")


def remove_slice_flows(device_id, src_host, first_segment):
    selector = build_ipv6_selector(src_host, first_segment)["criteria"]
    expected = {(item["type"], item["ip"]) for item in selector if "ip" in item}

    flows = onos_get(f"flows/{device_id}").get("flows", [])
    for flow in flows:
        if flow.get("appId") != APP_ID:
            continue
        criteria = flow.get("selector", {}).get("criteria", [])
        actual = {(item.get("type"), item.get("ip")) for item in criteria if item.get("ip")}
        if expected.issubset(actual):
            onos_delete(f"flows/{device_id}/{flow['id']}")
            print(f"  [ONOS] Removed flow {flow['id']} from {device_id}")


def install_srv6_route(src_host, dst_ip, segments):
    command = (
        f"ip route replace {dst_ip} encap seg6 mode encap "
        f"segs {','.join(segments)} dev {src_host}-eth0"
    )
    rc, _, err = mn_run(src_host, command)
    if rc != 0:
        raise RuntimeError(err or f"Could not install SRv6 route on {src_host}")
    print(f"  [SRv6] Route installed on {src_host}")


def remove_srv6_route(src_host, dst_ip):
    rc, _, _ = mn_run(src_host, f"ip route del {dst_ip}")
    if rc == 0:
        print(f"  [SRv6] Route removed from {src_host}")


def install_source_host_block(src_host, slice_name, dst_ip, blocked_ports):
    if not blocked_ports:
        return

    chain = f"SLICE_{slice_name.upper()}"
    mn_run(src_host, f"iptables -N {chain} 2>/dev/null || true")
    mn_run(src_host, f"iptables -F {chain}")
    for port in blocked_ports:
        mn_run(
            src_host,
            f"iptables -A {chain} -p tcp -d {dst_ip} --dport {port} -j REJECT",
        )
    mn_run(src_host, f"iptables -D OUTPUT -j {chain} 2>/dev/null || true")
    mn_run(src_host, f"iptables -I OUTPUT 1 -j {chain}")
    print(f"  [edge] Source-host block installed on {src_host}: ports {blocked_ports}")


def remove_source_host_block(src_host, slice_name):
    chain = f"SLICE_{slice_name.upper()}"
    mn_run(src_host, f"iptables -D OUTPUT -j {chain} 2>/dev/null || true")
    mn_run(src_host, f"iptables -F {chain} 2>/dev/null || true")
    mn_run(src_host, f"iptables -X {chain} 2>/dev/null || true")


def configure_middlebox(mb, slice_name, src_ip, bandwidth, blocked_ports):
    if mb == "mb1":
        config = {"slice": slice_name, "src_ip": src_ip, "sla_mbps": bandwidth}
        Path("/tmp/mb_monitor_config.json").write_text(json.dumps(config))
        print(f"  [mb1] Monitor configured: SLA={bandwidth} Mbps")
    elif mb == "mb2":
        config = {"blocked_ports": blocked_ports or []}
        Path("/tmp/mb_firewall_config.json").write_text(json.dumps(config))
        print(f"  [mb2] Firewall policy updated: blocked ports {blocked_ports or []}")
    elif mb == "mb3":
        config = {"slice": slice_name, "src_ip": src_ip}
        Path("/tmp/mb_logger_config.json").write_text(json.dumps(config))
        print("  [mb3] Logger configured")


def pretty_print_realized(realized_hops):
    print("\n  Realized transport per service hop:")
    for hop in realized_hops:
        print(f"    {hop['from']} -> {hop['to']}: {' -> '.join(hop['path'])}")


def enforce_unique_endpoint_pair(state, src, dst):
    for slice_name, slice_data in state.get("slices", {}).items():
        if slice_data["src"] == src and slice_data["dst"] == dst:
            raise RuntimeError(
                f"Slice '{slice_name}' already uses endpoint pair {src} -> {dst}. "
                "Workshop simplification: only one active slice per ordered endpoint pair."
            )


def choose_ingress_output(realized_hops, attachments, link_ports):
    first_hop = realized_hops[0]
    source_device = first_hop["src_dev"]

    if len(first_hop["path"]) > 1:
        next_device = first_hop["path"][1]
        output_port = link_ports.get((source_device, next_device))
        if not output_port:
            raise RuntimeError(
                f"No ONOS link-port mapping for {source_device} -> {next_device}."
            )
        return source_device, output_port

    destination = first_hop["to"]
    return source_device, attachments[destination]["port"]


def cmd_provision(args):
    if args.src == args.dst:
        print("[error] Source and destination must be different.")
        sys.exit(1)

    state = load_state()
    if args.name in state["slices"]:
        print(f"[error] Slice '{args.name}' already exists.")
        sys.exit(1)

    try:
        enforce_unique_endpoint_pair(state, args.src, args.dst)
    except RuntimeError as exc:
        print(f"[error] {exc}")
        sys.exit(1)

    total_reserved = sum(item["bandwidth"] for item in state["slices"].values())
    available = LINK_CAPACITY_MBPS - HEADROOM_MBPS - total_reserved
    if args.bandwidth > available:
        print("[error] Insufficient bandwidth.")
        print(f"  Requested: {args.bandwidth} Mbps")
        print(f"  Available: {available} Mbps")
        print(f"  Reserved:  {total_reserved} Mbps")
        sys.exit(1)

    src_ip = HOST_IPS[args.src]
    dst_ip = HOST_IPS[args.dst]
    service_nodes = [args.src] + args.chain + [args.dst]

    print(f"\n[provision] Provisioning slice '{args.name}'...")
    print(f"  src:       {args.src} ({src_ip})")
    print(f"  dst:       {args.dst} ({dst_ip})")
    print(f"  chain:     {' -> '.join(args.chain) if args.chain else 'direct'}")
    print(f"  intent:    {args.intent}")
    print(f"  bandwidth: {args.bandwidth} Mbps")

    try:
        graph, link_ports = build_topology_from_onos()
        attachments = build_attachment_map(service_nodes)
        realized = compute_realized_transport(service_nodes, graph, attachments, args.intent)
        segments = build_srv6_segments(service_nodes, realized)
        ingress_device, output_port = choose_ingress_output(realized, attachments, link_ports)
    except Exception as exc:
        print(f"[error] Failed to compute slice realization: {exc}")
        sys.exit(1)

    pretty_print_realized(realized)
    print("\n  SRv6 segment list:")
    print(f"    {' -> '.join(segments)}")

    queue_id = allocate_queue_id(state)
    try:
        bridge, interface_name = install_ovs_queue(
            ingress_device,
            output_port,
            queue_id,
            args.bandwidth,
        )
        install_queue_flow_rule(args.src, ingress_device, segments[0], output_port, queue_id)
        install_srv6_route(args.src, dst_ip, segments)
        install_source_host_block(args.src, args.name, dst_ip, args.blocked_ports or [])
        for middlebox in args.chain:
            configure_middlebox(
                middlebox,
                args.name,
                src_ip,
                args.bandwidth,
                args.blocked_ports or [],
            )
    except Exception as exc:
        print(f"[error] Failed during provisioning: {exc}")
        remove_source_host_block(args.src, args.name)
        remove_srv6_route(args.src, dst_ip)
        try:
            remove_slice_flows(ingress_device, args.src, segments[0])
        except Exception:
            pass
        try:
            remove_ovs_queue(interface_name, queue_id)
        except Exception:
            pass
        sys.exit(1)

    state["slices"][args.name] = {
        "src": args.src,
        "dst": args.dst,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "chain": args.chain,
        "intent": args.intent,
        "bandwidth": args.bandwidth,
        "queue_id": queue_id,
        "ingress_device": ingress_device,
        "ingress_bridge": bridge,
        "ingress_interface": interface_name,
        "output_port": str(output_port),
        "segments": segments,
        "realized_hops": realized,
        "blocked_ports": args.blocked_ports or [],
    }
    save_state(state)
    print(f"\n[provision] Slice '{args.name}' provisioned successfully.\n")


def cmd_teardown(args):
    state = load_state()
    slice_data = state["slices"].get(args.name)
    if not slice_data:
        print(f"[error] Slice '{args.name}' not found.")
        sys.exit(1)

    print(f"\n[teardown] Removing slice '{args.name}'...")
    remove_source_host_block(slice_data["src"], args.name)
    remove_srv6_route(slice_data["src"], slice_data["dst_ip"])
    remove_slice_flows(
        slice_data["ingress_device"],
        slice_data["src"],
        slice_data["segments"][0],
    )
    remove_ovs_queue(slice_data["ingress_interface"], slice_data["queue_id"])

    del state["slices"][args.name]
    save_state(state)
    print(f"[teardown] Slice '{args.name}' removed.\n")


def cmd_status(_args):
    state = load_state()
    slices = state.get("slices", {})
    if not slices:
        print("\n[status] No active slices.\n")
        return

    total = 0
    print(f"\n[status] Active slices: {len(slices)}\n")
    for name, slice_data in slices.items():
        print(f"  {name}")
        print(f"    Pair:       {slice_data['src']} -> {slice_data['dst']}")
        print(f"    Intent:     {slice_data['intent']}")
        print(f"    Chain:      {' -> '.join(slice_data['chain']) if slice_data['chain'] else 'direct'}")
        print(
            f"    Bandwidth:  {slice_data['bandwidth']} Mbps "
            f"(queue {slice_data['queue_id']})"
        )
        print(f"    Segments:   {' -> '.join(slice_data['segments'])}")
        for hop in slice_data.get("realized_hops", []):
            print(f"    Path:       {hop['from']} -> {hop['to']} : {' -> '.join(hop['path'])}")
        if slice_data.get("blocked_ports"):
            print(f"    Blocked:    ports {slice_data['blocked_ports']}")
        print()
        total += slice_data["bandwidth"]

    print(f"  Total reserved: {total} Mbps")
    print(f"  Available:      {LINK_CAPACITY_MBPS - HEADROOM_MBPS - total} Mbps\n")


def cmd_list_mbs(_args):
    print("\n  Available middlebox service functions:\n")
    for middlebox, description in MB_DESCRIPTIONS.items():
        print(f"  {middlebox}  {ENDPOINT_SIDS[middlebox]}  {description}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Topology-aware transport slice controller (workshop simplification)"
    )
    subparsers = parser.add_subparsers(dest="command")

    provision = subparsers.add_parser("provision")
    provision.add_argument("--name", required=True)
    provision.add_argument("--src", required=True, choices=HOST_CHOICES)
    provision.add_argument("--dst", required=True, choices=HOST_CHOICES)
    provision.add_argument(
        "--chain",
        nargs="*",
        default=[],
        choices=sorted(MB_DESCRIPTIONS.keys()),
    )
    provision.add_argument(
        "--intent",
        required=True,
        choices=["low-latency", "best-effort"],
    )
    provision.add_argument("--bandwidth", type=float, required=True)
    provision.add_argument("--blocked-ports", type=int, nargs="+", dest="blocked_ports")

    teardown = subparsers.add_parser("teardown")
    teardown.add_argument("--name", required=True)

    subparsers.add_parser("status")
    subparsers.add_parser("list-mbs")

    args = parser.parse_args()

    if args.command == "provision":
        cmd_provision(args)
    elif args.command == "teardown":
        cmd_teardown(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "list-mbs":
        cmd_list_mbs(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
