"""2" ingestion pipeline — resumable MusicBrainz crawl that updates data.json in place.

  python -m pipeline --limit 3 --suggest            # safe dry-run -> data.preview.json
  python -m pipeline --write                         # update data.json in place
  python -m pipeline --seed "Steve Albini" "Phil Ek" # explicit seeds

Design: a rate-limited MB fetcher (≤1 req/s) runs concurrently with Claude
judgment tasks, so the API wait time is spent on inference. Raw responses are
cached on disk, so any run resumes instantly and never re-hits the API.
"""
import argparse
import asyncio
import json
import os
import re
import time

from . import mb
from . import claude_tools
from .ratelimit import RateLimiter

HERE = os.path.dirname(__file__)
DEFAULT_DATA = os.path.normpath(os.path.join(HERE, "..", "indie-index", "data.json"))
CACHE_DIR = os.path.join(HERE, ".cache", "raw")
T0 = time.monotonic()


def log(msg):
    print(f"[{time.monotonic()-T0:6.1f}s] {msg}", flush=True)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", "", (t or "").lower())


def cache_get(name):
    p = os.path.join(CACHE_DIR, slug(name) + ".json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return None


def cache_put(name, raw):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, slug(name) + ".json"), "w") as f:
        json.dump(raw, f)


async def fetch_person(name, limiter, args):
    loop = asyncio.get_running_loop()
    try:
        raw = cache_get(name)
        if raw is None:
            await limiter.acquire()
            art = await loop.run_in_executor(None, mb.search_artist, name)
            if not art:
                log(f"  no MB match: {name}")
                return []
            await limiter.acquire()
            log(f"  MB fetch: {name}  ({art['id']})")
            raw = await loop.run_in_executor(None, mb.artist_credits_raw, art["id"])
            cache_put(name, raw)
        else:
            log(f"  cache hit: {name}")
        return mb.parse_credits(name, raw, args.year_min, args.year_max)
    except Exception as e:                       # one bad lookup must not kill the crawl
        log(f"  ERROR {name}: {type(e).__name__}: {e}")
        return []


async def run_referee(new_bands, via, model="sonnet", batch=25, concurrency=4):
    batches = [new_bands[i:i + batch] for i in range(0, len(new_bands), batch)]
    sem = asyncio.Semaphore(concurrency)

    async def judge(group):
        cands = [{"name": b, "via": via.get(b, [])} for b in group]
        async with sem:
            try:
                return await claude_tools.referee(cands, model=model)
            except Exception as e:
                log(f"  referee batch error ({len(group)} names): {e}")
                return {}

    out = {}
    for m in await asyncio.gather(*[judge(g) for g in batches]):
        out.update(m)
    return out


async def run(args):
    with open(args.data) as f:
        data = json.load(f)
    ids = {n["id"] for n in data["nodes"]}
    edge_keys = {f"{l['source']}|{l['target']}|{norm_title(l.get('album'))}"
                 for l in data["links"] if l.get("album")}
    engineers = [n["id"] for n in data["nodes"] if n["type"] == "engineer"]
    artists = [n["id"] for n in data["nodes"] if n["type"] == "artist"]

    seed = args.seed or engineers
    if args.grow:
        log(f"  grow: asking Claude for {args.grow} more in-scope engineers/producers…")
        nom = await claude_tools.suggest_engineers(engineers, args.grow, model=args.model)
        fresh = [e for e in nom if e not in ids and e not in seed]
        log(f"  grow: {len(fresh)} new engineers to crawl: {fresh}")
        seed = seed + fresh
    if args.limit:
        seed = seed[:args.limit]
    log(f"loaded {len(data['nodes'])} nodes / {len(data['links'])} links; "
        f"seed = {len(seed)} engineers; year window {args.year_min}-{args.year_max}")

    limiter = RateLimiter(args.rate)

    # Claude seed-suggestion runs CONCURRENTLY with the MB crawl (during waits)
    suggest_task = None
    if args.suggest:
        log("  claude: requesting adjacent in-scope artists (runs during MB waits)…")
        suggest_task = asyncio.create_task(_suggest(artists, args.model))

    fetched = await asyncio.gather(*[fetch_person(n, limiter, args) for n in seed])
    suggestions = await suggest_task if suggest_task else []

    # ---- merge (dedupe, earliest year wins) -------------------------------
    new_edges, seen = [], {}
    for credit in (c for group in fetched for c in group):
        k = f"{credit['source']}|{credit['target']}|{norm_title(credit['album'])}"
        if k in edge_keys:
            continue
        if k not in seen or credit["year"] < seen[k]["year"]:
            seen[k] = credit
    new_edges = list(seen.values())

    # candidate new bands + their connection context for the referee
    new_band_set = {e["target"] for e in new_edges if e["target"] not in ids}
    new_bands = sorted(new_band_set)
    via = {}
    for e in new_edges:
        if e["target"] in new_band_set:
            via.setdefault(e["target"], []).append((e["source"], e["album"], e["year"]))

    dropped = {}
    if new_bands and not args.no_referee:
        log(f"  referee: vetting {len(new_bands)} new artists (network-first, notability-only)…")
        dropped = {n: v for n, v in (await run_referee(new_bands, via, args.model)).items()
                   if v.get("keep") is False}
        shown = ", ".join(sorted(dropped)[:14])
        log(f"  referee dropped {len(dropped)}/{len(new_bands)}: {shown}{'…' if len(dropped) > 14 else ''}")

    # provenance src=mb → curated data (no src) stays protected; trim later by tag
    final_edges = [dict(e, src="mb") for e in new_edges if e["target"] not in dropped]
    kept_bands = [b for b in new_bands if b not in dropped]
    # newly-seeded engineers that actually produced credits need their own node (else edges dangle)
    new_eng = sorted({e["source"] for e in final_edges if e["source"] not in ids})
    added_nodes = ([{"id": s, "type": "engineer", "bio": "", "src": "mb"} for s in new_eng]
                   + [{"id": b, "type": "artist", "bio": "", "src": "mb"} for b in kept_bands])

    log(f"RESULT: +{len(final_edges)} credits, +{len(new_eng)} new engineers, +{len(kept_bands)} new artists "
        f"(from {sum(len(g) for g in fetched)} raw credits; referee dropped {len(dropped)})")
    if suggestions:
        missing = [s for s in suggestions if s not in ids]
        log(f"  claude suggested {len(suggestions)} artists; {len(missing)} not yet indexed: {missing}")
    for e in final_edges[:12]:
        log(f"    + {e['source']} — {e['target']} · {e['album']} ({e['year']}) · {e['role']}")

    data["nodes"].extend(added_nodes)
    data["links"].extend(final_edges)
    out = args.data if args.write else os.path.join(os.path.dirname(args.data), "data.preview.json")
    ser = lambda a: "[\n" + ",\n".join(json.dumps(o, ensure_ascii=False) for o in a) + "\n]"
    with open(out, "w") as f:
        f.write(f'{{\n"nodes":{ser(data["nodes"])},\n"links":{ser(data["links"])}\n}}\n')
    log(f"wrote {out}  ({'IN PLACE' if args.write else 'preview — review then re-run with --write'})")


async def _suggest(artists, model="sonnet"):
    try:
        return await claude_tools.suggest_artists(artists, model=model)
    except Exception as e:
        log(f"  claude suggest skipped: {e}")
        return []


def main():
    ap = argparse.ArgumentParser(prog="pipeline")
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--seed", nargs="*", help="explicit seed names (default: all engineers in data.json)")
    ap.add_argument("--limit", type=int, help="cap number of seeds (for testing)")
    ap.add_argument("--grow", type=int, default=0, help="ask Claude for N more in-scope engineers and crawl them")
    ap.add_argument("--year-min", type=int, default=1980, help="era-agnostic by default; sanity floor")
    ap.add_argument("--year-max", type=int, default=2025)
    ap.add_argument("--rate", type=float, default=1.0, help="MB requests/sec")
    ap.add_argument("--model", default="sonnet", help="claude model for referee/suggest (default: sonnet)")
    ap.add_argument("--no-referee", action="store_true", help="skip the Claude notability/scope vetting")
    ap.add_argument("--suggest", action="store_true", help="ask Claude for adjacent artists (concurrent)")
    ap.add_argument("--write", action="store_true", help="update data.json in place (default: preview)")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
