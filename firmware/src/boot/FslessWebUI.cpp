// SPDX-License-Identifier: GPL-3.0-or-later
// All UI bytes live in application program flash. No LittleFS is mounted.
#include "boot/FslessWebUI.h"
namespace FslessWebUI {
const char PAGE[] PROGMEM = R"SHINO(<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SHINO // TV — RAM Dashboard</title>
<style>
:root{font-family:system-ui,sans-serif;color:#e9edf1;background:#0d1118}
*{box-sizing:border-box}body{margin:0;padding:clamp(16px,4vw,35px)}
main{max-width:720px;margin:auto}header{display:flex;justify-content:space-between;gap:12px;align-items:center}
h1{font-size:clamp(24px,5vw,38px);letter-spacing:-1.4px;margin:10px 0 3px}
small,.muted{color:#a4aebf}p{line-height:1.5}
.pill{font-size:12px;border:1px solid #536273;border-radius:22px;padding:6px 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:12px;margin:26px 0}
article{border:1px solid #303b4a;background:linear-gradient(135deg,#202b3b,#141b27);
border-radius:19px;padding:18px;min-height:118px}
article strong{display:block;font-size:31px;margin-top:13px;letter-spacing:-1px}
article label{color:#b9c6d2;font-size:13px}
meter{width:100%;margin-top:8px}
footer{border-top:1px solid #303b4a;padding-top:17px;color:#a4aebf;font-size:13px}
a{color:#b6d8fc}a:focus-visible{outline:2px solid #7dbaf4}
</style>
<main><header><small>SHINO // CONTROL</small><span class="pill" id="state">WAITING FOR PC</span></header>
<h1>SHINO // TV</h1><p class="muted">ESP8266 live telemetry. Display and Web UI run from application flash. No filesystem provisioning.</p>
<section class="grid" aria-label="PC telemetry">
<article><label for="cpu">CPU usage</label><strong id="cpuV">—</strong><meter id="cpu" min="0" max="100" value="0"></meter></article>
<article><label for="gpu">GPU usage</label><strong id="gpuV">—</strong><meter id="gpu" min="0" max="100" value="0"></meter></article>
<article><label>RAM in use</label><strong id="ramV">—</strong></article>
<article><label>GPU temperature</label><strong id="tempV">—</strong></article>
</section>
<footer>RAM only · PC samples expire after six seconds. No native FS mount or automatic format.
<p><a href="/api/v1/bridge/status">Bridge diagnostics</a> ·
<a href="/api/v1/bridge/fs-plan">FS impact</a> ·
<a href="/api/v1/bridge/factory-return">Factory application reference</a></p>
<p>Only the optional separately compiled OEM application return writes flash. Neither a functioning dashboard nor an OEM app BIN guarantees full original filesystem recovery.</p></footer></main>
<script src="/ui.js" defer></script></html>)SHINO";

const char SCRIPT[] PROGMEM = R"SHINO((function(){
'use strict';
const el=id=>document.getElementById(id);
const number=(v,units)=>Number.isFinite(v)?v.toFixed(1)+units:'—';
async function poll(){
try{
const reply=await fetch('/api/v1/bridge/metrics',{cache:'no-store',credentials:'same-origin'});
if(!reply.ok)throw Error('HTTP '+reply.status);
const m=await reply.json();
const live=Boolean(m.received&&!m.stale);
el('state').textContent=live?'LIVE · PC':'WAITING / STALE';
el('cpuV').textContent=live?number(m.cpu_usage,'%'):'—';
el('gpuV').textContent=live&&m.gpu_available?number(m.gpu_usage,'%'):'—';
el('ramV').textContent=live?number(m.memory_used_gb,' GB'):'—';
el('tempV').textContent=live&&m.gpu_available?number(m.gpu_temp_c,'°C'):'—';
el('cpu').value=live?m.cpu_usage:0;
el('gpu').value=live&&m.gpu_available?m.gpu_usage:0;
}catch(_){el('state').textContent='DEVICE OFFLINE';}
}
poll();setInterval(poll,2000);
})();)SHINO";
} // namespace FslessWebUI
