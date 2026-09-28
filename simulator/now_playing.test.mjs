import assert from 'node:assert/strict';
import test from 'node:test';
import {
  WIDTH,HEIGHT,OVERLAY_MS,SAMPLE_TRACKS,createPreviewState,updatePreviewState,
  trackKey,normalizeMedia,normalizeMetrics,formatTime,fitText,gaugeColor,
  renderHealth,renderNowPlaying,renderPreview,validateArtworkFile,
  validateArtworkDimensions,ARTWORK_MAX_BYTES
} from './now_playing.mjs';

function fakeCanvas() {
  const calls={text:[],draw:[],fills:[]};
  const ctx = {
    textAlign:'left',font:'',
    clearRect(){},beginPath(){},roundRect(){},fill(){},strokeRect(){},
    fillRect(x,y,w,h){calls.fills.push([x,y,w,h]);},
    drawImage(...args){calls.draw.push(args);},
    fillText(s,x,y){calls.text.push([String(s),x,y]);},
    measureText(s){return {width:Array.from(s).length*7};}
  };
  return {ctx,calls};
}
test('true fixed 240 canvas and all FOUR values, including GPU temperature',()=>{
  assert.equal(WIDTH,240);assert.equal(HEIGHT,240);
  const {ctx,calls}=fakeCanvas();
  const m=renderHealth(ctx,{cpu:27,gpu:62,ram:43,gpuTemp:68});
  assert.deepEqual(Object.keys(m),['cpu','gpu','ram','gpuTemp']);
  for(const value of ['CPU','GPU','RAM','GPU TEMP','27%','62%','43%','68°C'])
    assert.ok(calls.text.some(row=>row[0]===value),value);
});
test('numeric data bounded, stale/invalid omitted, and never fake zero',()=>{
  assert.deepEqual(normalizeMetrics({cpu:-4,gpu:140,ram:'90',gpuTemp:NaN}),
    {cpu:0,gpu:100,ram:null,gpuTemp:null});
  const {ctx,calls}=fakeCanvas();
  renderHealth(ctx,{cpu:null,gpu:null,ram:null,gpuTemp:null});
  assert.equal(calls.text.filter(row=>row[0]==='—').length,4);
  assert.equal(gaugeColor(null),'#56545a');
  assert.notEqual(gaugeColor(19),gaugeColor(20));
  assert.notEqual(gaugeColor(49),gaugeColor(50));
  assert.notEqual(gaugeColor(79),gaugeColor(80));
});
test('music fields bounded, terminal/bidi controls removed, progress clamped',()=>{
  const m=normalizeMedia({state:'PLAYING',source:'Spotify.exe',title:'Title\n\u202e'+('x'.repeat(300)),
    artist:'  SHINOBIWAN  ',album:'Velvet',position_seconds:500,duration_seconds:229,
    cover_available:'true'});
  assert.equal(m.title.length,120);
  assert.equal(m.title.includes('\u202e'),false);
  assert.equal(m.title.includes('\n'),false);
  assert.equal(m.artist,'SHINOBIWAN');
  assert.equal(m.position_seconds,229);
  assert.equal(m.cover_available,false);
  assert.equal(normalizeMedia({state:'unknown'}).state,'UNKNOWN');
  assert.equal(normalizeMedia({}).position_seconds,null);
  assert.equal(normalizeMedia({position_seconds:NaN,duration_seconds:Infinity}).duration_seconds,null);
  assert.equal(formatTime(null),'--:--');
  assert.equal(formatTime(229),'3:49');
});
test('new playing track overlays health 5 s, progress-only update does not restart',()=>{
  let state=createPreviewState();
  assert.equal(state.view,'health');
  state=updatePreviewState(state,{type:'MEDIA',value:SAMPLE_TRACKS[1]},1000);
  assert.equal(state.view,'music');assert.equal(state.overlayUntil,1000+OVERLAY_MS);
  state=updatePreviewState(state,{type:'MEDIA',value:{...SAMPLE_TRACKS[1],position_seconds:42}},1300);
  assert.equal(state.overlayUntil,1000+OVERLAY_MS);
  state=updatePreviewState(state,{type:'TICK'},5999);assert.equal(state.view,'music');
  state=updatePreviewState(state,{type:'TICK'},6000);assert.equal(state.view,'health');
  assert.equal(state.overlayUntil,null);
  assert.deepEqual(state.metrics,normalizeMetrics({cpu:27,gpu:62,ram:43,gpuTemp:68}));
});
test('pause alone does not trigger overlay, manual health remains accessible',()=>{
  let state=createPreviewState();
  state=updatePreviewState(state,{type:'MEDIA',value:{...SAMPLE_TRACKS[1],state:'PAUSED'}},100);
  assert.equal(state.view,'health');
  state=updatePreviewState(state,{type:'SHOW_MUSIC'});
  assert.equal(state.view,'music');assert.equal(state.overlayUntil,null);
  state=updatePreviewState(state,{type:'SHOW_HEALTH'});
  assert.equal(state.view,'health');
  state=updatePreviewState(state,{type:'POLICY',value:'manual'});
  state=updatePreviewState(state,{type:'MEDIA',value:SAMPLE_TRACKS[0]},200);
  assert.equal(state.view,'health');
  state=updatePreviewState(state,{type:'POLICY',value:'invalid'});
  assert.equal(state.policy,'manual');
});
test('change during overlay restarts 5 s but no session does not trigger it',()=>{
  let state=createPreviewState();
  state=updatePreviewState(state,{type:'MEDIA',value:SAMPLE_TRACKS[1]},10);
  state=updatePreviewState(state,{type:'MEDIA',value:{...SAMPLE_TRACKS[0],title:'Another'}},400);
  assert.equal(state.overlayUntil,5400);
  state=updatePreviewState(state,{type:'MEDIA',value:{state:'NO_SESSION'}},600);
  assert.equal(state.overlayUntil,5400);
  assert.equal(trackKey(SAMPLE_TRACKS[0]),trackKey({...SAMPLE_TRACKS[0],position_seconds:100}));
});
test('renderer crops 320x200 cover to square and elides long text safely',()=>{
  const {ctx,calls}=fakeCanvas();
  const media={state:'PLAYING',title:'WAY TOO LONG '.repeat(20),artist:'ShinoBiWan',
    position_seconds:15,duration_seconds:229};
  const bitmap={width:320,height:200};
  renderNowPlaying(ctx,media,bitmap);
  assert.equal(calls.draw.length,1);
  assert.deepEqual(calls.draw[0],[bitmap,60,0,200,200,68,44,104,104]);
  assert.ok(calls.text.some(row=>row[0].endsWith('…')));
  assert.ok(calls.text.some(row=>row[0]==='0:15'));
  assert.ok(calls.text.some(row=>row[0]==='3:49'));
  const state=createPreviewState();
  assert.equal(renderPreview(ctx,state).cpu,27);
  const song=renderPreview(ctx,{...state,view:'music'});
  assert.equal(song.title,'Velvet HAMMER');
  assert.equal(fitText(ctx,'a'.repeat(100),21),'aa…');
});
test('artwork is manually selected and strictly bounded before browser decode',()=>{
  assert.equal(validateArtworkFile({type:'image/jpeg',size:22000}),null);
  assert.ok(validateArtworkFile({type:'text/html',size:1000}));
  assert.ok(validateArtworkFile({type:'image/jpeg',size:ARTWORK_MAX_BYTES+1}));
  assert.ok(validateArtworkFile(null));
  assert.equal(validateArtworkDimensions({width:192,height:192}),true);
  assert.equal(validateArtworkDimensions({width:4000,height:2000}),false);
  assert.equal(validateArtworkDimensions({width:0,height:192}),false);
  assert.equal(validateArtworkDimensions({width:192.5,height:192}),false);
});
