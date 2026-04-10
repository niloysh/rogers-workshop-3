---
marp: true
theme: workshop-readable
paginate: true
---

<!-- _class: title -->

<span class="tag">Lab 4</span>

# Transport Slicing
# with SRv6 and OVS Queues

Rogers Executive Workshop 3 — Transport Network

---

<!-- _class: divider -->

# Getting Started

What we are building and why it matters

---

# Lab 4 at a glance

In this lab you will:

- observe contention between two flows on a shared bottleneck
- provision a transport slice that enforces both a **path contract** and a **bandwidth contract**
- watch a waypoint logger confirm that SRv6 is steering traffic through the right service functions
- discover what happens when chain order does not match the physical topology
- hit the limits of admission control and reason about smarter policies

> **What to focus on** In this lab, a transport slice combines two things: a path contract (which waypoints traffic must visit) and a bandwidth contract (what rate is reserved). The exercises show what happens when each is present or absent.

---

# From Labs 1 to 4

| Lab   | What you learned             | What Lab 4 reuses                                            |
| ----- | ---------------------------- | ------------------------------------------------------------ |
| Lab 1 | OVS rules, match and action  | queue-based bandwidth treatment on the bottleneck            |
| Lab 2 | ONOS REST API, topology view | understanding the control plane — not used directly in Lab 4 |
| Lab 3 | SRv6 encap route programming | path steering through an explicit service chain              |
| Lab 4 | **This lab**                 | combines all three into one slice controller                 |

> **What changes in Lab 4** Instead of configuring each mechanism separately, you describe a slice and the controller wires up the SRv6 route and OVS queue for you.

---

# Lab 4 topology

```
h1 (10.0.0.1) --.
h3 (10.0.0.3) --+-- s1 --[10 Mbps]-- s2 -- s3 -- h2 (10.0.0.2)
                                       |     |
                                      mb1   mb2
                               (10.0.0.4) (10.0.0.5)
```

| Node | Role               | IPv4     | SRv6 SID |
| ---- | ------------------ | -------- | -------- |
| h1   | Slice source       | 10.0.0.1 | fc00::1  |
| h2   | Slice destination  | 10.0.0.2 | fc00::2  |
| h3   | Contending flow    | 10.0.0.3 | fc00::3  |
| mb1  | Waypoint / monitor | 10.0.0.4 | fc00::b1 |
| mb2  | Waypoint / logger  | 10.0.0.5 | fc00::b2 |

> **The bottleneck** The s1->s2 link runs at 10 Mbps. All traffic from h1 and h3 competes here.

---

# What is a transport slice?

In this lab, a transport slice has two components:

**Path contract — implemented with SRv6**
Traffic is wrapped in an outer IPv6+SRH packet that names each waypoint explicitly. The kernel processes the SRH at each hop, advancing to the next segment. No waypoint can be skipped.

**Bandwidth contract — implemented with OVS HTB queues**
An HTB queue on the bottleneck port reserves a minimum rate for the slice's traffic. Best-effort flows use whatever capacity remains.

> **What the exercises show** A queue without SRv6 reserves bandwidth but lets traffic skip waypoints. SRv6 without a queue enforces the path but not the rate. This lab shows what each looks like in isolation, then combined.

---

<!-- _class: compact -->

# HTB in one minute

HTB = **Hierarchical Token Bucket**

- traffic earns "credit" to send at a configured rate
- when enough credit is available, packets are transmitted
- this enforces an average rate while still allowing small bursts
- HTB applies this idea to multiple queues on the same link

```text
h1 packets --set_queue:1--> [ premium q ] --.
                                            +--> s1-eth3 --> 10 Mbps link
h3 packets ---------------> [ default q ] --'
```

**In this lab**
- the slice traffic is placed into an HTB queue on the bottleneck port
- that queue gets the reserved bandwidth for the slice
- other traffic uses whatever capacity is left

> **HTB is the bandwidth contract** in action: after provisioning, `h1` recovers from about 5 Mbps to about 8 Mbps.

---

# Service request vs realized slice

**What you request**
```python
sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
```
A high-level description: source, destination, waypoints, reserved rate.

**What the controller sets up**
- an SRv6 segment list: `fc00::b1, fc00::2`
- an OVS HTB queue on `s1-eth3`: min-rate=8 Mbps, max-rate=8 Mbps
- an `ovs-ofctl` flow rule: `h1 MAC → set_queue:1, normal`
- an `ip route` on `h1`: `10.0.0.2 encap seg6 mode encap segs ...`

> **The request is abstract; the realization is a handful of concrete commands** — the same ones you ran manually in Labs 1 and 3.

---

# Soft slicing

The guarantees in this lab are **soft**, not hard:

|           | This lab (soft)              | Hard equivalent                |
| --------- | ---------------------------- | ------------------------------ |
| Path      | SRv6 visits waypoints        | Dedicated fibre or wavelength  |
| Bandwidth | HTB reserves average rate    | Dedicated timeslot or spectrum |
| Isolation | Statistical — shared buffers | Physical — separate resources  |

You will see occasional retransmit spikes in the iperf output — this is normal. The path guarantee holds: traffic always visits the waypoint. The bandwidth guarantee is statistical: average rate is protected, but TCP dynamics cause short-term variance.

> **This is a simplified model** — it illustrates the concepts of path and bandwidth contracts.

---

# The slice controller

`SliceController` wraps the SRv6 and OVS steps from the earlier labs into three operations:

```python
sc = SliceController(net, ingress=s1, peer=s2, link_bw=10)
sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2")

sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)  # install queue + route
sc.status()    # show reserved and available bandwidth
sc.teardown("premium")  # remove queue + route
```

Open `slice_controller.py` and find these key methods before you start the exercises:

- `_add_queue()` — reserves bandwidth on the bottleneck link
- `_install_srv6_route()` — programs the SRv6 encap route on the source host
- `_build_segments()` — turns the chain list into a segment list
- `_check_admission()` — enforces the bandwidth budget before provisioning

---

<!-- _class: compact -->

# Before you start

| Terminal      | Purpose                                               |
| ------------- | ----------------------------------------------------- |
| 1 — Mininet   | run the demo and exercises                            |
| 2 — h1 log    | `tail -F /tmp/iperf_h1.log`                           |
| 3 — h3 log    | `tail -F /tmp/iperf_h3.log`                           |
| 4 — mb logger | `tail -F /tmp/mb1_bandwidth.log` or `mb2_packets.log` |

- work from `~/labs/lab4`
- `sudo` is required for Mininet

Key files:

| File                                              | Purpose                                         |
| ------------------------------------------------- | ----------------------------------------------- |
| `slice_controller.py`                             | the controller — read this before the exercises |
| `slice_demo.py`                                   | interactive demo — run this first               |
| `exercise1_skeleton.py` … `exercise3_skeleton.py` | your starting points                            |

---

<!-- _class: divider -->

# The Demo

`sudo python3 slice_demo.py`

---

# Demo overview

The demo walks through four phases — press ENTER to advance:

```text
Phase 1 — Baseline
  h1 sends 8 Mbps to h2 on the direct path.
  mb1 logger is running but SILENT.

Phase 2 — Contention
  h3 joins at 8 Mbps. Both flows share the 10 Mbps bottleneck.
  h1 drops to ~5 Mbps. mb1 logger still SILENT.

Phase 3 — Provision slice
  sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
  h1 recovers to ~8 Mbps. mb1 logger LIGHTS UP.

Phase 4 — Teardown
  sc.teardown("premium")
  h1 drops back to ~5 Mbps. mb1 goes SILENT.
```

> **Watch the mb1 logger** — its state changing in phases 3 and 4 is the path contract being installed and removed.

---

# What the demo proves

When the slice is provisioned, two things change at the same time:

```text
tail -F /tmp/iperf_h1.log        5 Mbps  →  8 Mbps   bandwidth contract
tail -F /tmp/mb1_bandwidth.log    silent  →  traffic  path contract
```

When the slice is torn down, both revert:

```text
tail -F /tmp/iperf_h1.log        8 Mbps  →  5 Mbps   no protection
tail -F /tmp/mb1_bandwidth.log    traffic →  silent   no path enforcement
```

> **Both contracts go together** — provisioning and teardown affect path and bandwidth at the same time, because they are part of the same slice description.

---

# Understanding the mb1 logger

The mb1 logger runs inside mb1's network namespace, counts bytes from h1's source MAC, and reports throughput each second:

```text
[mb1] [12:34:01]   0.00 Mbits/sec
[mb1] [12:34:02]   0.00 Mbits/sec       ← no slice yet
[mb1] [12:34:03]   7.82 Mbits/sec       ← slice provisioned
[mb1] [12:34:04]   7.91 Mbits/sec
```

The logger is running in phases 1 and 2, but silent — traffic is bypassing mb1 entirely because there is no SRv6 route yet. Silence means no steering, not no logger.

---

<!-- _class: independent -->

# Exercise 1

Provision a slice through a different waypoint

---

<!-- _class: independent compact -->

# Exercise 1 — Task

```bash
sudo python3 exercise1_skeleton.py
```

Both mb1 and mb2 loggers will be running before you provision anything.

Provision a single slice:
- source: `h1`, destination: `h2`
- must visit **`mb2`** (not mb1)
- bandwidth guarantee: **6 Mbps**

Before you run anything, predict:

1. `mb1` is connected to the topology — will it see traffic? Why or why not?
2. `h1` is sending at 8 Mbps but the slice only guarantees 6 Mbps — what will the iperf log show?
3. After teardown, both `h1` and `h3` send at 8 Mbps — how much does each get?

> **Hint** The `chain` parameter is a list of waypoint names — look at how `sc.provision()` is called in `slice_demo.py`.

---

<!-- _class: independent compact -->

# Exercise 1 — What to look for

- `mb2` logger lights up; `mb1` stays silent — even though `mb1` is connected to `s2`
- `iperf_h1.log` shows ~6 Mbps, not 8 — the queue enforces the contracted rate, not the sending rate
- after teardown, both loggers go quiet and throughput returns to fair share (~5 Mbps each)

> **SRv6 only visits waypoints you explicitly name** — connecting a host to the topology does not put it in any slice's path.

---

<!-- _class: independent -->

# Exercise 2

Chain ordering and topology awareness

---

<!-- _class: independent compact -->

# Exercise 2 — Task

```bash
sudo python3 exercise2_skeleton.py
```

The controller builds segment lists from whatever chain order you give it — it has no topology awareness.

```text
h1 --.
h3 --+-- s1 --[10Mbps]-- s2 -- s3 -- h2
                           |     |
                          mb1   mb2
```

**`mb1` is on `s2`. `mb2` is on `s3`.** Traffic flows naturally left to right.

**Step 1** — provision with `chain=["mb2", "mb1"]` (mb2 first) — RTT is measured automatically

**Step 2** — teardown, reprovision with `chain=["mb1", "mb2"]` (mb1 first) — RTT measured again

> **Before running** draw the packet path for each order and count how many times each switch is visited.

---

<!-- _class: independent compact -->

# Exercise 2 — The backtracking problem

With `chain=["mb2", "mb1"]` the segment list is `fc00::b2, fc00::b1, fc00::2`.

`mb2` is downstream of `mb1` — visiting it first forces the packet to backtrack:

```text
Wrong order:  h1→s1→s2→s3→mb2→s2→mb1→s2→s3→h2   (s2 visited 3×)
Right order:  h1→s1→s2→mb1→s2→s3→mb2→s3→h2        (no backtracking)
```

The controller accepted both without warning — it just maps names to SIDs.

---

<!-- _class: independent compact -->

# Exercise 2 — What to look for

- the RTT comparison at the end of the script — wrong order should be measurably higher
- both loggers show traffic in both cases — the path contract is enforced either way
- the controller accepted the inefficient order without complaint

> **What information would a controller need to detect backtracking?** It would need to know which switch each waypoint is attached to and the order switches appear along the path — topology awareness the simple controller in this lab does not have.

---

<!-- _class: independent -->

# Exercise 3

Admission control

---

<!-- _class: independent compact -->

# Exercise 3 — Task

```bash
sudo python3 exercise3_skeleton.py
```

The controller tracks reserved bandwidth and rejects requests that would exceed link capacity — first-come-first-served, no priority or preemption.

**Step 1** — provision a premium slice for `h1`: `chain=["mb1"]`, 8 Mbps

**Step 2** — try to provision a slice for `h3` with more bandwidth than remains:
```python
try:
    sc.provision("standard", src="h3", dst="h2", chain=[], bw=???)
except AdmissionError as e:
    print(e)
```
Read the error. What does it tell you about available capacity?

**Step 3** — find a value that fits, provision it, and observe both slices running simultaneously.

> **Hint** `sc.status()` shows reserved and available bandwidth at any point.

---

<!-- _class: independent compact -->

# Exercise 3 — What to look for

- the `AdmissionError` message and what each field says about remaining capacity
- the maximum `h3` can request is link capacity minus reserved — `h3` was already getting roughly that as best-effort, so what does the slice guarantee actually add?
- after both slices are provisioned, the link is fully allocated — the next request fails regardless of priority

**Reflection**

A high-priority emergency slice arrives. Can it preempt the standard slice? Why not?

What information would a smarter controller need to handle this?

> **Further reading** For a multi-agent deep reinforcement learning approach to coordinated slicing and admission control: M. Sulaiman et al., *Coordinated Slicing and Admission Control using Multi-Agent Deep Reinforcement Learning*, IEEE TNSM, Vol. 20(2), June 2023.

---

# Summary

In this lab you:

- observed two TCP flows competing on a 10 Mbps bottleneck without any slice
- provisioned a transport slice that combined an SRv6 path contract with an OVS bandwidth reservation
- saw both contracts take effect together when provisioning, and both removed together on teardown
- found that chain order must match the physical topology — the controller accepted an inefficient order without warning
- triggered an admission control rejection and reasoned about the limits of first-come-first-served policy

> **Labs 3 and 4 together** — Lab 3 showed SRv6 path steering manually and what encapsulation looks like on the wire. Lab 4 combined path steering with bandwidth reservation and exposed where a simple slice controller falls short.
