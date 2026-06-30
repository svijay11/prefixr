import TrueFocus from './TrueFocus';
import './IntroCopy.css';

const FOCUS = {
  blurAmount: 2,
  borderColor: '#2563eb',
  glowColor: 'rgba(37, 99, 235, 0.3)',
  animationDuration: 0.4,
  pauseBetweenAnimations: 1.4,
};

export default function IntroCopy() {
  return (
    <div className="intro-copy">
      <p className="intro-line">
        <TrueFocus sentence="Prefix caching" className="intro-focus" {...FOCUS} />
        <span className="intro-plain">
          {' '}
          is only half the problem. Most agents grow context turn over turn, constantly busting the
          prefix you just paid to warm.
        </span>
      </p>

      <p className="intro-line">
        <span className="intro-plain">Prefixr schedules every turn. It runs cost math locally and chooses </span>
        <TrueFocus sentence="preserve pad summarize" className="intro-focus" {...FOCUS} />
        <span className="intro-plain"> before your request leaves the machine.</span>
      </p>
    </div>
  );
}
