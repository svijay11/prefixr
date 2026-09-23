import { BrandIcons } from './brandIcons';
import './LogosMarquee.css';

const TOOLS = Object.keys(BrandIcons);

export default function LogosMarquee() {
  return (
    <div className="logos-marquee">
      <ul className="logos-marquee-list" aria-label="Supported tools and providers">
        {TOOLS.map((name) => (
          <li key={name} className="logos-marquee-item">
            <span className="logos-marquee-icon">{BrandIcons[name]}</span>
            <span className="logos-marquee-name">{name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
