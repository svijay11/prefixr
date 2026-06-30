import { useEffect, useRef, useState } from 'react';
import './LiveDashboard.css';

const SESSIONS = [
  { id: '4a2f', name: 'agent-run #4a2f', meta: 'anthropic · claude-sonnet', active: true },
  { id: 'cursor', name: 'cursor-session', meta: 'openai · gpt-4o' },
  { id: 'eval', name: 'eval-harness', meta: 'gemini · gemini-2.5-flash' },
];

const TURNS = [
  {
    turn: 24,
    time: 'just now',
    badge: 'preserve',
    badgeClass: 'badge-preserve',
    reason: 'Preserve: 87.3% hit rate beats all strategies; projected $0.002341 over 5 turns',
    pulse: true,
  },
  {
    turn: 23,
    time: '2m ago',
    badge: 'pad',
    badgeClass: 'badge-pad',
    reason: 'Pad injection: add 124 tokens to reach 2048-token checkpoint, saves $0.001892 over 5 turns',
  },
];

function useCountUp(target, active, duration = 1400, decimals = 0) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!active) {
      setValue(0);
      return;
    }
    const start = performance.now();
    let frame;
    const tick = (now) => {
      const t = Math.min((now - start) / duration, 1);
      const eased = 1 - (1 - t) ** 3;
      setValue(target * eased);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, active, duration]);

  if (decimals > 0) return value.toFixed(decimals);
  if (target >= 1000) return `${Math.round(value / 1000)}k`;
  return String(Math.round(value));
}

export default function LiveDashboard() {
  const rootRef = useRef(null);
  const [active, setActive] = useState(false);
  const [showSessions, setShowSessions] = useState(0);
  const [showStats, setShowStats] = useState(0);
  const [showBar, setShowBar] = useState(false);
  const [showTurns, setShowTurns] = useState(0);

  const hitRate = useCountUp(87.3, active, 1400, 1);
  const tokens = useCountUp(142000, active, 1600);
  const turns = useCountUp(24, active, 1200);
  const saved = useCountUp(0.0847, active, 1500, 4);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setActive(true);
          observer.disconnect();
        }
      },
      { threshold: 0.25 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!active) return;

    const timers = [
      setTimeout(() => setShowSessions(1), 200),
      setTimeout(() => setShowSessions(2), 400),
      setTimeout(() => setShowSessions(3), 600),
      setTimeout(() => setShowStats(1), 500),
      setTimeout(() => setShowStats(2), 650),
      setTimeout(() => setShowStats(3), 800),
      setTimeout(() => setShowStats(4), 950),
      setTimeout(() => setShowBar(true), 900),
      setTimeout(() => setShowTurns(1), 1100),
      setTimeout(() => setShowTurns(2), 1350),
    ];

    return () => timers.forEach(clearTimeout);
  }, [active]);

  return (
    <div className="live-dashboard" ref={rootRef}>
      <div className="mockup">
        <div className="mockup-bar">
          <div className="dot dot-r" />
          <div className="dot dot-y" />
          <div className="dot dot-g" />
          <div className="mockup-title">
            <span className="live-dot" />
            Prefixr Dashboard — localhost:4242
          </div>
        </div>
        <div className="mockup-body">
          <div className="mockup-sidebar">
            <h4>Sessions</h4>
            {SESSIONS.map((s, i) => (
              <div
                key={s.id}
                className={`session-item ${s.active ? 'active' : ''} ${showSessions > i ? 'visible' : ''}`}
              >
                {s.name}
                <span>{s.meta}</span>
              </div>
            ))}
          </div>
          <div className="mockup-main">
            <div className="stat-row">
              <div className={`stat-card ${showStats >= 1 ? 'visible' : ''}`}>
                <div className="label">Hit rate</div>
                <div className="value">{hitRate}%</div>
              </div>
              <div className={`stat-card ${showStats >= 2 ? 'visible' : ''}`}>
                <div className="label">Tokens cached</div>
                <div className="value">{tokens}</div>
              </div>
              <div className={`stat-card ${showStats >= 3 ? 'visible' : ''}`}>
                <div className="label">Turns</div>
                <div className="value">{turns}</div>
              </div>
              <div className={`stat-card ${showStats >= 4 ? 'visible' : ''}`}>
                <div className="label">Saved</div>
                <div className="value green">${saved}</div>
              </div>
            </div>

            <div className={`hit-bar-wrap ${showBar ? 'visible' : ''}`}>
              <div className="hit-bar-label">
                <span>Prefix cache utilization</span>
                <span>87.3%</span>
              </div>
              <div className="hit-bar-track">
                <div className={`hit-bar-fill ${showBar ? 'visible' : ''}`} />
              </div>
            </div>

            {TURNS.map((t, i) => (
              <div
                key={t.turn}
                className={`turn-card ${showTurns > i ? 'visible' : ''} ${t.pulse && showTurns > i ? 'pulse' : ''}`}
              >
                <div className="turn-header">
                  <span>Turn {t.turn} · {t.time}</span>
                  <span className={`badge ${t.badgeClass}`}>{t.badge}</span>
                </div>
                <div className="turn-reason">{t.reason}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
