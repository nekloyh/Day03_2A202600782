/**
 * Parse a raw LLM response string into structured Thought / Action / Observation segments.
 */

const ACTION_RE = /Action\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(/i;
const THOUGHT_RE = /Thought\s*:\s*([\s\S]*?)(?=(?:Action\s*:|Final Answer\s*:|$))/i;
const FINAL_RE = /Final Answer\s*:\s*([\s\S]*)/i;

export function parseAgentResponse(text) {
  const parts = [];

  const thoughtMatch = text.match(THOUGHT_RE);
  if (thoughtMatch) {
    parts.push({
      type: 'thought',
      content: thoughtMatch[1].trim(),
    });
  }

  const actionMatch = text.match(ACTION_RE);
  if (actionMatch) {
    const toolName = actionMatch[1];
    // Extract args between parentheses
    const openIdx = text.indexOf('(', actionMatch.index + actionMatch[0].length - 1);
    if (openIdx !== -1) {
      let depth = 0;
      let closeIdx = openIdx;
      for (let i = openIdx; i < text.length; i++) {
        if (text[i] === '(') depth++;
        if (text[i] === ')') depth--;
        if (depth === 0) { closeIdx = i; break; }
      }
      const argsStr = text.slice(openIdx + 1, closeIdx);
      parts.push({
        type: 'action',
        tool: toolName,
        args: argsStr.trim(),
        raw: text.slice(actionMatch.index, closeIdx + 1),
      });
    }
  }

  const finalMatch = text.match(FINAL_RE);
  if (finalMatch && !actionMatch) {
    parts.push({
      type: 'final_answer',
      content: finalMatch[1].trim(),
    });
  }

  if (parts.length === 0) {
    parts.push({ type: 'raw', content: text });
  }

  return parts;
}

/**
 * Map a trace event to a visual category for the timeline.
 */
export function classifyEvent(event) {
  const type = event.event || event.type || '';
  switch (type) {
    case 'AGENT_START':
      return { category: 'info', icon: '🚀', label: 'Agent Start', color: 'var(--info)' };
    case 'AGENT_STEP':
      return { category: 'thought', icon: '🧠', label: 'Thought', color: 'var(--trace-thought)' };
    case 'TOOL_CALL':
      return { category: 'action', icon: '⚡', label: 'Tool Call', color: 'var(--trace-action)' };
    case 'TOOL_RESULT':
      return { category: 'observation', icon: '👁️', label: 'Observation', color: 'var(--trace-observation)' };
    case 'FINAL_ANSWER':
      return { category: 'final', icon: '✅', label: 'Final Answer', color: 'var(--trace-final)' };
    case 'PARSER_ERROR':
      return { category: 'error', icon: '❌', label: 'Parse Error', color: 'var(--trace-error)' };
    case 'AGENT_ERROR':
      return { category: 'error', icon: '❌', label: 'Agent Error', color: 'var(--trace-error)' };
    case 'SEARCH_FALLBACK':
      return { category: 'warning', icon: '⚠️', label: 'Search Fallback', color: 'var(--trace-warning)' };
    case 'MIXED_RESPONSE_IGNORED_FINAL':
      return { category: 'warning', icon: '⚠️', label: 'Mixed Response', color: 'var(--trace-warning)' };
    case 'PREMATURE_FINAL_ANSWER_IGNORED':
      return { category: 'warning', icon: '⚠️', label: 'Premature Final', color: 'var(--trace-warning)' };
    case 'MAX_STEPS_EXCEEDED':
      return { category: 'error', icon: '🛑', label: 'Max Steps', color: 'var(--trace-error)' };
    case 'LLM_METRIC':
      return { category: 'metric', icon: '📊', label: 'LLM Metric', color: 'var(--text-muted)' };
    case 'MODEL_OBSERVATION_IGNORED':
      return { category: 'warning', icon: '🔇', label: 'Model Obs Ignored', color: 'var(--trace-warning)' };
    case 'AGENT_END':
      return { category: 'info', icon: '🏁', label: 'Agent End', color: 'var(--text-secondary)' };
    case 'RUN_COMPLETE':
      return { category: 'final', icon: '🎉', label: 'Run Complete', color: 'var(--success)' };
    default:
      return { category: 'info', icon: '📝', label: type || 'Event', color: 'var(--text-muted)' };
  }
}

/**
 * Extract step number from event data.
 */
export function getStepNumber(event) {
  return event?.data?.step ?? null;
}
