# 2″ ingestion pipeline

Resumable MusicBrainz crawl that grows `indie-index/data.json` in **rounds**.
Pure stdlib + the local `claude` binary — no `pip install`.

**Current state:** 2 rounds run. **469 nodes** (170 curated core + 299 crawl-added),
**620 album credits**, golden-age window **1995–2003**. Paused here (the graph is
getting dense; ego-search is the way to read it).

## The cycle of sieves

The graph grows by repeating one cycle (this is what the site's About page documents):

```
seed engineers → MusicBrainz crawl → SIEVE ① year window 1995–2003
              → SIEVE ② notability (Claude) → SIEVE ③ dedup → merge
              → Claude nominates more engineers → repeat
```

- **SIEVE ① year** and **③ dedup** are deterministic code.
- **SIEVE ② notability** is the *only* place the LLM touches data: it removes junk
  (compilations, DJ mixes, mis-parsed text, total unknowns) and nothing else.
  Network-first: keep almost everything a real engineer recorded, any genre.
- The **loop** is `--grow N`: Claude nominates N more in-scope engineers (the hubs),
  which seed the next round.

## Running a round

```bash
# 1. PREVIEW a round: nominate 25 new engineers, crawl + vet, write data.preview.json
python3 -m pipeline --model sonnet --year-min 1995 --year-max 2003 --grow 25

# 2. review data.preview.json, then MERGE it
cp indie-index/data.preview.json indie-index/data.json && rm indie-index/data.preview.json

# 3. backfill new nodes' MusicBrainz artist IDs (edges already carry release ids)
python3 pipeline/backfill_node_mbids.py

# 4. ship it
bash deploy.sh
```

Default seed (no `--grow`) is **every engineer already in `data.json`** — a plain
re-run just re-checks known engineers for newly-catalogued credits (cheap; cached).
Always preview first; only `--write` (or the `cp`) touches the canonical file.

## Provenance

- Every crawl-added node/link is tagged **`src:"mb"`** — the curated core has no tag,
  so the two are always separable and nothing automated overwrites a hand-checked entry.
- **Edges** carry the exact **release MBID** automatically (`mb.parse_credits`), so each
  credit deep-links to its source release. **Nodes** get their **artist MBID** via
  `backfill_node_mbids.py` (run it each round). Studios stay as search links (MB places).

## How it works

- **One MB call per person**: `/artist/{mbid}?inc=release-rels+artist-credits` returns
  role + album + year + performing band + release id. Parsing is deterministic — no LLM.
- **Rate limit ≤1 req/s** (`ratelimit.py`), shared globally. The crawl is mostly *waiting*;
  Claude tasks (referee, nomination) run concurrently inside those waits.
- **Resumable**: every raw response caches to `.cache/raw/{slug}.json`. Re-runs are instant
  and never re-hit the API. Crash/^C and resume freely. (Delete a cache file to force-refresh.)
- **Merge is deduped** by `source|target|normalized-album`, earliest year wins.

## CLI flags

| flag | effect |
|---|---|
| `--grow N` | Claude nominates N more in-scope engineers and crawls them |
| `--write` | update `data.json` in place (default: `data.preview.json`) |
| `--year-min / --year-max` | the era window (default 1980–2025; we use 1995–2003) |
| `--model` | claude model for referee/nomination (default `sonnet`) |
| `--no-referee` | skip SIEVE ② |
| `--suggest` | also print adjacent-artist suggestions |
| `--seed "A" "B"` | explicit seed names instead of all engineers |
| `--limit N` | cap seeds (testing) |

## Files

| file | role |
|---|---|
| `mb.py` | MusicBrainz client + deterministic parser (captures release MBID) |
| `claude_tools.py` | `claude -p` wrapper: SIEVE ② referee + engineer nomination |
| `ratelimit.py` | async token-bucket (≤1 req/s) |
| `__main__.py` | async orchestration, sieves, dedupe/merge, CLI |
| `backfill_node_mbids.py` | resolve node artist MBIDs from cache (run each round) |
| `.cache/raw/` | cached API responses (resumability) |
