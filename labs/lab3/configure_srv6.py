#!/usr/bin/env python3
"""
configure_srv6.py
─────────────────
Apply the repeated SRv6 host setup for Lab 3.

Run this from a regular shell after starting the Lab 3 topology:

    sudo python3 lab3_topology.py
    python3 configure_srv6.py

This script:
  - enables IPv6 forwarding on h1, h2, mb1, and mb2
  - enables SRv6 processing globally and on each host interface
  - assigns the SRv6 SID for each host

It does not install any SRv6 steering routes. Participants still do that
manually in the lab so the actual path-steering step remains explicit.
"""

from __future__ import annotations

import subprocess
import sys


HOSTS = {
    "h1": "fc00::1",
    "h2": "fc00::2",
    "mb1": "fc00::b1",
    "mb2": "fc00::b2",
}


def find_host_pid(host: str) -> str | None:
    result = subprocess.run(
        ["pgrep", "-f", f"mininet:{host}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None

    pids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return pids[0] if pids else None


def host_cmd(host: str, cmd: str) -> subprocess.CompletedProcess[str]:
    pid = find_host_pid(host)
    if not pid:
        raise RuntimeError(
            f"Could not find Mininet host namespace for {host}. "
            "Start lab3_topology.py first."
        )

    return subprocess.run(
        ["sudo", "mnexec", "-a", pid, "sh", "-lc", cmd],
        capture_output=True,
        text=True,
    )


def require_ok(host: str, cmd: str) -> None:
    result = host_cmd(host, cmd)
    if result.returncode != 0:
        raise RuntimeError(
            f"{host}: command failed: {cmd}\n"
            f"{result.stderr.strip() or result.stdout.strip()}"
        )


def ensure_sid(host: str, sid: str) -> None:
    iface = f"{host}-eth0"
    show = host_cmd(host, f"ip -6 addr show dev {iface}")
    if sid in show.stdout:
        return
    require_ok(host, f"ip -6 addr add {sid}/128 dev {iface}")


def ensure_srv6_reachability(host: str) -> None:
    iface = f"{host}-eth0"
    # Each SID is a /128 identifier, so add a shared on-link route for the
    # fc00::/64 lab SID space. This lets hosts resolve one another over the
    # L2 topology while keeping the SIDs themselves as host-specific /128s.
    require_ok(host, f"ip -6 route replace fc00::/64 dev {iface}")


def configure_host(host: str, sid: str) -> None:
    iface = f"{host}-eth0"
    require_ok(host, "sysctl -w net.ipv6.conf.all.forwarding=1")
    require_ok(host, "sysctl -w net.ipv6.conf.all.seg6_enabled=1")
    require_ok(host, f"sysctl -w net.ipv6.conf.{iface}.seg6_enabled=1")
    ensure_sid(host, sid)
    ensure_srv6_reachability(host)


def main() -> int:
    print("=" * 56)
    print("  Lab 3 — Configure SRv6 Hosts")
    print("=" * 56)
    print()

    try:
        for host, sid in HOSTS.items():
            print(f"[setup] {host}: enabling SRv6 and assigning SID {sid}")
            configure_host(host, sid)
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print()
    print("[done] Applied SRv6 host setup:")
    for host, sid in HOSTS.items():
        print(f"  {host:<4} -> {sid}")

    print()
    print("Next steps in the lab:")
    print("  1. Verify SID reachability with ping6")
    print("  2. Start the HTTP server and IDS with the helper scripts")
    print("  3. Add the SRv6 encap route on h1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
