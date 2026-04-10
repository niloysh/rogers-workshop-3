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
- install host intents and observe automatic flow-rule installation
- watch ONOS reroute traffic after a link failure

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

> **Your job changes** — instead of writing rules, you declare intent ("h1 and h2 should talk") and let the controller figure out the how.

---

# Where ONOS Fits

ONOS (Open Network Operating System) is an open-source SDN controller built for carrier-grade networks.

<div class="slide-figure">
  <img src="../../assets/figures/onos-overview.png" alt="Overview of ONOS showing applications, controller services, and southbound control of network devices." />
</div>

- ONOS sits between applications and the network devices
- applications express policy through ONOS APIs — no per-switch configuration needed
- ONOS discovers topology automatically and programs switches via OpenFlow
- **intents** let you declare *what* you want connected; ONOS works out *how*

---

# Triangle topology

<div class="topology-figure compact">
  <img src="../../assets/figures/triangle-topology.svg" alt="Triangle topology with hosts h1, h2, h3, and switches s1, s2, s3." />
</div>

- `s1`, `s2`, `s3` form a triangle — unlike Lab 1's linear topology, this has a loop
- loops cause broadcast storms in traditional networks, so STP blocks redundant ports to break them
- ONOS runs apps such as **reactive forwarding** (`fwd`) that install unicast rules on a computed path — unselected links carry no traffic
- when a link fails, ONOS recomputes and pushes new rules on the surviving path

> **STP avoids loops by disabling links. ONOS avoids them by controlling exactly which path each flow takes.**

---

<!-- _class: compact -->

# Before you start

You will need four terminals for this lab:

| Terminal | Purpose                                                |
| -------- | ------------------------------------------------------ |
| 1        | Mininet CLI                                            |
| 2        | ONOS CLI                                               |
| 3        | Lab scripts (`preflight_check.py`, `lab2_skeleton.py`) |
| 4        | `curl`, `ovs-ofctl`, checker                           |

- work from `~/labs/lab2`
- `sudo` is required for Mininet and Docker commands
- exit the Mininet CLI with `exit` or `Ctrl+D` to tear down the topology cleanly

---

<!-- _class: compact -->

# Check ONOS

Make sure the ONOS container is running:

```bash
docker ps | grep onos
```

If it is stopped, start it:

```bash
docker start onos
```

Wait ~30 seconds, then confirm the REST API is responding:

```bash
curl -u onos:rocks http://localhost:8181/onos/v1/devices
```

> **An empty device list is fine** — switches connect after you start Mininet. If the container does not exist at all, ask the instructor.

---

# Start the topology

Start Mininet connected to ONOS:

```bash
sudo python3 triangle_topology.py --onos
```

The `--onos` flag connects each OVS switch to ONOS as a remote OpenFlow controller on port `6653`. Once Mininet starts, watch for:

- which switches and links ONOS discovers
- when hosts appear — they only show up after their first packet
- what changes after you activate a forwarding app

> **Nothing forwards yet** — ONOS has discovered the topology but has not installed any rules. You will do that in the next step.

---

<!-- _class: compact -->

# Connect to the ONOS CLI

From terminal 2, connect to the ONOS Karaf CLI:

```bash
ssh -p 8101 -o HostKeyAlgorithms=+ssh-rsa onos@localhost
# password: rocks
```

List active applications to confirm ONOS is ready:

```text
onos> apps -a -s
```

> **The Karaf CLI is your window into ONOS** — you will use it to activate apps, inspect topology, and query intents throughout this lab.

---

<!-- _class: compact -->

# Activate the required apps

Activate the OpenFlow southbound and reactive forwarding apps:

```text
onos> app activate org.onosproject.openflow
onos> app activate org.onosproject.fwd
```

Confirm the switches have connected:

```text
onos> devices
```

You should see three devices in the `ACTIVE` state. If the list is empty, wait a few seconds and retry.

> **Note** You will deactivate `fwd` before the intent exercises — reactive forwarding and intents conflict with each other.

---

<!-- _class: compact -->

# Explore topology from the ONOS CLI

Run these commands and note what is — and is not — populated yet:

```text
onos> devices   # switches connected via OpenFlow
onos> ports     # ports on each switch
onos> links     # inter-switch links ONOS has discovered
onos> hosts     # end hosts — likely empty at this point
onos> flows     # rules installed by ONOS on the switches
```

Trigger host discovery from Mininet, then check hosts again:

```text
mininet> pingall
onos> hosts
```

> **ONOS learns switches and links first** — hosts only appear after their first packet, because ONOS sees the ARP or IP traffic and records the source.

---

<!-- _class: compact -->

# Inspect reactive forwarding

With `fwd` active, ONOS reacts to each new flow by computing a path and pushing rules to the switches — you never touched `ovs-ofctl`. Test it:

```text
mininet> h1 ping -c 3 h2
mininet> pingall
```

Check what ONOS installed on the switches:

```text
onos> flows
```

You can also verify directly on the switch from terminal 4:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

> **Compare with Lab 1** — the same rules are there, but ONOS wrote them, not you.

---

# Intents: what, not how

Reactive forwarding still requires ONOS to see a packet before it installs a rule. **Intents** go further — you declare the desired connectivity upfront and ONOS handles everything.

Instead of:
> install these exact flow rules on these exact switches

you say:
> connect host A to host B

ONOS then computes a path, installs the rules, and recomputes automatically if the topology changes.

---

# Turn off reactive forwarding

Before testing intents, deactivate `fwd` — the two approaches conflict:

```text
onos> app deactivate org.onosproject.fwd
```

Keep the same Mininet topology running — do not restart it. Host discovery and the traffic context from the earlier steps carry over into the intent demo.

> **Connectivity will break briefly** until you install an intent in the next step. That is expected.

---

<!-- _class: compact -->

# Install a host intent

Confirm ONOS still knows the hosts from the earlier discovery step:

```text
onos> hosts
```

Install a bidirectional host intent — replace the IDs with what `hosts` returned:

```text
onos> add-host-intent <h1-id> <h2-id>
onos> intents -i
```

Verify ONOS has programmed the switches and traffic flows:

```text
mininet> h1 ping -c 3 h2
```

> **Notice** You did not specify a path or write a single flow rule — ONOS translated the intent into switch programming automatically.

---

# Intent preserves connectivity

<div class="topology-figure compact">
  <img src="../../assets/figures/triangle-intent-reroute.svg" alt="Triangle topology with the direct s1 to s2 link failed and traffic rerouted through s3 while the intent remains installed." />
</div>

In the next steps you will take down the `s1–s2` link while the host intent is active. Watch what ONOS does:

- does the intent change?
- does the path change?
- does connectivity survive?

> **The diagram shows what you are about to observe** — keep it in mind as you work through the failure and recovery steps.

---

# Path before failure

With the intent working, confirm which path ONOS is currently using:

```text
mininet> h1 ping -c 3 h2
onos> paths of:0000000000000001 of:0000000000000002
```

You should see the direct one-hop path:

```text
of:0000000000000001/2-of:0000000000000002/2; cost=1.0
```

> **Take note of this path** — after you bring the link down in the next step, you will watch ONOS replace it.

---

<!-- _class: compact -->

# Tear down the direct link

Disable the `s1-s2` link, then check the path again:

```text
mininet> link s1 s2 down
mininet> h1 ping -c 5 h2
onos> paths of:0000000000000001 of:0000000000000002
```

Now observe ONOS:

```text
onos> links
onos> intents -i
onos> flows
```

Expected path while the link is down:

```text
of:0000000000000001/3-of:0000000000000003/3==>of:0000000000000003/2-of:0000000000000002/3; cost=2.0
```

> **What this shows** The intent stays installed, but ONOS recomputes the path and moves traffic over `s1 -> s3 -> s2`.

---

<!-- _class: compact -->

# Restore the direct path

Bring the direct link back and confirm ONOS returns to the shorter path:

```text
mininet> link s1 s2 up
onos> paths of:0000000000000001 of:0000000000000002
```

Expected path after recovery:

```text
of:0000000000000001/2-of:0000000000000002/2; cost=1.0
```

From OVS, inspect rules on the alternate switch while the failure is active:

Run this in your regular shell, not inside `mininet>` or `onos>`:

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s3
```

> **What changes** The path and flow rules change. The intent does not.

---

# List and remove intents

List all installed intents and note the `appId` and `id` from the output:

```text
onos> intents -i
```

Remove the intent using those values:

```text
onos> remove-intent org.onosproject.cli 0x0
```

Confirm it is gone and check what happened to the flow rules:

```text
onos> intents -i
onos> flows
```

> **When an intent is removed, ONOS withdraws the rules it installed** — the switch goes back to dropping that traffic.

---

<!-- _class: divider -->

# REST API

Query ONOS first with `curl`, then from Python

---

<!-- _class: compact -->

# Start with `curl`

You can query the ONOS REST API directly from your regular shell:

```text
Base URL:  http://localhost:8181/onos/v1
Auth:      onos / rocks
```

Try:

```bash
curl -u onos:rocks http://localhost:8181/onos/v1/devices
```

Useful endpoints:

| Endpoint            | Returns                |
| ------------------- | ---------------------- |
| `/devices`          | switches               |
| `/links`            | discovered links       |
| `/hosts`            | discovered hosts       |
| `/flows/<deviceId>` | flow rules on a switch |
| `/intents`          | installed intents      |

---

<!-- _class: compact -->

# Add a flow rule with `curl`

POST the example template to a switch:

```bash
curl -u onos:rocks -X POST \
  -H 'Content-Type: application/json' \
  http://localhost:8181/onos/v1/flows/of:0000000000000001 \
  -d @flow_rule_template.json
```

Verify the rule was installed:

```text
onos> flows
```

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
```

> **This is the same operation your Lab 2 app will perform** — the difference is that your app will build the rule body dynamically rather than loading a fixed template.

---

<!-- _class: compact -->

# Remove a flow rule with the REST API

To remove a rule, you need:

- the device ID
- the flow ID on that device

First inspect the flows:

```bash
curl -u onos:rocks http://localhost:8181/onos/v1/flows/of:0000000000000001
```

Then delete the specific flow:

```bash
curl -u onos:rocks -X DELETE \
  http://localhost:8181/onos/v1/flows/of:0000000000000001/<flowId>
```

> **Why this matters** Your Lab 2 app will use the same two ideas: POST new rules when a path is chosen, then DELETE old rules when the path changes.

---

<!-- _class: compact -->

# Query topology from Python

The lab includes example scripts that call the same endpoints you tested with `curl`:

```python
import requests

BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')

devices = requests.get(f'{BASE}/devices', auth=AUTH).json()['devices']
for d in devices:
    print(d['id'], d['type'], d['available'])

hosts = requests.get(f'{BASE}/hosts', auth=AUTH).json()['hosts']
for h in hosts:
    print(h['id'], h['ipAddresses'], h['locations'][0]['elementId'])
```

Run `pingall` first so ONOS has discovered all hosts, then:

```bash
python3 query_topology.py
```

> **The REST API returns the same data as the ONOS CLI** — `devices`, `links`, `hosts`, and `flows` are all queryable this way from any language.

---

<!-- _class: divider -->

# Independent Challenge

Building a small controller-side application

---

<!-- _class: independent compact -->

# What You Will Build

In this challenge, you will write a small ONOS-facing Python app that:

- finds two hosts by IP address
- asks ONOS for the current shortest path
- installs flow rules directly through the REST API
- monitors for link failure
- recomputes and reinstalls rules after a failure

> **Key difference from the earlier slides** Here you are not using intents. Your Python app is acting like a small controller application.

---

<!-- _class: independent compact -->

# Keep These Open

Keep all four terminals running during the challenge:

| Terminal     | Use during challenge                                        |
| ------------ | ----------------------------------------------------------- |
| 1 — Mininet  | `pingall`, `link s1 s2 down`, manual pings                  |
| 2 — ONOS CLI | `links`, `hosts`, `flows`, `paths`                          |
| 3 — Your app | `python3 lab2_skeleton.py 10.0.0.1 10.0.0.2`                |
| 4 — Shell    | `preflight_check.py`, `verify_lab2.py`, `curl`, `ovs-ofctl` |

---

<!-- _class: independent compact -->

# Files You Will Use

| File                                   | Purpose                                  |
| -------------------------------------- | ---------------------------------------- |
| `preflight_check.py`                   | confirm ONOS is ready before you start   |
| `lab2_skeleton.py`                     | your starter app — complete the TODOs    |
| `verify_lab2.py`                       | checker — run after your app is working  |
| `flow_rule_template.json`              | JSON shape for a flow rule POST          |
| `query_topology.py`, `inspect_path.py` | example helpers for host and path lookup |
| `solutions/lab2_solution.py`           | reference solution                       |

---

<!-- _class: independent compact -->

# Get Ready

Before you run `lab2_skeleton.py`, check readiness with:

```text
python3 preflight_check.py
```

It confirms:

- ONOS is reachable
- switches, links, and host IPs are visible
- `paths` returns a route between the endpoint switches

If it fails:

- rerun `pingall` if host IPs are missing
- check `links` and `ports` if `paths` is empty

> **Rule of thumb** The challenge works only after ONOS knows the links, the hosts, and at least one path between the two endpoint switches.

---

<!-- _class: independent compact -->

# How to think about it

Your app works in five steps:

1. **Find** the two hosts in ONOS by IP
2. **Query** the current path between their attachment switches
3. **Install** flow rules on each switch along that path
4. **Detect** when a link on that path fails
5. **Reroute** — remove the old rules and install new ones for the new path

The next two slides walk through steps 1 and 2. Steps 3–5 are your TODOs in `lab2_skeleton.py`.

---

<!-- _class: independent compact -->

# Step 1: Find Hosts

First, use `/hosts` to answer two questions:

- what is the ONOS host ID for `10.0.0.1` and `10.0.0.2`?
- which switch is each host attached to?

You can reuse `query_hosts.py`, or inspect the same logic below:

```python
import requests

BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')

hosts = requests.get(f'{BASE}/hosts', auth=AUTH).json()['hosts']
for h in hosts:
    print(h['id'], h['ipAddresses'], h['locations'][0]['elementId'])
```

> **What to look for** Find the entries for `10.0.0.1` and `10.0.0.2`, then note their host IDs and attachment switches.

---

<!-- _class: independent compact -->

# Step 2: Inspect The Path

Then use those attachment switches to query the path between them.

You can also run the example script:

```text
python3 inspect_path.py of:0000000000000001 of:0000000000000002
```

The Python logic looks like this:

```python
import requests

BASE = 'http://localhost:8181/onos/v1'
AUTH = ('onos', 'rocks')

paths = requests.get(
    f'{BASE}/paths/of:0000000000000001/of:0000000000000002',
    auth=AUTH
).json()['paths']

for link in paths[0]['links']:
    print(link['src']['device'], link['src']['port'], '->',
          link['dst']['device'], link['dst']['port'])
```

> **What to look for** You are turning ONOS topology state into a concrete device-and-port path.

---

<!-- _class: independent compact -->

# Your tasks

1. **Start the topology** if it is not already running:
  ```bash
  sudo python3 triangle_topology.py --onos
  ```
2. **Run the preflight check** to confirm ONOS sees the topology:
  ```bash
  python3 preflight_check.py
  ```
3. **Complete the TODOs** in `lab2_skeleton.py`
4. **Run your app:**
  ```bash
  python3 lab2_skeleton.py 10.0.0.1 10.0.0.2
  ```
5. **Verify** with Mininet, ONOS, and your app all running:
  ```bash
  sudo python3 verify_lab2.py 10.0.0.1 10.0.0.2
  ```
6. **Trigger a failure** with `link s1 s2 down` and confirm your app reroutes

> **Stuck?** Compare with `solutions/lab2_solution.py`

---

<!-- _class: independent compact -->

# Troubleshooting

| Symptom                      | Fix                                                    |
| ---------------------------- | ------------------------------------------------------ |
| `hosts` is empty             | run `pingall` in Mininet first                         |
| hosts visible but `ip(s)=[]` | run `pingall` again, then recheck `hosts`              |
| `devices` is empty           | confirm ONOS is running and `openflow` is active       |
| `paths` returns empty        | check `links` and `ports` before debugging your app    |
| app prints "host not found"  | ONOS has not learned that host yet — run `pingall`     |
| rerouting does not happen    | check whether the failed port shows `isEnabled: false` |

---

<!-- _class: independent compact -->

# Hints

- **Find hosts by IP** — query `/hosts` and check each host's `ipAddresses` list
- **Compute a path** — find attachment devices from `/hosts`, then query `/paths/<src>/<dst>`
- **Install a rule** — POST to `/flows/<deviceId>` using the shape in `flow_rule_template.json`
- **Clean up old rules** — query `/flows/<deviceId>`, keep rules with your `appId`, DELETE them one by one
- **Detect a failure** — poll `/devices/<deviceId>/ports` and watch for a path port where `isEnabled` becomes `false`

---

# Summary

In this lab you:

- connected Mininet to ONOS and observed automatic topology discovery
- explored the network from both the ONOS CLI and the REST API
- used intents to request connectivity without writing flow rules
- watched ONOS reroute traffic after a link failure
- built a small controller app that installs and replaces rules through the REST API

> **Coming up** Lab 3 moves from centralized control to path steering with SRv6 — instead of a controller deciding the path, the ingress node encodes it directly in the packet header.
