---
marp: true
theme: workshop-readable
paginate: true
---

<!-- _class: title -->

<span class="tag">Lab 4</span>

# Transport Slice Requests
# with ONOS and SRv6

Rogers Executive Workshop 3 — Transport Network

---

<!-- _class: divider -->

# Getting Started

What this lab teaches and how to work through it

---

# Lab 4 at a glance

In this lab you will:

- observe contention on a shared bottleneck
- run one guided demo of a bandwidth-protected slice
- express slice requirements by editing a small `SLICE_REQUEST`
- ask for a low-latency path, a service chain, and an admissible bandwidth request
- watch the controller realize each request with SRv6 routes and, when needed, an OVS queue

> **What to focus on** In this lab, you are not programming the controller directly. You describe the service you want, and the controller realizes it.

---

# From earlier labs to Lab 4

| Lab    | What you learned                 | What Lab 4 reuses                             |
| ------ | -------------------------------- | --------------------------------------------- |
| Lab 1  | OVS and match/action forwarding  | OVS queues to reserve bandwidth               |
| Lab 2  | ONOS as the control plane        | ONOS-managed switches                         |
| Lab 3  | SRv6 steering with ONOS          | service chaining plus low-latency path steering |
| Lab 4  | **this lab**                     | combines these into one slice-request workflow |

> **The change in Lab 4** You no longer type low-level queue or SRv6 commands in the exercises. You edit a short request file.

---

# Lab 4 topology

```text
                               mb1   mb2
                                |     |
                                +--+--+
                                   |
    h1 ---.
          +-- s1 --[30ms, 10Mbps]--- s2 --- h2
    h3 ---'   |                      |
              +---------[5ms]--- r1 ---[5ms]
```

| Node | Role                    | IPv4     | SID / Note                     |
| ---- | ----------------------- | -------- | ------------------------------ |
| h1   | source                  | 10.0.0.1 | `fc00::1`                      |
| h2   | destination             | 10.0.0.2 | `fc00::2`                      |
| h3   | competing flow          | 10.0.0.3 | `fc00::3`                      |
| mb1  | telemetry monitor       | 10.0.0.4 | `fc00::b1`                     |
| mb2  | security inspector      | 10.0.0.5 | `fc00::b2`                     |
| r1   | alternate-path router   | 10.0.0.6 | `fc00::a1` / `fc00::a2`        |

> **Key idea** The direct `s1-s2` path is slower and bandwidth-limited. The path via `r1` is faster, but ONOS does not choose it by default.

---

# Two contracts in this lab

Every slice request can affect two things:

**Path / service contract**
- implemented with SRv6
- decides which path traffic takes
- decides which waypoints traffic must visit

**Bandwidth contract**
- implemented with an OVS HTB queue
- reserves bandwidth on the direct bottleneck when requested

> **Simple rule** SRv6 decides *where* traffic goes. The queue decides *how much bottleneck bandwidth* is reserved.

---

# What you edit

The learner-facing object is always:

```python
SLICE_REQUEST = {
    "name": "premium",
    "src": "h1",
    "dst": "h2",
    "latency_objective": "standard",
    "bandwidth_mbps": 8,
    "waypoints": ["mb1"],
}
```

You only edit this block in the exercise request files.

> **Do not start in `_internal/`** That folder contains the controller and helper code. The pedagogical focus is the request.

---

# What each field means

| Field | Meaning | Notes |
| ----- | ------- | ----- |
| `latency_objective` | path objective | `"standard"` or `"low"` |
| `bandwidth_mbps` | reserved bandwidth | `0` means best-effort |
| `waypoints` | ordered service functions | e.g. `["mb1"]`, `["mb1", "mb2"]` |

Important details:

- `latency_objective="low"` is a qualitative goal, not a numeric latency guarantee
- in this topology, `"low"` is realized by steering via `r1`
- `waypoints` lists the service functions in order
- learners never need to type `r1` or `r1b` directly

---

# Request vs realization

**What you request**

```python
SLICE_REQUEST = {
    "name": "express",
    "src": "h1",
    "dst": "h2",
    "latency_objective": "low",
    "bandwidth_mbps": 0,
    "waypoints": ["mb1"],
}
```

**What the controller realizes**

- forward path: `h1 -> r1 -> mb1 -> h2`
- reverse path: `h2 -> mb1 -> r1b -> h1`
- queue guarantee: `none`

> **This is the abstraction boundary** Learners edit the request. The controller expands it into forward and reverse SRv6 routes and, if needed, a bandwidth reservation.

---

# What the middleboxes do

`mb1` = telemetry monitor
- reports observed slice throughput
- helps confirm that traffic really visited the waypoint

`mb2` = security inspector
- inspects the inner flow
- reports `[OK]` or `[ALERT]`
- gives Exercise 2 a clearly different service function

> **The logs are part of the lesson** If a middlebox log lights up, the request's path and waypoint requirements are being realized.

---

<!-- _class: compact -->

# Before you start

Open fresh terminals and work from:

```bash
cd ~/labs/lab4
```

Suggested terminals:

| Terminal | Purpose |
| -------- | ------- |
| 1 | demo or exercise runner |
| 2 | ONOS CLI |
| 3 | `tail -F /tmp/iperf_h1.log` |
| 4 | `tail -F /tmp/iperf_h3.log` |
| 5 | middlebox log: `tail -F /tmp/mb1_bandwidth.log` or `tail -F /tmp/mb2_security.log` |

---

<!-- _class: compact -->

# ONOS prerequisites

Make sure ONOS is running, then confirm these apps:

```text
onos> app activate org.onosproject.openflow
onos> app activate org.onosproject.fwd
onos> app activate org.onosproject.proxyarp
```

Then enable IPv6 forwarding in `fwd`:

```text
onos> cfg set org.onosproject.fwd.ReactiveForwarding ipv6Forwarding true
```

> **Without `ipv6Forwarding true`** the switches will not forward the outer SRv6 IPv6 packets correctly.

---

# Files you will use

| File | Purpose |
| ---- | ------- |
| `demo/run.py` | instructor-led guided demo runner |
| `demo/slice_request.py` | fixed request to inspect during the demo |
| `exercises/part1/run.py` | low-latency exercise runner |
| `exercises/part1/slice_request.py` | file learners edit for Part 1 |
| `exercises/part2/run.py` | service-chain exercise runner |
| `exercises/part2/slice_request.py` | file learners edit for Part 2 |
| `exercises/part3/run.py` | admission-control exercise runner |
| `exercises/part3/slice_request.py` | file learners edit for Part 3 |

Solutions:

- `solutions/part1/slice_request.py`
- `solutions/part2/slice_request.py`
- `solutions/part3/slice_request.py`

---

<!-- _class: divider -->

# The Demo

One guided example before the exercises

---

# Run the demo

From `~/labs/lab4`:

```bash
sudo python3 demo/run.py
```

This demo uses a fixed request in:

```text
demo/slice_request.py
```

> **What it teaches** A slice can keep the standard path, require a waypoint, and reserve bandwidth at the same time.

---

# Demo phases

The demo walks through four phases:

```text
Phase 1 — Baseline
  h1 sends to h2 on the direct path.
  mb1 is silent.

Phase 2 — Contention
  h3 joins.
  h1 and h3 share the 10 Mbps bottleneck.

Stop and inspect the request
  the runner asks you to open `demo/slice_request.py`
  and predict what will happen before the slice is applied.

Phase 3 — Slice active
  h1 still uses the direct path,
  but now traffic must visit mb1
  and h1 gets an 8 Mbps guarantee.

Phase 4 — Teardown
  the path and bandwidth guarantees disappear.
```

---

# What the demo proves

When the slice is active, two things change:

```text
/tmp/iperf_h1.log         ~5 Mbps  ->  ~8 Mbps
/tmp/mb1_bandwidth.log    silent   ->  traffic
```

That means:

- the bandwidth contract is active
- the waypoint contract is active

When the slice is removed, both revert.

> **One request, two effects** The slice changes both the path/service behavior and the bandwidth treatment.

---

<!-- _class: divider -->

# Exercises

Each part follows the same simple workflow

---

# Exercise workflow

For every part:

1. run the part's `run.py`
2. the runner starts the lab and prints which `slice_request.py` to edit
3. edit only the `SLICE_REQUEST` block
4. come back and press ENTER
5. the runner reloads your request from disk and validates it

If the request is invalid, the runner prints the error and waits for you to edit the file again.

> **This is intentional** You should be thinking about the service request, not the Mininet or controller boilerplate.

---

# Exercise 1

Low-latency path request

---

<!-- _class: compact -->

# Exercise 1 — Goal and command

Goal:

- ask for a lower-latency service from `h1` to `h2`
- keep the telemetry monitor in the chain
- keep it best-effort

Run:

```bash
sudo python3 exercises/part1/run.py
```

Edit when prompted:

```text
exercises/part1/slice_request.py
```

> **What to predict first** If `h1` moves off the direct bottleneck, what should happen to `h3`'s throughput?

---

<!-- _class: compact -->

# Exercise 1 — What to look for

- `h1` should move to the faster path via `r1`
- `h3` should remain on the direct `s1-s2` bottleneck
- `mb1` should still log the slice traffic
- no queue is reserved, so this is a path objective, not a bandwidth guarantee

> **Concept** `latency_objective="low"` changes the path realization, not the requested bandwidth.

---

# Exercise 2

Service-chain request

---

<!-- _class: compact -->

# Exercise 2 — Goal and command

Goal:

- keep the standard path
- keep the traffic best-effort
- satisfy this service requirement:

```text
telemetry monitor -> security inspector -> destination
```

Run:

```bash
sudo python3 exercises/part2/run.py
```

Edit when prompted:

```text
exercises/part2/slice_request.py
```

---

<!-- _class: compact -->

# Exercise 2 — What to look for

- both `mb1` and `mb2` logs should light up
- `h1` and `h3` should still compete on the direct bottleneck
- the latency objective should remain standard

> **Concept** `waypoints` expresses the service chain. It does not, by itself, ask for a lower-latency path or a bandwidth reservation.

---

# Exercise 3

Admission control

---

<!-- _class: compact -->

# Exercise 3 — Goal and command

The runner first installs a fixed premium request for `h1`:

```python
{
    "latency_objective": "standard",
    "bandwidth_mbps": 8,
    "waypoints": ["mb1"],
}
```

Then you edit a competing request for `h3`.

Run:

```bash
sudo python3 exercises/part3/run.py
```

Edit when prompted:

```text
exercises/part3/slice_request.py
```

---

<!-- _class: compact -->

# Exercise 3 — Capacity reasoning

The direct bottleneck capacity is `10 Mbps`.

If `8 Mbps` is already reserved for the premium slice, then:

```text
10 Mbps total - 8 Mbps reserved = 2 Mbps remaining
```

So:

- a new reservation above `2 Mbps` must be rejected
- `2 Mbps` or less can be admitted
- best-effort traffic is not the same as a reservation

> **Concept** Admission control is about finite resources. A request can be valid in structure and still be rejected by policy.

---

<!-- _class: compact -->

# Troubleshooting

| Symptom | What to check |
| ------- | ------------- |
| switches do not forward SRv6 traffic | `ipv6Forwarding true` in ONOS |
| request will not load | edit only `SLICE_REQUEST` and keep it a Python dictionary |
| middlebox log stays idle | confirm the request really includes that waypoint |
| low-latency result not visible | check whether the request asks for `latency_objective: "low"` |
| admission request rejected | compare requested bandwidth with remaining capacity |

---

# Summary

In this lab you:

- used a learner-facing request to describe a transport slice
- saw how path objectives, service chains, and bandwidth requests are separate ideas
- used SRv6 to realize path and waypoint requirements
- used an OVS queue to realize a bandwidth contract
- saw admission control reject a request that exceeded the remaining budget

> **Big picture** The value of slicing is not the syntax of the controller API. It is the ability to describe the service you want and reason about how the network realizes it.
