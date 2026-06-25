"""MusicBrainz client (stdlib only) + deterministic credit parser.

One call per person: /artist/{mbid}?inc=release-rels+artist-credits gives
role + release title + date + performing band, no follow-up lookups needed.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "2inch/0.1 ( shawnzam@gmail.com )"          # MB requires a descriptive UA
BASE = "https://musicbrainz.org/ws/2"

# MB relationship types we treat as production/engineering credits
CREDIT_ROLES = {"producer", "engineer", "mix", "mastering", "recording",
                "audio", "sound", "balance", "programming"}
ROLE_MAP = {"audio": "engineer", "sound": "engineer"}   # normalize to our vocab
SKIP_BANDS = {"various artists", "[various artists]", "[unknown]"}


def _get(url: str, retries: int = 4) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for i in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (503, 429) and i < retries - 1:
                time.sleep(2 * (i + 1))   # MB throttle / busy — back off and retry
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if i < retries - 1:
                time.sleep(2 * (i + 1))
                continue
            raise


def search_artist(name: str) -> dict | None:
    q = urllib.parse.quote(f'artist:"{name}"')
    d = _get(f"{BASE}/artist?query={q}&fmt=json&limit=5")
    arts = d.get("artists", [])
    # prefer an exact (case-insensitive) name match, else top hit
    for a in arts:
        if a.get("name", "").lower() == name.lower():
            return a
    return arts[0] if arts else None


def artist_credits_raw(mbid: str) -> dict:
    return _get(f"{BASE}/artist/{mbid}?inc=release-rels+artist-credits&fmt=json")


def _band_name(release: dict) -> str | None:
    ac = release.get("artist-credit")
    if not ac:
        return None
    return "".join((c.get("name", "") + c.get("joinphrase", "")) for c in ac).strip()


def parse_credits(person: str, raw: dict, year_min: int, year_max: int) -> list[dict]:
    """raw MB artist payload -> list of {source, target, album, year, role}."""
    out = []
    for rel in raw.get("relations", []):
        if rel.get("target-type") != "release":
            continue
        t = rel.get("type")
        if t not in CREDIT_ROLES:
            continue
        rl = rel.get("release") or {}
        year = (rl.get("date") or "")[:4]
        if not year.isdigit():
            continue
        y = int(year)
        if y < year_min or y > year_max:
            continue
        band = _band_name(rl)
        if not band or band.lower() in SKIP_BANDS or band == person:
            continue
        attrs = rel.get("attributes") or []
        role = ROLE_MAP.get(t, t)
        if attrs:
            role = " ".join(attrs) + " " + role
        out.append({"source": person, "target": band,
                    "album": rl.get("title"), "year": y, "role": role,
                    "mbid": rl.get("id")})
    return out
