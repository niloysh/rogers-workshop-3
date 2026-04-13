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

<blockquote class="info">In Lab 1, you were the control plane. In Lab 2, ONOS is — watch how it discovers the network, installs rules, and recovers from failure without you touching a switch.</blockquote>

---

<!-- _class: compact -->

# From Lab 1 to Lab 2

- **Lab 1** showed forwarding in its simplest form: you wrote the exact match/action rules yourself.
- That made the mechanism visible, but it also meant you had to reason locally, one switch at a time.
- **Lab 2** keeps the same underlying idea, but moves the control point up to ONOS.
- ONOS discovers the topology, learns where hosts are, computes paths, and installs the switch rules needed to realize connectivity.
- When the topology changes, ONOS can update those rules again without you logging into each switch.

<blockquote class="info">The data plane is still realized by flow rules in the switches. What changes is the level of abstraction: instead of programming one device at a time, you work through a controller with a network-wide view.</blockquote>

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

<blockquote class="tip">If there were only one path, a link failure would mean no connectivity. The redundant paths are why rerouting works.</blockquote>

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

<blockquote class="warning">Leftover Mininet state from Lab 1 will break Lab 2. <code>sudo mn -c</code> is not optional.</blockquote>

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

<blockquote class="tip">The helpers are provided — your job is to wire them together in four short parts.</blockquote>

---

<!-- _class: compact -->

# Troubleshooting

**ONOS shows no devices, or the REST API returns an empty device list.**
Wait a few seconds after starting `triangle_topology.py`, then check `onos> devices` again. If it is still empty, confirm Mininet is running and the `openflow` app is active.

**`hosts` is empty, or the notebook says a host was not found.**
Run `pingall` in Mininet first. ONOS only learns hosts after it sees traffic from them.

**`org.onosproject.fwd` is active and devices are connected, but `pingall` still fails.**
ONOS may be in a bad state. Run `sudo docker restart onos`, wait 1–2 minutes, reconnect the ONOS CLI, confirm `onos> devices` shows all switches as connected, then retry `pingall`.

**Jupyter shows `NameError`, or the notebook state seems inconsistent.**
Run the cells from top to bottom. If you jumped around, restart the kernel and rerun the notebook in order.

**I deactivated `org.onosproject.fwd`, but traffic still works.**
Wait a few seconds and check `onos> flows` again. The old `fwd` rules may still be present; the exercise should start only after they disappear.

**The reroute loop keeps reacting to the same failure over and over.**
In Part 4, make sure you save the return value of `reroute_once(...)` back into `path_links`. Otherwise the loop keeps watching the old broken path.

---

# Summary

In this lab you:

- connected Mininet to ONOS and observed automatic topology discovery
- explored the network from both the ONOS CLI and the REST API
- added and removed flow rules through the ONOS REST API
- completed a notebook controller that detects link failure and reroutes via the REST API

<blockquote class="info">Lab 3 keeps the goal of programmable forwarding, but changes how the path is expressed: with SRv6, the route is carried in the packet itself as a segment list.</blockquote>
