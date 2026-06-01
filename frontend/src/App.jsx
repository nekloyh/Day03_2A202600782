import { useState, useCallback } from 'react';
import Sidebar from './components/layout/Sidebar';
import ChatPanel from './components/chat/ChatPanel';
import TracePanel from './components/trace/TracePanel';
import ArtifactsPanel from './components/artifacts/ArtifactsPanel';
import MetricsDashboard from './components/metrics/MetricsDashboard';
import SettingsPanel from './components/settings/SettingsPanel';
import { useAgent } from './hooks/useAgent';
import './App.css';

const TAB_TITLES = {
  chat: '💬 Chat + 🔍 Trace',
  trace: '🔍 Trace Viewer',
  artifacts: '📄 Research Artifacts',
  metrics: '📊 Performance Metrics',
  settings: '⚙️ Settings',
};

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const [config, setConfig] = useState({
    provider: 'scripted',
    maxSteps: 10,
    offline: true,
  });

  const agent = useAgent();

  const handleRun = useCallback((topic) => {
    agent.run({
      topic,
      provider: config.provider,
      offline: config.offline,
      maxSteps: config.maxSteps,
    });
  }, [agent, config]);

  const renderContent = () => {
    switch (activeTab) {
      case 'chat':
        return (
          <div className="app__split">
            <div className="app__split-pane">
              <div className="app__pane-header">💬 Chat</div>
              <ChatPanel
                onRun={handleRun}
                status={agent.status}
                finalAnswer={agent.finalAnswer}
                error={agent.error}
              />
            </div>
            <div className="app__split-pane">
              <div className="app__pane-header">🔍 ReAct Trace</div>
              <div style={{ flex: 1, overflow: 'hidden', padding: 'var(--space-md)' }}>
                <TracePanel
                  trace={agent.trace}
                  metrics={agent.metrics}
                  status={agent.status}
                  maxSteps={config.maxSteps}
                />
              </div>
            </div>
          </div>
        );

      case 'trace':
        return (
          <div className="app__full-pane" style={{ padding: 'var(--space-md)' }}>
            <TracePanel
              trace={agent.trace}
              metrics={agent.metrics}
              status={agent.status}
              maxSteps={config.maxSteps}
            />
          </div>
        );

      case 'artifacts':
        return (
          <div className="app__full-pane">
            <ArtifactsPanel artifacts={agent.artifacts} />
          </div>
        );

      case 'metrics':
        return (
          <div className="app__full-pane">
            <MetricsDashboard metrics={agent.metrics} trace={agent.trace} />
          </div>
        );

      case 'settings':
        return (
          <div className="app__full-pane">
            <SettingsPanel config={config} onChange={setConfig} />
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="app">
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        provider={config.provider}
        isOnline={!config.offline}
      />
      <main className="app__main">
        <header className="app__header">
          <div className="app__header-title">
            {TAB_TITLES[activeTab] || 'Research Gap Analyzer'}
          </div>
          <div className="app__header-actions">
            {agent.status === 'running' && (
              <button className="btn btn--ghost btn--sm" onClick={agent.cancel}>
                ⏹ Cancel
              </button>
            )}
            {(agent.status === 'completed' || agent.status === 'error') && (
              <button className="btn btn--ghost btn--sm" onClick={agent.reset}>
                🔄 Reset
              </button>
            )}
            <span className="badge badge--primary">{config.provider}</span>
          </div>
        </header>
        <div className="app__content">
          {renderContent()}
        </div>
      </main>
    </div>
  );
}
