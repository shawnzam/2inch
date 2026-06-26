# AGENTS.md

Guidance for AI agents (and humans) working in this repo. Read this first.

**2″ (two inch)** — an interactive D3 force-graph of who recorded which indie/alt
records (golden-age window **1995–2003**), grown by a "sieve" pipeline that crawls
MusicBrainz and uses an LLM only to filter noise. Live: **https://2inch.fm**.
Background: [`README.md`](README.md), [`building-sieve-networks.md`](building-sieve-networks.md),
[`pipeline/README.md`](pipeline/README.md).

## Repo map

| path | what it is |
|---|---|
| `indie-index/index.html` | the **entire** front end — D3 v7 (CDN), one self-contained file, **no build step** |
| `indie-index/about.html` | method page (cycle-of-sieves diagram, verbatim prompts) |
| `indie-index/data.json` | the dataset: `{nodes, links}`, provenance-tagged. **The served source of truth.** |
| `indie-index/{favicon.svg,og.png}` | static brand assets |
| `pipeline/` | resumable Python crawler (stdlib only + local `claude` binary) |
| `functions/` | **Cloudflare Pages Functions** (edge): dynamic Open Graph per share link |
| `deploy.sh` | one-command deploy to Cloudflare Pages |
| `package.json` | deps for the Functions only (`workers-og`); the app + pipeline have none |

## Commands

```bash
# run the site locally (static; Functions do NOT run here)
cd indie-index && python3 -m http.server 8742          # → http://localhost:8742

# run a crawl round (see pipeline/README.md for the full workflow)
python3 -m pipeline --model sonnet --year-min 1995 --year-max 2003 --grow 25   # preview
python3 pipeline/backfill_node_mbids.py                 # resolve node MBIDs after merging

# deploy (needs ~/.cf_2inch_token; deploys site + Functions)
bash deploy.sh
```

## Hard rules

- **Respect the process — never hand-edit `data.json`.** Every node/edge must come
  through the pipeline. If a record is missing (e.g. a self-produced album MusicBrainz
  has no engineer credit for), that's an honest gap — fix it *upstream* at MusicBrainz or
  leave it. The About page promises this; hand-patching breaks it. See the curated/crawl
  split below.
- **Provenance is sacred.** Crawl-added nodes/links carry `"src":"mb"`; the hand-curated
  core has no `src`. They must stay separable. Edges carry their MusicBrainz **release**
  id (`mbid`); nodes carry their **artist** id (`mbid`) — both power "view source" links.
- **The app has no build step.** Keep `index.html` self-contained. Match the existing
  manila/rust/ink aesthetic and the monospace/grotesque type.
- **Don't commit secrets.** The CF token lives in `~/.cf_2inch_token` (never in the repo).
  `node_modules/` and `pipeline/.cache/` are gitignored.

## Gotchas (real landmines, learned the hard way)

- **`d3.select("svg")` grabs the FIRST svg on the page** — there are tiny legend SVGs
  before the graph SVG. The graph svg has `id="net"`; select that, never the bare tag.
- **Cloudflare Pages Functions must live in `functions/` at the PROJECT ROOT**, not inside
  `indie-index/`. Inside the assets dir they're served as static files, never compiled.
  A successful deploy prints "Compiled Worker successfully".
- **satori (workers-og) does NOT decode HTML entities.** In `functions/og.js` use literal
  Unicode (`″ → –`), and do NOT HTML-escape text — it renders `&amp;` literally.
- **After a deploy, the apex (`2inch.fm`/`2inch.pages.dev`) edge-caches the old copy for a
  few seconds.** Verify against the immutable `https://<hash>.2inch.pages.dev` URL the
  deploy prints, or just wait and re-check.
- **Verify renders with a real browser (Playwright), not headless `chrome --screenshot`** —
  the latter freezes before the D3 force simulation ticks and shows a blank/empty graph.
- Share links use **`?query` (not `#hash`)** so the edge Function can read them for dynamic
  previews: `?n=<node-slug>` and `?p=<from-slug>,<to-slug>`.

## How to verify a change

1. `cd indie-index && python3 -m http.server 8742`, open it, exercise the change.
2. For the OG Functions: they only run when deployed (or `wrangler pages dev`). After
   `bash deploy.sh`, `curl https://2inch.pages.dev/og?n=steve-albini` should return a PNG,
   and `curl 'https://2inch.pages.dev/?n=steve-albini'` should show a custom `og:title`.
3. Commit only when the user asks; end commit messages with the project's Co-Authored-By
   trailer. The repo is public (`github.com/shawnzam/2inch`) — push with `git push`.
