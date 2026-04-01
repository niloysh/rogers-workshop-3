---
marp: true
theme: workshop-readable
paginate: true
---

<!-- _class: title -->

<span class="tag">Lab 3</span>

# SRv6 Path Steering
# and Service Function Chaining

Rogers Executive Workshop 3 — Transport Network Programmability

---

<!-- _class: divider -->

# Getting Started

The topology and what we are trying to show

---

# Lab 3 at a glance

In this lab you will:

- start a topology with a firewall and IDS off the direct path
- manually enable SRv6 on each host and assign Segment IDs
- show that normal routing bypasses both service functions
- program a Segment Routing Header to chain traffic through them
- inspect SRH headers in transit using tshark
- observe the firewall block non-HTTP traffic and the IDS alert on suspicious requests

> **What to focus on** Without SRv6, malicious traffic reaches h2 undetected. With SRv6, it passes through both service functions first. The chain only works if the path is explicitly programmed.

---

# Lab 3 topology

```
    h1 ── s1 ── s2 ── h2
                |
               mb1  (firewall)
                |
               mb2  (IDS)
```

| Node | Role                | IPv4     | SRv6 SID |
| ---- | ------------------- | -------- | -------- |
| h1   | Traffic source      | 10.0.0.1 | fc00::1  |
| h2   | Traffic destination | 10.0.0.2 | fc00::2  |
| mb1  | Firewall            | 10.0.0.3 | fc00::b1 |
| mb2  | IDS                 | 10.0.0.4 | fc00::b2 |

> **The key detail** The direct path h1→s1→s2→h2 completely bypasses mb1 and mb2. SRv6 is what forces traffic through the service chain.

---

# Service chain behaviour

**mb1 — firewall**
- allows HTTP traffic (TCP port 80)
- blocks everything else (ICMP, other protocols)
- traffic that passes mb1 continues to mb2

**mb2 — IDS (Intrusion Detection System)**
- passively inspects all HTTP requests passing through
- prints `[OK]` for normal requests
- prints `[ALERT]` for suspicious URLs (e.g. `/malware`, `/exploit`)
- always lets traffic pass — IDS detects but does not block

> **Why this matters** Without the service chain, malicious requests reach h2 undetected. With SRv6 steering, every request is inspected — even if the IDS cannot stop it, the attack is logged.

---

<!-- _class: compact -->

# Before you start

For this lab:

- work from `~/labs/lab3`
- keep four terminals open
- run Mininet with `sudo`
- remember that host commands run from the Mininet CLI, for example:
  - `mininet> h1 ip -6 route show`

Keep these open:

1. Mininet
   Start the topology and run host commands here.
2. h2 HTTP terminal
   Run `./run_h2_http_server.sh` here.
3. mb1 service terminal
   Run `./run_mb1_firewall.sh` here.
4. mb2 service terminal
   Run `./run_mb2_ids.sh` here.
5. Shell / checker terminal
   Run `preflight_check.py`, `verify_lab3.py`, and `./enter_host.sh` here.

---

<!-- _class: compact -->

# Start the topology

```bash
sudo python3 lab3_topology.py
```

This topology uses standalone OVS switches. Lab 3 does not need ONOS or a separate OpenFlow controller.

Verify connectivity:

```
mininet> nodes
mininet> pingall
```

Start the HTTP server on h2 for the baseline tests:

```bash
./run_h2_http_server.sh
```

> **Tip** Run this from the separate `h2 HTTP terminal`, not from the Mininet prompt.

> **Expected** pingall succeeds. h2 is now serving HTTP on port 80. At this point mb1 and mb2 are just connected hosts — no service functions running yet.

---

<!-- _class: compact -->

# Check readiness

Now run the pre-flight check from your regular shell:

```bash
python3 preflight_check.py
```

It confirms:

- Mininet is running
- `s1` and `s2` exist
- the base topology is ready for SRv6
- required tools such as `tshark` are available

---

<!-- _class: divider -->

# SRv6 Setup

Enable IPv6 SIDs first, then compare before and after steering

---

# Do it once by hand on h1

These three commands show the full pattern on one host:

```
mininet> h1  sysctl -w net.ipv6.conf.all.forwarding=1
mininet> h1  sysctl -w net.ipv6.conf.all.seg6_enabled=1
mininet> h1  sysctl -w net.ipv6.conf.h1-eth0.seg6_enabled=1
mininet> h1  ip -6 addr add fc00::1/128  dev h1-eth0
```

- `forwarding=1` lets the host forward IPv6 packets
- `seg6_enabled=1` tells the kernel to process Segment Routing Headers
- `fc00::1/128` is h1's Segment ID

> **The key idea** The other hosts use the same pattern: enable forwarding, enable SRv6, then assign the correct SID.

---

# Apply the same setup to all hosts

Now use the helper script for the repeated setup:

```
python3 configure_srv6.py
```

It applies:

- `h1  -> fc00::1`
- `h2  -> fc00::2`
- `mb1 -> fc00::b1`
- `mb2 -> fc00::b2`
- an on-link route for the shared `fc00::/64` lab SID space

> **Why use a script here** You already saw the pattern on h1. The script saves time and avoids copy-paste mistakes, but the actual SRv6 route programming still stays manual.

---

# Verify SID reachability

After `configure_srv6.py`, confirm the SIDs are reachable:

```
mininet> h1 ping6 -c 2 fc00::2     # h1 → h2
mininet> h1 ping6 -c 2 fc00::b1    # h1 → mb1
mininet> h1 ping6 -c 2 fc00::b2    # h1 → mb2
```

> **Expected** All three pings succeed. If any fail, check that seg6_enabled and forwarding are set correctly on all hosts.

> **Why this works with /128 SIDs** Each host keeps a host-specific `/128` SID, and `configure_srv6.py` also adds an on-link route for `fc00::/64` so the SIDs are reachable across the switched topology.

> **From this point on** Use `ping6` and IPv6 `curl -g "http://[...]"` commands in this lab. `pingall` is still useful for the initial IPv4 sanity check, but it does not show SRv6 behaviour.

---

<!-- _class: divider -->

# Baseline

Before adding an SRv6 route, confirm plain IPv6 still bypasses the service chain

---

# Confirm the default IPv6 path bypasses mb1 and mb2

SRv6 is enabled on the hosts now, but we have not added any steering rule on `h1` yet.
So the normal path still goes directly h1→s1→s2→h2 and does not pass through the service functions.

Start the IDS on mb2 first so we can see whether it captures anything:

Run this in the `mb2` service terminal:

```
./run_mb2_ids.sh
```

Now send a request from h1 directly to h2 over IPv6:

```
mininet> h1 curl -g "http://[fc00::2]/malware"
```

> **Expected** h2 responds (or 404 — that's fine). mb2 IDS prints **nothing** — the request never passed through mb2. This gives us the baseline before path steering.

---

# Start the firewall

Now start mb1's firewall:

Run this in the `mb1` service terminal:

```
./run_mb1_firewall.sh
```

You should see the firewall rules printed:

```
[mb1 firewall] Active rules:
  ACCEPT  tcp -- anywhere  anywhere  tcp dpt:80
  DROP    all -- anywhere  anywhere
```

Quick sanity check:

```
mininet> h1 ping6 -c 3 fc00::b1
```

> **Why this still works** This ping goes to `mb1` itself, so it hits the INPUT path on mb1 rather than the FORWARD chain. The meaningful firewall test comes next, after we steer forwarded IPv6 traffic through `mb1`.

---

<!-- _class: divider -->

# Path Steering

Programming the service chain with SRv6

---

# How Inline Steering Works

We start with a normal IPv6 request:

```
h1  ── HTTP over IPv6 ──>  h2 (fc00::2)
```

After the SRv6 route is installed on `h1`, the *same* IPv6 request is steered through the service chain:

```
h1  ──>  mb1  ──>  mb2  ──>  h2
        fc00::b1   fc00::b2   fc00::2
```

Conceptually, the packet now carries:

```
IPv6 header
  current destination: first active segment

SRH
  service waypoints: mb1, mb2
  final destination: h2

Payload
  the original HTTP request
```

> **What inline means here** The packet keeps its original IPv6 destination (`fc00::2`), and the SRH adds the service waypoints that must be visited first.

---

# Inline Vs Encap

You will often see two SRv6 route modes:

**`mode inline`**
- inserts an SRH into the packet that is already being sent
- keeps the original IPv6 destination as the packet's real destination
- good when the traffic is already IPv6 and the endpoints can understand the path change

**`mode encap`**
- wraps the original packet inside a new outer IPv6 header
- the SRv6 information lives in that outer packet
- useful when you want a cleaner tunnel-like wrapper around the original traffic

> **Why this lab uses `inline`** It keeps the demo easier to read. The HTTP request is still the same IPv6 flow from `h1` to `h2`, and SRv6 simply adds the service-chain instructions on top.

---

# Program the service chain

On h1, install the SRv6 route that steers traffic through mb1 then mb2:

```
mininet> h1 ip -6 route add fc00::2 encap seg6 mode inline segs fc00::b1,fc00::b2 dev h1-eth0
```

Verify the route was added:

```
mininet> h1 ip -6 route show
```

> **Reading the segs list** `fc00::b1,fc00::b2` means: visit mb1 first, then mb2. Because this route uses `mode inline`, the final destination `fc00::2` is already the packet's normal IPv6 destination and does not need to appear in `segs`.

---

<!-- _class: compact -->

# Test 1 — normal HTTP request

Send a normal HTTP request from h1 to h2:

```
mininet> h1 curl -g "http://[fc00::2]/index.html"
```

Watch mb2's IDS output — you should see:

```
[HH:MM:SS] [mb2 IDS] [OK]    fc00::1 → fc00::2 — GET /index.html HTTP/1.1
```

> **What this shows** The request passed through both mb1 (allowed by firewall) and mb2 (inspected by IDS). The IDS sees it and marks it OK.

---

<!-- _class: compact -->

# Test 2 — suspicious HTTP request

Send a request with a suspicious URL:

```
mininet> h1 curl -g "http://[fc00::2]/malware"
```

Watch mb2's IDS output — you should see:

```
[HH:MM:SS] [mb2 IDS] [ALERT] fc00::1 → fc00::2 — GET /malware HTTP/1.1
```

> **What this shows** The firewall (mb1) allowed the request because it is HTTP. The IDS (mb2) detected the suspicious URL and raised an alert. h2 still responds — the IDS detects but does not block. The attack is logged even though it gets through.

---

# Test 3 — ping blocked by firewall

Try to ping h2 with SRv6 active:

```
mininet> h1 ping6 -c 3 fc00::2
```

> **Expected** Pings fail — mb1's firewall blocks ICMP. The traffic reaches mb1, but the FORWARD chain drops it before it can reach mb2 or h2.

Check the firewall counters on mb1:

```
mininet> mb1 ip6tables -L FORWARD -v -n
```

> **Notice** The DROP rule's packet counter increments with each blocked ping.

---

<!-- _class: compact -->

# Inspect the SRH with tshark

Capture and inspect the SRH on mb2 from a regular shell:

```bash
./enter_host.sh mb2
# now inside mb2's shell:
tshark -i mb2-eth0 -Y "ipv6.routing.type == 4" -V -c 1
```

Then send one request from Mininet:

```text
mininet> h1 curl -g "http://[fc00::2]/test"
```

Look for these fields:

```
Routing Header (Type 4 - Segment Routing)
  Segments Left: 0
  Last Entry: 1
  Address[0]: fc00::2    ← final destination
  Address[1]: fc00::b2   ← mb2 (current)
  Address[2]: fc00::b1   ← mb1 (already visited / first waypoint)
```

> **At mb2** the SRH only contains the service waypoints. `fc00::2` still appears as the final destination, but it is not an extra service hop.

---

# Remove the route — confirm bypass

Remove the SRv6 route:

```
mininet> h1 ip -6 route del fc00::2
```

Now send the same malicious request:

```
mininet> h1 curl http://10.0.0.2/malware
```

> **Expected** h2 responds. mb2 IDS prints **nothing** — the traffic bypassed the service chain completely. The attack goes undetected.

> **This is the core demonstration** SRv6 is what guarantees traffic passes through the service chain. Without it, there is no enforcement.

---

<!-- _class: divider -->

# Independent Challenge

---

<!-- _class: independent compact -->

# What you will build

The current chain is: **h1 → mb1 → mb2 → h2**

Your challenge is to also protect traffic going the **other direction**:

**h2 → mb2 → mb1 → h1** (reverse chain)

Currently h2 can send traffic back to h1 without using that reverse chain.

In this challenge you will:

- install a reverse SRv6 route on `h2`
- verify that reverse traffic visits `mb2` before `mb1`
- confirm that `mb1` still blocks ICMP on the reverse path

> **What changes from the guided part** The service chain itself stays the same. You are adding the return path so steering works in both directions.

---

<!-- _class: independent compact -->

# Files you will use

Use these files for the challenge:

- `lab3_skeleton.py` prints the reverse-chain task and route shape
- `verify_lab3.py` checks the reverse route and service-chain behavior
- `lab3_solution.py` is the reference solution
- `enter_host.sh` opens a shell in any host namespace
- `run_h2_http_server.sh`, `run_mb1_firewall.sh`, and `run_mb2_ids.sh` start the long-running services

---

<!-- _class: independent compact -->

# Your tasks

1. **Install the reverse SRv6 route on h2**
   - destination: `fc00::1`
   - waypoints: `mb2` first, then `mb1`, then `h1`
2. **Verify the reverse path** with a short capture on `mb2`
   - use `tshark` to confirm reverse traffic reaches the IDS first
3. **Test the firewall** from the reverse direction
   - `ping6` from `h2` to `h1` should still fail at `mb1`
4. **Explain** in a comment:
   - why does the reverse chain visit `mb2` before `mb1`?
   - what would change if the order were reversed?

Run the task prompt if you want a reminder:

```bash
mininet> h2 python3 lab3_skeleton.py
```

---

<!-- _class: independent compact -->

# Check your work

Keep Mininet, the firewall, and the IDS running while you verify.

Run:

```bash
sudo python3 verify_lab3.py
```

The checker looks for:

- SRv6 is configured on all hosts
- the forward route still exists on `h1`
- the reverse route exists on `h2`
- HTTP can still traverse the forward chain
- ICMP is still blocked by the firewall in both directions

Reference solution:

```bash
mininet> h2 python3 lab3_solution.py
sudo python3 verify_lab3.py
```

---

<!-- _class: independent compact -->

# Troubleshooting

- if `ping6 fc00::2` fails after `configure_srv6.py`, recheck `seg6_enabled` and SID assignment on all hosts
- if `curl -g "http://[fc00::2]/..."` fails, restart the server with `./run_h2_http_server.sh`
- if the firewall does not block `ping6`, restart it with `./run_mb1_firewall.sh`
- if the IDS log is empty, restart it with `./run_mb2_ids.sh` before you send traffic
- if the reverse path is not working, start with `h2 ip -6 route show`

---

<!-- _class: independent compact -->

# Hints

> **Reverse segs order** For the return path h2→mb2→mb1→h1, the segs list should be `fc00::b2,fc00::b1`. The final destination `fc00::1` stays as the packet's normal IPv6 destination.

> **mb1 firewall and replies** The firewall already has a rule allowing `--sport 80` (HTTP replies). Check with `mb1 ip6tables -L FORWARD -v -n` after testing.

> **Reverse verification** The IDS script only inspects HTTP requests, not responses. For the reverse path, `tshark` on `mb2` is the cleanest proof that traffic visits the IDS first.

> **A good reverse test** Start `tshark` on `mb2`, then run `h2 ping6 -c 3 fc00::1`. The ping should still fail at `mb1`, but `mb2` should see the SRH traffic first.

> **Debugging** If the route is not working, check `h2 ip -6 route show` and make sure all SRv6 sysctl settings are correct on h2.

---

# Summary

What you did in Lab 3:

- Started a topology with a firewall and IDS off the direct path
- Showed that normal routing bypasses both service functions
- Manually enabled SRv6 and assigned Segment IDs on all hosts
- Programmed a two-node service chain using a Segment Routing Header
- Observed the firewall block non-HTTP traffic
- Watched the IDS detect a malicious request in real time
- Confirmed that removing the SRv6 route bypasses the chain entirely

**In Lab 4** the `--srv6` flag in `workshop_topology.py` automates exactly what you did manually today. The slice controller combines this with ONOS and OVS queuing to provision complete transport slices.

---

# Quick reference — Lab 3 commands

```bash
# SRv6 setup (run per host via mininet> h1 ...)
sysctl -w net.ipv6.conf.all.forwarding=1
sysctl -w net.ipv6.conf.all.seg6_enabled=1
sysctl -w net.ipv6.conf.<iface>.seg6_enabled=1
ip -6 addr add <sid>/128 dev <iface>

# SRv6 route (install on ingress host)
ip -6 route add <dst-sid> encap seg6 mode inline \
  segs <sid1>,<sid2>,<dst-sid> dev <iface>
ip -6 route del <dst-sid>          # remove route
ip -6 route show                   # show routes

# Service scripts
./run_h2_http_server.sh
./run_mb1_firewall.sh
./run_mb2_ids.sh

# Open a host shell
./enter_host.sh mb2
# then inside that shell:
cat /tmp/mb2_ids.log

# Packet inspection
tshark -i mb2-eth0 -Y "ipv6.routing.type == 4" -V -c 1
```
