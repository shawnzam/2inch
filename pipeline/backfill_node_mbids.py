#!/usr/bin/env python3
"""Backfill node-level MusicBrainz artist IDs from the crawl cache (offline, deterministic).

Run AFTER merging a grow round, so new engineer/artist nodes deep-link to
/artist/<mbid> in the sidebar. Crawl EDGES already carry their release id
automatically (see mb.py); this fills the NODES.

- Studios are skipped (they're MB 'places', not artists -> they keep a search link).
- Existing mbids are never clobbered.
- A handful of collab-named artists won't resolve from cache; they fall back to
  a MusicBrainz search link, which is fine.
"""
import json, os, re

HERE = os.path.dirname(__file__)
CACHE = os.path.join(HERE, ".cache", "raw")
DATA = os.path.normpath(os.path.join(HERE, "..", "indie-index", "data.json"))


def norm(s):
    s = s.lower()
    if s.startswith("the "):
        s = s[4:]
    return re.sub(r"[^a-z0-9]", "", s)


exact, nm = {}, {}
for fn in os.listdir(CACHE):
    if not fn.endswith(".json"):
        continue
    raw = json.load(open(os.path.join(CACHE, fn)))
    if raw.get("id") and raw.get("name"):                     # the crawled person's own id
        exact.setdefault(raw["name"].lower(), raw["id"]); nm.setdefault(norm(raw["name"]), raw["id"])
    for rel in raw.get("relations", []):
        for c in ((rel.get("release") or {}).get("artist-credit") or []):   # band ids
            a = c.get("artist") or {}
            if a.get("id") and a.get("name"):
                exact.setdefault(a["name"].lower(), a["id"]); nm.setdefault(norm(a["name"]), a["id"])

d = json.load(open(DATA))
new = 0
for n in d["nodes"]:
    if n["type"] == "studio" or n.get("mbid"):
        continue
    mbid = exact.get(n["id"].lower()) or nm.get(norm(n["id"]))
    if mbid:
        n["mbid"] = mbid; new += 1

ser = lambda a: "[\n" + ",\n".join(json.dumps(o, ensure_ascii=False) for o in a) + "\n]"
open(DATA, "w").write("{\n\"nodes\":" + ser(d["nodes"]) + ",\n\"links\":" + ser(d["links"]) + "\n}\n")
art = [n for n in d["nodes"] if n["type"] != "studio"]
print(f"backfilled {new} node MBIDs; {sum(1 for n in art if n.get('mbid'))}/{len(art)} non-studio nodes deep-link")
