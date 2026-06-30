import BlurText from './BlurText';
import './HeroHeadline.css';

export default function HeroHeadline() {
  return (
    <BlurText
      as="h1"
      text="The cache scheduler for back-to-back agent turns."
      delay={120}
      animateBy="words"
      direction="top"
      stepDuration={0.35}
      threshold={0.1}
      className="hero-headline"
    />
  );
}
