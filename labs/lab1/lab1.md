---
marp: true
theme: workshop-readable
paginate: true
---

<!-- _class: title -->

<span class="tag">Lab 1</span>

# Programmable Forwarding
# with OVS + Mininet

Rogers Executive Workshop 3 — Transport Network Programmability

---

<!-- _class: divider -->

# Getting Started

Mininet, OVS, and your first flow rules

---

# Lab 1 at a glance

In this lab you will:

- start from Mininet's default topology
- observe how OVS behaves with and without flow rules
- install a few OpenFlow rules by hand
- build a simple topology in Python

> **What to focus on** For this lab, treat each rule as `match -> action -> counter`.

---

# SDN and OpenFlow

<div class="slide-figure">
  <img src="../../assets/figures/sdn-and-openflow.png" alt="Diagram showing the relationship between software-defined networking and OpenFlow." />
</div>

- SDN separates the control plane from the data plane
- OpenFlow is one protocol a controller can use to program switches
- in this lab, we mostly program OVS directly from the terminal

> **Keep this distinction in mind** OpenFlow describes the rule; OVS applies it in the switch.

---

# Open vSwitch (OVS)

OVS is a software switch for Linux with OpenFlow support.

- packet forwarding happens in the datapath
- management and control happen in userspace
- a remote controller can install rules remotely
- in this lab we mainly use `ovs-ofctl -O OpenFlow13` and `ovs-vsctl`

> **In this lab** Think of OVS as the switch you are programming.

---

# Mininet

Mininet is a lightweight network emulator that lets you run hosts, switches, and links on a single machine.

- hosts run in separate Linux network namespaces
- switches are software switches built with OVS
- the CLI lets us inspect nodes and run host commands quickly
- `sudo mn` starts a tiny network: `h1 -- s1 -- h2`

> **Why this matters** You can test network behavior quickly without needing separate physical devices.

---

# Before you start

For the lab exercises:

- work from `~/labs/lab1`
- keep two terminals open
- run Mininet and `ovs-ofctl` commands with `sudo`
- use `Ctrl+D` or `exit` to leave the Mininet CLI cleanly

---

# Start Mininet

Start the default topology:

```bash
sudo mn
```

<div class="topology-figure compact">
  <img src="../../assets/figures/mininet-default-topology.svg" alt="Default topology started by sudo mn with hosts h1 and h2 connected through switch s1." />
</div>

You should land in the Mininet CLI with two hosts and one switch:

```text
mininet>
```

> **You should see** `h1`, `h2`, `s1`, and a default controller.

---

# First Mininet commands

Use these commands right away in the Mininet CLI:

```text
mininet> nodes
mininet> net
mininet> dump
mininet> h1 ip addr show
```

- `nodes` lists all hosts and switches
- `net` shows the link-level topology
- `dump` shows interface details
- prefix a host name to run a command inside that host

---

# Inspect the default topology

Now verify that the default topology came up correctly:

```
mininet> nodes        # list all nodes
mininet> net          # show links between nodes
mininet> dump         # show interface details
```

Run commands inside a host:

```
mininet> h1 ifconfig
mininet> h1 ip addr show
```

> **What this shows** Each host has its own interface (`h1-eth0` etc.), because Mininet isolates hosts in separate Linux network namespaces.

---

# Test connectivity

Ping between hosts and run a bandwidth test:

```
mininet> h1 ping -c 3 h2
mininet> pingall
mininet> iperf h1 h2
```

> **What this means** Pings succeed because Mininet starts with a default learning controller. In the next step, you will disable it and see what happens without explicit rules.

---

# Useful extras

```text
mininet> pingall
mininet> iperf h1 h2
mininet> py h1.IP()
```

> **You can use these tools** `pingall` checks connectivity, `iperf` measures bandwidth, and `py` gives you access to Mininet objects from the CLI.

---

# Built-in Mininet topologies

Mininet can also start larger topologies without writing Python:

```bash
sudo mn --topo=single
sudo mn --topo=linear,3
sudo mn --topo=tree,depth=2,fanout=2
```

> **You will do this later in the lab** After the built-in examples, you will build your own topology in Python.

---

<!-- _class: divider -->

# OpenFlow and OVS

Programming the data plane

---

# OpenFlow — match + action

OpenFlow lets you program switch forwarding behaviour. Every flow rule has three parts:

**Match** — which packets does this rule apply to?
- Source / destination IP, MAC, TCP/UDP port, input port, VLAN tag
- OpenFlow 1.3 defines 40+ possible match fields

**Action** — what to do with matched packets?
- `output:N` — forward out port N
- `drop` — discard the packet
- `output:FLOOD` — send out all ports

**Counter** — `n_packets` and `n_bytes` track traffic matching this rule

> **For this lab** You only need `match` and `action`. The full OpenFlow model comes later in the workshop.

---

# Example flow-table entry

<div class="slide-figure">
  <img src="../../assets/figures/openflow-flow-table-entry.png" alt="Annotated example of an OpenFlow flow-table entry." />
</div>

> **How to read this entry** Match fields select packets, counters show activity, and actions define the forwarding behavior.

---

# OVS command reference

`ovs-ofctl -O OpenFlow13` manages OVS flow rules from the terminal:

```bash
# Inspect a switch
sudo ovs-ofctl -O OpenFlow13 show s1              # ports and capabilities
sudo ovs-ofctl -O OpenFlow13 dump-flows s1        # all flow rules + counters
sudo ovs-ofctl -O OpenFlow13 dump-ports s1        # per-port statistics

# Manage flow rules
sudo ovs-ofctl -O OpenFlow13 add-flow s1 <spec>   # add a rule
sudo ovs-ofctl -O OpenFlow13 del-flows s1         # remove all rules
```

> **Before adding rules** Run `ovs-ofctl -O OpenFlow13 show s1` first, because port numbers depend on link order and may differ from the examples.

---

# Observe switches with no rules

Restart Mininet with a two-switch topology and no controller:

```bash
sudo mn -c
sudo mn --topo=linear,2 --controller=none --switch ovs,protocols=OpenFlow13
```

Try to ping:

```
mininet> h1 ping -c 3 h2     # fails
mininet> pingall              # all fail
```

Inspect the empty flow tables:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
sudo ovs-ofctl -O OpenFlow13 dump-flows s2
```

> **What you should observe** Without flow rules, switches drop all traffic. No rule means no forwarding.

---

# Add flow rules manually

Install bidirectional rules to connect `h1` and `h2` across `s1 -> s2`:

```bash
# s1: route h1↔h2 traffic toward s2
sudo ovs-ofctl -O OpenFlow13 add-flow s1 \
  ip,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=output:2
sudo ovs-ofctl -O OpenFlow13 add-flow s1 \
  ip,nw_src=10.0.0.2,nw_dst=10.0.0.1,actions=output:1

# s2: same rules on the other switch
sudo ovs-ofctl -O OpenFlow13 add-flow s2 \
  ip,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=output:2
sudo ovs-ofctl -O OpenFlow13 add-flow s2 \
  ip,nw_src=10.0.0.2,nw_dst=10.0.0.1,actions=output:1
```

> **Before you paste the rules** Use `ovs-ofctl -O OpenFlow13 show s1` and `ovs-ofctl -O OpenFlow13 show s2` to confirm which port connects to which neighbour.

---

# Test connectivity and inspect counters

Verify h1 ↔ h2 connectivity:

```
mininet> h1 ping -c 5 h2
mininet> iperf h1 h2
```

Inspect the flow rules:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

You should see counters like:

```
cookie=0x0, duration=12.3s, n_packets=5, n_bytes=490,
  ip,nw_src=10.0.0.1,nw_dst=10.0.0.2 actions=output:2
```

> **What to check** `n_packets` and `n_bytes` should increase as traffic matches your rule.

---

<!-- _class: divider -->

# Mininet Python API

Building topologies in code

---

# A minimal topology in Python

Create `simple_topo.py`:

```python
from mininet.net import Mininet
from mininet.node import OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI

net = Mininet()

h1 = net.addHost('h1', ip='10.0.0.1/24')
h2 = net.addHost('h2', ip='10.0.0.2/24')
s1 = net.addSwitch('s1', cls=OVSSwitch, protocols='OpenFlow13')

net.addLink(h1, s1, cls=TCLink, bw=10, delay='5ms')
net.addLink(h2, s1, cls=TCLink, bw=10, delay='5ms')

net.start()
net.staticArp()
CLI(net)
net.stop()
```

---

# Run it and add flow rules

Run the topology:

```
sudo python3 simple_topo.py
```

`pingall` will fail — no rules. Add them from a second terminal:

```
sudo ovs-ofctl -O OpenFlow13 add-flow s1 \
  ip,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=output:2
sudo ovs-ofctl -O OpenFlow13 add-flow s1 \
  ip,nw_src=10.0.0.2,nw_dst=10.0.0.1,actions=output:1
```

```
mininet> h1 ping -c 3 h2    # now works
```

`net.staticArp()` preloads ARP entries, so the IP rules above are enough for this example.

Before adding rules, run `ovs-ofctl -O OpenFlow13 show s1` once so the port numbers match your setup.

> **Use this structure** Every topology follows the same pattern: add nodes -> add links -> `start()` -> interact -> `stop()`.

---

<!-- _class: independent -->

# Independent Challenge

---

<!-- _class: independent -->

# Challenge topology

Build the topology below and implement the required connectivity:

<div class="topology-figure compact">
  <img src="../../assets/figures/lab1-challenge-topology.svg" alt="Challenge topology with host h1 attached to s1, host h2 attached to s2, host h3 attached to s4, and switches s1, s2, s3, and s4 forming two possible branches." />
</div>

All links: **10 Mbps, 5 ms delay**

Use the same link settings everywhere so you can focus on forwarding behavior.

- `h1` and `h2` must communicate
- `h1` and `h3` must communicate
- `h2` and `h3` **cannot** reach each other

Get `h1 <-> h2` working first, then add the rules for `h1 <-> h3`.

---

<!-- _class: independent -->

# Your tasks

Work through the challenge in this order:

1. **Complete the topology** in `topology_starter.py`, then start it:
  ```text
  sudo python3 topology_starter.py
  ```
2. **Add the flow rules** in `install_rules.sh`, then run them from a second terminal:
  ```text
  sudo bash install_rules.sh
  ```
3. **Explain** in a comment: which missing rule prevents `h2` and `h3` from communicating?

If you get stuck, compare your work with:
`solutions/topology_solution.py` and `solutions/install_rules_solution.sh`

---

<!-- _class: independent -->

# Challenge files

Use these files for the challenge:

- `topology_starter.py` builds the Mininet topology
- `install_rules.sh` installs your OpenFlow rules
- `verify_challenge.py` checks whether the required behavior works
- `solutions/` contains the reference answers

---

<!-- _class: independent -->

# Check your work

Use the checker after your topology and rules are ready.

To verify your own work, run:
```text
sudo python3 verify_challenge.py
```

By default, the checker uses:
```text
topology_starter.py
install_rules.sh
```

If the checker reports an incomplete topology, finish the TODO sections in `topology_starter.py` before rerunning it.

To verify the reference solution instead, run:
```text
sudo python3 verify_challenge.py --topology solutions/topology_solution.py --rules solutions/install_rules_solution.sh
```

---

<!-- _class: independent -->

# Troubleshooting

- `h3 is missing a host link` means the topology TODOs are still incomplete
- `version negotiation failed` means the command needs `ovs-ofctl -O OpenFlow13`
- if traffic still fails, check port numbers with `show`, then rule counters with `dump-flows`
- if needed, compare your files with the reference solutions in `solutions/`

---

<!-- _class: independent -->

# Hints

> **To find port numbers** Run `ovs-ofctl -O OpenFlow13 show <switch>` or `net` in the Mininet CLI.

> **One valid path plan** Use `s1 -> s2` for `h1 <-> h2`, and `s1 -> s3 -> s4` for `h1 <-> h3`.

> **When a switch has multiple outgoing links** Include `in_port` to avoid ambiguity:
> `ip,in_port=1,nw_src=10.0.0.1,nw_dst=10.0.0.2,actions=output:2`

> **If your rules keep disappearing** Add `idle_timeout=0` to prevent them from expiring:
> `sudo ovs-ofctl -O OpenFlow13 add-flow s1 idle_timeout=0,ip,...`

> **For `h2` and `h3` isolation** You do not need an explicit `drop` rule. If no rule matches, the packet is dropped automatically.

> **If traffic still does not flow** Run `ovs-ofctl -O OpenFlow13 dump-flows <switch>` on each switch along the path. A `n_packets` counter stuck at 0 usually means that switch is missing a rule.

---

<!-- _class: independent -->

# Stretch challenge

After your main solution works, reroute `h1 <-> h3` over the alternate branch.

- first make `h1 <-> h3` work via `s1 -> s3 -> s4`
- then change the rules so it works via `s1 -> s2 -> s4`
- keep `h1 <-> h2` working throughout
- use `ovs-ofctl -O OpenFlow13 dump-flows` counters to confirm which path is active

> **What you should observe** Connectivity still works, but different switches and rules accumulate the packet counters.

Stretch reference: `solutions/install_rules_stretch.sh`

---

# Summary

What you did in Lab 1:

- Started from Mininet's default topology and basic CLI commands
- Observed that OVS switches drop all traffic without flow rules
- Installed match + action flow rules manually using `ovs-ofctl`
- Watched packet counters confirm your rules were working
- Built a simple custom topology using the Mininet Python API

**Next in the schedule** is Concepts 2, where you will connect this hands-on work to the OpenFlow model, controllers, and intents. After that, Lab 2 moves from manual rules to controller-based connectivity with ONOS.
