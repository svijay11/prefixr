import { useEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';
import './ProductDemo.css';

const PROMPT =
  'Add retry logic to the API client and fix the failing auth tests…';

const SCENES = ['ide', 'intercept', 'prefixr'];

export default function ProductDemo() {
  const [scene, setScene] = useState(0);
  const [typed, setTyped] = useState('');
  const panelsRef = useRef([]);
  const frameRef = useRef(null);
  const loopRef = useRef(null);
  const masterTlRef = useRef(null);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setScene(0);
      setTyped(PROMPT);
      panelsRef.current.forEach((el, i) => {
        if (el) gsap.set(el, { opacity: i === 0 ? 1 : 0, y: 0 });
      });
      return;
    }

    const runLoop = () => {
      masterTlRef.current?.kill();
      const tl = gsap.timeline({
        onComplete: () => {
          loopRef.current = gsap.delayedCall(0.8, runLoop);
        },
      });
      masterTlRef.current = tl;

      // Scene 0: IDE typing
      setScene(0);
      setTyped('');
      panelsRef.current.forEach((el, i) => {
        if (el) gsap.set(el, { opacity: i === 0 ? 1 : 0, y: i === 0 ? 0 : 12 });
      });

      const typeObj = { len: 0 };
      tl.to(typeObj, {
        len: PROMPT.length,
        duration: 2.8,
        ease: 'none',
        onUpdate: () => setTyped(PROMPT.slice(0, Math.round(typeObj.len))),
      });
      tl.to({}, { duration: 0.9 });

      // Scene 1: intercept
      tl.call(() => setScene(1));
      tl.to(panelsRef.current[0], { opacity: 0, y: -10, duration: 0.35, ease: 'power2.in' });
      tl.fromTo(
        panelsRef.current[1],
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.45, ease: 'power3.out' },
        '-=0.15',
      );
      tl.to({}, { duration: 1.8 });

      // Scene 2: prefixr optimizer
      tl.call(() => setScene(2));
      tl.to(panelsRef.current[1], { opacity: 0, y: -10, duration: 0.35, ease: 'power2.in' });
      tl.fromTo(
        panelsRef.current[2],
        { opacity: 0, y: 16 },
        { opacity: 1, y: 0, duration: 0.45, ease: 'power3.out' },
        '-=0.15',
      );
      tl.to({}, { duration: 2.6 });

      return tl;
    };

    const start = gsap.delayedCall(0.6, runLoop);
    return () => {
      start.kill();
      loopRef.current?.kill();
      masterTlRef.current?.kill();
    };
  }, []);

  useEffect(() => {
    if (frameRef.current) {
      gsap.fromTo(
        frameRef.current,
        { opacity: 0, y: 48, scale: 0.96 },
        { opacity: 1, y: 0, scale: 1, duration: 1, ease: 'power3.out', delay: 0.3 },
      );
    }
  }, []);

  return (
    <div className="product-demo">
      <div className="product-demo-frame" ref={frameRef}>
        <div className="product-demo-chrome">
          <div className="dot dot-r" />
          <div className="dot dot-y" />
          <div className="dot dot-g" />
          <span className="product-demo-title">
            {scene === 0 && 'Cursor — agent-workspace'}
            {scene === 1 && 'prefixr proxy — localhost:4242'}
            {scene === 2 && 'prefixr optimizer — turn #24'}
          </span>
        </div>

        <div className="product-demo-scene">
          {/* IDE */}
          <div
            className={`product-demo-panel ${scene === 0 ? 'active' : ''}`}
            ref={(el) => { panelsRef.current[0] = el; }}
          >
            <div className="ide-layout">
              <div className="ide-sidebar">
                <div className="ide-sidebar-label">Explorer</div>
                <div className="ide-file active">auth.ts</div>
                <div className="ide-file">api-client.ts</div>
                <div className="ide-file">auth.spec.ts</div>
              </div>
              <div className="ide-main">
                <div className="ide-editor">
                  <div><span className="ide-line-num">12</span><span className="ide-kw">export async function</span> <span className="ide-fn">refreshToken</span>() {'{'}</div>
                  <div><span className="ide-line-num">13</span>  <span className="ide-kw">const</span> res = <span className="ide-kw">await</span> fetch(<span className="ide-str">'/api/auth'</span>);</div>
                  <div><span className="ide-line-num">14</span>  <span className="ide-kw">return</span> res.json();</div>
                  <div><span className="ide-line-num">15</span>{'}'}</div>
                  <div><span className="ide-line-num">16</span><span className="ide-cm">// TODO: add retry + tests</span></div>
                </div>
                <div className="ide-agent">
                  <div className="ide-agent-label">
                    <span className="ide-agent-dot" />
                    Agent · Claude Sonnet
                  </div>
                  <div className="ide-agent-input">
                    {typed}
                    <span className="ide-cursor" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Intercept */}
          <div
            className={`product-demo-panel ${scene === 1 ? 'active' : ''}`}
            ref={(el) => { panelsRef.current[1] = el; }}
            style={{ opacity: 0 }}
          >
            <div className="intercept-body">
              <div className="intercept-flow">
                <div className="intercept-node">Cursor agent</div>
                <span className="intercept-arrow">→</span>
                <div className="intercept-node">api.anthropic.com</div>
                <span className="intercept-arrow">→</span>
                <div className="intercept-node highlight">localhost:4242</div>
                <span className="intercept-arrow">→</span>
                <div className="intercept-node">Anthropic API</div>
              </div>
              <p className="intercept-caption">
                Prefixr intercepts locally — your keys never leave your machine unoptimized.
              </p>
            </div>
          </div>

          {/* Prefixr optimizer */}
          <div
            className={`product-demo-panel ${scene === 2 ? 'active' : ''}`}
            ref={(el) => { panelsRef.current[2] = el; }}
            style={{ opacity: 0 }}
          >
            <div className="prefixr-body">
              <div className="prefixr-log">
                <div className="prefixr-log-line">→ turn #24 incoming (18,420 tokens)</div>
                <div className="prefixr-log-line info">  evaluating preserve vs summarize…</div>
                <div className="prefixr-log-line info">  hit_rate: 0.873 · horizon: 5 turns</div>
                <div className="prefixr-log-line warn">  pad: +124 tokens to 2048 checkpoint</div>
                <div className="prefixr-log-line ok">✓ action: preserve (saves $0.002341)</div>
                <div className="prefixr-log-line ok">✓ forwarded · 16,080 tokens cached</div>
              </div>
              <div className="prefixr-decision">
                <div className="prefixr-decision-title">Optimizer decision</div>
                <span className="prefixr-badge">preserve</span>
                <div className="prefixr-log-line" style={{ color: 'rgba(255,255,255,0.55)', fontFamily: 'Inter, sans-serif', fontSize: '0.72rem', lineHeight: 1.55 }}>
                  87.3% hit rate beats all strategies over the next 5 turns. Context left intact.
                </div>
                <div className="prefixr-stat-row">
                  <div className="prefixr-stat">
                    <div className="prefixr-stat-label">Hit rate</div>
                    <div className="prefixr-stat-value">87.3%</div>
                  </div>
                  <div className="prefixr-stat">
                    <div className="prefixr-stat-label">Saved</div>
                    <div className="prefixr-stat-value teal">$0.0847</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="product-demo-tabs" aria-hidden="true">
        {SCENES.map((_, i) => (
          <button
            key={SCENES[i]}
            type="button"
            className={`product-demo-tab ${scene === i ? 'active' : ''}`}
            tabIndex={-1}
          />
        ))}
      </div>
    </div>
  );
}
