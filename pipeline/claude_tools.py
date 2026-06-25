"""Thin async wrapper over the local `claude` binary (headless `-p` mode).

Used for the JUDGMENT work that runs concurrently during MB rate-limit waits:
seed expansion, disambiguation, Discogs free-text role normalization.
NOT used to parse MusicBrainz (that's already structured — see mb.py).
"""
import asyncio
import json
import re
import shutil

CLAUDE = shutil.which("claude") or "claude"


async def ask(prompt: str, timeout: float = 180, model: str = "sonnet") -> str:
    """Run `claude -p --model <model> <prompt>` and return its stdout text."""
    proc = await asyncio.create_subprocess_exec(
        CLAUDE, "-p", "--model", model, prompt,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    if proc.returncode != 0:
        raise RuntimeError(f"claude exited {proc.returncode}: {err.decode()[:300]}")
    return out.decode().strip()


def extract_json_array(text: str):
    """Pull the first JSON array out of an LLM reply (tolerates prose/fences)."""
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


REFEREE_PROMPT = """You vet candidate musical artists discovered by crawling the \
production credits of indie / alternative recording engineers (Albini, McEntire, \
Ek, Vernhes, etc.). The project is NETWORK-FIRST: keep almost everything a real \
engineer recorded, across ANY genre and ANY era. Your only job is removing noise.

For each candidate, set keep=true UNLESS it is clearly one of:
  - not a real musical artist: "Various Artists", a label sampler/compilation, a DJ \
mix, a soundtrack-various, spoken-word/audiobook, or mis-parsed/garbled text;
  - a total unknown with NO discernible notability: no real label, no press, no \
Wikipedia/Discogs footprint — indistinguishable from noise.

NOT reasons to drop: wrong genre, wrong era, being obscure-but-real, being famous \
(e.g. a rock legend an indie engineer happened to record stays IN). When unsure, \
keep=true — we trim later.

Return ONLY a JSON array, one object per candidate: {"name": <exact name>, \
"keep": true|false, "reason": <short>}."""


async def referee(candidates: list[dict], timeout: float = 240, model: str = "sonnet") -> dict:
    """candidates: [{name, via:[(engineer, album, year), ...]}] -> {name: verdict}."""
    lines = []
    for c in candidates:
        ex = "; ".join(f"{e} – {al} ({y})" for e, al, y in c["via"][:3])
        lines.append(f'- {c["name"]}  [recorded by: {ex}]')
    prompt = REFEREE_PROMPT + "\n\nCANDIDATES:\n" + "\n".join(lines)
    arr = extract_json_array(await ask(prompt, timeout, model))
    return {o["name"]: o for o in arr if isinstance(o, dict) and o.get("name")}


async def suggest_artists(done_names: list[str], era="1995-2003",
                          scene="US/UK indie, alternative, post-rock, lo-fi, slowcore, math-rock",
                          n=12, model="sonnet") -> list[str]:
    """Given artists we already have, ask Claude for adjacent in-scope ones."""
    sample = ", ".join(done_names[:80])
    prompt = (
        f"You curate a database of {era} {scene} recording credits. "
        f"We ALREADY have these artists: {sample}. "
        f"Name {n} more well-documented artists/bands from the SAME scene and era "
        f"that are NOT in that list and whose producers/engineers would be worth indexing. "
        f"Reply with ONLY a JSON array of name strings, nothing else."
    )
    return extract_json_array(await ask(prompt, model=model))


async def suggest_engineers(existing: list[str], n=25, era="1995-2003",
                            scene="US/UK indie, alternative, post-rock, lo-fi, slowcore, "
                                  "math-rock, post-hardcore, shoegaze",
                            model="sonnet") -> list[str]:
    """Nominate more real recording engineers/producers in scope (the graph's hubs)."""
    sample = ", ".join(existing[:90])
    prompt = (
        f"You curate a database of {era} {scene} recording credits. "
        f"We ALREADY index these recording engineers/producers: {sample}. "
        f"Name {n} MORE real, well-documented recording engineers or producers who worked with "
        f"bands in that scene and era and are NOT already in the list. Favor people who recorded "
        f"several notable indie/alternative acts (they connect the graph). Use the name MusicBrainz "
        f"would list them under. Reply with ONLY a JSON array of name strings, nothing else."
    )
    return extract_json_array(await ask(prompt, model=model))
