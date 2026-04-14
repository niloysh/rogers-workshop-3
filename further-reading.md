---
layout: page
permalink: /further-reading/
---

# Further Reading

Workshop 3 explores network programmability through OVS, ONOS, and SRv6. Another direction is to make the forwarding plane itself more programmable. Languages such as P4 (Programming Protocol-independent Packet Processors) let designers specify how packets are parsed, measured, and processed inside switches or NICs, which can enable richer telemetry, finer-grained anomaly detection, and selective function offloading in 5G networks.

### Slice Monitoring

**Dynamic SLA-aware Network Slice Monitoring**  
N. Saha, M. T. Arashloo, N. Shahriar, R. Boutaba. ACM SIGMETRICS '26. Ann Arbor, Michigan, USA. June 8-12, 2026.  
[Read the paper (PDF)](https://rboutaba.cs.uwaterloo.ca/Papers/2026/saha-sigmetrics26.pdf)

This connects naturally to Lab 4's slice-monitoring theme: once a slice has been provisioned, how should the network observe whether its SLA is actually being met, and how should monitoring adapt as slice conditions change?

### Fine-Grained Telemetry And Anomaly Detection

**Rethinking Telemetry Design for Fine-Grained Anomaly Detection in 5G User Planes**  
N. Saha, N. Limam, Y. Xiao, R. Boutaba. IEEE/IFIP Network Operations and Management Symposium (NOMS). Rome, Italy. May 18-22, 2026.  
[Read the paper (PDF)](https://rboutaba.cs.uwaterloo.ca/Papers/2026/saha-noms26.pdf)

This extends the workshop's telemetry story toward anomaly detection in the user plane. It asks what kind of telemetry is detailed enough to expose transient or slice-specific anomalies without overwhelming the network with monitoring overhead.

### Programmable Data Planes And Offloading

**Blink: A P4-Based 5G Centralized Unit**  
M. Rouili, R. Boutaba. IEEE/IFIP Network Operations and Management Symposium (NOMS). Honolulu, HI, USA. May 12-16, 2025.  
[Read the paper (PDF)](https://rboutaba.cs.uwaterloo.ca/Papers/Conferences/2023/rouili-blink-noms25.pdf)

This paper shows how programmable data planes can support 5G functions directly. It is a good example of offloading part of the packet-processing work when performance or timing constraints make a purely software design less attractive.

### Real-Time Detection In Open RAN

**RAID: In-Network RA Signaling Storm Detection for 5G Open RAN**  
M. Rouili, Y. Xiao, S. Liu, R. Boutaba.  
[Read the paper (PDF)](https://rboutaba.cs.uwaterloo.ca/Papers/2026/rouili-noms26.pdf)

This paper shows how P4-programmable switches can help protect O-RAN control planes by detecting and filtering malicious RA signaling directly in the network, before those requests overwhelm the Central Unit.
