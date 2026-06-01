import './Sidebar.css';

const NAV_ITEMS = [
  { id: 'chat',      icon: '💬', label: 'Chat' },
  { id: 'trace',     icon: '🔍', label: 'Trace' },
  { id: 'artifacts', icon: '📄', label: 'Artifacts' },
  { id: 'metrics',   icon: '📊', label: 'Metrics' },
  { id: 'settings',  icon: '⚙️', label: 'Settings' },
];

export default function Sidebar({ activeTab, onTabChange, provider, isOnline }) {
  return (
    <aside className="sidebar">
      <div className="sidebar__logo">
        <div className="sidebar__logo-icon">🔬</div>
        <div className="sidebar__logo-text">
          <span className="sidebar__logo-title">Research Gap</span>
          <span className="sidebar__logo-sub">ReAct Agent</span>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            className={`sidebar__nav-item ${activeTab === item.id ? 'sidebar__nav-item--active' : ''}`}
            onClick={() => onTabChange(item.id)}
          >
            <span className="sidebar__nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="sidebar__footer">
        <div className="sidebar__provider">
          <span className={`sidebar__provider-dot ${isOnline ? 'sidebar__provider-dot--online' : 'sidebar__provider-dot--offline'}`} />
          <span>{provider || 'scripted'} • {isOnline ? 'online' : 'offline'}</span>
        </div>
      </div>
    </aside>
  );
}
