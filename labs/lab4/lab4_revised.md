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

What you will build

---

# Lab 4 at a glance

In this lab you will:

- start a topology with three transport nodes and three service functions
- inspect how the slice controller combines ONOS, SRv6, and queueing
- use simple sender/receiver traffic generators to observe slice effects
- provision two example slices on different endpoint pairs
- compare low-latency and best-effort realizations
- create two final slices from a short customer brief

> **Goal** Use one controller command to provision a simple transport slice from endpoint pair, chain, intent, and bandwidth.

---

# The Lab 4 idea

A slice request has four parts:

- **src / dst**
- **chain**
- **intent**
- **bandwidth**

The controller translates that into:

- a realized transport path
- an SRv6 segment list
- a queue reservation
- middlebox configuration

---

# Workshop simplification

Only one active slice may use a given ordered endpoint pair.

Examples:

- `h1 -> h2` and `h3 -> h2` can coexist
- two simultaneous `h1 -> h2` slices cannot

---

# Lab 4 topology

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

---

# Available service functions

```bash
python3 slice_controller_v2.py list-mbs
```

```text
  mb1  fc00::b1  throughput monitor
  mb2  fc00::b2  firewall policy
  mb3  fc00::b3  flow logger
```

---

# What the intents mean

- **low-latency** → prefer the shortest realized path
- **best-effort** → prefer a longer alternate path

---

# Demo slice 1 — premium monitored video

```bash
python3 slice_controller_v2.py provision \
  --name video_gold \
  --src h1 \
  --dst h2 \
  --chain mb1 \
  --intent low-latency \
  --bandwidth 5
```

---

# Demo slice 2 — logged background traffic

```bash
python3 slice_controller_v2.py provision \
  --name telemetry_silver \
  --src h3 \
  --dst h2 \
  --chain mb3 \
  --intent best-effort \
  --bandwidth 2
```

---

# Participant exercise

## Slice 1
- premium monitored video
- `h1 -> h2`
- choose chain, intent, and bandwidth

## Slice 2
- secured and logged web access
- `h3 -> h2`
- block port 8080
- choose chain, intent, and bandwidth

---

# Summary

A transport slice combines:

- path selection
- bandwidth treatment
- service-chain policy
