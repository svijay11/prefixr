import { useRef } from 'react';
import { gsap } from 'gsap';
import { useGSAP } from '@gsap/react';
import { BrandIcons } from './brandIcons';
import './LogosMarquee.css';

gsap.registerPlugin(useGSAP);

const TOOLS = Object.keys(BrandIcons);

export default function LogosMarquee() {
  const rootRef = useRef(null);
  const trackRef = useRef(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();

      mm.add(
        {
          isFine: '(prefers-reduced-motion: no-preference)',
          reduceMotion: '(prefers-reduced-motion: reduce)',
        },
        (context) => {
          const { reduceMotion } = context.conditions;
          const track = trackRef.current;
          const root = rootRef.current;
          if (!track) return;

          if (reduceMotion) {
            gsap.set(track, { x: 0 });
            return;
          }

          gsap.set(track, { x: 0 });
          const distance = track.scrollWidth / 2;
          if (distance < 1) return;

          const loopTween = gsap.to(track, {
            x: -distance,
            duration: Math.max(32, distance / 34),
            ease: 'none',
            repeat: -1,
          });

          const pause = () => loopTween.pause();
          const play = () => loopTween.play();
          root?.addEventListener('pointerenter', pause);
          root?.addEventListener('pointerleave', play);

          return () => {
            root?.removeEventListener('pointerenter', pause);
            root?.removeEventListener('pointerleave', play);
          };
        },
        rootRef
      );

      return () => mm.revert();
    },
    { scope: rootRef }
  );

  const loop = [...TOOLS, ...TOOLS];

  return (
    <div className="logos-marquee" ref={rootRef}>
      <h2 className="logos-marquee-heading">Works with every tool you already use</h2>
      <div className="logos-marquee-viewport" aria-label="Supported tools and providers">
        <div className="logos-marquee-fade logos-marquee-fade--left" aria-hidden="true" />
        <div className="logos-marquee-fade logos-marquee-fade--right" aria-hidden="true" />
        <div className="logos-marquee-track" ref={trackRef}>
          {loop.map((name, i) => (
            <div
              key={`${name}-${i}`}
              className="logos-marquee-item"
              aria-hidden={i >= TOOLS.length ? true : undefined}
            >
              <span className="logos-marquee-icon">{BrandIcons[name]}</span>
              <span className="logos-marquee-name">{name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
