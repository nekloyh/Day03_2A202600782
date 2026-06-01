import { useState } from 'react';
import { classifyEvent, getStepNumber } from '../../utils/traceParser';
import { formatTimestamp } from '../../utils/formatters';

export default function TraceStepCard({ event, index }) {
  const [open, setOpen] = useState(false);
  const info = classifyEvent(event);
  const step = getStepNumber(event);
  const data = event.data || {};

  const renderBody = () => {
    const eventType = event.event;

    if (eventType === 'AGENT_STEP') {
      const response = data.response || '';
      // Try to separate Thought and Action from the response
      const thoughtMatch = response.match(/Thought\s*:\s*([\s\S]*?)(?=Action\s*:|Final Answer\s*:|$)/i);
      const actionMatch = response.match(/Action\s*:\s*([\s\S]*)/i);
      return (
        <div className="trace-step__content">
          {thoughtMatch && (
            <div className="trace-step__thought">{thoughtMatch[1].trim()}</div>
          )}
          {actionMatch && (
            <div className="trace-step__action" style={{ marginTop: '8px' }}>
              <code className="trace-step__tool-name">⚡ {actionMatch[1].trim().split('(')[0]}</code>
            </div>
          )}
          {!thoughtMatch && !actionMatch && <div>{response}</div>}
        </div>
      );
    }

    if (eventType === 'TOOL_CALL') {
      return (
        <div className="trace-step__action">
          <div className="trace-step__tool-name">⚡ {data.tool}</div>
          <div className="trace-step__json">
            {JSON.stringify(data.args, null, 2)}
          </div>
        </div>
      );
    }

    if (eventType === 'TOOL_RESULT') {
      const result = data.result;
      const resultStr = typeof result === 'string' ? result : JSON.stringify(result, null, 2);
      const truncated = resultStr.length > 800 ? resultStr.slice(0, 800) + '\n...[truncated]' : resultStr;
      return (
        <div>
          <div className="trace-step__tool-name" style={{ color: 'var(--trace-observation)', marginBottom: '8px' }}>
            👁️ {data.tool} result
          </div>
          <div className="trace-step__json">{truncated}</div>
        </div>
      );
    }

    if (eventType === 'FINAL_ANSWER') {
      return <div className="trace-step__final">{data.answer}</div>;
    }

    if (eventType === 'PARSER_ERROR' || eventType === 'AGENT_ERROR') {
      return (
        <div className="trace-step__error">
          <strong>{data.error}</strong>
          {data.message && <div style={{ marginTop: '4px' }}>{data.message}</div>}
          {data.expected_format && (
            <div style={{ marginTop: '4px', color: 'var(--text-muted)' }}>
              Expected: <code>{data.expected_format}</code>
            </div>
          )}
          {data.available_tools && (
            <div style={{ marginTop: '4px', color: 'var(--text-muted)' }}>
              Available: {data.available_tools.join(', ')}
            </div>
          )}
        </div>
      );
    }

    if (eventType === 'LLM_METRIC') {
      return (
        <div className="trace-step__json">
          {`Provider: ${data.provider || '–'}
Model: ${data.model || '–'}
Prompt tokens: ${data.prompt_tokens || 0}
Completion tokens: ${data.completion_tokens || 0}
Total tokens: ${data.total_tokens || 0}
Latency: ${data.latency_ms || 0}ms
Cost: $${(data.cost_estimate || 0).toFixed(4)}`}
        </div>
      );
    }

    // Fallback: render raw JSON
    return (
      <div className="trace-step__json">
        {JSON.stringify(data, null, 2)}
      </div>
    );
  };

  const badgeStyle = {
    background: `${info.color}20`,
    color: info.color,
  };

  return (
    <div className="trace-step" style={{ animationDelay: `${index * 60}ms` }}>
      <div className="trace-step__node" style={{ background: info.color }}>
        <span style={{ fontSize: '10px' }}>{info.icon}</span>
      </div>
      <div className="trace-step__card">
        <div className="trace-step__header" onClick={() => setOpen(!open)}>
          {step != null && <span className="trace-step__header-step">#{step}</span>}
          <span className="trace-step__header-badge" style={badgeStyle}>
            {info.label}
          </span>
          {event.event === 'TOOL_CALL' && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--trace-action)' }}>
              {data.tool}
            </span>
          )}
          <span className="trace-step__header-time">
            {formatTimestamp(event.timestamp)}
          </span>
          <span className={`trace-step__header-chevron ${open ? 'trace-step__header-chevron--open' : ''}`}>
            ▶
          </span>
        </div>
        <div className={`trace-step__body ${open ? 'trace-step__body--open' : ''}`}>
          {open && renderBody()}
        </div>
      </div>
    </div>
  );
}
