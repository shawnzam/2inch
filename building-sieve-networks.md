# Building a Sieve Network

*A playbook for growing a curated relationship graph from an open API + an LLM, and
showing it as an interactive D3 network in a single HTML file.*

This is the method behind [2inch.fm](https://2inch.fm) — a map of who recorded which
indie records — but nothing here is music-specific. It works for any
**who-did-what-with-whom** dataset: papers ↔ co-authors, films ↔ crew, repos ↔
contributors, recipes ↔ ingredients, companies ↔ board members. If you can get
relationship data from an API, you can build one of these.

The whole thing is two halves:

1. **The sieve pipeline** — how to *grow* a trustworthy dataset.
2. **The D3 interface** — how to *show* it.

---

## Part 1 — The methodology: the cycle of sieves

### The core idea

Most "let an LLM build my dataset" projects fail the same way: the model **fabricates**.
It invents plausible credits that don't exist. The fix is to never let the model
*author* data — only **sieve** it.

> **The LLM is a filter, not a source.** Real data comes from a structured API. The model
> only (a) throws out noise and (b) suggests where to look next.

Everything flows from that. You get an honest, verifiable graph instead of a confident
hallucination.

### The cycle

```
  seed entities ──▶ crawl an open API ──▶ SIEVE ① scope (deterministic)
                                        ──▶ SIEVE ② notability (LLM)
                                        ──▶ SIEVE ③ dedup (deterministic)
                                        ──▶ merge (tagged with provenance)
                                        ──▶ LLM nominates more seeds ──┐
            ▲                                                          │
            └──────────────────────────────────────────────────────────┘
```

Each pass through the cycle is a **round**. You run a few rounds and watch it grow.

- **Seed** with a handful of high-degree *hubs* you trust (for music: famous engineers;
  for papers: seminal authors). Hubs are the move — each one drags in a cluster.
- **Crawl** the API for each seed's relationships. Parse **deterministically** — the API
  already returns structured data, so no LLM is needed to read it. (This is the step
  people wrongly hand to an LLM.)
- **Sieve ① — scope:** a hard, code-level filter (a date window, a category). Cheap, exact,
  no model.
- **Sieve ② — notability:** the *only* place the LLM touches data. It looks at each new
  candidate and answers one yes/no: *is this real and notable, or is it noise?* It removes
  compilations-posing-as-entities, mis-parsed junk, total unknowns. It does **not** judge
  taste, importance, or scope. When unsure → keep.
- **Sieve ③ — dedup:** drop anything already in the graph. Deterministic.
- **Merge** survivors, **tagging each with its provenance** (see below).
- **Nominate:** ask the LLM for more in-scope *hubs* you don't have yet. Those seed the
  next round. This is the only generative thing it does, and even here it's proposing
  *search terms*, not data.

### The five principles that make it trustworthy

1. **LLM as sieve, not author.** Deterministic parse; the model only judges and nominates.
   It can't fabricate a credit because it never writes one.
2. **Provenance on everything.** Tag every auto-added node/edge (`src:"mb"`). Your
   hand-curated core has no tag. Now the two are *always separable* — you can trim all
   auto data in one line, and nothing automated can silently overwrite a checked entry.
   Better: store the **exact source ID** (the API record's id) on each edge, so every
   fact deep-links to where it came from. One click to verify.
3. **Network-first growth.** Don't try to filter *for* relevance — keep almost everything a
   trusted hub connects to, then prune later. A real engineer recording an off-genre record
   is a *true edge*; keep it. Completeness of the *network* beats purity of the *set*.
4. **Resumable, cached, polite.** Cache every raw API response to disk. Rate-limit to be a
   good citizen. Then re-runs are instant, crashes resume for free, and re-parsing (e.g. to
   capture a field you forgot) needs zero new calls. **This cache is your real database.**
5. **Be honest about bias.** Every project has an arbitrary boundary (a date window, a
   scene, a definition). State it plainly and **publish your prompts verbatim**. For an
   audience that distrusts AI, transparency *is* the authority — "here's exactly how every
   call was made" beats a polished black box.

### Knowing when to stop

Watch the **nomination well run dry**. When the LLM starts suggesting hubs you already have,
or reaching outside your scope, you've saturated the domain. Stop. (You'll also hit a
*rendering* ceiling first — see Part 2.)

### Why an LLM at all?

Two jobs a deterministic crawler can't do:
- **Noise judgment.** Is "DJ Promo Mix Vol 7" a real artist? Is "qwertyuiop asdf" garbage?
  A human knows instantly; regex doesn't. That's the notability sieve.
- **Frontier expansion.** "Given these 60 hubs, name 25 more from the same world." That's
  taste-as-recall, which is exactly what a model trained on the whole internet is good at —
  and it's *safe*, because the suggestions get crawled and sieved like everything else.

---

## Part 2 — The interface: an interactive D3 network in one HTML file

The whole front end is **one self-contained `index.html`** — D3 v7 from a CDN, no build
step, no framework. It fetches a `data.json` and renders a force-directed graph. Host it as
a static file anywhere.

### Data shape

```json
{
  "nodes": [
    { "id": "Steve Albini", "type": "engineer", "bio": "…", "src": "mb", "mbid": "a4d4…" }
  ],
  "links": [
    { "source": "Steve Albini", "target": "Shellac", "label": "Terraform", "year": 1998,
      "src": "mb", "mbid": "55e5…" }
  ]
}
```

Keep nodes light (the browser loads them all). `type` drives color/shape; `src`/`mbid` are
your provenance.

### The force simulation (the heart)

```js
const sim = d3.forceSimulation(nodes)
  .force("link",   d3.forceLink(links).id(d => d.id).distance(d => d.affil ? 52 : 92))
  .force("charge", d3.forceManyBody().strength(d => d.type === "engineer" ? -440 : -130))
  .force("center", d3.forceCenter(width / 2, height / 2))
  .force("collide", d3.forceCollide(d => radius[d.type] + 7));
```

- **`forceManyBody` (charge):** negative = repulsion. Give your *hubs* stronger repulsion so
  they push apart and the graph doesn't clump.
- **`forceLink.distance`:** longer for "important" edges, short for tight affiliations.
- **`forceCollide`:** stops node overlap. Underrated; do it.
- Size nodes by **degree** (how connected they are) so hubs read as hubs.

### Rendering + interactions

```js
node.call(d3.drag().on("start", …).on("drag", …).on("end", …))  // drag to reposition
    .on("click", (e, d) => showCard(d))                          // click → details panel
    .on("mouseenter", (e, d) => highlightNeighbors(d));          // hover → fade the rest
svg.call(d3.zoom().scaleExtent([0.25, 4]).on("zoom",
         e => g.attr("transform", e.transform)));                // scroll to zoom, drag to pan
```

On every simulation `tick`, copy `d.x/d.y` onto the SVG elements. That's the animation loop.

### The one feature that makes a dense graph usable: ego-network search

A full force graph past a few hundred nodes is an unreadable hairball. The fix is **search =
ego-network**: typing a name shows that node *plus its neighbors*, not just the node.

```js
if (query) {
  const matched = new Set(nodes.filter(n => n.id.toLowerCase().includes(query)).map(n => n.id));
  const keep = new Set(matched);
  links.forEach(l => {                       // pull in 1-hop neighbors
    if (matched.has(id(l.source))) keep.add(id(l.target));
    if (matched.has(id(l.target))) keep.add(id(l.source));
  });
  activeNodes = nodes.filter(n => keep.has(n.id));
}
```

This is the difference between "cool but useless" and "I can actually explore this."
Consider making an **ego view the default** once you're past ~500 nodes.

### Click-to-focus, paths, and shareable views

Three cheap additions turn a static graph into something people *use* and *share*:

- **Click-to-focus.** Clicking a node recenters the graph on its ego-network; click a
  neighbor to walk outward, click empty space to reset. The whole graph becomes navigable
  node by node, which is how anyone actually reads a hairball.
- **Path-finding (six degrees).** A breadth-first search over the link list returns the
  shortest chain between any two nodes. For a relationship graph this is *the* signature
  feature, and it's ~20 lines.
- **Deep-linkable views.** Encode the current view in the URL (`?n=<node>`, `?p=<from>,<to>`)
  and read it on load. Now every view is shareable and the address bar *is* the share button.
  Use **`?query`, not `#hash`** — fragments never reach the server, which matters for the
  dynamic share previews below.

### The detail panel (where provenance shows its work)

Click a node → a sidebar with its relationships. This is where you **show your sources**:
each row deep-links to the exact API record it came from, and curated rows are marked
"curated." Lazy-enrich here too — fetch album art / thumbnails / extra metadata *on click*,
cached in memory, so the initial load stays tiny.

### Real gotchas we hit (so your friend doesn't)

- **`d3.select("svg")` grabs the *first* svg on the page** — if you have a tiny legend SVG
  before your graph SVG, D3 draws the whole graph into the legend and clips it to ~50px.
  *Give your graph svg an `id` and select that.* (Cost us an afternoon.)
- **SVG sizing:** size the graph svg with `position:absolute; inset:0` inside a positioned
  container, or it can collapse and clip everything.
- **The legibility ceiling is ~500–1000 nodes**, and it's a *rendering* limit, not a data
  one — your JSON is fine at 10× that. Past it, you need ego-views / canvas / WebGL, not a
  bigger file. So a database doesn't "unlock scale" here; rendering does.
- **CORS for live enrichment:** some APIs send permissive CORS and work straight from the
  browser (MusicBrainz, the iTunes Search API). Others (Discogs) need a token / a proxy.
  Test before you design around it.
- **Static JSON on a CDN beats a database** for read-only data you render whole. It's
  faster (edge-cached), free, and simpler than standing up an API in front of a DB. Only
  reach for a real datastore when you add writes, search, or subgraph queries.

---

## Part 3 — The toolchain

- **Crawler:** Python, *stdlib only* (`urllib`, `asyncio`, `json`) so it runs anywhere with
  no `pip install`. Async producer/consumer so the **API rate-limit wait is spent running
  LLM inference** — the crawler is mostly sleeping; the model judges/nominates in those gaps.
  Wall-time ≈ max(crawl, inference), not the sum.
- **The LLM:** the local `claude` CLI in headless mode — `claude -p --model sonnet "…"` —
  called as a subprocess. Sonnet is plenty for keep/drop judgments and cheap. Cache its
  outputs too.
- **Hosting:** Cloudflare Pages via `wrangler pages deploy`. Single static dir, a scoped API
  token for one-command redeploys, a custom domain (apex `CNAME → *.pages.dev`, proxied).
- **Sharing:** static Open Graph tags get you *a* preview; for one that's *specific to each
  link* (this node's web, that six-degrees chain), render it at the edge. On Cloudflare Pages
  a Function reads the `?query`, injects per-link `og:title`/`description`, and points
  `og:image` at a second Function that renders a 1200×630 PNG with `workers-og` (satori +
  resvg). It stays inside the **free Workers tier** at small scale. Gotchas: the `functions/`
  dir must sit at the project *root* (not in the assets dir, or it's served as a static file
  and never compiled); and satori does **not** decode HTML entities — use literal Unicode and
  don't HTML-escape your text.
- **Verification:** drive a real browser with **Playwright** to screenshot and assert the
  graph actually rendered — headless `chrome --screenshot` freezes before the force sim
  settles and lies to you.

---

## The shortest version

> Crawl a real API for relationships. Parse it with code, not a model. Use an LLM only to
> **throw out junk** and **suggest where to look next** — never to write data. Tag everything
> with where it came from. Render it as a D3 force graph in one HTML file, and make search
> show a node's *neighborhood*, not just the node. State your biases and publish your prompts.

That's a sieve network. Go build one about something you love.
