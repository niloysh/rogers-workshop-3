---
marp: true
theme: workshop-readable
paginate: true
---

<!-- _class: title -->

<span class="tag">Lab 4</span>

# Transport Slicing
# with SRv6 and OVS Queues

Rogers Executive Workshop 3 — Transport Network Programmability

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

> **What to focus on** A transport slice is not just a rate limit and it is not just a routing rule. It is a combined contract: *this traffic will visit these functions, in this order, at this guaranteed rate.* Neither component alone is sufficient.

---

# From Labs 1 to 4

| Lab   | What you learned             | What Lab 4 reuses                                            |
| ----- | ---------------------------- | ------------------------------------------------------------ |
| Lab 1 | OVS rules, match and action  | queue-based bandwidth treatment on the bottleneck            |
| Lab 2 | ONOS REST API, topology view | understanding the control plane — not used directly in Lab 4 |
| Lab 3 | SRv6 encap route programming | path steering through an explicit service chain              |
| Lab 4 | **This lab**                 | combines all three into one slice controller                 |

> **What changes in Lab 4** Instead of configuring each mechanism separately, you describe a slice and the controller realizes it. The plumbing is hidden. The contracts are explicit.

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

A transport slice is a service-level request with two components that must both be active:

**Path contract — enforced by SRv6**
Traffic is wrapped in an outer IPv6+SRH packet that names each waypoint explicitly. The kernel processes the SRH at each hop, advancing to the next segment. No waypoint can be skipped.

**Bandwidth contract — enforced by OVS HTB queues**
An HTB queue on the bottleneck port guarantees a minimum rate for the slice's traffic. Best-effort flows get whatever is left.

> **Why both are needed** A queue without SRv6 protects bandwidth but lets traffic skip service functions. SRv6 without a queue enforces the path but not the rate. A slice needs both.

---

# Service request vs realized slice

These are not the same thing:

**What you request**
```python
sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
```
A service-level description: source, destination, waypoints, rate.

**What the controller realizes**
- an SRv6 segment list: `fc00::b1, fc00::2`
- an OVS HTB queue on s1-eth3: min-rate=8 Mbps, max-rate=8 Mbps
- an ovs-ofctl flow rule: h1 MAC -> set_queue:1, normal
- an ip route on h1: `10.0.0.2 encap seg6 mode encap segs ...`

> **The service request is abstract. The realization is concrete.** The controller translates one into the other.

---

# Soft slicing

The guarantees in this lab are **soft**, not hard:

|           | Soft (this lab)              | Hard                           |
| --------- | ---------------------------- | ------------------------------ |
| Path      | SRv6 always visits waypoints | Dedicated fibre or wavelength  |
| Bandwidth | HTB guarantees average rate  | Dedicated timeslot or spectrum |
| Isolation | Statistical — shared buffers | Physical — separate resources  |

You will see occasional retransmit spikes in the iperf logs. This is expected — it is what soft slicing looks like in practice. The path guarantee is hard: traffic always visits the waypoint. The bandwidth guarantee is soft: average rate is protected but TCP dynamics cause transient variance.

> **This is production-realistic.** Most commercial network slicing — including 5G — is soft slicing.

---

# The slice controller

Lab 4 uses a `SliceController` class that abstracts the plumbing:

```python
sc = SliceController(net, ingress=s1, peer=s2, link_bw=10)
sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2")

# Provision: installs OVS queue + SRv6 route atomically
sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)

# Status: shows reserved and available bandwidth
sc.status()

# Teardown: removes queue + route atomically
sc.teardown("premium")
```

Open `slice_controller.py` and find these key methods:

- `_add_queue()` — reserves bandwidth on the bottleneck
- `_install_srv6_route()` — programs the SRv6 encap route on the source host
- `_build_segments()` — turns the chain list into a SRv6 segment list
- `_check_admission()` — enforces the bandwidth budget

---

<!-- _class: compact -->

# Before you start

For this lab:

- work from `~/labs/lab4`
- keep four terminals open

| Terminal      | Purpose                                               |
| ------------- | ----------------------------------------------------- |
| 1 — Mininet   | Run the demo and exercises                            |
| 2 — h1 log    | `tail -F /tmp/iperf_h1.log`                           |
| 3 — h3 log    | `tail -F /tmp/iperf_h3.log`                           |
| 4 — mb logger | `tail -F /tmp/mb1_bandwidth.log` or `mb2_packets.log` |

Files in `~/labs/lab4`:

```
slice_controller.py     the controller -- read this to understand the API
slice_demo.py           interactive demo -- run this first
exercise1_skeleton.py   your starting point for each exercise
exercise2_skeleton.py
exercise3_skeleton.py
```

---

<!-- _class: divider -->

# The Demo

`sudo python3 slice_demo.py`

---

# Demo overview

The demo walks through four phases. Press ENTER to advance.

```
Phase 1 -- Baseline
          h1 sends 8 Mbps to h2, direct path.
          mb1 logger is running but SILENT.

Phase 2 -- Contention
          h3 joins at 8 Mbps. Both flows share the 10 Mbps bottleneck.
          h1 drops to ~5 Mbps. mb1 logger still SILENT.

Phase 3 -- Provision slice
          sc.provision("premium", src="h1", dst="h2", chain=["mb1"], bw=8)
          h1 recovers to ~8 Mbps. mb1 logger LIGHTS UP.

Phase 4 -- Teardown
          sc.teardown("premium")
          h1 drops to ~5 Mbps. mb1 goes SILENT.
```

> **Watch for** the mb1 logger changing state in phases 3 and 4. That is the SRv6 path contract being enforced and removed.

---

# What the demo proves

When the slice is provisioned, two things change simultaneously:

```
tail -F /tmp/iperf_h1.log       5 Mbps  ->  8 Mbps   bandwidth contract
tail -F /tmp/mb1_bandwidth.log   silent  ->  traffic  path contract
```

When the slice is torn down, both revert simultaneously:

```
tail -F /tmp/iperf_h1.log       8 Mbps  ->  5 Mbps   no protection
tail -F /tmp/mb1_bandwidth.log   traffic ->  silent   no path enforcement
```

> **The key observation** Provisioning and teardown are atomic — both contracts go together. This is what makes it a slice rather than two separate configurations.

---

# Understanding the mb1 logger

The mb1 bandwidth logger runs inside mb1's network namespace. It counts bytes with h1's source MAC and reports throughput every second:

```
[mb1] [12:34:01]   0.00 Mbits/sec
[mb1] [12:34:02]   0.00 Mbits/sec       <- no slice yet
[mb1] [12:34:03]   7.82 Mbits/sec  <- slice traffic
[mb1] [12:34:04]   7.91 Mbits/sec  <- slice traffic
```

The logger is silent in phases 1 and 2 even though it is running — this is the evidence that traffic bypasses mb1 without SRv6. Silence is not absence of the logger. It is absence of the slice.

---

<!-- _class: divider -->

# Exercise 1

Provision a slice through a different waypoint

---

# Exercise 1 — Task

```
sudo python3 exercise1_skeleton.py
```

The topology has both mb1 and mb2. Both loggers will be running before you provision anything.

Your task: provision a single slice with these requirements:
- source: h1, destination: h2
- the slice must visit **mb2** (not mb1)
- bandwidth guarantee: **6 Mbps**

**What to observe:**
- Which logger lights up when the slice is provisioned?
- What happens to the other logger?
- After teardown, what do both logs show?

> **Hint** Look at how `sc.provision()` is called in `slice_demo.py`. The `chain` parameter is a list of waypoint names.

---

# Exercise 1 — What to think about

Before you run anything, predict the answers:

1. mb1 is connected to the topology. Will it see traffic? Why or why not?

2. h1 is sending at 8 Mbps but the slice guarantees 6 Mbps. What will the iperf log show?

3. After teardown, h1 and h3 both send at 8 Mbps. How much does each get?

> **The key insight** SRv6 only visits the waypoints you explicitly name in `chain=[]`. Connecting a host to the topology does not put it in any slice's path. The path contract is exact.

---

# Exercise 1 — What a good answer looks like

A strong solution will:

- provision the slice with exactly one `sc.provision()` call
- show mb2 logger showing traffic and mb1 logger staying silent simultaneously
- explain why mb1 is silent even though it is connected to s2
- observe that after teardown both loggers go quiet and throughput returns to fair share

> **Evidence matters** The iperf log and the mb2 logger together are the proof. The provision command output alone is not enough — it only shows what the controller intended, not what was delivered.

---

<!-- _class: divider -->

# Exercise 2

Chain ordering and topology awareness

---

# Exercise 2 — Background

```
sudo python3 exercise2_skeleton.py
```

The slice controller builds segment lists from whatever chain order you give it. It has no topology awareness — it does not know which switch each waypoint is attached to.

```
h1 --.
h3 --+-- s1 --[10Mbps]-- s2 -- s3 -- h2
                           |     |
                          mb1   mb2
```

**mb1 is on s2. mb2 is on s3.** Traffic flows naturally left to right: s1 -> s2 -> s3.

---

# Exercise 2 — Task

Your task: provision a slice through **both** mb1 and mb2.

**Step 1** — provision with `chain=["mb2", "mb1"]` (mb2 first)
- the built-in `measure_rtt()` helper runs automatically
- both loggers will show traffic — but is the path efficient?

**Step 2** — teardown and reprovision with `chain=["mb1", "mb2"]` (mb1 first)
- RTT is measured again automatically
- the script prints a comparison at the end

> **Hint** Draw the actual packet path for each chain order on the topology diagram above. Count how many times each switch is visited.

---

# Exercise 2 — The backtracking problem

With `chain=["mb2", "mb1"]` the segment list is `fc00::b2, fc00::b1, fc00::2`.

The packet visits mb2 first — but mb2 is on s3, downstream of mb1 on s2. To then visit mb1 the packet must travel backwards:

```
Wrong order:
h1->s1->s2->s3->mb2->s2->mb1->s2->s3->h2   (s2 visited 3 times)

Correct order:
h1->s1->s2->mb1->s2->s3->mb2->s3->h2        (no backtracking)
```

> **What this shows** The controller accepted both orders without complaint. It has no topology awareness — it just maps names to SIDs. A production controller needs to know the physical location of each waypoint to build efficient segment lists.

---

# Exercise 2 — What a good answer looks like

A strong solution will:

- show the RTT comparison printed at the end of the script
- draw the packet path for each chain order and count switch visits
- explain why the controller accepted the wrong order without warning
- answer: what information would the controller need to detect backtracking?

> **The connection to research** This limitation — topology-blind segment list construction — is one of the problems that motivates smarter slice controllers. A controller with topology awareness can validate chain order before provisioning.

---

<!-- _class: divider -->

# Exercise 3

Admission control

---

# Exercise 3 — Background

```
sudo python3 exercise3_skeleton.py
```

The slice controller tracks total reserved bandwidth and rejects new slices that would exceed link capacity.

```python
class AdmissionError(Exception):
    """Raised when a slice request exceeds available bandwidth."""
    pass
```

This is **first-come-first-served** admission control — the simplest possible policy. It protects committed slices but has no concept of priority, preemption, or demand prediction.

---

# Exercise 3 — Task

**Step 1** — provision a premium slice for h1: `chain=["mb1"]`, 8 Mbps

**Step 2** — try to provision a slice for h3 with more bandwidth than is available:
```python
try:
    sc.provision("standard", src="h3", dst="h2", chain=[], bw=???)
except AdmissionError as e:
    print(e)
```
Read the error message. What does it tell you about available capacity?

**Step 3** — find a bandwidth value that fits. Provision it and observe both slices running.

> **Hint** `sc.status()` shows reserved and available bandwidth at any point.

---

# Exercise 3 — Reflection

After completing the exercise, think about these questions:

- The link is now fully allocated. What happens to the next request, regardless of priority?

- A high-priority emergency slice arrives. Can it preempt the standard slice? Why not?

- What information would a smarter controller need to make better decisions?

**Further reading**

Our controller makes a binary accept/reject decision with no knowledge of traffic priorities, demand patterns, or future requests. For a multi-agent deep reinforcement learning approach to coordinated slicing and admission control:

> M. Sulaiman, A. Moyyedi, M. Ahmadi, M. A. Salahuddin, R. Boutaba and A. Saleh. *Coordinated Slicing and Admission Control using Multi-Agent Deep Reinforcement Learning.* IEEE Transactions on Network and Service Management, Vol. 20(2), pp. 1110-1124, June 2023.

---

# Exercise 3 — What a good answer looks like

A strong solution will:

- show the `AdmissionError` output and explain what each field means
- correctly calculate the maximum bandwidth h3 can request (link capacity minus reserved)
- observe that h3 was already getting roughly that amount as best-effort — and explain what the slice guarantee adds
- answer the preemption question: first-come-first-served has no mechanism to remove a committed slice

> **The larger point** Admission control is not just about saying no. It is about maintaining commitments to existing slices while fairly allocating remaining capacity. Simple policies fail under dynamic demand — which is why the research cited above matters.

---

<!-- _class: divider -->

# Summary

---

# What you did in Lab 4

- Observed contention between two TCP flows sharing a 10 Mbps bottleneck
- Provisioned a transport slice combining SRv6 path enforcement and OVS bandwidth guarantee
- Confirmed that both contracts are enforced atomically — provisioning and teardown affect both simultaneously
- Discovered that chain order must match the physical topology, and that a topology-blind controller accepts inefficient orders without warning
- Triggered an admission control rejection and reasoned about the limits of first-come-first-served policy

**The larger picture**

Labs 3 and 4 together show the full arc: Lab 3 introduced SRv6 path steering manually and showed what encapsulation looks like on the wire. Lab 4 combined path steering with bandwidth reservation, abstracted both into a slice controller, and exposed the limitations that motivate smarter systems.

---

<!-- _class: compact -->

# Quick reference — Lab 4 commands

```python
# Slice controller API
sc = SliceController(net, ingress=s1, peer=s2, link_bw=10)
sc.configure_srv6("h1", "h2", "h3", "mb1", "mb2")
sc.provision("name", src="h1", dst="h2", chain=["mb1"], bw=8)
sc.teardown("name")
sc.status()

# Admission control
from slice_controller import AdmissionError
try:
    sc.provision(...)
except AdmissionError as e:
    print(e)
```

```bash
# Watch logs
tail -F /tmp/iperf_h1.log
tail -F /tmp/iperf_h3.log
tail -F /tmp/mb1_bandwidth.log
tail -F /tmp/mb2_packets.log

# Inspect OVS state from Mininet CLI
mininet> sh ovs-ofctl dump-flows s1
mininet> sh ovs-vsctl list queue
mininet> sh tc class show dev s1-eth3

# Check SRv6 route
mininet> h1 ip route show
mininet> h1 ip -6 neigh show
```