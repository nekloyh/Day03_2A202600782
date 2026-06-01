import { useState, useMemo } from 'react';
import TraceStatusBar from './TraceStatusBar';
import TraceFilter from './TraceFilter';
import TraceTimeline from './TraceTimeline';
import './TracePanel.css';

const ERROR_EVENTS = new Set(['PARSER_ERROR', 'AGENT_ERROR', 'MAX_STEPS_EXCEEDED']);

export default function TracePanel({ trace, metrics, status, maxSteps }) {
  const [activeFilters, setActiveFilters] = useState([]);
  const [searchText, setSearchText] = useState('');

  const handleFilterToggle = (key) => {
    setActiveFilters(prev =>
      prev.includes(key) ? prev.filter(f => f !== key) : [...prev, key]
    );
  };

  const filteredEvents = useMemo(() => {
    let events = trace;

    // Apply event type filters
    if (activeFilters.length > 0) {
      events = events.filter(e => {
        if (activeFilters.includes('error') && ERROR_EVENTS.has(e.event)) return true;
        return activeFilters.includes(e.event);
      });
    }

    // Apply text search
    if (searchText.trim()) {
      const query = searchText.toLowerCase();
      events = events.filter(e => {
        const str = JSON.stringify(e).toLowerCase();
        return str.includes(query);
      });
    }

    return events;
  }, [trace, activeFilters, searchText]);

  return (
    <div className="trace-panel">
      <TraceStatusBar
        status={status}
        trace={trace}
        metrics={metrics}
        maxSteps={maxSteps}
      />
      <TraceFilter
        activeFilters={activeFilters}
        onFilterChange={handleFilterToggle}
        searchText={searchText}
        onSearchChange={setSearchText}
      />
      <TraceTimeline events={filteredEvents} />
    </div>
  );
}
