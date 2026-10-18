// SPDX-License-Identifier: GPL-3.0-or-later
// Real 240x240 four-card browser mirror. All bytes live in application
// PROGMEM; no LittleFS, external font, CDN, images or writes.
#include "boot/FslessWebUI.h"
namespace FslessWebUI {
const char PAGE[] PROGMEM = R"SHINO(<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SHINO // TV · Native UI V2</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#101318;color:#f6f3ef}
*{box-sizing:border-box}body{margin:0;padding:20px 12px}
main{max-width:760px;margin:auto}header{display:flex;align-items:center;justify-content:space-between;margin:0 0 16px;gap:12px}
header strong{letter-spacing:.12em;font-size:13px}#state{color:#bfc9d4;border:1px solid #394755;border-radius:18px;padding:5px 10px;font-size:11px}
.viewport{width:720px;height:720px;margin:auto}
.screen{width:240px;height:240px;transform:scale(3);transform-origin:top left;
background:#101318;display:grid;grid-template-columns:108px 108px;grid-template-rows:108px 108px;gap:8px;padding:8px}
.card{width:108px;height:108px;position:relative;border:1px solid #394755;border-radius:12px;background:#222933}
.label{position:absolute;top:10px;left:9px;color:#bfc9d4;font-size:11px;line-height:11px;font-weight:400;white-space:nowrap}
.value{position:absolute;top:47px;left:9px;color:#f6f3ef;font:700 19px/21px ui-monospace,Consolas,monospace;
letter-spacing:-1px;white-space:nowrap;font-variant-numeric:tabular-nums}
.track{position:absolute;left:8px;bottom:10px;width:90px;height:6px;border-radius:3px;background:#536277;overflow:hidden}
.fill{display:none;width:0;height:6px;border-radius:3px;background:#66d39a;transition:none}
.update-panel{max-width:720px;margin:18px auto 0;padding:14px;border:1px solid #394755;border-radius:12px;background:#222933}
.update-panel strong{font-size:13px;letter-spacing:.04em}
.update-panel p{font-size:12px;line-height:1.5;color:#bfc9d4;margin:8px 0}
.update-panel a{font-size:12px;color:#b9d9fb}
.update-panel .read-only{display:inline-block;margin-left:8px;padding:3px 7px;border:1px solid #8f7a40;color:#dec781;border-radius:10px;font-size:10px}
footer{font-size:12px;line-height:1.55;color:#aab6c3;max-width:720px;margin:15px auto 0}
footer a{color:#b9d9fb}a:focus-visible{outline:2px solid #66d39a}
@media(max-width:760px){.viewport{width:480px;height:480px}.screen{transform:scale(2)}}
@media(max-width:520px){.viewport{width:240px;height:240px}.screen{transform:scale(1)}}
</style></head><body><main>
<header><strong>SHINO // TV</strong><span id="state" role="status">WAITING FOR PC</span></header>
<div class="viewport"><section class="screen" aria-label="240 by 240 pixel four-metric device display">
<article class="card"><span class="label">CPU usage</span><output id="cpuV" class="value">—</output>
<div class="track" role="progressbar" aria-label="CPU usage" aria-valuemin="0" aria-valuemax="100" id="cpuTrack"><span class="fill" id="cpuFill"></span></div></article>
<article class="card"><span class="label">GPU usage</span><output id="gpuV" class="value">—</output>
<div class="track" role="progressbar" aria-label="GPU usage" aria-valuemin="0" aria-valuemax="100" id="gpuTrack"><span class="fill" id="gpuFill"></span></div></article>
<article class="card"><span class="label">RAM in use</span><output id="ramV" class="value">—</output>
<div class="track" role="progressbar" aria-label="RAM percentage in use" aria-valuemin="0" aria-valuemax="100" id="ramTrack"><span class="fill" id="ramFill"></span></div></article>
<article class="card"><span class="label">GPU<br>temperature</span><output id="tempV" class="value">—</output>
<div class="track" role="progressbar" aria-label="GPU temperature visual scale 30 to 90 Celsius" aria-valuemin="0" aria-valuemax="100" id="tempTrack"><span class="fill" id="tempFill"></span></div></article>
</section></div>
<section class="update-panel" aria-label="Firmware update status">
<strong>Firmware &amp; updates</strong><span class="read-only">READ-ONLY PREFLIGHT</span>
<p>Native SHINO-to-SHINO installation is NOT enabled in this firmware candidate.
No update file selection, upload or flash-write route is registered.
Check the device geometry before a separately reviewed writer is developed.</p>
<a href="/api/v1/bridge/ota/capabilities">View read-only OTA capabilities</a>
</section>
<footer>Exact 240×240 grid · 4 permanent values · colors reflect bar fill, not GPU danger thresholds.
PC measurements live only in RAM and expire after six seconds. No filesystem is provisioned.
<p><a href="/api/v1/bridge/status">Diagnostics</a> · <a href="/api/v1/bridge/fs-plan">Filesystem impact</a> ·
<a href="/api/v1/bridge/factory-return">Factory application reference</a></p>
Only a separately compiled exact-OEM application return may write flash; an OEM application BIN does not restore the original filesystem.</footer>
</main><script src="/ui.js" defer></script></body></html>)SHINO";

const char SCRIPT[] PROGMEM = R"SHINO((function(){
'use strict';
const colors=['#66D39A','#D8C35E','#D9894A','#8E394B'];
const thresholds=[20,50,80];
const ids=['cpu','gpu','ram','temp'];
const previous=[null,null,null,null];
const el=id=>document.getElementById(id);
const clamp100=v=>Math.max(0,Math.min(100,v));
function band(p){return p<20?0:p<50?1:p<80?2:3;}
function stableBand(prior,p){
if(prior===null)return band(p);
let b=prior;
while(b<3&&p>=thresholds[b]+2)b++;
while(b>0&&p<thresholds[b-1]-2)b--;
return b;
}
function fillPixels(p){return !Number.isFinite(p)||p<=0?0:Math.max(1,Math.min(90,Math.floor(90*clamp100(p)/100+0.5)));}
function fixed(v,unit){return Number.isFinite(v)?v.toFixed(1)+unit:'—';}
function setCard(i,text,pct){
const key=ids[i],fill=el(key+'Fill'),track=el(key+'Track');
el(key+'V').textContent=text;
if(!Number.isFinite(pct)||pct<0){
previous[i]=null;
fill.style.width='0px';
fill.style.display='none';
fill.style.borderRadius='0';
track.removeAttribute('aria-valuenow');return;
}
const p=clamp100(pct);
previous[i]=stableBand(previous[i],p);
const pixels=fillPixels(p);
// Discrete whole-device-pixel updates match the native LCD and avoid a
// lingering colored fragment when the metric falls to precisely 0.0%.
fill.style.width=pixels+'px';
fill.style.display=pixels===0?'none':'block';
// Native draws tiny 1..5px fills as plain rectangles, not malformed pills.
fill.style.borderRadius=pixels<6?'0':'3px';
fill.style.backgroundColor=colors[previous[i]];
track.setAttribute('aria-valuenow',p.toFixed(1));
}
function render(m){
const live=Boolean(m&&m.received&&!m.stale);
const gpu=live&&m.gpu_available===true;
el('state').textContent=live?'LIVE · PC':'WAITING / STALE';
if(!live){for(let i=0;i<4;i++)setCard(i,'—',null);return;}
const ram=Number.isFinite(m.memory_used_gb)?m.memory_used_gb:null;
const total=m.memory_total_gb;
const ramPct=Number.isFinite(total)&&total>0&&ram!==null&&ram<=total?clamp100(100*ram/total):null;
setCard(0,fixed(m.cpu_usage,'%'),Number.isFinite(m.cpu_usage)?m.cpu_usage:null);
setCard(1,gpu?fixed(m.gpu_usage,'%'):'—',gpu&&Number.isFinite(m.gpu_usage)?m.gpu_usage:null);
setCard(2,ram===null?'—':fixed(ram,' GB'),ramPct);
setCard(3,gpu?fixed(m.gpu_temp_c,'°C'):'—',gpu&&Number.isFinite(m.gpu_temp_c)?
clamp100(100*(m.gpu_temp_c-30)/60):null);
}
let pollingDenied=false;
async function poll(){
if(pollingDenied)return;
try{
const response=await fetch('/api/v1/bridge/metrics',{cache:'no-store',credentials:'same-origin'});
if(response.status===401||response.status===403){
pollingDenied=true; // Reopen / to perform a new explicit Digest login.
render(null);el('state').textContent='SESSION EXPIRED · REOPEN /';
return;
}
if(!response.ok)throw Error('Metrics request failed');
render(await response.json());
}catch(_){render(null);el('state').textContent='DEVICE OFFLINE';}
}
poll();setInterval(poll,2000);
})();)SHINO";
} // namespace FslessWebUI
