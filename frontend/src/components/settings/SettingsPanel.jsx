import '../metrics/MetricsDashboard.css';

export default function SettingsPanel({ config, onChange }) {
  const handleChange = (key, value) => {
    onChange({ ...config, [key]: value });
  };

  return (
    <div className="settings">
      <h2 className="settings__title">⚙️ Agent Settings</h2>

      <div className="settings__group">
        <div className="settings__group-title">LLM Provider</div>

        <div className="settings__field">
          <label className="settings__label">Provider</label>
          <select
            className="settings__select"
            value={config.provider}
            onChange={e => handleChange('provider', e.target.value)}
          >
            <option value="scripted">Scripted (Demo)</option>
            <option value="mimo">Xiaomi MiMo</option>
            <option value="openai">OpenAI GPT-4o</option>
            <option value="google">Google Gemini</option>
            <option value="local">Local (Phi-3 GGUF)</option>
          </select>
        </div>
      </div>

      <div className="settings__group">
        <div className="settings__group-title">Agent Configuration</div>

        <div className="settings__field">
          <label className="settings__label">
            Max Steps
            <span className="settings__range-value">{config.maxSteps}</span>
          </label>
          <input
            type="range"
            className="settings__range"
            min="1"
            max="20"
            value={config.maxSteps}
            onChange={e => handleChange('maxSteps', parseInt(e.target.value))}
          />
        </div>

        <div className="settings__field">
          <div className="settings__toggle">
            <div
              className={`settings__toggle-switch ${config.offline ? 'settings__toggle-switch--on' : ''}`}
              onClick={() => handleChange('offline', !config.offline)}
            />
            <label className="settings__label" style={{ marginBottom: 0, cursor: 'pointer' }}
              onClick={() => handleChange('offline', !config.offline)}>
              Offline Mode (Mock Data)
            </label>
          </div>
        </div>
      </div>

      <div className="settings__group">
        <div className="settings__group-title">About</div>
        <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
          <p><strong>Research Gap Analyzer</strong> uses the ReAct (Reasoning + Acting) pattern to analyze academic literature and identify research gaps.</p>
          <p style={{ marginTop: '8px' }}>The agent follows a Thought → Action → Observation loop, using tools to search papers, extract evidence, compare findings, and generate structured reports.</p>
          <p style={{ marginTop: '8px', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
            Lab 3 — Agentic AI Course • Design Pattern: ReAct
          </p>
        </div>
      </div>
    </div>
  );
}
