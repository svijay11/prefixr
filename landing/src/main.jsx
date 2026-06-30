import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import CardNav from './CardNav';
import ProductDemo from './ProductDemo';
import LiveDashboard from './LiveDashboard';
import IntroCopy from './IntroCopy';
import HeroHeadline from './HeroHeadline';

const navItems = [
  {
    label: 'Product',
    bgColor: '#141c2b',
    textColor: '#fff',
    links: [
      { label: 'Features', href: '#features', ariaLabel: 'View features' },
      { label: 'How it works', href: '#how', ariaLabel: 'How prefixr works' },
      { label: 'Live dashboard', href: '#dashboard', ariaLabel: 'See the live dashboard' },
    ],
  },
  {
    label: 'Integrations',
    bgColor: '#1c2738',
    textColor: '#fff',
    links: [
      { label: 'Cursor', href: 'https://github.com/svijay11/prefixr/blob/main/docs/CURSOR.md', ariaLabel: 'Cursor setup guide' },
      { label: 'OpenAI & Anthropic', href: '#features', ariaLabel: 'Supported providers' },
      { label: 'Gemini & DeepSeek', href: '#features', ariaLabel: 'More providers' },
    ],
  },
  {
    label: 'Developers',
    bgColor: '#0f4c5c',
    textColor: '#fff',
    links: [
      { label: 'GitHub', href: 'https://github.com/svijay11/prefixr', ariaLabel: 'GitHub repository' },
      { label: 'Install', href: '#install', ariaLabel: 'Install prefixr' },
      { label: 'Quick start', href: '#how', ariaLabel: 'Quick start guide' },
    ],
  },
];

function mount(id, node) {
  const el = document.getElementById(id);
  if (el) createRoot(el).render(<StrictMode>{node}</StrictMode>);
}

mount('card-nav-root', (
  <CardNav
    logoText="prefixr"
    logoAlt="prefixr"
    logoHref="#"
    items={navItems}
    baseColor="rgba(250, 248, 245, 0.92)"
    menuColor="#141c2b"
    buttonBgColor="#141c2b"
    buttonTextColor="#fff"
    buttonLabel="Install"
    buttonHref="#install"
    ease="power3.out"
  />
));

mount('product-demo-root', <ProductDemo />);
mount('live-dashboard-root', <LiveDashboard />);
mount('intro-copy-root', <IntroCopy />);
mount('hero-headline-root', <HeroHeadline />);
