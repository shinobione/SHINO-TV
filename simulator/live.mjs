/** Same-origin SHINO // TV metrics adapter. Does not access or command the SmallTV. */
const finite = (value, key) => {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new TypeError(`Invalid PC telemetry: ${key}`);
  return value;
};
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

/**
 * Convert the real bridge's contract into our preview-only metrics shape.
 * Note: the device firmware still consumes Times-Z's original six-tile contract.
 */
export function metricsToScene(payload) {
  if (!payload || payload.ok !== true) throw new TypeError('PC telemetry unavailable');
  const cpu = clamp(finite(payload.cpu_usage, 'cpu_usage'), 0, 100);
  const used = finite(payload.memory_used_gb, 'memory_used_gb');
  const total = finite(payload.memory_total_gb, 'memory_total_gb');
  if (total <= 0 || used < 0 || used > total) throw new TypeError('Invalid RAM capacity/usage');
  const gpuAvailable = payload.gpu_available === true;
  const gpu = gpuAvailable ? clamp(finite(payload.gpu_usage, 'gpu_usage'), 0, 100) : 0;
  const gpuTemp = gpuAvailable ? clamp(finite(payload.gpu_temp_c, 'gpu_temp_c'), -40, 130) : 0;
  return {
    kind: 'metrics',
    title: 'PC HEALTH',
    source: 'live',
    gpuAvailable,
    cpu,
    gpu,
    ram: clamp((used / total) * 100, 0, 100),
    gpuTemp
  };
}

export function unavailableMetricsScene() {
  return {kind:'metrics', title:'PC HEALTH', source:'offline', gpuAvailable:false, cpu:0, gpu:0, ram:0, gpuTemp:0};
}
