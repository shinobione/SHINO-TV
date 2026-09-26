import assert from 'node:assert/strict';
import test from 'node:test';
import {metricsToScene, unavailableMetricsScene} from './live.mjs';

test('bridge telemetry converts RAM GB to percentage',()=>{
  const s=metricsToScene({ok:true,cpu_usage:42,gpu_usage:60,gpu_temp_c:67,gpu_available:true,memory_used_gb:8,memory_total_gb:16});
  assert.equal(s.kind,'metrics');assert.equal(s.cpu,42);assert.equal(s.gpu,60);
  assert.equal(s.ram,50);assert.equal(s.gpuTemp,67);assert.equal(s.source,'live');
});
test('missing GPU telemetry is clearly marked, not falsely presented as 0 percent',()=>{
  const s=metricsToScene({ok:true,cpu_usage:31,gpu_available:false,memory_used_gb:12,memory_total_gb:16});
  assert.equal(s.gpuAvailable,false);assert.equal(s.ram,75);
});
test('rejects missing / nonsensical telemetry',()=>{
  for(const p of [null,{ok:false},{ok:true,cpu_usage:20,memory_used_gb:3,memory_total_gb:0},
    {ok:true,cpu_usage:NaN,memory_used_gb:3,memory_total_gb:16},
    {ok:true,cpu_usage:20,memory_used_gb:20,memory_total_gb:16}]) {
    assert.throws(()=>metricsToScene(p),TypeError);
  }
});
test('offline state is separate from live/demo',()=>{
  assert.deepEqual(unavailableMetricsScene().source,'offline');
});
