import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);

/**
 * Clean GSAP scroll reveals — replaces CSS IntersectionObserver reveals
 * with restrained, Apple-like opacity + translate motion.
 */
export function initScrollAnimations() {
  const mm = gsap.matchMedia();

  mm.add('(prefers-reduced-motion: reduce)', () => {
    gsap.set('.reveal, .reveal-left, .reveal-right, .reveal-scale', {
      clearProps: 'all',
      opacity: 1,
    });
  });

  mm.add('(prefers-reduced-motion: no-preference)', () => {
    const targets = gsap.utils.toArray(
      '.reveal, .reveal-left, .reveal-right, .reveal-scale'
    );

    targets.forEach((el) => {
      el.classList.add('gsap-ready');

      const fromX = el.classList.contains('reveal-left')
        ? -36
        : el.classList.contains('reveal-right')
          ? 36
          : 0;
      const fromY = el.classList.contains('reveal-scale') ? 20 : fromX ? 0 : 28;
      const fromScale = el.classList.contains('reveal-scale') ? 0.97 : 1;

      gsap.fromTo(
        el,
        { autoAlpha: 0, x: fromX, y: fromY, scale: fromScale },
        {
          autoAlpha: 1,
          x: 0,
          y: 0,
          scale: 1,
          duration: 0.85,
          ease: 'power3.out',
          overwrite: 'auto',
          scrollTrigger: {
            trigger: el,
            start: 'top 88%',
            toggleActions: 'play none none none',
            once: true,
          },
        }
      );
    });

    // Soft parallax on terminal blocks (subtle)
    gsap.utils.toArray('.terminal-wrap').forEach((el) => {
      gsap.to(el, {
        y: -18,
        ease: 'none',
        scrollTrigger: {
          trigger: el,
          start: 'top bottom',
          end: 'bottom top',
          scrub: 0.6,
        },
      });
    });

    // Section headings: slight rise on enter
    gsap.utils.toArray('.section-heading').forEach((el) => {
      if (el.closest('.reveal')) return;
      gsap.fromTo(
        el,
        { autoAlpha: 0, y: 18 },
        {
          autoAlpha: 1,
          y: 0,
          duration: 0.7,
          ease: 'power2.out',
          scrollTrigger: {
            trigger: el,
            start: 'top 90%',
            once: true,
          },
        }
      );
    });
  });

  return () => mm.revert();
}
