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
- hit the limits of admission control and reason about smarter policies

> **What to focus on** In this lab, a transport slice combines two things: a path contract (which waypoints traffic must visit) and a bandwidth contract (what rate is reserved). The exercises show how changing the slice changes what waypoint sees traffic, and what happens when a new request exceeds the remaining bandwidth budget.

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

> **What the exercises show** The first exercise changes the slice request and asks which waypoint should light up. The second shows what happens when the controller runs out of reservable bandwidth.

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
| `exercises/part1.py`                              | waypoint-selection exercise                     |
| `exercises/part2.py`                              | admission-control exercise                      |

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

<!-- _class: divider -->

# Exercises

From guided demo to independent slice requests

---

<!-- _class: independent compact -->

# Files you will use

- `exercises/part1.py` — provision a slice through `mb2` with a 6 Mbps guarantee
- `exercises/part2.py` — trigger admission control and find a bandwidth that fits
- `slice_demo.py` — reference behavior from the guided section
- `slice_controller.py` — controller methods behind the exercise TODOs

Solutions live separately:

- `solutions/part1.py`
- `solutions/part2.py`

> **Work from `~/labs/lab4`** and edit the exercise file before you run each part.

---

<!-- _class: independent -->

# Exercise 1

Provision a slice through a different waypoint

---

<!-- _class: independent compact -->

# Exercise 1 — Tasks

1. Open `exercises/part1.py`.
2. Fill in the `sc.provision(...)` TODO so the slice goes from `h1` to `h2`, visits `mb2`, and guarantees `6` Mbps.
3. Fill in the `sc.teardown(...)` TODO with the same slice name.
4. Run:

   ```bash
   sudo python3 exercises/part1.py
   ```

Before you press ENTER in the script, predict:

1. `mb1` is connected to the topology — will it see traffic? Why or why not?
2. `h1` sends at 8 Mbps but the slice guarantees only 6 Mbps — what should `iperf_h1.log` show?
3. After teardown, both `h1` and `h3` send at 8 Mbps — how much should each get?

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

Admission control

---

<!-- _class: independent compact -->

# Exercise 2 — Capacity Check

The bottleneck link is `10` Mbps.

If the controller provisions a premium slice for `h1` with `8` Mbps, only `2` Mbps remains reservable for new slices.

That means:

- a request for more than `2` Mbps must be rejected
- a request for `2` Mbps or less can be accepted
- best-effort traffic may still use leftover capacity, but that is not the same as a reservation

> **Keep the distinction clear** Best-effort throughput is opportunistic. A slice bandwidth contract is explicit and tracked by the controller.

---

<!-- _class: independent compact -->

# Exercise 2 — Tasks

1. Open `exercises/part2.py`.
2. Fill in TODO 1 to provision a premium slice for `h1` through `mb1` with `8` Mbps.
3. Fill in TODO 2 with a request for `h3` that is too large, and catch the `AdmissionError`.
4. Fill in TODO 3 with a value that fits in the remaining budget.
5. Run:

   ```bash
   sudo python3 exercises/part2.py
   ```

As you work, use `sc.status()` to compare reserved and available bandwidth with the request you are trying to make.

---

<!-- _class: independent compact -->

# Exercise 2 — What to look for

- the `AdmissionError` message and what each field says about remaining capacity
- the maximum `h3` can request is link capacity minus reserved — `h3` was already getting roughly that as best-effort, so what does the slice guarantee actually add?
- after both slices are provisioned, the link is fully allocated — the next request fails regardless of priority

**Reflection**

A high-priority emergency slice arrives. Can it preempt the standard slice? Why not?

What information would a smarter controller need to handle this?

> **Further reading** For a multi-agent deep reinforcement learning approach to coordinated slicing and admission control: M. Sulaiman et al., *Coordinated Slicing and Admission Control using Multi-Agent Deep Reinforcement Learning*, IEEE TNSM, Vol. 20(2), June 2023.

---

<!-- _class: independent compact -->

# Hints

- **Exercise 1 path** — the slice should name `mb2`, not `mb1`
- **Exercise 1 teardown** — use the same slice name you provisioned
- **Exercise 2 budget** — `10 Mbps total - 8 Mbps reserved = 2 Mbps remaining`
- **Exercise 2 status check** — `sc.status()` tells you how much bandwidth is already reserved and how much is still available

---

# Summary

In this lab you:

- observed two TCP flows competing on a 10 Mbps bottleneck without any slice
- provisioned a transport slice through a different waypoint and saw only the named waypoint receive traffic
- saw path and bandwidth contracts take effect together when provisioning, and both removed together on teardown
- triggered an admission control rejection and reasoned about the limits of first-come-first-served policy

> **Labs 3 and 4 together** — Lab 3 showed manual SRv6 path steering and what encapsulation looks like on the wire. Lab 4 moved up one level: describe a slice, then watch the controller realize the path and bandwidth contracts for you.
