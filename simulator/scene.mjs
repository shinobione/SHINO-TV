/** SHINO // TV scene protocol v0. Preview only; no network or hardware access. */
const LIMITS = { metrics: ['cpu', 'gpu', 'ram', 'gpuTemp'], music: ['progress'], agent: ['progress'], release: ['days'] };
const trim = (value, fallback, max = 40) => typeof value === 'string' ? value.trim().slice(0, max) || fallback : fallback;
const number = (value, fallback, min, max) => typeof value === 'number' && Number.isFinite(value) ? Math.max(min, Math.min(max, value)) : fallback;

export const PRESETS = {
  metrics: {kind:'metrics', title:'PC HEALTH', cpu:27, gpu:62, ram:43, gpuTemp:68},
  music: {kind:'music', title:'NOW PLAYING', artist:'SHINOBIWAN', track:'MACHINE FEVER', progress:38},
  agent: {kind:'agent', title:'CODEX', status:'RUNNING', task:'Build simulator', progress:72},
  release: {kind:'release', title:'NEXT RELEASE', artist:'SHINOBIWAN', track:'DANCE AT MY FUNERAL', days:12}
};

export function normalizeScene(raw) {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw) || !Object.hasOwn(LIMITS, raw.kind)) {
    throw new TypeError('Scene must be an object with kind: metrics, music, agent or release.');
  }
  const kind = raw.kind;
  const result = {kind, title: trim(raw.title, PRESETS[kind].title, 24)};
  if (kind === 'metrics') {
    for (const field of LIMITS.metrics) result[field] = number(raw[field], PRESETS.metrics[field], field === 'gpuTemp' ? -40 : 0, field === 'gpuTemp' ? 130 : 100);
    result.source = ['demo', 'live', 'offline'].includes(raw.source) ? raw.source : 'demo';
    result.gpuAvailable = raw.gpuAvailable !== false;
  } else if (kind === 'music') {
    result.artist = trim(raw.artist, 'UNKNOWN ARTIST', 32);
    result.track = trim(raw.track, 'UNKNOWN TRACK', 48);
    result.progress = number(raw.progress, 0, 0, 100);
  } else if (kind === 'agent') {
    result.status = trim(raw.status, 'UNKNOWN', 18).toUpperCase();
    result.task = trim(raw.task, 'No current task', 56);
    result.progress = number(raw.progress, 0, 0, 100);
  } else {
    result.artist = trim(raw.artist, 'SHINOBIWAN', 32);
    result.track = trim(raw.track, 'UNTITLED', 48);
    result.days = Math.round(number(raw.days, 0, 0, 9999));
  }
  return result;
}

const C = { bg:'#0b0c10', panel:'#181b21', line:'#33343a', white:'#f0ede9', muted:'#a8a5a2', gold:'#e2ad63', lime:'#a8d0b6', purple:'#b7a2d9'};
function round(ctx, x,y,w,h,r,fill) {
  ctx.fillStyle=fill; ctx.beginPath(); ctx.moveTo(x+r,y);ctx.lineTo(x+w-r,y);ctx.quadraticCurveTo(x+w,y,x+w,y+r);
  ctx.lineTo(x+w,y+h-r);ctx.quadraticCurveTo(x+w,y+h,x+w-r,y+h);ctx.lineTo(x+r,y+h);
  ctx.quadraticCurveTo(x,y+h,x,y+h-r);ctx.lineTo(x,y+r);ctx.quadraticCurveTo(x,y,x+r,y);ctx.closePath();ctx.fill();
}
function label(ctx, str,x,y,size=11,color=C.white,weight=500,maxWidth=202) {
  ctx.fillStyle=color;ctx.font=`${weight} ${size}px system-ui, sans-serif`;ctx.fillText(str,x,y,maxWidth);
}
function bar(ctx, name, v, y, color=C.gold, unit='%') {
  label(ctx,name,19,y,11,C.muted,700);ctx.textAlign='right';label(ctx,v===null?'N/A':`${Math.round(v)}${unit}`,221,y,12,C.white,700,65);ctx.textAlign='left';
  round(ctx,19,y+8,202,7,3,C.line);if(v !== null && v>0)round(ctx,19,y+8,202*Math.min(1,v/100),7,3,color);
}
export function renderScene(ctx, input) {
  const scene=normalizeScene(input);
  ctx.clearRect(0,0,240,240);ctx.fillStyle=C.bg;ctx.fillRect(0,0,240,240);
  ctx.strokeStyle=C.line;ctx.strokeRect(.5,.5,239,239);
  round(ctx,14,14,212,30,8,C.panel);
  label(ctx,'//',23,34,12,C.gold,800);label(ctx,scene.title,46,34,12,C.white,800,165);
  ctx.fillStyle=C.gold;ctx.fillRect(17,53,36,2);
  if(scene.kind==='metrics'){
    if (scene.source === 'offline') {
      label(ctx,'PC OFFLINE',19,107,22,C.gold,800);
      label(ctx,'Start the companion service',19,140,11,C.muted,600);
      label(ctx,'No SmallTV connection required',19,163,10,C.muted,500);
    } else {
      label(ctx,scene.source === 'live'?'LIVE SYSTEM / THIS PC':'SYSTEM / DEMO DATA',19,77,9,C.muted,700);
      for(const [i,key] of ['cpu','gpu','ram'].entries())bar(ctx,key.toUpperCase(),key==='gpu'&&!scene.gpuAvailable?null:scene[key],98+i*34,i===1?C.purple:C.gold);
      label(ctx,`GPU TEMP  ${scene.gpuAvailable?`${Math.round(scene.gpuTemp)}°C`:'N/A'}`,19,215,12,C.lime,700);
    }
  } else if(scene.kind==='music'){
    round(ctx,19,68,80,80,12,C.panel);label(ctx,'S',45,120,47,C.gold,800);
    label(ctx,scene.artist.toUpperCase(),111,91,10,C.gold,700,110);
    label(ctx,scene.track.toUpperCase(),111,113,13,C.white,800,108);
    label(ctx,'NOW PLAYING',111,140,9,C.muted,700);
    round(ctx,19,174,202,8,4,C.line);if(scene.progress>0)round(ctx,19,174,202*scene.progress/100,8,4,C.gold);
    label(ctx,`${Math.round(scene.progress)}%`,19,202,11,C.muted,600);
  } else if(scene.kind==='agent'){
    label(ctx,'AGENT STATUS',19,81,10,C.muted,700);
    round(ctx,19,93,202,42,9,C.panel);label(ctx,scene.status,31,119,20,scene.status==='RUNNING'?C.lime:C.gold,800);
    label(ctx,scene.task,19,155,11,C.white,500);
    round(ctx,19,173,202,9,4,C.line);if(scene.progress>0)round(ctx,19,173,202*scene.progress/100,9,4,C.purple);
    label(ctx,`${Math.round(scene.progress)}% COMPLETE`,19,204,11,C.muted,700);
  } else {
    label(ctx,scene.artist.toUpperCase(),19,78,11,C.gold,700);
    label(ctx,scene.track.toUpperCase(),19,105,15,C.white,800);
    round(ctx,19,126,202,72,10,C.panel);
    label(ctx,String(scene.days).padStart(2,'0'),30,180,43,C.gold,800,95);
    label(ctx,'DAYS',125,178,16,C.white,800);
    label(ctx,'COUNTDOWN / DEMO',19,217,9,C.muted,700);
  }
  ctx.strokeStyle=C.line;ctx.beginPath();ctx.moveTo(18,229);ctx.lineTo(222,229);ctx.stroke();
  return scene;
}
