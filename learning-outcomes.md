---
layout: page
permalink: /learning-outcomes/
---

<style>
.outcomes { margin-top: 8px; }
.outcome-group {
  margin-bottom: 28px;
  padding: 20px 24px;
  border-radius: 8px;
  border-left: 3px solid #e4e2da;
  background: #faf9f6;
}
.outcome-group h3 {
  font-size: 14px;
  font-weight: 600;
  color: #3a3a3a;
  margin: 0 0 12px;
  padding: 0;
  border: none;
  font-family: inherit;
}
.outcome-group ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.outcome-group li {
  font-size: 14px;
  color: #4a4740;
  line-height: 1.6;
  padding: 4px 0 4px 16px;
  position: relative;
}
.outcome-group li::before {
  content: '→';
  position: absolute;
  left: 0;
  color: #9c9a94;
  font-size: 12px;
  top: 5px;
}
.outcome-group.concepts { border-left-color: #4a3f8f; background: #eeedf8; }
.outcome-group.concepts h3 { color: #4a3f8f; }
.outcome-group.lab { border-left-color: #1a6b57; background: #e4f2ed; }
.outcome-group.lab h3 { color: #1a6b57; }
.outcome-group.slicing { border-left-color: #7a6a2e; background: #f5f0e0; }
.outcome-group.slicing h3 { color: #7a6a2e; }
.outcome-group.capstone { border-left-color: #3a3a3a; background: #efefef; }
.outcome-group.capstone h3 { color: #3a3a3a; }
.intro-text { font-size: 14px; color: #6b6860; margin-bottom: 24px; line-height: 1.7; }
</style>

# Learning Outcomes

<p class="intro-text">By the end of this workshop, participants will be able to:</p>

<div class="outcomes">

  <div class="outcome-group concepts">
    <h3>Programmable networking</h3>
    <ul>
      <li>Explain how SDN addresses the limitations of traditional networks through control/data plane separation</li>
      <li>Program OVS switches with flow rules and implement connectivity policies using Mininet</li>
    </ul>
  </div>

  <div class="outcome-group lab">
    <h3>SDN controllers and intents</h3>
    <ul>
      <li>Use the ONOS REST API in Python to query topology and install host intents</li>
      <li>Observe how a controller automates path computation and handles link failures</li>
    </ul>
  </div>

  <div class="outcome-group slicing">
    <h3>Network slicing and SRv6</h3>
    <ul>
      <li>Explain how network virtualization enables transport slicing and the trade-off between hard and soft isolation</li>
      <li>Program SRv6 paths to steer traffic through specific nodes and inspect SRH headers with tshark</li>
    </ul>
  </div>

  <div class="outcome-group capstone">
    <h3>Transport slice controller</h3>
    <ul>
      <li>Describe how ONOS, SRv6, and OVS queuing combine to provision a transport slice</li>
      <li>Provision and verify an isolated slice alongside a competing traffic flow</li>
    </ul>
  </div>

</div>