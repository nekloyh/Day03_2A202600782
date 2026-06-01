import { formatTokens, formatLatency } from '../../utils/formatters';

export default function TraceStatusBar({ status, trace, metrics, maxSteps }) {
  // Compute current step from trace
  const stepEvents = trace.filter(e => e.event === 'AGENT_STEP');
  const currentStep = stepEvents.length;
  const progressPct = maxSteps > 0 ? Math.min((currentStep / maxSteps) * 100, 100) : 0;

  // Aggregate tokens from metrics
  const totalTok = metrics.reduce((s, m) => s + (m.total_tokens || 0), 0);
  const avgLat = metrics.length > 0
    ? Math.round(metrics.reduce((s, m) => s + (m.latency_ms || 0), 0) / metrics.length)
    : 0;

  const statusLabel = {
    idle: 'Idle',
    running: 'Running...',
    completed: 'Completed',
    error: 'Error',
  }[status] || status;

  return (
    <div className="trace-status">
      <div className="trace-status__indicator">
        <span className={`trace-status__dot trace-status__dot--${status}`} />
        <span>{statusLabel}</span>
      </div>

      <div className="trace-status__progress">
        <div className="trace-status__progress-label">
          <span>Step {currentStep}/{maxSteps || '–'}</span>
          <span>{Math.round(progressPct)}%</span>
        </div>
        <div className="trace-status__progress-bar">
          <div className="trace-status__progress-fill" style={{ width: `${progressPct}%` }} />
        </div>
      </div>

      <div className="trace-status__stats">
        <div className="trace-status__stat">
          <span className="trace-status__stat-value">{formatTokens(totalTok)}</span>
          <span className="trace-status__stat-label">Tokens</span>
        </div>
        <div className="trace-status__stat">
          <span className="trace-status__stat-value">{formatLatency(avgLat)}</span>
          <span className="trace-status__stat-label">Avg Lat</span>
        </div>
        <div className="trace-status__stat">
          <span className="trace-status__stat-value">{trace.length}</span>
          <span className="trace-status__stat-label">Events</span>
        </div>
      </div>
    </div>
  );
}
