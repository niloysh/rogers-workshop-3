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

- start a topology with two service waypoints off the direct path
- manually enable SRv6 on each host and assign Segment IDs
- show that normal routing bypasses both service functions
- program an SRv6 encapsulation route to chain traffic through them
- inspect the outer SRv6 packet in transit using tshark
- observe the IDS log tunneled HTTP requests at the second waypoint

> **What to focus on** Without SRv6, traffic reaches h2 on the direct path. With SRv6 encap, h1 wraps the original flow in an outer IPv6+SRH packet and forces it through the service chain first.

---

# Lab 3 topology

<div class="topology-figure compact">
  <img src="../../assets/figures/lab3-service-chain-topology.svg" alt="Lab 3 topology with h1 connected to s1, s1 connected to s2, h2 connected to s2, and both service nodes mb1 and mb2 attached directly to s2." />
</div>

| Node | Role                | IPv4     | SRv6 SID |
| ---- | ------------------- | -------- | -------- |
| h1   | Traffic source      | 10.0.0.1 | fc00::1  |
| h2   | Traffic destination | 10.0.0.2 | fc00::2  |
| mb1  | Waypoint 1          | 10.0.0.3 | fc00::b1 |
| mb2  | IDS / waypoint 2    | 10.0.0.4 | fc00::b2 |

> **The key detail** The direct path h1→s1→s2→h2 completely bypasses mb1 and mb2. SRv6 is what forces traffic through the service chain.

---

# Service chain behaviour

**mb1 — waypoint 1**
- the first hop in the SRv6 service chain
- forwards the outer SRv6 packet toward mb2
- a good place to observe the outer SRH with `tshark`

**mb2 — IDS (Intrusion Detection System)**
- passively inspects tunneled HTTP requests that pass through
- prints `[OK]` for normal requests
- prints `[ALERT]` for suspicious URLs (e.g. `/malware`, `/exploit`)
- always lets traffic pass — IDS detects but does not block

> **Why this matters** Without the service chain, malicious requests reach h2 undetected. With SRv6 encap, the original request is carried inside an outer SRv6 packet that must visit mb1 and mb2 before h2.

---

<!-- _class: compact -->

# Before you start

For this lab:

- work from `~/labs/lab3`
- keep three or four terminals open
- run Mininet with `sudo`
- remember that host commands run from the Mininet CLI, for example:
  - `mininet> h1 ip -6 route show`

Keep these open:

1. Mininet
   Start the topology and run host commands here.
2. h2 HTTP terminal
   Run `./run_h2_http_server.sh` here.
3. mb2 service terminal
   Run `./run_mb2_ids.sh` here.
4. Shell / checker terminal
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

> **Traffic split in this lab** The SRv6 transport uses IPv6 SIDs, but the application traffic from the hosts stays ordinary IPv4. That is exactly what `encap` is useful for.

---

<!-- _class: divider -->

# Baseline

Before adding an SRv6 tunnel route, confirm plain IPv4 still bypasses the service chain

---

# Confirm the default IPv4 path bypasses mb1 and mb2

SRv6 is enabled on the hosts now, but we have not added any steering rule on `h1` yet.
So the normal path still goes directly h1→s1→s2→h2 and does not pass through the service functions.

Start the IDS on mb2 first so we can see whether it captures anything:

Run this in the `mb2` service terminal:

```
./run_mb2_ids.sh
```

Now send a request from h1 directly to h2 over IPv4:

```
mininet> h1 curl http://10.0.0.2/malware
```

> **Expected** h2 responds (or 404 — that's fine). mb2 IDS prints **nothing** — the request never passed through mb2. This gives us the baseline before SRv6 encap steering.

---

<!-- _class: divider -->

# Path Steering

Programming the service chain with SRv6

---

# Same Request, Different Path

Before path steering:

```text
h1  ───────────────>  h2
     direct IPv4 path
```

After adding the SRv6 encap route on `h1`:

```text
h1  ──>  mb1  ──>  mb2  ──>  h2
        waypoint    IDS
```

The request itself is still:

```text
GET /index.html   to   10.0.0.2
```

> **What changes** The application traffic does not change. Only the route on `h1` changes. With `encap`, h1 wraps the original request in a new outer IPv6+SRH packet and sends that packet through `mb1` and `mb2`.

---

# What The Encapsulated Packet Carries

Conceptually, the steered packet now looks like:

```text
Outer IPv6 header
  src: fc00::1
  current destination: fc00::b1

SRH waypoint list
  1. fc00::b1   (mb1)
  2. fc00::b2   (mb2)
  final destination: fc00::2   (h2)

Inner IPv4 packet
  original destination: 10.0.0.2

Payload
  GET /index.html
```

- at `mb1`, the packet advances to `mb2`
- at `mb2`, the packet advances to the final segment `fc00::2`
- at `h2`, the outer SRv6 wrapper is consumed and the original packet is delivered
- the inner HTTP request stays the same the whole time

> **What encap means here** The original request is preserved as the inner packet. SRv6 adds a new outer IPv6+SRH wrapper that carries it through the service chain.

---

# Inline Vs Encap

| Mode     | Think of it as                                           | Best fit                                                      |
| -------- | -------------------------------------------------------- | ------------------------------------------------------------- |
| `inline` | add the SRH to the same IPv6 packet                      | simple native IPv6 steering                                   |
| `encap`  | wrap the original traffic in a new outer IPv6+SRH packet | slice transport, tunnel-like steering, non-IPv6 inner traffic |

> **Why this lab uses `encap`** This is closer to how slice transport is usually presented: the original traffic stays intact while SRv6 adds an outer transport wrapper that carries it through the required waypoints.

---

# Program the service chain

On h1, install the SRv6 encap route that steers traffic through mb1 then mb2:

```
mininet> h1 ip route add 10.0.0.2 encap seg6 mode encap segs fc00::b1,fc00::b2,fc00::2 dev h1-eth0
```

Verify the route was added:

```
mininet> h1 ip route show
```

> **Reading the segs list** `fc00::b1,fc00::b2,fc00::2` means: visit mb1 first, then mb2, then deliver the outer SRv6 packet to h2. The original IPv4 request to `10.0.0.2` stays inside the encapsulated packet the whole time.

---

<!-- _class: compact -->

# Test 1 — normal HTTP request

Send a normal HTTP request from h1 to h2:

```
mininet> h1 curl http://10.0.0.2/index.html
```

Watch mb2's IDS output — you should see:

```
[HH:MM:SS] [mb2 IDS] [OK]    10.0.0.1 → 10.0.0.2 — GET /index.html HTTP/1.1
```

> **What this shows** The outer SRv6 packet forced the request through mb1 and mb2. The IDS at mb2 can still inspect the tunneled HTTP request and mark it OK.

---

<!-- _class: compact -->

# Test 2 — suspicious HTTP request

Send a request with a suspicious URL:

```
mininet> h1 curl http://10.0.0.2/malware
```

Watch mb2's IDS output — you should see:

```
[HH:MM:SS] [mb2 IDS] [ALERT] 10.0.0.1 → 10.0.0.2 — GET /malware HTTP/1.1
```

> **What this shows** The IDS at mb2 can still inspect the tunneled HTTP request and raise an alert. h2 still responds — the IDS detects but does not block.

---

<!-- _class: compact -->

# Inspect the outer SRv6 packet with tshark

Open a shell in `mb1` from a regular shell:

```bash
./enter_host.sh mb1
# now inside mb1's shell:
tshark -i mb1-eth0 -Y "ipv6.routing.type == 4" -V -c 1
```

Then send one request from Mininet:

```text
mininet> h1 curl http://10.0.0.2/test
```

Look for these fields in the outer packet:

```
Routing Header (Type 4 - Segment Routing)
  Segments Left: 2 or 1
  Last Entry: 2
  Address[0]: fc00::2    ← outer final destination
  Address[1]: fc00::b2   ← second waypoint
  Address[2]: fc00::b1   ← first waypoint
```

> **What to notice** With `encap`, the SRH belongs to the outer IPv6 transport packet. The original request to `10.0.0.2` is carried inside it.

---

# Remove the route — confirm bypass

Remove the SRv6 route:

```
mininet> h1 ip route del 10.0.0.2
```

Now send the same malicious request:

```
mininet> h1 curl http://10.0.0.2/malware
```

> **Expected** h2 still responds, but mb2 IDS prints **nothing** — the request bypassed the service chain completely.

> **What this proves** SRv6 is what makes the service chain happen. Without that route, traffic falls back to the normal direct path.

---

<!-- _class: divider -->

# Independent Challenge

---

<!-- _class: independent compact -->

# What you will build

The current chain is: **h1 → mb1 → mb2 → h2**

Your challenge is to also steer traffic going the **other direction**:

**h2 → mb2 → mb1 → h1** (reverse chain)

Currently h2 can send traffic back to h1 without using that reverse chain.

In this challenge you will:

- install a reverse SRv6 route on `h2`
- verify that ping replies now come back through `mb1`
- keep the reverse path logic consistent with the forward path

> **What changes from the guided part** The service chain itself stays the same. You are adding the return path so steering works in both directions.

---

<!-- _class: independent compact -->

# Files you will use

Use these files for the challenge:

- `lab3_skeleton.py` prints the reverse-chain task and route shape
- `verify_lab3.py` checks the reverse route and service-chain behavior
- `lab3_solution.py` is the reference solution
- `enter_host.sh` opens a shell in any host namespace
- `run_h2_http_server.sh` and `run_mb2_ids.sh` start the long-running services

---

<!-- _class: independent compact -->

# Your tasks

1. **Install the reverse SRv6 route on h2**
   - destination: `10.0.0.1`
   - waypoints: `mb2` first, then `mb1`, then `h1`
2. **Open a short capture on mb1**
   - use one `tshark` filter that matches both ping requests and replies
3. **Run the same ping again** from `h1` to `h2`
   - before the reverse route, mb1 mainly sees only requests
   - after the reverse route, mb1 sees requests and replies
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

Keep Mininet, the HTTP server, and the IDS running while you verify.

Run:

```bash
sudo python3 verify_lab3.py
```

The checker looks for:

- SRv6 is configured on all hosts
- the forward route still exists on `h1`
- the reverse route exists on `h2`
- HTTP can still traverse the forward chain
- the IDS still logs forward traffic

Reference solution:

```bash
mininet> h2 python3 lab3_solution.py
sudo python3 verify_lab3.py
```

---

<!-- _class: independent compact -->

# Troubleshooting

- if `ping6 fc00::2` fails after `configure_srv6.py`, recheck `seg6_enabled` and SID assignment on all hosts
- if `curl http://10.0.0.2/...` fails, restart the server with `./run_h2_http_server.sh`
- if the IDS log is empty, restart it with `./run_mb2_ids.sh` before you send traffic
- if the reverse path is not working, start with `h2 ip route show`
- if `tshark` shows no SRH, confirm you installed the route with `mode encap` and included the final SID in the segs list
- if the mb1 capture shows only requests, the reverse route is still missing or incorrect

---

<!-- _class: independent compact -->

# Hints

> **Reverse segs order** For the return path h2→mb2→mb1→h1, the segs list should be `fc00::b2,fc00::b1,fc00::1`.

> **Simple reverse proof** Open `./enter_host.sh mb1`, then run:
> `tshark -i mb1-eth0 -Y "icmp && ip.addr==10.0.0.1 && ip.addr==10.0.0.2"`

> **What to expect** Before the reverse route, mb1 mainly sees only `h1 -> h2` echo requests. After the reverse route, the same `h1 ping -c 3 10.0.0.2` also produces `h2 -> h1` echo replies on mb1.

> **Debugging** If the route is not working, check `h2 ip route show` and make sure all SRv6 sysctl settings are correct on h2.

---

# Summary

What you did in Lab 3:

- Started a topology with two service waypoints off the direct path
- Showed that normal routing bypasses both service functions
- Manually enabled SRv6 and assigned Segment IDs on all hosts
- Programmed a two-node service chain using SRv6 encapsulation
- Inspected the outer SRv6 packet in transit with `tshark`
- Watched the IDS detect a malicious request carried inside the SRv6 tunnel
- Confirmed that removing the SRv6 route bypasses the chain entirely

In **Lab 4** the SliceController automates exactly what you did manually today, and combines it with OVS bandwidth reservation to provision complete transport slices.

---

# Quick reference — Lab 3 commands

```bash
# SRv6 setup (run per host via mininet> h1 ...)
sysctl -w net.ipv6.conf.all.forwarding=1
sysctl -w net.ipv6.conf.all.seg6_enabled=1
sysctl -w net.ipv6.conf.<iface>.seg6_enabled=1
ip -6 addr add <sid>/128 dev <iface>

# SRv6 route (install on ingress host)
ip route add <dst-ipv4> encap seg6 mode encap \
  segs <sid1>,<sid2>,<dst-sid> dev <iface>
ip route del <dst-ipv4>            # remove route
ip route show                      # show routes

# Service scripts
./run_h2_http_server.sh
./run_mb2_ids.sh

# Open a host shell
./enter_host.sh mb2
# then inside that shell:
cat /tmp/mb2_ids.log

# Packet inspection
tshark -i mb2-eth0 -Y "ipv6.routing.type == 4" -V -c 1
```
