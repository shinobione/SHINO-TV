import assert from 'node:assert/strict';
import test from 'node:test';
import {PRESETS, normalizeScene, renderScene} from './scene.mjs';
test('four distinct scene presets normalize',()=>{for(const [kind,scene] of Object.entries(PRESETS)) assert.equal(normalizeScene(scene).kind,kind)});
test('rejects malformed scenes and unsupported kinds',()=>{for(const value of [null,[],{}, {kind:'remote'}, 'metrics']) assert.throws(()=>normalizeScene(value),TypeError)});
test('clamps metrics, temperatures and truncates text',()=>{let s=normalizeScene({kind:'metrics',cpu:-1,gpu:999,ram:Infinity,gpuTemp:160,title:'x'.repeat(50)});assert.equal(s.cpu,0);assert.equal(s.gpu,100);assert.equal(s.ram,43);assert.equal(s.gpuTemp,130);assert.equal(s.title.length,24)});
test('sanitizes numeric and text fields without interpreting HTML',()=>{let s=normalizeScene({kind:'music',artist:'<script>alert(1)</script>',track:'Song',progress:105});assert.equal(s.artist,'<script>alert(1)</script>');assert.equal(s.progress,100);assert.equal(normalizeScene({kind:'release',days:-4}).days,0)});
test('render function works with canvas-like 2D context',()=>{const ctx=new Proxy({}, {get:(target,prop)=>prop in target?target[prop]:(...args)=>{},set:(target,prop,value)=>{target[prop]=value;return true}});assert.equal(renderScene(ctx,PRESETS.agent).kind,'agent');});

test('manually applied metrics are explicitly marked as a frozen snapshot',()=>{
 const scene=normalizeScene({kind:'metrics',source:'manual',cpu:20,gpu:0,ram:78,gpuTemp:47,gpuAvailable:true});
 assert.equal(scene.source,'manual');assert.equal(scene.cpu,20);assert.equal(scene.ram,78);
});
