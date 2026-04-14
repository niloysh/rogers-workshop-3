---
layout: page
permalink: /further-reading/
---

<style>
.intro-text { font-size: 14px; color: #6b6860; margin-bottom: 24px; line-height: 1.7; }
.page-section { margin-top: 28px; }
.page-section h2 {
  font-size: 16px;
  color: #3a3a3a;
  margin: 0 0 10px;
  padding: 0;
  border: none;
}
.page-section p {
  font-size: 14px;
  color: #4a4740;
  line-height: 1.7;
  margin: 0 0 12px;
}
.paper-title { font-weight: 600; color: #1a1917; }
.paper-meta { color: #6b6860; }
.paper-link a {
  color: #3a3a3a;
  text-decoration: underline;
  text-underline-offset: 2px;
}
.paper-link a:hover { color: #1a1917; }
</style>

# Further Reading

<p class="intro-text">Workshop 3 explores transport network programmability through OVS, ONOS, and SRv6. Another direction is to make the forwarding plane itself more programmable. Languages such as Programming Protocol-independent Packet Processors (P4) let designers specify how packets are parsed, measured, and processed inside switches or NICs, which can enable richer telemetry, finer-grained anomaly detection, and selective function offloading in 5G networks.</p>

<div class="page-section">
  <h2>Slice Monitoring</h2>
  <p><span class="paper-title">Dynamic SLA-aware Network Slice Monitoring</span><br><span class="paper-meta">N. Saha, M. T. Arashloo, N. Shahriar, R. Boutaba. ACM SIGMETRICS '26. Ann Arbor, Michigan, USA. June 8-12, 2026.</span></p>
  <p class="paper-link"><a href="https://rboutaba.cs.uwaterloo.ca/Papers/2026/saha-sigmetrics26.pdf">Read the paper (PDF)</a></p>
  <p>This connects naturally to Lab 4's slice-monitoring theme: once a slice has been provisioned, how should the network observe whether its SLA is actually being met, and how should monitoring adapt as slice conditions change?</p>
</div>

<div class="page-section">
  <h2>Fine-Grained Telemetry And Anomaly Detection</h2>
  <p><span class="paper-title">Rethinking Telemetry Design for Fine-Grained Anomaly Detection in 5G User Planes</span><br><span class="paper-meta">N. Saha, N. Limam, Y. Xiao, R. Boutaba. IEEE/IFIP Network Operations and Management Symposium (NOMS). Rome, Italy. May 18-22, 2026.</span></p>
  <p class="paper-link"><a href="https://rboutaba.cs.uwaterloo.ca/Papers/2026/saha-noms26.pdf">Read the paper (PDF)</a></p>
  <p>This extends the workshop's telemetry story toward anomaly detection in the user plane. It asks what kind of telemetry is detailed enough to expose transient or slice-specific anomalies without overwhelming the network with monitoring overhead.</p>
</div>

<div class="page-section">
  <h2>Programmable Data Planes And Offloading</h2>
  <p><span class="paper-title">Blink: A P4-Based 5G Centralized Unit</span><br><span class="paper-meta">M. Rouili, R. Boutaba. IEEE/IFIP Network Operations and Management Symposium (NOMS). Honolulu, HI, USA. May 12-16, 2025.</span></p>
  <p class="paper-link"><a href="https://rboutaba.cs.uwaterloo.ca/Papers/Conferences/2023/rouili-blink-noms25.pdf">Read the paper (PDF)</a></p>
  <p>This paper shows how programmable data planes can support 5G functions directly. It is a good example of offloading part of the packet-processing work when performance or timing constraints make a purely software design less attractive.</p>
</div>

<div class="page-section">
  <h2>Real-Time Detection In Open RAN</h2>
  <p><span class="paper-title">RAID: In-Network RA Signaling Storm Detection for 5G Open RAN</span><br><span class="paper-meta">M. Rouili, Y. Xiao, S. Liu, R. Boutaba.</span></p>
  <p class="paper-link"><a href="https://rboutaba.cs.uwaterloo.ca/Papers/2026/rouili-noms26.pdf">Read the paper (PDF)</a></p>
  <p>This paper shows how P4-programmable switches can help protect O-RAN control planes by detecting and filtering malicious RA signaling directly in the network, before those requests overwhelm the Central Unit.</p>
</div>
