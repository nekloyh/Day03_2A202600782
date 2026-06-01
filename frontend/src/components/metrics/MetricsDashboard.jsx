import { formatTokens, formatCost, formatLatency, totalTokens, totalCost, averageLatency } from '../../utils/formatters';
import './MetricsDashboard.css';

export default function MetricsDashboard({ metrics, trace }) {
  const totTok = totalTokens(metrics);
  const totCst = totalCost(metrics);
  const avgLat = averageLatency(metrics);
  const steps = trace.filter(e => e.event === 'AGENT_STEP').length;
  const errors = trace.filter(e =>
    ['PARSER_ERROR', 'AGENT_ERROR', 'MAX_STEPS_EXCEEDED'].includes(e.event)
  ).length;

  // Max tokens for chart scaling
  const maxTok = Math.max(1, ...metrics.map(m => Math.max(m.prompt_tokens || 0, m.completion_tokens || 0)));

  if (metrics.length === 0) {
    return (
      <div className="metrics">
        <div className="artifacts-empty">
          <div className="artifacts-empty__icon">📊</div>
          <div>No metrics yet</div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
            Run the agent to collect performance data
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="metrics">
      {/* Summary Cards */}
      <div className="metrics__cards">
        <div className="metrics__card" style={{ animationDelay: '0ms' }}>
          <div className="metrics__card-value">{formatTokens(totTok)}</div>
          <div className="metrics__card-label">Total Tokens</div>
        </div>
        <div className="metrics__card" style={{ animationDelay: '60ms' }}>
          <div className="metrics__card-value">{formatCost(totCst)}</div>
          <div className="metrics__card-label">Est. Cost</div>
        </div>
        <div className="metrics__card" style={{ animationDelay: '120ms' }}>
          <div className="metrics__card-value">{formatLatency(Math.round(avgLat))}</div>
          <div className="metrics__card-label">Avg Latency</div>
        </div>
        <div className="metrics__card" style={{ animationDelay: '180ms' }}>
          <div className="metrics__card-value">{steps}</div>
          <div className="metrics__card-label">Steps</div>
        </div>
        <div className="metrics__card" style={{ animationDelay: '240ms' }}>
          <div className="metrics__card-value" style={{ color: errors > 0 ? 'var(--error)' : 'var(--success)' }}>
            {errors}
          </div>
          <div className="metrics__card-label">Errors</div>
        </div>
        <div className="metrics__card" style={{ animationDelay: '300ms' }}>
          <div className="metrics__card-value">{metrics.length}</div>
          <div className="metrics__card-label">LLM Calls</div>
        </div>
      </div>

      {/* Token Bar Chart */}
      <div className="metrics__section">
        <div className="metrics__section-title">Token Usage per LLM Call</div>
        <div className="metrics__chart">
          {metrics.map((m, i) => {
            const promptH = ((m.prompt_tokens || 0) / maxTok) * 130;
            const compH = ((m.completion_tokens || 0) / maxTok) * 130;
            return (
              <div key={i} className="metrics__bar-group">
                <div className="metrics__bar-value">{m.prompt_tokens || 0}</div>
                <div className="metrics__bar metrics__bar--prompt" style={{ height: `${promptH}px` }} />
                <div className="metrics__bar metrics__bar--completion" style={{ height: `${compH}px` }} />
                <div className="metrics__bar-value">{m.completion_tokens || 0}</div>
                <div className="metrics__bar-label">#{i + 1}</div>
              </div>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: '16px', marginTop: '8px', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
          <span><span style={{ color: 'var(--info)' }}>■</span> Prompt</span>
          <span><span style={{ color: 'var(--primary-light)' }}>■</span> Completion</span>
        </div>
      </div>

      {/* Detail Table */}
      <div className="metrics__section">
        <div className="metrics__section-title">LLM Call Details</div>
        <table className="metrics__table">
          <thead>
            <tr>
              <th>#</th>
              <th>Provider</th>
              <th>Model</th>
              <th>Prompt Tok</th>
              <th>Comp. Tok</th>
              <th>Total</th>
              <th>Latency</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {metrics.map((m, i) => (
              <tr key={i}>
                <td>{i + 1}</td>
                <td>{m.provider || '–'}</td>
                <td>{m.model || '–'}</td>
                <td>{m.prompt_tokens || 0}</td>
                <td>{m.completion_tokens || 0}</td>
                <td>{m.total_tokens || 0}</td>
                <td>{formatLatency(m.latency_ms)}</td>
                <td>{formatCost(m.cost_estimate)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
