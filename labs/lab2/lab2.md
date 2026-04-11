---
marp: true
theme: workshop-readable
paginate: true
---

<!-- _class: title -->

<span class="tag">Lab 2</span>

# Controller-Based Connectivity
# with ONOS

Rogers Executive Workshop 3 — Transport Network

---

<!-- _class: divider -->

# Getting Started

Connecting Mininet to ONOS

---

# Lab 2 at a glance

In this lab you will:

- connect a triangle topology to ONOS
- explore devices, links, hosts, and flows from the ONOS CLI
- query ONOS from Python through the REST API
- add and remove flow rules through the ONOS REST API
- build a small controller-side app that reacts to link failure

> **What to focus on** In Lab 1, you were the control plane. In Lab 2, ONOS is — watch how it discovers the network, installs rules, and recovers from failure without you touching a switch.

---

# From Lab 1 to Lab 2

In Lab 1 you installed flow rules manually with `ovs-ofctl`.

Today ONOS does that work automatically:

|               | Lab 1          | Lab 2              |
| ------------- | -------------- | ------------------ |
| Flow rules    | You write them | ONOS installs them |
| Topology view | You infer it   | ONOS discovers it  |
| Link failure  | Traffic stops  | ONOS reroutes      |
| Control plane | You            | ONOS               |

> **Your job changes** — instead of configuring each switch directly, you observe ONOS state and program the network through the controller.

---

# Where ONOS Fits

ONOS (Open Network Operating System) is an open-source SDN controller built for carrier-grade networks.

<div class="slide-figure">
  <img src="../../assets/figures/onos-overview.png" alt="Overview of ONOS showing applications, controller services, and southbound control of network devices." />
</div>

- ONOS sits between applications and the network devices
- applications express policy through ONOS APIs — no per-switch configuration needed
- ONOS discovers topology automatically and programs switches via OpenFlow
- controller apps can query state and install rules without logging into each switch

---

# Triangle topology

<div class="topology-figure compact">
  <img src="../../assets/figures/triangle-topology.svg" alt="Triangle topology with hosts h1, h2, h3, and switches s1, s2, s3." />
</div>

- `s1`, `s2`, `s3` form a triangle — there are two paths between any pair of switches
- ONOS picks one path per flow and installs rules only on that path
- when a link fails, ONOS recomputes and pushes new rules on the surviving path

> **The redundant paths are why rerouting works** — if there were only one path, a link failure would mean no connectivity.

---

<!-- _class: compact -->

# Before you start

**First: clean up Lab 1 completely.**

1. Exit any running Mininet (`Ctrl+D` or `exit` in the Mininet terminal)
2. Run `sudo mn -c` in a terminal
3. Close all Lab 1 terminals

Then open **four fresh terminals** and `cd ~/labs/lab2` in each:

| Terminal | Purpose                                               |
| -------- | ----------------------------------------------------- |
| 1        | Mininet CLI                                           |
| 2        | ONOS CLI                                              |
| 3        | Jupyter notebook (walkthrough + exercise)             |
| 4        | `ovs-ofctl` and shell verification                    |

> **Leftover Mininet state from Lab 1 will break Lab 2.** `sudo mn -c` is not optional.

---

# Start the topology

Make sure you are in `~/labs/lab2/`, then start Mininet (terminal 1):

```bash
sudo python3 triangle_topology.py
```

Once Mininet is running, connect to the ONOS CLI (terminal 2):

```bash
ssh -p 8101 -o HostKeyAlgorithms=+ssh-rsa onos@localhost
# password: rocks
```

You will be dropped into the ONOS shell:

```text
    ____  _  ______  ____
   / __ \/ |/ / __ \/ __/
  / /_/ /    / /_/ /\ \
  \____/_/|_/\____/___/

onos@root >
```

---

<!-- _class: compact -->

# Activate the required apps

First, check which apps are already active:

```text
onos> apps -a -s
```

You need three apps running — `openflow` speaks OpenFlow to the switches, `fwd` reacts to traffic and installs forwarding rules, `proxyarp` answers ARP requests on behalf of hosts. If any are missing, activate them:

```text
onos> app activate org.onosproject.openflow
onos> app activate org.onosproject.fwd
onos> app activate org.onosproject.proxyarp
```

Confirm the switches have connected:

```text
onos> devices
```

You should see three devices with `local-status=connected`. If the list is empty, wait a few seconds and retry.

---

<!-- _class: compact -->

# Explore the topology

ONOS discovered the switches the moment they connected. Confirm in the ONOS CLI:

```text
onos> devices
onos> links
```

Now check for hosts:

```text
onos> hosts
```

The list is empty — ONOS has never seen a packet from any host yet. Trigger host discovery from Mininet (terminal 1):

```text
mininet> pingall
```

Check hosts again:

```text
onos> hosts
```

All three hosts now appear. ONOS learned them by observing the first packet from each one.

---

<!-- _class: compact -->

# ONOS wrote the rules — you didn't

From the ONOS CLI (terminal 2), look at what `fwd` installed:

```text
onos> flows
```

```text
id=4200000baf0cae, state=ADDED, bytes=98, packets=1, duration=2,
  appId=org.onosproject.fwd,
  selector=[IN_PORT:1, ETH_DST:00:00:00:00:00:01, ETH_SRC:00:00:00:00:00:03],
  treatment=[OUTPUT:3]
```

You can also verify directly on the switch — just like in Lab 1 (terminal 4):

```bash
sudo ovs-ofctl dump-flows s1 -O OpenFlow13
```

```text
cookie=0x4200003f9f0001, priority=10,in_port="s1-eth1",
  dl_src=00:00:00:00:00:01,dl_dst=00:00:00:00:00:02 actions=output:"s1-eth2"
```

Both views show the same rules. If either is empty, the rules timed out — run `pingall` from Mininet and check again immediately.

---

<!-- _class: divider -->

# REST API

Inspect ONOS state and program the network from your own code

---

<!-- _class: compact -->

# REST walkthrough

In terminal 3 (inside `~/labs/lab2/`):

- run `jupyter notebook`
- when Jupyter opens in your browser, open `rest_walkthrough.ipynb`
- keep Mininet and ONOS CLI running in terminals 1 and 2
- do not run this inside `mininet>` or `onos>`
- run each cell in order and read the output before moving on

---

<!-- _class: divider -->

# Exercises

Building a small controller-side application

---

<!-- _class: compact -->

# What You Will Build

Open `exercises/exercise.ipynb` in Jupyter. You will complete a notebook that acts like a small controller application:

- finds two hosts by IP address
- asks ONOS for the current shortest path
- installs flow rules directly through the REST API
- monitors for link failure
- recomputes and reinstalls rules after a failure

> **Key idea** The helpers are provided — your job is to wire them together in four short parts.

---

# Summary

In this lab you:

- connected Mininet to ONOS and observed automatic topology discovery
- explored the network from both the ONOS CLI and the REST API
- added and removed flow rules through the ONOS REST API
- completed a notebook controller that detects link failure and reroutes via the REST API

> **Coming up** Lab 3 moves from centralized control to path steering with SRv6 — instead of a controller deciding the path, the ingress node encodes it directly in the packet header.
