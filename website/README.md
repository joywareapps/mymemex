# MyMemex Website

Marketing and documentation site for [mymemex.app](https://mymemex.app), built with [Astro](https://astro.build) and Tailwind CSS.

## Pages

- `/` — Landing page with hero, feature overview, and live demo link
- `/features` — Full feature list with technical details
- `/roadmap` — Milestone history and upcoming work

## Development

```bash
npm install
npm run dev       # Dev server at localhost:4321
npm run build     # Build to ./dist/
npm run preview   # Preview built site
```

## Deployment

The site is deployed as static files. Use the deploy script from the repo root:

```bash
bash website/update-website.sh
```

Requires `MYMEMEX_WEBSITE_DEPLOY_PATH` env var pointing to the web server document root.
