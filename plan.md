---
permalink: /plan
layout: default
---

# Workshop 3 – Plan (Internal; Draft v1) 
**Programmable Transport Networks with SDN**  
April 14

# Introduction  
**9:00 – 9:15**

Topics:

- Welcome and workshop logistics  
- Overview of the Rogers Executive Workshop Series  
- Recap of previous workshops  
  - Workshop 1 – 5G Core  
  - Workshop 2 – RAN  
- Motivation for Workshop 3 – Transport Networks  
- Overview of workshop agenda  

# Session 1 – Introduction to Software-Defined Networking  
**9:15 – 10:30**

Topics:

- Traditional networking architecture  
- Limitations of distributed control planes  
- Motivation for programmable networks  
- Separation of control and data planes  
- SDN architecture (controller and switches)  
- OpenFlow abstraction  
- Flow tables: *match + action* model  

# Lab 1 – SDN Data Plane (Open vSwitch + Mininet)  
**10:45 – 12:00**

### Part 1: Walkthrough (20m)
**Goal:** Understand the topology and observe switch behavior without forwarding rules.

**Tasks:**
- Start the Mininet topology  
- Inspect hosts, switches, and links  
- Test connectivity  
- Inspect switch flow tables  

### Part 2: Guided exercise (25m)
**Goal:** Show how flow rules enable packet forwarding.

**Tasks:**
- Identify switch ports  
- Install a forwarding rule  
- Test connectivity  
- Inspect resulting flow entries  

### Part 3: Independent exercise (30m)
**Goal:** Implement a simple connectivity policy using flow rules.

**Tasks:**
- Allow communication between one pair of hosts  
- Block communication between another pair  
- Verify connectivity behavior  
- Inspect the resulting flow tables


# Session 2 – SDN Controllers and ONOS  
**1:30 – 2:30**

Topics:

- Limitations of manual flow programming  
- Role of the SDN controller  
- Controller responsibilities:
  - topology discovery  
  - network state management  
  - path computation  
  - flow rule installation  
- ONOS architecture  
- Intent-based networking  

# Lab 2 – Network Control with ONOS  
**2:45 – 4:00**

### Part 1: Walkthrough (20m)
**Goal:** Understand how the SDN controller observes and manages the network.

**Tasks:**
- Start the ONOS controller  
- Connect the Mininet topology to ONOS  
- Inspect discovered devices, links, and hosts  
- Observe the network view maintained by the controller  


### Part 2: Guided excercise (25m)
**Goal:** Use the ONOS CLI to create and inspect connectivity.

**Tasks:**
- Create a host-to-host intent  
- Verify connectivity between hosts  
- Inspect the flows installed by the controller  
- Identify the path selected across the network  

### Part 3: Independent exercise (30m)
**Goal:** Automate path setup using the ONOS API.

**Tasks:**
- Use provided skeleton code to query network state  
- Retrieve or compute connectivity between two hosts  
- Install connectivity using the API  
- Test behavior after a link failure  
- Inspect the updated path or flows


### Part 4: Optional demo - Service differentiation under load (10 min)

**Goal:** Illustrate how transport policies can protect latency-sensitive services such as cloud gaming during congestion.

**Context:**  
Rogers has seen our cloud-gaming demo previously. 
Using a simplified scenario, this demo shows some of the underlying principles that enable such service differentiation.

**Preconfigured (scripted):**
- Mininet topology with a shared bottleneck link
- OVS queues configured on the bottleneck switch
- Traffic generation scripts representing two traffic classes

**Demo:**
- Generate traffic for two flows sharing the same bottleneck link
- Increase load so both flows compete for limited capacity
- Apply controller policies mapping each flow to a different queue
- Observe how the protected traffic class maintains better throughput under congestion

**Discussion:**  
This simplified example illustrates how transport networks can enforce differentiated service levels using SDN. 
Our cloud-gaming demo builds on these principles, but operates on top of our lab 5G network, and incorporates our 
developed solutions for 5G slice monitoring and slice resource scaling.


# Workshop Conclusion  
**4:00 – 4:30**

### Goal
Summarize key concepts from the workshop series.

### Topics

- Recap of the Rogers Executive Workshop Series  
  - Workshop 1 – 5G Core Networks  
  - Workshop 2 – Radio Access Networks (RAN)  
  - Workshop 3 – Transport Networks  

- Role of programmable networking in modern networks  
- Relationship between data plane, control plane, and automation systems  
- How SDN controllers enable centralized network control  
- Discussion and questions