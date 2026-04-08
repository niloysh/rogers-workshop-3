#!/usr/bin/env python3
"""
lab4_solution.py
────────────────
Reference solution — revised Lab 4 independent challenge.

Workshop simplification:
  only one active slice may use a given ordered endpoint pair.

Reference design:
  Slice 1 — premium monitored video
    h1 -> h2
    chain: mb1
    intent: low-latency
    bandwidth: 5 Mbps

  Slice 2 — secured and logged web access
    h3 -> h2
    chain: mb2 -> mb3
    intent: best-effort
    bandwidth: 3 Mbps
    blocked ports: 8080
"""

import subprocess
import sys


def run(cmd):
    print(f"  $ {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr:
        print(f"  [error] {result.stderr.strip()}", file=sys.stderr)
    return result.returncode


def main():
    print("\n[solution] Slice 1 — premium monitored video\n")
    run(
        "python3 slice_controller_v2.py provision "
        "--name video_gold "
        "--src h1 --dst h2 "
        "--chain mb1 "
        "--intent low-latency "
        "--bandwidth 5"
    )

    print("\n[solution] Slice 2 — secured and logged web access\n")
    run(
        "python3 slice_controller_v2.py provision "
        "--name web_guard "
        "--src h3 --dst h2 "
        "--chain mb2 mb3 "
        "--intent best-effort "
        "--bandwidth 3 "
        "--blocked-ports 8080"
    )

    print("\n[solution] Status\n")
    run("python3 slice_controller_v2.py status")

    print(
        """
[solution] Why these choices fit the revised lab:

  Slice 1 needs monitoring and premium treatment.
    -> mb1 gives throughput visibility
    -> low-latency uses the shortest realized path
    -> 5 Mbps comfortably satisfies the >=4 Mbps target

  Slice 2 needs ordinary web access, blocked admin access, and logging.
    -> mb2 carries the firewall policy
    -> mb3 provides logging / audit evidence
    -> best-effort is appropriate for non-premium transport
    -> blocking port 8080 satisfies the security requirement

  Why these endpoint pairs?
    -> Slice 1 uses h1 -> h2
    -> Slice 2 uses h3 -> h2
    -> This satisfies the workshop simplification: one active slice per
       ordered endpoint pair while keeping the classifier simple.
"""
    )


if __name__ == "__main__":
    main()
