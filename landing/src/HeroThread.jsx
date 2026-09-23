import { useRef } from 'react';
import { gsap } from 'gsap';
import { useGSAP } from '@gsap/react';
import './HeroThread.css';

gsap.registerPlugin(useGSAP);

function drawRibbon(ctx, w, h, t) {
  const midY = h * 0.62;
  const amp = Math.min(h * 0.2, 72);
  const sway = Math.sin(t * 0.7) * (w * 0.035);

  ctx.clearRect(0, 0, w, h);

  // No ambient wash — keep the hero background pure white
  const layers = 6;
  for (let i = 0; i < layers; i++) {
    const p = i / (layers - 1);
    const thickness = 14 + p * 26;
    const yOff = (p - 0.5) * 18;
    const phase = t * 1.05 + p * 1.2;

    ctx.beginPath();
    const steps = 64;
    for (let s = 0; s <= steps; s++) {
      const u = s / steps;
      const x = -w * 0.06 + u * w * 1.12 + sway * Math.cos(u * Math.PI);
      const wave =
        Math.sin(u * Math.PI * 2.15 + phase) * amp * 0.55 +
        Math.sin(u * Math.PI * 1.05 - phase * 0.55) * amp * 0.32;
      const y = midY + wave + yOff;
      if (s === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    const grad = ctx.createLinearGradient(0, 0, w, 0);
    grad.addColorStop(0, `rgba(255, 214, ${110 + i * 6}, ${0.45 + p * 0.4})`);
    grad.addColorStop(0.35, `rgba(255, 228, ${140 + i * 4}, ${0.55 + p * 0.35})`);
    grad.addColorStop(0.65, `rgba(${130 + i * 10}, ${175 + i * 8}, 255, ${0.5 + p * 0.4})`);
    grad.addColorStop(1, `rgba(${100 + i * 8}, ${160 + i * 6}, 245, ${0.45 + p * 0.4})`);

    ctx.strokeStyle = grad;
    ctx.lineWidth = thickness;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.globalAlpha = 0.92;
    ctx.stroke();
  }
  ctx.globalAlpha = 1;
}

export default function HeroThread() {
  const rootRef = useRef(null);
  const canvasRef = useRef(null);
  const wrapRef = useRef(null);

  useGSAP(
    () => {
      const canvas = canvasRef.current;
      const root = rootRef.current;
      const wrap = wrapRef.current;
      if (!canvas || !root || !wrap) return;

      const ctx = canvas.getContext('2d');
      const dpr = Math.min(window.devicePixelRatio || 1, 1.75);
      let raf = 0;
      let running = true;

      const resize = () => {
        const { width, height } = root.getBoundingClientRect();
        canvas.width = Math.max(1, Math.floor(width * dpr));
        canvas.height = Math.max(1, Math.floor(height * dpr));
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      };

      resize();

      const mm = gsap.matchMedia();

      mm.add('(prefers-reduced-motion: reduce)', () => {
        drawRibbon(ctx, canvas.clientWidth, canvas.clientHeight, 0.9);
        gsap.set(wrap, { x: 0, rotation: 0 });
      });

      mm.add('(prefers-reduced-motion: no-preference)', () => {
        const motion = { t: 0 };

        gsap.to(motion, {
          t: Math.PI * 2,
          duration: 16,
          ease: 'none',
          repeat: -1,
        });

        gsap.to(wrap, {
          x: 36,
          duration: 6.5,
          ease: 'sine.inOut',
          yoyo: true,
          repeat: -1,
        });

        gsap.to(wrap, {
          rotation: 3,
          duration: 10,
          ease: 'sine.inOut',
          yoyo: true,
          repeat: -1,
        });

        const tick = () => {
          if (!running) return;
          drawRibbon(ctx, canvas.clientWidth, canvas.clientHeight, motion.t);
          raf = requestAnimationFrame(tick);
        };
        raf = requestAnimationFrame(tick);

        return () => {
          running = false;
          cancelAnimationFrame(raf);
        };
      });

      window.addEventListener('resize', resize);
      return () => {
        running = false;
        cancelAnimationFrame(raf);
        window.removeEventListener('resize', resize);
        mm.revert();
      };
    },
    { scope: rootRef }
  );

  return (
    <div className="hero-thread" ref={rootRef} aria-hidden="true">
      <div className="hero-thread-wrap" ref={wrapRef}>
        <canvas ref={canvasRef} className="hero-thread-canvas" />
      </div>
      <div className="hero-thread-grain" />
    </div>
  );
}
