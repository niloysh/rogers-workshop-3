---
permalink: /
layout: page
---

<style>
.schedule-legend{display:flex;gap:20px;flex-wrap:wrap;margin:16px 0 12px}
.legend-item{display:flex;align-items:center;gap:6px;font-size:13px;color:#6b6860}
.legend-pip{width:10px;height:10px;border-radius:2px;flex-shrink:0}
.series-links{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0 16px}
.series-link{font-size:14px;color:#6b6860;text-decoration:none;padding:5px 11px;border-radius:5px;border:1px solid #e4e2da;background:white}
.series-link:hover{border-color:#6b6860;color:#1a1917}
.schedule{display:flex;flex-direction:column;gap:4px;margin:0 0 32px}
.schedule-row{display:grid;grid-template-columns:88px 1fr 72px;align-items:stretch}
.schedule-time{display:flex;align-items:flex-start;padding-top:14px;padding-right:16px;font-family:monospace;font-size:12px;color:#9c9a94;justify-content:flex-end}
.schedule-dur{display:flex;align-items:flex-start;padding-top:14px;padding-left:12px;font-family:monospace;font-size:11px;color:#9c9a94;white-space:nowrap}
.schedule-block{border-radius:8px;padding:14px 18px;border-left:3px solid transparent}
.block-title{font-size:14px;font-weight:600;line-height:1.3;margin:0 0 5px;padding:0;border:none}
.block-desc{font-size:13px;color:#6b6860;line-height:1.55;margin:0}
.block-footer{margin-top:8px}
.row-concepts .schedule-block{background:#eeedf8;border-left-color:#4a3f8f}
.row-concepts .block-title{color:#4a3f8f}
.row-lab .schedule-block{background:#e4f2ed;border-left-color:#1a6b57}
.row-lab .block-title{color:#1a6b57}
.row-break .schedule-block{background:#f5f0e0;border-left-color:#7a6a2e}
.row-break .block-title{color:#7a6a2e;font-weight:400}
.row-shared .schedule-block{background:#efefef;border-left-color:#3a3a3a}
.row-shared .block-title{color:#3a3a3a}
.materials-link{display:inline-flex;align-items:center;gap:5px;font-family:monospace;font-size:10px;letter-spacing:.06em;text-transform:uppercase;text-decoration:none;padding:3px 9px;border-radius:4px;border:1px solid #e4e2da;color:#9c9a94;cursor:default}
.materials-link.available{color:#6b6860;border-color:#6b6860;cursor:pointer}
.materials-link.available:hover{background:#1a1917;color:#fff;border-color:#1a1917}
.materials-link svg{width:12px;height:12px;flex-shrink:0;vertical-align:middle}
.quick-links{margin-top:32px;padding-top:24px;border-top:1px solid #e4e2da}
.quick-links-grid{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.quick-link{font-size:13px;color:#6b6860;text-decoration:none;padding:5px 11px;border-radius:5px;border:1px solid #e4e2da;background:white}
.quick-link:hover{border-color:#6b6860;color:#1a1917}
@media(max-width:600px){.schedule-row{grid-template-columns:52px 1fr 52px}.schedule-block{padding:12px 14px}}
</style>

Welcome to **Workshop 3** in the Rogers Executive Workshop Series, presented as part of the [Rogers Chair in Network Automation](https://rboutaba.cs.uwaterloo.ca/).

This workshop complements the previous sessions in the series:

<div class="series-links">
  <a class="series-link" href="https://niloysh.github.io/rogers-workshop/">Workshop 1 — 5G Core Networks</a>
  <a class="series-link" href="https://mhmd97z.github.io/rogers-workshop-2/">Workshop 2 — Radio Access Networks</a>
</div>

The first workshop focused on 5G core deployment, network slicing, slice monitoring and data processing, and dynamic resource scaling, while the second explored 5G RAN deployment, closed-loop controls in O-RAN, and xApps development for monitoring and control.

In this third workshop, we turn our attention to the transport network, which interconnects the RAN and the core. Participants will learn how **Software-Defined Networking (SDN)** enables programmable and automated transport infrastructures. Through a combination of lectures and hands-on labs, participants will explore programmable forwarding using **Open vSwitch** and **Mininet**, centralized control using the **ONOS SDN controller**, and path control using **SRv6**, culminating in a simplified transport slice controller that demonstrates the key concepts.

## Workshop Schedule

<div class="schedule-legend">
  <span class="legend-item"><span class="legend-pip" style="background:#4a3f8f"></span>Concepts</span>
  <span class="legend-item"><span class="legend-pip" style="background:#1a6b57"></span>Labs</span>
  <span class="legend-item"><span class="legend-pip" style="background:#7a6a2e"></span>Breaks</span>
</div>

<div class="schedule">

  <div class="schedule-row row-shared">
    <div class="schedule-time">9:00</div>
    <div class="schedule-block">
      <div class="block-title">Introduction</div>
      <div class="block-desc">Welcome, logistics, and agenda overview.</div>
    </div>
    <div class="schedule-dur">15 min</div>
  </div>

  <div class="schedule-row row-concepts">
    <div class="schedule-time">9:15</div>
    <div class="schedule-block">
      <div class="block-title">Concepts 1 — Programmable networking</div>
      <div class="block-desc">Why traditional networks are difficult to change, and how SDN addresses this by separating the control plane from the data plane.</div>
      <div class="block-footer">
        <a class="materials-link" href="#"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="12" height="12"><path d="M6 1v7M3 5l3 3 3-3M1 10h10"/></svg> Slides — TBA</a>
      </div>
    </div>
    <div class="schedule-dur">20 min</div>
  </div>

  <div class="schedule-row row-lab">
    <div class="schedule-time">9:35</div>
    <div class="schedule-block">
      <div class="block-title">Lab 1 — Programmable forwarding with OVS + Mininet</div>
      <div class="block-desc">Build a network topology in Mininet and program OVS switches directly with flow rules. You are the control plane.</div>
      <div class="block-footer">
        <a class="materials-link available" href="assets/slides/lab1.html" target="_blank"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="12" height="12"><path d="M6 1v7M3 5l3 3 3-3M1 10h10"/></svg> Lab materials</a>
      </div>
    </div>
    <div class="schedule-dur">60 min</div>
  </div>

  <div class="schedule-row row-break">
    <div class="schedule-time">10:35</div>
    <div class="schedule-block">
      <div class="block-title">Coffee break</div>
    </div>
    <div class="schedule-dur">15 min</div>
  </div>

  <div class="schedule-row row-concepts">
    <div class="schedule-time">10:50</div>
    <div class="schedule-block">
      <div class="block-title">Concepts 2 — OpenFlow, controllers and intents</div>
      <div class="block-desc">The OpenFlow model behind Lab 1, how an SDN controller automates it, and how intents express network policy at a higher level of abstraction.</div>
      <div class="block-footer">
        <a class="materials-link" href="#"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="12" height="12"><path d="M6 1v7M3 5l3 3 3-3M1 10h10"/></svg> Slides — TBA</a>
      </div>
    </div>
    <div class="schedule-dur">25 min</div>
  </div>

  <div class="schedule-row row-lab">
    <div class="schedule-time">11:15</div>
    <div class="schedule-block">
      <div class="block-title">Lab 2 — Controller-based connectivity with ONOS</div>
      <div class="block-desc">Connect your topology to ONOS and use the REST API in Python to query the network, install host intents, and observe automatic re-routing after a link failure.</div>
      <div class="block-footer">
        <a class="materials-link available" href="assets/slides/lab2.html" target="_blank"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="12" height="12"><path d="M6 1v7M3 5l3 3 3-3M1 10h10"/></svg> Lab materials</a>
      </div>
    </div>
    <div class="schedule-dur">60 min</div>
  </div>

  <div class="schedule-row row-break">
    <div class="schedule-time">12:15</div>
    <div class="schedule-block">
      <div class="block-title">Lunch break</div>
    </div>
    <div class="schedule-dur">60 min</div>
  </div>

  <div class="schedule-row row-concepts">
    <div class="schedule-time">1:15</div>
    <div class="schedule-block">
      <div class="block-title">Concepts 3 — Network slicing and SRv6</div>
      <div class="block-desc">How network virtualization enables transport slicing, hard vs soft isolation, and how SRv6 provides path control using standard IPv6 extension headers.</div>
      <div class="block-footer">
        <a class="materials-link" href="#"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="12" height="12"><path d="M6 1v7M3 5l3 3 3-3M1 10h10"/></svg> Slides — TBA</a>
      </div>
    </div>
    <div class="schedule-dur">30 min</div>
  </div>

  <div class="schedule-row row-lab">
    <div class="schedule-time">1:45</div>
    <div class="schedule-block">
      <div class="block-title">Lab 3 — SRv6 path programming</div>
      <div class="block-desc">Assign SRv6 segment IDs, program a Segment Routing Header on an ingress host, and steer traffic through a middlebox. Inspect the SRH in transit with tshark.</div>
      <div class="block-footer">
        <a class="materials-link" href="#"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="12" height="12"><path d="M6 1v7M3 5l3 3 3-3M1 10h10"/></svg> Lab materials — TBA</a>
      </div>
    </div>
    <div class="schedule-dur">60 min</div>
  </div>

  <div class="schedule-row row-break">
    <div class="schedule-time">2:45</div>
    <div class="schedule-block">
      <div class="block-title">Coffee break</div>
    </div>
    <div class="schedule-dur">15 min</div>
  </div>

  <div class="schedule-row row-lab">
    <div class="schedule-time">3:00</div>
    <div class="schedule-block">
      <div class="block-title">Lab 4 — Transport slice controller</div>
      <div class="block-desc">Bring everything together. A provided controller combines ONOS, SRv6, and OVS queuing to demonstrate transport slice provisioning — then extend it with your own second slice.</div>
      <div class="block-footer">
        <a class="materials-link" href="#"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="12" height="12"><path d="M6 1v7M3 5l3 3 3-3M1 10h10"/></svg> Lab materials — TBA</a>
      </div>
    </div>
    <div class="schedule-dur">70 min</div>
  </div>

  <div class="schedule-row row-shared">
    <div class="schedule-time">4:10</div>
    <div class="schedule-block">
      <div class="block-title">Wrap-up and Q&amp;A</div>
      <div class="block-desc">Open discussion and workshop feedback.</div>
      <div class="block-footer">
        <a class="materials-link available" href="https://docs.google.com/forms/d/e/1FAIpQLSeeYKe7PKKg0iLa_khv73pAFY2ke9KzenRFFz9bPcBhUPJ8mQ/viewform?usp=header" target="_blank"><svg viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.5" width="12" height="12"><path d="M6 1v7M3 5l3 3 3-3M1 10h10"/></svg> Feedback form</a>
      </div>
    </div>
    <div class="schedule-dur">10 min</div>
  </div>

</div>

## Quick Links

- [Learning outcomes](learning-outcomes)
- [Workshop feedback](https://docs.google.com/forms/d/e/1FAIpQLSeeYKe7PKKg0iLa_khv73pAFY2ke9KzenRFFz9bPcBhUPJ8mQ/viewform?usp=header)
