import { useState, useCallback, useRef } from 'react';

/**
 * Hook to manage agent run state — talks to POST /api/run
 * and accumulates trace events + metrics.
 */
export function useAgent() {
  const [status, setStatus] = useState('idle');       // idle | running | completed | error
  const [trace, setTrace] = useState([]);
  const [metrics, setMetrics] = useState([]);
  const [finalAnswer, setFinalAnswer] = useState(null);
  const [artifacts, setArtifacts] = useState(null);
  const [runId, setRunId] = useState(null);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  const run = useCallback(async ({ topic, provider, offline, maxSteps }) => {
    setStatus('running');
    setTrace([]);
    setMetrics([]);
    setFinalAnswer(null);
    setArtifacts(null);
    setError(null);
    setRunId(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic,
          provider: provider || 'scripted',
          offline: offline !== false,
          max_steps: maxSteps || 10,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const errBody = await res.text();
        throw new Error(`Server error ${res.status}: ${errBody}`);
      }

      const data = await res.json();
      setRunId(data.run_id);
      setTrace(data.trace || []);
      setFinalAnswer(data.final_answer);
      setArtifacts(data.artifacts);

      // Extract metrics from trace events
      const llmMetrics = (data.trace || [])
        .filter(e => e.event === 'LLM_METRIC')
        .map(e => e.data);
      setMetrics(data.metrics?.length ? data.metrics : llmMetrics);

      setStatus(data.status === 'error' ? 'error' : 'completed');
      if (data.status === 'error') {
        setError(data.final_answer);
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        setStatus('idle');
        return;
      }
      setError(err.message);
      setStatus('error');
    }
  }, []);

  const cancel = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    setStatus('idle');
    setTrace([]);
    setMetrics([]);
    setFinalAnswer(null);
    setArtifacts(null);
    setError(null);
    setRunId(null);
  }, []);

  return {
    status,
    trace,
    metrics,
    finalAnswer,
    artifacts,
    runId,
    error,
    run,
    cancel,
    reset,
  };
}
