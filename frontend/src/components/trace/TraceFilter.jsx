import { useState } from 'react';

const EVENT_FILTERS = [
  { key: 'AGENT_STEP',   label: '🧠 Thought',     category: 'thought' },
  { key: 'TOOL_CALL',    label: '⚡ Action',       category: 'action' },
  { key: 'TOOL_RESULT',  label: '👁️ Observation', category: 'observation' },
  { key: 'FINAL_ANSWER', label: '✅ Final',        category: 'final' },
  { key: 'error',        label: '❌ Error',        category: 'error' },
  { key: 'LLM_METRIC',   label: '📊 Metric',      category: 'metric' },
];

export default function TraceFilter({ activeFilters, onFilterChange, searchText, onSearchChange }) {
  return (
    <div className="trace-filter">
      {EVENT_FILTERS.map(filter => {
        const isActive = activeFilters.includes(filter.key);
        return (
          <button
            key={filter.key}
            className={`trace-filter__chip ${isActive ? 'trace-filter__chip--active' : ''}`}
            onClick={() => onFilterChange(filter.key)}
          >
            {filter.label}
          </button>
        );
      })}
      <input
        type="text"
        className="trace-filter__search"
        placeholder="Search trace..."
        value={searchText}
        onChange={e => onSearchChange(e.target.value)}
      />
    </div>
  );
}
