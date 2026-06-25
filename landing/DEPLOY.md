# Deploying to Vercel

Only the **marketing site** should be public. The dashboard and proxy stay local.

## Vercel project settings

| Setting | Value |
|---------|--------|
| **Root Directory** | `landing` |
| **Framework Preset** | Other |
| **Build Command** | `npm run build` |
| **Output Directory** | `out` |
| **Install Command** | `npm install` (or leave default) |

## What visitors see

- `https://your-domain.vercel.app` → marketing page only
- No Python, no proxy, no dashboard API

## What stays local (never on Vercel)

| Thing | URL | Why |
|-------|-----|-----|
| Proxy API | `localhost:4242/v1` | Intercepts your API keys |
| Dashboard | `localhost:4242/dashboard` | Reads local SQLite DB |
| Session data | `~/.prefixr/sessions.db` | On your machine |

## Dev localhost ports (not deployed)

| Port | Purpose | Command |
|------|---------|---------|
| 4242 | Real app (proxy + dashboard) | `prefixr run` |
| 3001 | Preview landing page locally | `npm run dev:landing` |
| 3000 | Preview dashboard HTML locally | `npm run dev:dashboard` |

Only port **4242** is the real product. 3000/3001 are developer previews.
