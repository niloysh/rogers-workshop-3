---
layout: page
permalink: /learning-outcomes/
---

<style>
.intro-text { font-size: 14px; color: #6b6860; margin-bottom: 24px; line-height: 1.7; }
.page-section { margin-top: 26px; }
.page-section h2 {
  font-size: 16px;
  color: #3a3a3a;
  margin: 0 0 10px;
  padding: 0;
  border: none;
}
.page-section ul { margin: 0; }
.page-section li {
  font-size: 14px;
  color: #4a4740;
  line-height: 1.7;
  margin: 0 0 8px;
}
</style>

# Learning Outcomes

<p class="intro-text">By the end of this workshop, participants will have developed practical skills in the following areas:</p>

<div class="page-section">
  <h2>SDN Data Plane Programmability</h2>
  <ul>
    <li>Build a simple Mininet topology and use Open vSwitch as a programmable forwarding plane.</li>
    <li>Install, inspect, and validate flow rules on OVS switches to implement a desired forwarding policy.</li>
  </ul>
</div>

<div class="page-section">
  <h2>Network Programmability with ONOS</h2>
  <ul>
    <li>Connect a topology to ONOS and use its APIs to inspect devices, links, hosts, and paths.</li>
    <li>Use intents and other controller-driven abstractions to automate connectivity and reason about controller responses to link failures.</li>
  </ul>
</div>

<div class="page-section">
  <h2>Path Steering with SRv6</h2>
  <ul>
    <li>Configure SRv6 segment IDs and program Segment Routing Headers to steer traffic along a chosen path.</li>
    <li>Verify, using packet inspection and path observation, that SRv6 traffic traverses the intended intermediate nodes or middleboxes.</li>
  </ul>
</div>

<div class="page-section">
  <h2>Transport Slicing</h2>
  <ul>
    <li>Combine ONOS, SRv6, and OVS queuing to provision a simplified transport slice end to end.</li>
    <li>Evaluate slice behavior under competing traffic and relate the observed results to transport-level isolation goals.</li>
  </ul>
</div>
