// Test the EXACT JS string embedded in FslessWebUI.cpp. Never contacts a device.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const file = path.join(__dirname, '..', 'firmware', 'src', 'boot', 'FslessWebUI.cpp');
const source = fs.readFileSync(file, 'utf8');
const scriptMatch = source.match(/const char SCRIPT\[\] PROGMEM = R"SHINO\(([\s\S]*?)\)SHINO";/);
assert.ok(scriptMatch, 'compiled Web UI SCRIPT must be extractable');

function harness() {
  const nodes = new Map();
  function node(id) {
    if (!nodes.has(id)) {
      const attributes = new Map();
      nodes.set(id, {
        textContent: '',
        style: {width: '', backgroundColor: ''},
        setAttribute: (key, value) => attributes.set(key, value),
        removeAttribute: key => attributes.delete(key),
        attr: key => attributes.get(key),
      });
    }
    return nodes.get(id);
  }
  const script = scriptMatch[1].replace(
    'poll();setInterval(poll,2000);',
    'globalThis.__math = { band,stableBand,fillPixels,render,previous };'
  );
  assert.notEqual(script, scriptMatch[1], 'test injection anchor should exist');
  const context = {document: {getElementById: node}, console};
  vm.runInNewContext(script, context, {timeout: 200});
  return {m: context.__math, node};
}
const normal = {
  received: true, stale: false, gpu_available: true,
  cpu_usage: 5, gpu_usage: 0, memory_used_gb: 11.2,
  memory_total_gb: 16, gpu_temp_c: 50,
};
test('four native-sized browser cards and dynamic example values', () => {
  assert.equal((source.match(/<article class="card">/g) ?? []).length, 4);
  assert.match(source, /grid-template-columns:108px 108px/);
  assert.match(source, /width:240px;height:240px/);
  assert.match(source, /background:#536277/);
  const {m, node} = harness();
  m.render(normal);
  assert.equal(node('cpuV').textContent, '5.0%');
  assert.equal(node('gpuV').textContent, '0.0%');
  assert.equal(node('ramV').textContent, '11.2 GB');
  assert.equal(node('tempV').textContent, '50.0°C');
  assert.equal(node('cpuFill').style.width, '5px');
  assert.equal(node('gpuFill').style.width, '0px');
  assert.equal(node('ramFill').style.width, '63px');
  assert.equal(node('tempFill').style.width, '30px');
  assert.equal(node('cpuFill').style.backgroundColor, '#66D39A');
  assert.equal(node('ramFill').style.backgroundColor, '#D9894A');
  assert.equal(node('tempFill').style.backgroundColor, '#D8C35E');
  assert.equal(node('ramTrack').attr('aria-valuenow'), '70.0');
});
test('zero fill is truly invisible, with crisp integer tiny bars and no ghost animation', () => {
  assert.match(source, /\.fill\{display:none;width:0;height:6px;border-radius:3px;[^\n]*transition:none\}/);
  const {m,node}=harness();
  m.render({...normal,gpu_usage:23});
  assert.equal(node('gpuFill').style.display,'block');
  assert.equal(node('gpuFill').style.width,'21px');
  assert.equal(node('gpuFill').style.borderRadius,'3px');
  m.render({...normal,gpu_usage:0});
  assert.equal(node('gpuV').textContent,'0.0%');
  assert.equal(node('gpuFill').style.width,'0px');
  assert.equal(node('gpuFill').style.display,'none');
  m.render({...normal,gpu_usage:0.1});
  assert.equal(node('gpuFill').style.width,'1px');
  assert.equal(node('gpuFill').style.display,'block');
  assert.equal(node('gpuFill').style.borderRadius,'0');
  m.render({...normal,gpu_usage:0});
  assert.equal(node('gpuFill').style.display,'none');
  m.render({...normal,stale:true});
  for (const id of ['cpu','gpu','ram','temp']) {
    assert.equal(node(id+'Fill').style.display,'none');
    assert.equal(node(id+'Fill').style.width,'0px');
  }
});
test('all threshold boundaries and 2pp hysteresis', () => {
  const {m, node} = harness();
  for (const [v,b] of [[0,0],[19.9,0],[20,1],[49.9,1],[50,2],[79.9,2],[80,3],[100,3]]) {
    assert.equal(m.band(v), b);
  }
  assert.equal(m.fillPixels(0), 0);
  assert.equal(m.fillPixels(.01), 1);
  assert.equal(m.fillPixels(100), 90);
  m.render({...normal, cpu_usage: 49.8});
  assert.equal(node('cpuFill').style.backgroundColor, '#D8C35E');
  m.render({...normal, cpu_usage: 50.1});
  assert.equal(node('cpuFill').style.backgroundColor, '#D8C35E');
  m.render({...normal, cpu_usage: 52});
  assert.equal(node('cpuFill').style.backgroundColor, '#D9894A');
  m.render({...normal, cpu_usage: 48});
  assert.equal(node('cpuFill').style.backgroundColor, '#D9894A');
  m.render({...normal, cpu_usage: 47.9});
  assert.equal(node('cpuFill').style.backgroundColor, '#D8C35E');
});
test('RAM without real denominator keeps used amount and neutral bar', () => {
  const {m,node} = harness();
  m.render({...normal, memory_total_gb: undefined});
  assert.equal(node('ramV').textContent, '11.2 GB');
  assert.equal(node('ramFill').style.width, '0px');
  assert.equal(node('ramTrack').attr('aria-valuenow'), undefined);
  m.render({...normal, memory_total_gb: 9});
  assert.equal(node('ramFill').style.width, '0px');
});
test('GPU loss retains CPU/RAM, stale retains four cards and clears color history', () => {
  const {m,node} = harness();
  m.render({...normal, gpu_available: false});
  assert.equal(node('cpuV').textContent, '5.0%');
  assert.equal(node('ramV').textContent, '11.2 GB');
  assert.equal(node('gpuV').textContent, '—');
  assert.equal(node('tempV').textContent, '—');
  assert.equal(node('gpuFill').style.width, '0px');
  assert.equal(node('tempFill').style.width, '0px');
  m.render({...normal, cpu_usage: 52});
  m.render({...normal, stale: true});
  for (const id of ['cpu','gpu','ram','temp']) {
    assert.equal(node(id+'V').textContent, '—');
    assert.equal(node(id+'Fill').style.width, '0px');
  }
  assert.equal(m.previous[0], null);
  m.render({...normal, cpu_usage: 50});
  assert.equal(node('cpuFill').style.backgroundColor, '#D9894A');
});
test('temperature uses 30-90 visual scale and long labels never disappear', () => {
  const {m,node} = harness();
  m.render({...normal, cpu_usage:100,gpu_usage:100,memory_used_gb:16,gpu_temp_c:90});
  assert.equal(node('cpuV').textContent, '100.0%');
  assert.equal(node('gpuV').textContent, '100.0%');
  assert.equal(node('tempV').textContent, '90.0°C');
  assert.equal(node('ramFill').style.width,'90px');
  assert.equal(node('tempFill').style.width,'90px');
  assert.equal(node('tempFill').style.backgroundColor,'#8E394B');
  m.render({...normal,gpu_temp_c:30});
  assert.equal(node('tempFill').style.width,'0px');
});
