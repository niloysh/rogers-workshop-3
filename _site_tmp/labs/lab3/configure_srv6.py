#!/usr/bin/env python3
"""
configure_srv6.py
─────────────────
Apply the repeated SRv6 host setup for Lab 3.

Run this from a regular shell after starting the Lab 3 topology:

    sudo python3 topology.py
    python3 configure_srv6.py

This script:
  - enables IPv6 forwarding on h1, h2, mb1, mb2, and r1
  - enables SRv6 processing globally and on each host interface
  - assigns the SRv6 SID for each host
  - for r1 (dual-homed router): enables SRv6 on both interfaces and adds
    the fc00::/64 on-link route on each so it can reach all SIDs

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

# r1 is dual-homed (r1-eth0 → s1, r1-eth1 → s2) and needs special handling.
ROUTERS = {
    "r1": "fc00::a1",
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
            "Start topology.py first."
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


def configure_router(host: str, sid: str) -> None:
    """Configure a dual-homed host as an SRv6 router.

    r1 has two interfaces:
      r1-eth0 → s1  (SID is assigned here)
      r1-eth1 → s2

    Both interfaces need seg6_enabled so the kernel processes SRH on
    packets arriving from either switch.

    Routing on r1 must be explicit — ECMP across both interfaces causes
    packets to bounce back through the slow s1-s2 link:

      eth0 → s1   (h1 lives here: fc00::1)
      eth1 → s2   (h2, mb1, mb2 live here: all other fc00:: SIDs)

    So we install:
      fc00::/64    dev eth1   (default: toward s2)
      fc00::1/128  dev eth0   (more-specific: h1 is on the s1 side)
    """
    require_ok(host, "sysctl -w net.ipv6.conf.all.forwarding=1")
    require_ok(host, "sysctl -w net.ipv6.conf.all.seg6_enabled=1")
    for iface in [f"{host}-eth0", f"{host}-eth1"]:
        require_ok(host, f"sysctl -w net.ipv6.conf.{iface}.seg6_enabled=1")

    # Default route for fc00::/64 — all SIDs are reachable via s2 (eth1)
    # except h1 which is on s1 (eth0).  Using replace so re-runs are safe.
    require_ok(host, f"ip -6 route replace fc00::/64    dev {host}-eth1")
    require_ok(host, f"ip -6 route replace fc00::1/128  dev {host}-eth0")

    # Assign fc00::a1 to eth0 (s1-facing) — used in the forward chain
    # so h1 reaches r1 directly via s1 without crossing the slow s1-s2 link.
    ensure_sid(host, sid)

    # Assign fc00::a2 to eth1 (s2-facing) — used in the reverse chain
    # so mb1 (on s2) reaches r1 directly via s2 without crossing the slow link.
    eth1 = f"{host}-eth1"
    eth1_sid = "fc00::a2"
    show = host_cmd(host, f"ip -6 addr show dev {eth1}")
    if eth1_sid not in show.stdout:
        require_ok(host, f"ip -6 addr add {eth1_sid}/128 dev {eth1}")


def main() -> int:
    print("=" * 56)
    print("  Lab 3 — Configure SRv6 Hosts")
    print("=" * 56)
    print()

    try:
        for host, sid in HOSTS.items():
            print(f"[setup] {host}: enabling SRv6 and assigning SID {sid}")
            configure_host(host, sid)
        for host, sid in ROUTERS.items():
            print(f"[setup] {host}: configuring dual-homed SRv6 router, SID {sid}")
            configure_router(host, sid)
    except RuntimeError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1

    print()
    print("[done] Applied SRv6 setup:")
    for host, sid in {**HOSTS, **ROUTERS}.items():
        print(f"  {host:<4} -> {sid}")

    print()
    print("Next steps in the lab:")
    print("  1. Verify SID reachability with ping6")
    print("  2. Start the HTTP server and IDS with the helper scripts")
    print("  3. Add the SRv6 encap route on h1 (via r1 → mb1 → mb2 → h2)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
