/** SHINO // TV V0.4: opt-in, same-origin PC-only GSMTC/browser preview. */
import {
  SAMPLE_TRACKS, createPreviewState, updatePreviewState, normalizeMedia, trackKey,
  renderPreview, validateArtworkDimensions, OVERLAY_MS
} from './now_playing.mjs';

const q=id=>document.getElementById(id);
const canvas=q('screen'),ctx=canvas.getContext('2d');
let state=createPreviewState(),live=false,epoch=0,requestBusy=false;
let art=null,artRevision=null,artPending=null,artToken=0;
let interval=null,activeRequest=null;

function discardArt(){
  artToken++;
  if(art&&typeof art.close==='function')art.close();
  art=null;artRevision=null;artPending=null;
}
function repaint(){
  renderPreview(ctx,state,art);
  q('health').setAttribute('aria-pressed',String(state.view==='health'));
  q('music').setAttribute('aria-pressed',String(state.view==='music'));
  const seconds=state.overlayUntil===null?null:
    Math.max(0,(state.overlayUntil-performance.now())/1000);
  q('scene-status').textContent=state.view==='health'?'PC HEALTH / FOUR DEMO VALUES':
    seconds===null?'NOW PLAYING / MANUAL':'NOW PLAYING / '+seconds.toFixed(1)+'s OVERLAY';
}
function mediaView(){
  q('source').textContent=state.media.source||'No published session';
  q('track').textContent=state.media.title||'No active track';
  q('artist').textContent=state.media.artist||'—';
}
function stopLive(message='OFF · DEMO ONLY'){
  live=false;epoch++;
  if(interval!==null){clearInterval(interval);interval=null;}
  if(activeRequest){activeRequest.abort();activeRequest=null;}
  q('start').disabled=false;q('stop').disabled=true;
  discardArt();
  state=updatePreviewState(state,{type:'SHOW_HEALTH'});
  q('live-state').textContent=message;
  q('cover-status').textContent='Cover: not loaded';
  repaint();
}
function setDemo(snapshot,name){
  stopLive('OFF · DEMO ONLY');
  const prev=trackKey(state.media);
  state=updatePreviewState(state,{type:'MEDIA',value:snapshot},performance.now());
  if(prev!==trackKey(state.media))discardArt();
  q('live-state').textContent='OFF · '+name+' DEMO';
  q('cover-status').textContent='Cover: demo fallback (no upload)';
  mediaView();repaint();
}
async function fetchArtwork(revision,identity,run){
  const token=++artToken;
  artPending=revision;
  try{
    const controller=new AbortController();
    activeRequest=controller;
    const timeout=setTimeout(()=>controller.abort(),4000);
    let result;
    try{
      result=await fetch('/api/v1/media/cover?revision='+revision,{
        cache:'no-store',headers:{'X-Shino-Preview':'1'},signal:controller.signal
      });
    }finally{clearTimeout(timeout);if(activeRequest===controller)activeRequest=null;}
    if(!result.ok||result.headers.get('Content-Type')!=='image/jpeg')
      throw new Error('No current preview JPEG');
    const length=Number(result.headers.get('Content-Length'));
    if(!Number.isInteger(length)||length<=0||length>40*1024)
      throw new Error('Invalid JPEG size');
    const blob=await result.blob();
    if(blob.size!==length||blob.size>40*1024)throw new Error('Invalid JPEG body');
    const bitmap=await createImageBitmap(blob);
    if(!validateArtworkDimensions(bitmap)){bitmap.close();throw new Error('Invalid image dimensions');}
    if(!live||run!==epoch||token!==artToken||identity!==trackKey(state.media)){
      bitmap.close();return;
    }
    if(art&&typeof art.close==='function')art.close();
    art=bitmap;artRevision=revision;artPending=null;
    q('cover-status').textContent='Cover: LIVE · PC RAM only ('+blob.size+' bytes)';
    repaint();
  }catch(_error){
    if(live&&run===epoch&&token===artToken){
      artPending=null;
      q('cover-status').textContent='Cover: not available; fallback shown';
    }
  }
}
async function poll(){
  if(!live||requestBusy)return;
  const run=epoch;
  requestBusy=true;
  const controller=new AbortController();
  activeRequest=controller;
  const timeout=setTimeout(()=>controller.abort(),7000);
  try{
    const response=await fetch('/api/v1/media/state',{
      cache:'no-store',headers:{'X-Shino-Preview':'1'},signal:controller.signal
    });
    if(!response.ok||response.headers.get('Content-Type')!=='application/json; charset=utf-8')
      throw new Error('Preview feed unavailable');
    const length=Number(response.headers.get('Content-Length'));
    if(!Number.isInteger(length)||length>4096||length<=0)throw new Error('Invalid response size');
    const packet=await response.json();
    if(!live||run!==epoch)return;
    if(!packet||typeof packet!=='object'||!packet.media)throw new Error('Invalid snapshot');
    const media=normalizeMedia(packet.media);
    const before=trackKey(state.media);
    state=updatePreviewState(state,{type:'MEDIA',value:media},performance.now());
    const after=trackKey(state.media);
    const rev=typeof packet.cover_revision==='string'&&/^[a-f0-9]{64}$/.test(packet.cover_revision)
      ? packet.cover_revision:null;
    if(before!==after || (artRevision!==null && artRevision!==rev))discardArt();
    const status=typeof packet.status==='string'?packet.status:'UNAVAILABLE';
    q('live-state').textContent=status==='READY'?'LIVE · CONNECTED':
      status==='WAITING'?'LIVE · WAITING FOR GSMTC':
      status==='NO_SESSION'?'LIVE · NO MEDIA SESSION':
      status==='STALE'?'LIVE · STALE / RETRYING':'LIVE · MEDIA UNAVAILABLE';
    if(status!=='READY'||!rev){
      discardArt();
      q('cover-status').textContent='Cover: not available';
    }else if(artRevision!==rev&&artPending!==rev){
      // Artwork is a distinct, bounded, read-only route; never sent to the TV.
      void fetchArtwork(rev,after,run);
    }
    mediaView();repaint();
  }catch(_error){
    if(!live||run!==epoch)return;
    discardArt();
    state=updatePreviewState(state,{type:'MEDIA',value:{state:'UNAVAILABLE'}},performance.now());
    q('live-state').textContent='LIVE · PREVIEW SERVER UNAVAILABLE / RETRYING';
    q('cover-status').textContent='Cover: unavailable';
    mediaView();repaint();
  }finally{
    clearTimeout(timeout);
    if(activeRequest===controller)activeRequest=null;
    requestBusy=false;
  }
}
function startLive(){
  if(live)return;
  stopLive();
  live=true;epoch++;
  q('start').disabled=true;q('stop').disabled=false;
  state=updatePreviewState(state,{type:'MEDIA',value:{state:'UNAVAILABLE'}},performance.now());
  q('live-state').textContent='LIVE · CONNECTING';
  q('cover-status').textContent='Cover: awaiting live snapshot';
  mediaView();repaint();
  void poll();
  interval=setInterval(()=>void poll(),3000);
}
q('start').addEventListener('click',startLive);
q('stop').addEventListener('click',()=>stopLive('OFF · LIVE PREVIEW STOPPED'));
q('demo-a').addEventListener('click',()=>setDemo(SAMPLE_TRACKS[0],'VELVET HAMMER'));
q('demo-b').addEventListener('click',()=>setDemo(SAMPLE_TRACKS[1],'WEAPON IS FED'));
q('health').addEventListener('click',()=>{
  state=updatePreviewState(state,{type:'SHOW_HEALTH'});repaint();
});
q('music').addEventListener('click',()=>{
  state=updatePreviewState(state,{type:'SHOW_MUSIC'});repaint();
});
q('policy').addEventListener('change',event=>{
  state=updatePreviewState(state,{type:'POLICY',value:event.target.value});repaint();
});
q('save').addEventListener('click',()=>{
  const link=document.createElement('a');
  link.download='shino-tv-live-preview-240x240.png';
  link.href=canvas.toDataURL('image/png');link.click();
});
setInterval(()=>{
  if(state.overlayUntil===null)return;
  state=updatePreviewState(state,{type:'TICK'},performance.now());repaint();
},150);
window.addEventListener('pagehide',()=>stopLive('OFF · PAGE CLOSED'));
mediaView();repaint();
