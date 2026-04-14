---
layout: page
permalink: /setup/
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
.page-section p {
  font-size: 14px;
  color: #4a4740;
  line-height: 1.7;
  margin: 0 0 12px;
}
pre { margin: 12px 0 0; }
</style>

# Workshop Setup

<p class="intro-text">Use the bootstrap script if a machine still needs workshop setup. On the workshop machines, this should already have been run for you, so most participants should not need to do anything here.</p>

<div class="page-section">
  <h2>When to use this</h2>
  <p>The workshop environment is based on <strong>Ubuntu 22.04 LTS</strong>. If your machine is already prepared, you can skip this page and go straight to the labs. If something appears to be missing, or if you are setting up a fresh Ubuntu 22.04 install for the workshop, use the bootstrap script below.</p>
</div>

<div class="page-section">
  <h2>Download and run</h2>
  <p>As a general habit, take a quick look at any script before running it. You can review the downloaded file with <code>less bootstrap.sh</code> or open the local copy linked below, then run it once you understand the high-level steps.</p>
  <p>The bootstrap script is meant to set up everything needed for the workshop on a fresh install.</p>
  <p>Download the script, make it executable if needed, and run it from a terminal:</p>
  <pre><code class="language-bash">curl -O https://raw.githubusercontent.com/niloysh/rogers-workshop-3/main/scripts/bootstrap.sh
chmod +x bootstrap.sh
./bootstrap.sh</code></pre>
  <p>If you prefer, you can also open the local copy here: <a href="{{ '/scripts/bootstrap.sh' | relative_url }}"><code>scripts/bootstrap.sh</code></a>.</p>
</div>
