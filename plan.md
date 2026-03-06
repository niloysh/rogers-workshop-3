---
permalink: /plan
layout: page
---

# Workshop 3 – Plan (Internal; Draft v2)  
**Programmable Transport Networks with SDN**  
April 14

---

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

---

# Concepts 1 – Programmable Networking  
**9:15 – 9:35 (20 min)**

Topics:

- Traditional networking architecture  
- Limitations of distributed control planes  
- Motivation for programmable networks  
- Separation of control and data planes  
- SDN architecture (controller and switches)

Goal: introduce the motivation for **programmable transport networks**.

---

# Lab 1 – Forwarding Behavior with Flow Rules  
**9:35 – 10:30**

This lab introduces how packet forwarding can be programmed directly in network switches.

### Part 1 – Observe network behavior

Goal: understand how switches behave without forwarding rules.

Tasks:

- Start the Mininet topology  
- Inspect hosts, switches, and links  
- Attempt connectivity between hosts  
- Observe what happens when switches do not have forwarding rules  

Key takeaway: switches require forwarding rules to determine how packets are handled.

### Part 2 – Install forwarding rules

Goal: introduce the basic match–action forwarding model.

Tasks:

- Install a simple forwarding rule on a switch  
- Test connectivity between hosts  
- Inspect installed flow entries  

Explanation:

- packet forwarding is controlled by flow rules  
- each rule specifies how packets matching certain fields should be handled

### Part 3 – Inspect rule matching

Goal: understand how rule fields determine packet forwarding behavior.

Tasks:

- Inspect the fields used in flow rules  
- Modify rule matching behavior  
- Observe how forwarding behavior changes  

Key takeaway: packet forwarding behavior depends on the installed rules and their matches.

---

# Coffee Break  
**10:30 – 10:45**

---

# Concepts 2 – OpenFlow and Network Policy  
**10:45 – 11:10 (25 min)**

Topics:

- OpenFlow abstraction  
- Flow tables and the match–action model  
- Rule priority and packet matching  
- Using forwarding rules to implement network policy

Goal: connect the first lab to the underlying **OpenFlow model**.

---

# Lab 1 – Implementing Network Policy  
**11:10 – 12:00**

Participants extend the earlier experiment and implement simple forwarding policies.

### Guided exercise

Tasks:

- Modify existing rules to change forwarding behavior  
- Observe how different rules affect connectivity  
- Inspect the relationship between rule fields and behavior  

Explanation:

- flow tables enable flexible and programmable control of packet forwarding  
- policies can be realized by choosing which traffic is allowed or blocked

### Independent challenge

Goal: implement a simple selective connectivity policy.

Tasks:

- Allow communication between one pair of hosts  
- Block communication between another pair  
- Verify resulting connectivity behavior  
- Inspect the final flow rules

Discussion:

- Manual rule programming is possible, but becomes difficult to manage as network size grows  
- This motivates the need for centralized network controllers

---

# Lunch Break  
**12:00 – 1:00**

---

# Concepts 3 – Centralized Network Control  
**1:00 – 1:25 (25 min)**

Topics:

- Limitations of manual flow programming  
- Role of the SDN controller  
- Controller responsibilities:
  - topology discovery  
  - network state management  
  - path computation  
  - rule installation

Goal: explain why **centralized controllers** are needed in programmable networks.

---

# Lab 2 – Controller-Based Connectivity  
**1:25 – 2:15**

This lab shows how controllers automate forwarding decisions across the network.

### Part 1 – Observe controller behavior

Goal: understand how the controller maintains a global network view.

Tasks:

- Start the controller  
- Connect the Mininet topology to the controller  
- Inspect discovered devices, links, and hosts  
- Observe the controller’s view of the network  

Key takeaway: the controller maintains network-wide state and uses it to manage connectivity.

### Part 2 – Create controller-driven connectivity

Goal: observe how the controller installs forwarding behavior automatically.

Tasks:

- Create host-to-host connectivity through the controller  
- Verify connectivity between hosts  
- Inspect the flows installed by the controller  
- Identify the selected path across the network  

Explanation:

- the controller computes paths and installs forwarding rules automatically  
- connectivity can be requested at a higher level than individual switch rules

### Part 3 – Independent challenge

Goal: explore controller-managed connectivity for additional traffic pairs.

Tasks:

- Create additional connectivity requests between hosts  
- Observe how paths are installed  
- Inspect resulting flow rules  

Key takeaway: controllers automate network control across multiple switches.

---

# Coffee Break  
**2:15 – 2:30**

---

# Concepts 4 – Automation and Network Policies  
**2:30 – 3:00 (30 min)**

Topics:

- Intent-based networking  
- High-level policy versus low-level forwarding rules  
- Controller APIs and automation

Goal: explain how network behavior can be **programmatically controlled through software**.

---

# Lab 2 – Automated Network Control  
**3:00 – 3:30**

This lab introduces controller-driven automation using software interfaces.

### Guided exercise

Tasks:

- Use provided skeleton code to query network state  
- Install connectivity using the controller API  
- Verify connectivity behavior  

Explanation:

- network state can be accessed programmatically  
- connectivity and policy can be installed through software

### Independent challenge

Goal: modify the automation logic to implement different connectivity behavior.

Tasks:

- Update the script to install a different connectivity policy  
- Test behavior after a link failure  
- Inspect updated paths and flow rules  

Key takeaway: network policies can be implemented and automated through software.

---

# Lab 3 – Service Differentiation Under Load  
**3:30 – 3:50**

This activity illustrates how SDN policies can differentiate traffic when multiple flows compete for limited capacity.

Context:

Rogers has previously seen our cloud-gaming demonstration.  
This activity focuses on the transport mechanisms that enable such service differentiation.

### Guided setup

Goal: establish a baseline before congestion.

Tasks:

- Generate traffic between two host pairs sharing the same bottleneck link  
- Observe baseline throughput for both flows  

Explanation:

- when resources are uncongested, different traffic classes can behave similarly

### Guided exercise

Goal: observe differentiated behavior under congestion.

Tasks:

- Increase offered load so both flows compete for the same bottleneck link  
- Apply controller policies that map each flow to a different queue  
- Measure throughput again and compare results  

Observation:

- prioritized traffic maintains better performance under congestion  
- best-effort traffic absorbs a larger share of the degradation

### Independent challenge

Goal: explore how different traffic policies affect service differentiation.

Tasks:

- Modify queue assignments for the flows  
- Observe how throughput changes  
- Identify which policies protect performance under congestion  

Key takeaway: SDN policies can enforce differentiated service levels across shared infrastructure.

Discussion:

- These mechanisms form the basis for service differentiation in modern networks  
- Our full cloud-gaming demonstration builds on these principles using our 5G testbed  
- In that platform, network slices are monitored using slice-level telemetry and resource allocations are adapted using automated scaling mechanisms

---

# Workshop Conclusion  
**3:50 – 4:00**

Topics:

- Recap of the Rogers Executive Workshop Series  
  - Workshop 1 – Core  
  - Workshop 2 – RAN  
  - Workshop 3 – Transport  
- Key ideas from programmable transport networks  
- Discussion and feedback