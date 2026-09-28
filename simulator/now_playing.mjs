/**
 * SHINO // TV V0.3 browser-only 240×240 music / four-value health preview.
 * Pure scene model and Canvas rendering. NO fetch, WebSocket, device API,
 * filesystem, account permissions, service worker or firmware action.
 */
export const WIDTH = 240;
export const HEIGHT = 240;
export const OVERLAY_MS = 5000;
export const ARTWORK_MAX_BYTES = 1024 * 1024;
export const ARTWORK_MAX_PIXELS = 4_000_000;
export const ARTWORK_MAX_SIDE = 4096;
const C = Object.freeze({
  bg:'#0a0b0e', panel:'#17191d', line:'#33353a', text:'#f5eee5',
  muted:'#a6a3a1', gold:'#dda967', pale:'#edc892', mint:'#77bf9a',
  yellow:'#d5bc67', orange:'#c8844f', burgundy:'#853f4a', inactive:'#56545a'
});
const fields = ['cpu','gpu','ram','gpuTemp'];
const sanitize = (value, limit, fallback='') => typeof value === 'string'
  ? value.replace(/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,' ')
    .replace(/\s+/g,' ').trim().slice(0,limit) || fallback
  : fallback;
const bounded = (v, max) => typeof v === 'number' && Number.isFinite(v)
  ? Math.min(max,Math.max(0,v)) : null;
const seconds = value => typeof value === 'number' && Number.isFinite(value)
  ? Math.min(7*86400,Math.max(0,Math.floor(value))) : null;
const sourceObj = value => value && typeof value === 'object' && !Array.isArray(value) ? value : {};

export const SAMPLE_METRICS = Object.freeze({cpu:27,gpu:62,ram:43,gpuTemp:68});
export const SAMPLE_TRACKS = Object.freeze([
  Object.freeze({state:'PLAYING',source:'DEMO / Spotify.exe',title:'Velvet HAMMER',
    artist:'ShinoBiWan',album:'Velvet HAMMER',position_seconds:44,
    duration_seconds:229,cover_available:false}),
  Object.freeze({state:'PLAYING',source:'DEMO / Spotify.exe',title:'Weapon is FED',
    artist:'ShinoBiWan',album:'COAL TO DIAMOND',position_seconds:6,
    duration_seconds:165,cover_available:false})
]);

export function normalizeMetrics(raw) {
  const source = sourceObj(raw);
  const values = {};
  for (const key of fields) values[key] = bounded(source[key], key==='gpuTemp'?120:100);
  return values; // missing data is null/stale, never invented zero
}
export function normalizeMedia(raw) {
  const s=sourceObj(raw), rawState=sanitize(s.state,18).toUpperCase();
  const state=['PLAYING','PAUSED','STOPPED','CHANGING','CLOSED','NO_SESSION','UNAVAILABLE']
    .includes(rawState)?rawState:'UNKNOWN';
  const duration=seconds(s.duration_seconds);
  let position=seconds(s.position_seconds);
  if (duration !== null && position !== null) position=Math.min(position,duration);
  return {
    state, source:sanitize(s.source,80), title:sanitize(s.title,120),
    artist:sanitize(s.artist,120), album:sanitize(s.album,120),
    position_seconds:position, duration_seconds:duration,
    cover_available:s.cover_available===true
  };
}
export function trackKey(media) {
  const m=normalizeMedia(media);
  return JSON.stringify([m.source,m.title,m.artist,m.album]);
}
export function createPreviewState() {
  return {
    view:'health', policy:'overlay', overlayUntil:null,
    metrics:normalizeMetrics(SAMPLE_METRICS), media:normalizeMedia(SAMPLE_TRACKS[0])
  };
}
export function updatePreviewState(state,event,now=0) {
  const current=state || createPreviewState(), type=event?.type;
  if(type==='METRICS') return {...current, metrics:normalizeMetrics(event.value)};
  if(type==='POLICY') {
    if(!['overlay','manual'].includes(event.value)) return current;
    return {...current,policy:event.value,
      overlayUntil:event.value==='manual'?null:current.overlayUntil};
  }
  if(type==='SHOW_HEALTH') return {...current,view:'health',overlayUntil:null};
  if(type==='SHOW_MUSIC') return {...current,view:'music',overlayUntil:null};
  if(type==='MEDIA') {
    const media=normalizeMedia(event.value);
    const changed=trackKey(media)!==trackKey(current.media);
    const newTrack=changed && media.title && media.state==='PLAYING';
    const auto=current.policy==='overlay' && newTrack &&
      (current.view==='health'||current.overlayUntil!==null);
    return {...current,media,
      view:auto?'music':current.view,
      overlayUntil:auto?now+OVERLAY_MS:current.overlayUntil};
  }
  if(type==='TICK' && current.overlayUntil!==null && now>=current.overlayUntil)
    return {...current,view:'health',overlayUntil:null};
  return current;
}
export function gaugeColor(percent) {
  const p=bounded(percent,100);
  if(p===null) return C.inactive;
  return p<20?C.mint:p<50?C.yellow:p<80?C.orange:C.burgundy;
}
function box(ctx,x,y,w,h,r,color) {
  ctx.beginPath();ctx.roundRect(x,y,w,h,r);ctx.fillStyle=color;ctx.fill();
}
function label(ctx,value,x,y,size=11,color=C.text,weight=600) {
  ctx.fillStyle=color;ctx.textAlign='left';ctx.font=weight+' '+size+'px system-ui, sans-serif';
  ctx.fillText(String(value),x,y);
}
export function fitText(ctx,value,maxPx) {
  const str=typeof value==='string'?value:'';
  if(ctx.measureText(str).width<=maxPx) return str;
  const chars=Array.from(str);let left=0,right=chars.length;
  while(left<right) {
    const mid=Math.ceil((left+right)/2);
    if(ctx.measureText(chars.slice(0,mid).join('')+'…').width<=maxPx) left=mid;
    else right=mid-1;
  }
  return chars.slice(0,left).join('')+'…';
}
function frame(ctx,name,state='') {
  ctx.clearRect(0,0,WIDTH,HEIGHT);
  ctx.fillStyle=C.bg;ctx.fillRect(0,0,WIDTH,HEIGHT);
  ctx.strokeStyle=C.line;ctx.strokeRect(.5,.5,239,239);
  box(ctx,12,11,216,29,7,C.panel);
  label(ctx,'//',20,30,12,C.gold,800);
  label(ctx,name,42,30,10,C.text,800);
  if(state) {
    ctx.font='700 9px system-ui, sans-serif';
    const color=state==='PLAYING'?C.mint:state==='PAUSED'?C.yellow:C.muted;
    ctx.textAlign='right';ctx.fillStyle=color;ctx.fillText(state,219,29);ctx.textAlign='left';
  }
}
function valueCard(ctx,x,y,name,value,unit,percent) {
  box(ctx,x,y,104,73,9,C.panel);
  label(ctx,name,x+10,y+16,9,C.muted,750);
  label(ctx,value===null?'—':Math.round(value)+unit,x+10,y+45,
        value===null?23:25,value===null?C.inactive:C.text,750);
  box(ctx,x+10,y+57,84,5,3,C.line);
  if(percent!==null && percent>0) {
    const width=84*Math.min(100,percent)/100;
    box(ctx,x+10,y+57,Math.max(1,width),5,Math.min(2.5,width/2),gaugeColor(percent));
  }
}
export function renderHealth(ctx,metrics) {
  const m=normalizeMetrics(metrics);
  frame(ctx,'PC HEALTH');
  label(ctx,'FOUR VALUES  /  DEMO PREVIEW',16,55,9,C.muted,600);
  valueCard(ctx,14,65,'CPU',m.cpu,'%',m.cpu);
  valueCard(ctx,122,65,'GPU',m.gpu,'%',m.gpu);
  valueCard(ctx,14,145,'RAM',m.ram,'%',m.ram);
  // 100°C is a UI demo bar normalization, NOT a hardware alarm threshold.
  valueCard(ctx,122,145,'GPU TEMP',m.gpuTemp,'°C',m.gpuTemp===null?null:Math.min(100,m.gpuTemp));
  label(ctx,'METRICS VIEW ALWAYS AVAILABLE',16,231,8,C.muted,650);
  return m;
}
export function formatTime(secondsValue) {
  const n=seconds(secondsValue);
  if(n===null) return '--:--';
  const m=Math.floor(n/60),s=n%60;
  return m+':'+String(s).padStart(2,'0');
}
function artwork(ctx,bitmap) {
  const x=68,y=44,size=104;
  ctx.fillStyle=C.panel;ctx.fillRect(x,y,size,size);
  const w=bitmap?.width,h=bitmap?.height;
  if(Number.isFinite(w)&&Number.isFinite(h)&&w>0&&h>0) {
    const edge=Math.min(w,h),sx=(w-edge)/2,sy=(h-edge)/2;
    ctx.drawImage(bitmap,sx,sy,edge,edge,x,y,size,size);
  } else {
    box(ctx,x+6,y+6,size-12,size-12,8,'#252025');
    ctx.strokeStyle=C.gold;ctx.strokeRect(x+15,y+15,size-30,size-30);
    label(ctx,'S',x+37,y+69,44,C.gold,800);
    label(ctx,'NO ART',x+27,y+84,9,C.muted,700);
  }
  ctx.strokeStyle=C.line;ctx.strokeRect(x+.5,y+.5,size-1,size-1);
}
export function renderNowPlaying(ctx,rawMedia,bitmap=null) {
  const m=normalizeMedia(rawMedia);
  frame(ctx,'NOW PLAYING',m.state);
  artwork(ctx,bitmap);
  ctx.font='800 13px system-ui, sans-serif';
  label(ctx,fitText(ctx,m.title||'NO ACTIVE TRACK',210),15,169,13,C.text,800);
  ctx.font='600 11px system-ui, sans-serif';
  label(ctx,fitText(ctx,m.artist||'NO ARTIST',210),15,186,11,C.gold,600);
  box(ctx,15,200,210,6,3,C.line);
  const canProgress=m.duration_seconds!==null && m.duration_seconds>0 &&
    m.position_seconds!==null;
  if(canProgress) {
    const w=210*m.position_seconds/m.duration_seconds;
    if(w>0)box(ctx,15,200,Math.max(1,w),6,Math.min(3,w/2),C.gold);
  }
  label(ctx,formatTime(m.position_seconds),15,224,10,C.muted,700);
  ctx.font='700 10px system-ui, sans-serif';ctx.textAlign='right';ctx.fillStyle=C.muted;
  ctx.fillText(formatTime(m.duration_seconds),225,224);ctx.textAlign='left';
  return m;
}
export function renderPreview(ctx,state,artworkBitmap=null) {
  return state.view==='music'
    ? renderNowPlaying(ctx,state.media,artworkBitmap)
    : renderHealth(ctx,state.metrics);
}
export function validateArtworkFile(file) {
  if(!file || !['image/jpeg','image/png','image/webp'].includes(file.type))
    return 'Choose a local JPEG, PNG or WebP image.';
  if(!Number.isFinite(file.size)||file.size<=0||file.size>ARTWORK_MAX_BYTES)
    return 'Artwork exceeds the 1 MiB PC-only preview limit.';
  return null;
}
export function validateArtworkDimensions(bitmap) {
  const w=bitmap?.width,h=bitmap?.height;
  return Number.isInteger(w)&&Number.isInteger(h)&&w>0&&h>0&&
    w<=ARTWORK_MAX_SIDE&&h<=ARTWORK_MAX_SIDE&&w*h<=ARTWORK_MAX_PIXELS;
}
