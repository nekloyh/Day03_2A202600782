import { useState, useRef, useEffect } from 'react';
import './ChatPanel.css';

export default function ChatPanel({ onRun, status, finalAnswer, error }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(scrollToBottom, [messages, finalAnswer]);

  // When finalAnswer arrives, add it as agent message
  useEffect(() => {
    if (finalAnswer && status === 'completed') {
      setMessages(prev => {
        // Avoid duplicating
        const last = prev[prev.length - 1];
        if (last?.type === 'agent' && last?.content === finalAnswer) return prev;
        return [...prev, { type: 'agent', content: finalAnswer, isFinal: true }];
      });
    }
  }, [finalAnswer, status]);

  // When error arrives
  useEffect(() => {
    if (error && status === 'error') {
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.type === 'error' && last?.content === error) return prev;
        return [...prev, { type: 'error', content: error }];
      });
    }
  }, [error, status]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || status === 'running') return;
    setMessages(prev => [...prev, { type: 'user', content: text }]);
    setInput('');
    onRun(text);
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleQuickRun = (topic) => {
    setMessages(prev => [...prev, { type: 'user', content: topic }]);
    onRun(topic);
  };

  const handleTextareaInput = (e) => {
    setInput(e.target.value);
    // Auto resize
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
  };

  return (
    <div className="chat-panel">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-messages__empty">
            <div className="chat-messages__empty-icon">🔬</div>
            <div className="chat-messages__empty-title">Research Gap Analyzer</div>
            <div className="chat-messages__empty-hint">
              Enter a research topic to analyze, or use a quick start below.
              The ReAct agent will search papers, extract evidence, compare findings, and identify research gaps.
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`msg msg--${msg.type === 'user' ? 'user' : 'agent'}`}>
            <div className={`msg__avatar msg__avatar--${msg.type === 'user' ? 'user' : 'agent'}`}>
              {msg.type === 'user' ? '👤' : '🤖'}
            </div>
            <div className="msg__body">
              {msg.type === 'error' ? (
                <div className="msg__error">{msg.content}</div>
              ) : msg.isFinal ? (
                <div className="msg__final">{msg.content}</div>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {status === 'running' && (
          <div className="chat-loading">
            <div className="chat-loading__dots">
              <div className="chat-loading__dot" />
              <div className="chat-loading__dot" />
              <div className="chat-loading__dot" />
            </div>
            Agent is thinking...
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="input-bar">
        <div className="input-bar__row">
          <textarea
            ref={textareaRef}
            className="input-bar__textarea"
            placeholder="Enter research topic... e.g., self-supervised learning for medical imaging"
            value={input}
            onChange={handleTextareaInput}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={status === 'running'}
          />
          <button
            className="input-bar__send"
            onClick={handleSend}
            disabled={!input.trim() || status === 'running'}
          >
            {status === 'running' ? '⏳' : '▶ Run'}
          </button>
        </div>
        <div className="input-bar__actions">
          <button
            className="input-bar__quick"
            onClick={() => handleQuickRun('self-supervised learning for medical image segmentation')}
            disabled={status === 'running'}
          >
            🏥 Medical SSL
          </button>
          <button
            className="input-bar__quick"
            onClick={() => handleQuickRun('efficient transformer architectures for edge devices')}
            disabled={status === 'running'}
          >
            ⚡ Efficient Transformers
          </button>
          <button
            className="input-bar__quick"
            onClick={() => handleQuickRun('federated learning for privacy-preserving healthcare AI')}
            disabled={status === 'running'}
          >
            🔒 Federated Learning
          </button>
        </div>
      </div>
    </div>
  );
}
