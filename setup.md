---
layout: page
permalink: /setup/
---

<style>
.setup-sections { margin-top: 8px; }
.setup-group {
  margin-bottom: 28px;
  padding: 20px 24px;
  border-radius: 8px;
  border-left: 3px solid #e4e2da;
  background: #faf9f6;
}
.setup-group h3 {
  font-size: 14px;
  font-weight: 600;
  color: #3a3a3a;
  margin: 0 0 12px;
  padding: 0;
  border: none;
  font-family: inherit;
}
.setup-group p {
  font-size: 14px;
  color: #4a4740;
  line-height: 1.7;
  margin: 0 0 12px;
}
.setup-group p:last-child { margin-bottom: 0; }
.setup-group ul {
  margin: 0;
  padding: 0;
  list-style: none;
}
.setup-group li {
  font-size: 14px;
  color: #4a4740;
  line-height: 1.7;
  padding: 6px 0 6px 16px;
  position: relative;
}
.setup-group li::before {
  content: '→';
  position: absolute;
  left: 0;
  color: #9c9a94;
  font-size: 12px;
  top: 8px;
}
.setup-group.notice { border-left-color: #4a3f8f; background: #eeedf8; }
.setup-group.notice h3 { color: #4a3f8f; }
.setup-group.steps { border-left-color: #1a6b57; background: #e4f2ed; }
.setup-group.steps h3 { color: #1a6b57; }
.intro-text { font-size: 14px; color: #6b6860; margin-bottom: 24px; line-height: 1.7; }
pre { margin: 12px 0 0; }
</style>

# Workshop Setup

<p class="intro-text">Use the bootstrap script if a machine still needs workshop setup. On the workshop machines, this should already have been run for you, so most participants should not need to do anything here.</p>

<div class="setup-sections">

  <div class="setup-group notice">
    <h3>When to use this</h3>
    <p>The workshop environment is based on <strong>Ubuntu 22.04 LTS</strong>. If your machine is already prepared, you can skip this page and go straight to the labs. If something appears to be missing, or if you are setting up a fresh Ubuntu 22.04 install for the workshop, use the bootstrap script below.</p>
  </div>

  <div class="setup-group steps">
    <h3>Download and run</h3>
    <p>As a general habit, take a quick look at any script before running it. You can review the downloaded file with <code>less bootstrap.sh</code> or open the local copy linked below, then run it once you understand the high-level steps.</p>
    <p>The bootstrap script is meant to set up everything needed for the workshop on a fresh install.</p>
    <p>Download the script, make it executable if needed, and run it from a terminal:</p>
    <pre><code class="language-bash">curl -O https://raw.githubusercontent.com/niloysh/rogers-workshop-3/main/scripts/bootstrap.sh
chmod +x bootstrap.sh
./bootstrap.sh</code></pre>
    <p>If you prefer, you can also open the local copy here: <a href="{{ '/scripts/bootstrap.sh' | relative_url }}"><code>scripts/bootstrap.sh</code></a>.</p>
  </div>

</div>
