import { useRef, useEffect } from 'react';
import TraceStepCard from './TraceStepCard';

export default function TraceTimeline({ events }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div className="trace-timeline">
        <div className="trace-timeline__empty">
          <div className="trace-timeline__empty-icon">🔍</div>
          <div>No trace events yet</div>
          <div style={{ fontSize: 'var(--text-xs)' }}>
            Run the agent to see the ReAct loop in real-time
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="trace-timeline">
      <div className="trace-timeline__list">
        {events.map((event, idx) => (
          <TraceStepCard key={idx} event={event} index={idx} />
        ))}
        <div ref={endRef} />
      </div>
    </div>
  );
}
