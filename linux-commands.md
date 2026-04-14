---
layout: page
permalink: /linux-commands/
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
.command { font-family: monospace; font-size: 13px; color: #1a1917; }
</style>

# Basic Linux Commands

<p class="intro-text">These are the commands participants will use repeatedly across Labs 1 to 4. Most are standard Linux shell commands; a few are workshop-specific commands inside the Mininet CLI or ONOS CLI.</p>

<div class="page-section">
  <h2>Terminal basics</h2>
  <ul>
    <li><span class="command">cd ~/labs/labX</span> — move into the lab folder before running commands.</li>
    <li><span class="command">exit</span> or <span class="command">Ctrl+D</span> — leave Mininet cleanly or close the current shell.</li>
    <li><span class="command">sudo</span> — run Mininet, OVS, and some network commands with administrator privileges.</li>
    <li><span class="command">bash script.sh</span> — run a shell script provided in an exercise.</li>
    <li><span class="command">python3 file.py</span> — run the Python topology, verifier, or controller scripts.</li>
  </ul>
</div>

<div class="page-section">
  <h2>Running and cleaning the labs</h2>
  <ul>
    <li><span class="command">sudo mn -c</span> — clean up leftover Mininet state before restarting a lab.</li>
    <li><span class="command">ssh -p 8101 -o HostKeyAlgorithms=+ssh-rsa onos@localhost</span> — open the ONOS CLI.</li>
    <li><span class="command">./script.sh</span> — run a lab helper script from the current folder, such as the HTTP server or IDS launcher.</li>
    <li><span class="command">jupyter notebook</span> — open the Lab 2 REST walkthrough and exercise notebooks.</li>
    <li><span class="command">tail -F /tmp/file.log</span> — follow a live log during the Lab 4 slice exercises.</li>
    <li><span class="command">sudo docker restart onos</span> — restart ONOS if the controller gets stuck.</li>
  </ul>
</div>

<div class="page-section">
  <h2>Network inspection and testing</h2>
  <ul>
    <li><span class="command">ip addr show</span> — inspect host interfaces and addresses.</li>
    <li><span class="command">ip route add ...</span> and <span class="command">ip route del ...</span> — add or remove SRv6 routes in Lab 3.</li>
    <li><span class="command">ip -6 addr add ...</span> — assign IPv6 SRv6 SIDs to interfaces.</li>
    <li><span class="command">ping -c N host</span> and <span class="command">ping6 -c N ipv6-address</span> — test IPv4 and IPv6 reachability.</li>
    <li><span class="command">curl http://...</span> — send HTTP traffic through the service chain.</li>
    <li><span class="command">sysctl -w key=value</span> — enable IPv6 forwarding and SRv6 support on hosts.</li>
    <li><span class="command">tshark -i iface ...</span> — capture and inspect SRv6 packets on an interface.</li>
  </ul>
</div>

<div class="page-section">
  <h2>Workshop-specific CLI commands</h2>
  <ul>
    <li><span class="command">mininet&gt; nodes</span>, <span class="command">net</span>, <span class="command">dump</span> — inspect the Mininet topology.</li>
    <li><span class="command">mininet&gt; pingall</span>, <span class="command">iperf h1 h2</span>, <span class="command">h1 ping -c 3 h2</span>, <span class="command">py h1.IP()</span> — test connectivity and inspect Mininet host state.</li>
    <li><span class="command">mininet&gt; h1 ip ...</span> or <span class="command">h1 curl ...</span> — run a Linux command inside a specific Mininet host.</li>
    <li><span class="command">onos&gt; apps -s -a</span>, <span class="command">devices</span>, <span class="command">links</span>, <span class="command">hosts</span>, <span class="command">flows</span> — inspect ONOS state.</li>
    <li><span class="command">onos&gt; app activate org.onosproject.&lt;app&gt;</span> — enable required ONOS apps.</li>
    <li><span class="command">onos&gt; cfg get org.onosproject.fwd.ReactiveForwarding</span> — verify that IPv6 forwarding is enabled.</li>
    <li><span class="command">sudo ovs-ofctl dump-flows s1 -O OpenFlow13</span> — inspect switch flow rules.</li>
    <li><span class="command">sudo ovs-ofctl add-flow s1 ...</span>, <span class="command">del-flows s1</span>, <span class="command">show s1</span> — manage OVS rules directly in Lab 1.</li>
  </ul>
</div>
