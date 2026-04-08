---
marp: true
theme: workshop-readable
paginate: true
---

<!-- _class: title -->

<span class="tag">Lab 4</span>

# Transport Slice Controller

Rogers Executive Workshop 3 — Transport Network Programmability

---

<!-- _class: divider -->

# Getting Started

Using Labs 1 to 3 together

---

# Lab 4 at a glance

In this lab you will:

- start a topology with three transport nodes and three service functions
- inspect how a slice controller combines ONOS, SRv6, and queueing
- provision two example slices and compare how they are realized
- observe how intent changes transport treatment
- design two final slices from a short customer brief

> **Goal** Use one controller command to realize a simple notion of transport network slicing from service requirements.

---

# From Labs 1 to 4

| Lab   | What you learned              | What Lab 4 reuses                                  |
| ----- | ----------------------------- | -------------------------------------------------- |
| Lab 1 | OVS rules, match + action     | queue-based bandwidth treatment                    |
| Lab 2 | ONOS REST API, topology view  | topology and attachment discovery from the control plane |
| Lab 3 | SRv6 encap route programming  | path steering through an explicit service chain    |

> **What changes in Lab 4** Instead of configuring each mechanism separately, you ask for a slice and let the controller realize it.

---

# What a slice request says

In this lab, a slice request has four parts:

- **src / dst** — which endpoints are communicating
- **chain** — which service functions the traffic must visit
- **intent** — what transport policy we want
- **bandwidth** — what rate should be reserved

That is the service-level view of the slice.

---

# What the controller realizes

The controller translates that request into:

- a realized transport path across the ONOS-discovered topology
- an SRv6 segment list
- a queue reservation on the ingress side
- middlebox-specific configuration

> **Key idea** The service request is abstract. The realized path and segment list are concrete.

---

# Workshop simplification

For this workshop version, we use one simplifying rule:

> Only one active slice may use a given ordered endpoint pair `src -> dst`.

That means:

- one slice can use `h1 -> h2`
- another slice can use `h3 -> h2`
- but two concurrent slices cannot both use `h1 -> h2`

> **Why we do this** It keeps the classifier simple so the lab stays focused on slicing, not flow-classification design.

---

# Revised Lab 4 topology

```text
               mb1
                |
 h1 ── r1 ───── r2 ── h2
        \       /
         \     /
          \   /
            r3 ── h3
           /  \
         mb2  mb3
```

- `r1`, `r2`, and `r3` are transport nodes discovered by ONOS
- `h1`, `h2`, and `h3` are workshop endpoints
- `mb1`, `mb2`, and `mb3` are service functions attached at the edge

> **Why this topology matters** The triangle core gives more than one transport path, so the intent field can affect the realization.

---

# Available service functions

Use the revised controller:

```bash
python3 slice_controller_v2.py list-mbs
```

Expected output:

```text
  mb1  fc00::b1  throughput monitor
  mb2  fc00::b2  firewall policy
  mb3  fc00::b3  flow logger
```

> **How to think about these** The chain names the service functions. The intent does not choose the services; it chooses how transport is realized between them.

---

# What the intents mean

In this lab:

- **`low-latency`** means prefer the shortest realized transport path
- **`best-effort`** means prefer a longer alternate path when one exists

Both intents still use the same overall controller workflow:

- discover topology
- choose a path
- build an SRv6 segment list
- apply bandwidth treatment

---

# Keep these open

Keep four terminals open:

1. **Mininet** — topology, host commands, `pingall`
2. **ONOS CLI** — inspect devices, links, and flows
3. **Shell** — run `slice_controller_v2.py`, `preflight_check.py`, `verify_lab4.py`
4. **Host shells** — open `h1`, `h3`, or middleboxes with `./enter_host.sh`

---

# Start the topology

```bash
sudo python3 lab4_topology.py
```

When the topology starts, it also:

- configures SRv6 on all hosts and middleboxes
- starts the middlebox services
- starts HTTP services on `h2` on ports `80` and `8080`
- starts UDP receivers on `h2` on ports `5004` and `5005`

---

# Bring ONOS online

Connect to the ONOS CLI:

```bash
ssh -p 8101 -o HostKeyAlgorithms=+ssh-rsa onos@localhost
# password: rocks
```

Activate the required apps:

```text
onos> app activate org.onosproject.openflow
onos> app activate org.onosproject.fwd
```

---

# Sanity-check the environment

From Mininet:

```text
mininet> pingall
```

From ONOS:

```text
onos> devices
onos> links
onos> hosts
```

From your shell:

```bash
python3 preflight_check.py
python3 slice_controller_v2.py list-mbs
```

> **You should see** Three transport nodes, the discovered hosts, and the three available service functions.

---

<!-- _class: divider -->

# Traffic checks

Where the performance evidence comes from

---

# h2 already has demo receivers running

`lab4_topology.py` starts two UDP receiver processes on `h2`:

```text
h2:5004  primary service test
h2:5005  secondary service test
```

The receiver prints:

- throughput
- latency
- jitter
- packet loss

If you want to watch the live output directly, use:

```bash
tail -f /tmp/h2_receiver5004.log
tail -f /tmp/h2_receiver5005.log
```

> **Why this matters** The controller tells you what it intended to provision. The receiver output tells you what transport performance was actually delivered.

---

# Baseline test — primary flow

Open a shell in `h1`:

```bash
./enter_host.sh h1
```

Run a short UDP test to `h2:5004`:

```bash
python3 sender.py --host 10.0.0.2 --port 5004 --rate 3 --duration 20 --label primary
```

> **What to observe** Watch the receiver-side throughput, latency, jitter, and loss in `/tmp/h2_receiver5004.log`. This is your baseline measurement for the premium service before any slice is provisioned.

---

# Baseline test — competing flow

In another shell, open `h3`:

```bash
./enter_host.sh h3
```

Run a second UDP flow to `h2:5005`:

```bash
python3 sender.py --host 10.0.0.2 --port 5005 --rate 8 --duration 20 --label secondary
```

> **Why we use `h3` here** It gives us a second source host, which fits the workshop simplification for concurrent slices.

---

<!-- _class: divider -->

# The Controller

Read `provision` as a pipeline

---

# Read the controller in stages

Open `slice_controller_v2.py` and find these pieces:

- `build_topology_from_onos()` — builds the transport graph from ONOS links
- `select_path()` — maps intent to a path policy
- `compute_realized_transport()` — computes a realized path for each service hop
- `build_srv6_segments()` — turns that realization into an SRv6 segment list
- `install_ovs_queue()` — reserves bandwidth treatment
- `install_queue_flow_rule()` — marks the slice traffic into that queue
- `install_srv6_route()` — installs the SRv6 encap route at the source host

> **This is the Lab 4 story** discovery, policy, realization, then enforcement.

---

# The important distinction

These are not the same thing:

**Service chain**
- `h1 -> mb1 -> h2`

**Realized transport path**
- the actual ONOS-discovered path from `h1` toward `mb1`
- then from `mb1` toward `h2`

**SRv6 segment list**
- the explicit sequence of SIDs that enforces that realization

> **What you are learning here** A slice is not just "visit mb1". It is "visit mb1 via a chosen transport realization."

---

<!-- _class: divider -->

# Demo 1

Premium monitored video

---

# Demo slice 1 — premium monitored video

Provision a monitored premium slice:

```bash
python3 slice_controller_v2.py provision \
  --name video_gold \
  --src h1 \
  --dst h2 \
  --chain mb1 \
  --intent low-latency \
  --bandwidth 5
```

> **What this asks for** Connect `h1` to `h2`, force traffic through the monitor, prefer the shortest realized path, and reserve 5 Mbps.

---

# What to look for in the output

The controller should print:

- the service request fields
- the realized transport path per service hop
- the SRv6 segment list
- the queue installation
- the ONOS classifier installation
- the middlebox configuration

You are looking for evidence that:

- ONOS discovery was used
- intent influenced path selection
- SRv6 encoded the result

---

# Inspect the first slice

Check controller state:

```bash
python3 slice_controller_v2.py status
```

Inspect the route on `h1`:

```text
mininet> h1 ip route show
```

Inspect ONOS flows:

```text
onos> flows
```

Inspect the monitor output:

```bash
cat /tmp/mb_monitor.json
```

---

# Re-run the primary traffic test

From your `h1` shell, run the same UDP test again:

```bash
python3 sender.py --host 10.0.0.2 --port 5004 --rate 3 --duration 20 --label primary
```

> **What to look for** Compare `/tmp/h2_receiver5004.log` to the earlier baseline. This is the simplest way to tie the slice configuration to observed transport behavior.

---

<!-- _class: divider -->

# Demo 2

Background logged service on a different endpoint pair

---

# Demo slice 2 — logged background traffic

Keep the first slice active.

Now provision a second slice:

```bash
python3 slice_controller_v2.py provision \
  --name telemetry_silver \
  --src h3 \
  --dst h2 \
  --chain mb3 \
  --intent best-effort \
  --bandwidth 2
```

> **Why this works concurrently** It uses a different ordered endpoint pair, `h3 -> h2`, which fits the workshop simplification.

---

# Compare the two active slices

Check status again:

```bash
python3 slice_controller_v2.py status
```

Compare:

- endpoint pair
- intent
- requested bandwidth
- realized path
- segment list
- logger output

> **What changes** The slices differ in endpoint pair, intent, bandwidth, and service function. Demo 1 is premium and monitored; Demo 2 is ordinary and logged.

---

# Re-run the secondary traffic test

From your `h3` shell, run the UDP test again:

```bash
python3 sender.py --host 10.0.0.2 --port 5005 --rate 8 --duration 20 --label secondary
```

> **What to notice** This slice is best-effort, not premium. The important comparison here is the controller realization, not a guaranteed throughput target.

---

# Cleanup before the challenge

When you are done with the demo comparison, remove both example slices:

```bash
python3 slice_controller_v2.py teardown --name video_gold
python3 slice_controller_v2.py teardown --name telemetry_silver
python3 slice_controller_v2.py status
```

> **Why cleanup matters** It resets the endpoint pairs so you can reuse them in the independent challenge.

---

<!-- _class: divider -->

# Independent Challenge

Translate requirements into slices

---

# Customer brief

Provision two final slices from this short customer brief.

**Slice 1 — premium monitored video**
> "We need a premium video service from `h1` to `h2`. It needs guaranteed bandwidth and monitoring evidence that the service is being delivered."

**Slice 2 — secured and logged web access**
> "We need ordinary web access from `h3` to `h2`. Port `80` must work, port `8080` must not, and we want evidence that this traffic was part of the service chain."

---

# Your tasks

1. Choose the right chain for **Slice 1**
2. Choose the right chain for **Slice 2**
3. Choose the right intent for each slice
4. Choose reasonable bandwidth values
5. Provision both slices with `slice_controller_v2.py provision`
6. Verify the behavior from controller state, host tests, and middlebox output

> **What we are testing** Whether you can turn service requirements into chain, intent, and bandwidth.

---

# Hints

For **Slice 1**, ask yourself:

- which service function provides throughput visibility?
- does this traffic want premium or ordinary transport treatment?

For **Slice 2**, ask yourself:

- which service function is associated with firewall policy?
- which service function gives you an audit-style record?
- which endpoint pair should this slice use?

---

# Useful verification commands

Controller state:

```bash
python3 slice_controller_v2.py status
```

Performance checks:

```bash
./enter_host.sh h1
python3 sender.py --host 10.0.0.2 --port 5004 --rate 3 --duration 20 --label primary
```

Web checks:

```bash
./enter_host.sh h3
curl http://10.0.0.2:80
curl http://10.0.0.2:8080
```

Middlebox evidence:

```bash
cat /tmp/h2_receiver5004.log
cat /tmp/h2_receiver5005.log
cat /tmp/mb_monitor.json
cat /tmp/mb_firewall.json
cat /tmp/mb_logger.json
```

Checker:

```bash
python3 verify_lab4.py
```

---

# What a good answer looks like

A strong solution will:

- pick a chain that matches the service requirement
- pick an intent that matches the transport requirement
- justify the bandwidth choice
- use different endpoint pairs for the two active slices
- verify the result with evidence, not just with the provision command output

> **As in the earlier labs, focus on evidence** Show why the slice is realized the way you intended.

---

# Summary

What you did in the revised Lab 4:

- treated a slice as a service-level request
- used ONOS discovery to obtain transport topology context
- used intent to influence the realized transport path
- used SRv6 to encode that realization as a segment list
- used queueing to add bandwidth treatment
- combined all of that into a simple transport-slice controller workflow

**Key idea** A transport slice is not only a service chain. It is a service chain plus a transport realization policy.

---

# Quick reference — Lab 4 commands

```bash
# Topology
sudo python3 lab4_topology.py
python3 preflight_check.py

# Controller
python3 slice_controller_v2.py list-mbs
python3 slice_controller_v2.py provision \
  --name <name> \
  --src <host> --dst <host> \
  --chain <mb> [<mb>...] \
  --intent <low-latency|best-effort> \
  --bandwidth <Mbps> \
  [--blocked-ports <port> [<port>...]]
python3 slice_controller_v2.py status
python3 slice_controller_v2.py teardown --name <name>

# Host shells
./enter_host.sh h1
./enter_host.sh h3

# Verification
python3 verify_lab4.py
```
