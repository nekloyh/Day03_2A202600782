/**
 * Format token counts, costs, latency for display.
 */

export function formatTokens(count) {
  if (count == null) return '–';
  if (count >= 1000) return `${(count / 1000).toFixed(1)}k`;
  return String(count);
}

export function formatCost(cost) {
  if (cost == null || cost === 0) return '$0.00';
  if (cost < 0.001) return '<$0.001';
  return `$${cost.toFixed(4)}`;
}

export function formatLatency(ms) {
  if (ms == null) return '–';
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)}s`;
  return `${ms}ms`;
}

export function formatTimestamp(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function totalTokens(metrics) {
  return metrics.reduce((sum, m) => sum + (m.total_tokens || 0), 0);
}

export function totalCost(metrics) {
  return metrics.reduce((sum, m) => sum + (m.cost_estimate || 0), 0);
}

export function averageLatency(metrics) {
  if (metrics.length === 0) return 0;
  return metrics.reduce((sum, m) => sum + (m.latency_ms || 0), 0) / metrics.length;
}
