# Music Production Credits API Research

## Executive Summary

For querying recording engineers/producers and their album credits, **Discogs** is the better API for the straightforward use case of "give me all albums by engineer X with years and artists." However, **MusicBrainz** has superior data granularity (recording-level vs release-level, detailed relationship types with attributes like "co-", "assistant", "executive"). The best approach may be a **hybrid strategy** or using MusicBrainz with specific relationship includes.

---

## 1. MusicBrainz API

### Overview
- **Base URL:** `https://musicbrainz.org/ws/2/`
- **Formats:** XML (default) or JSON (`?fmt=json`)
- **Rate Limit:** ~1 req/sec for unauthenticated users; strict User-Agent required
- **No API key** needed for read access
- **Docs:** https://musicbrainz.org/doc/MusicBrainz_API

### Relationship Types (Production/Engineering)

#### Artist -> Recording relationships
| Relationship | UUID | Description |
|-------------|------|-------------|
| `producer` | `5c0ceac3-feb4-41f0-868d-dc06f6e27fc0` | General producer |
| `engineer` | `5dcc52af-7064-4051-8d62-7d80f4c3c907` | General engineer |
| `audio` (engineer) | `ca8d6d99-b847-439c-b0ec-33d8a1b942bc` | Audio/sound equipment engineer |
| `mastering` | `30adb2d7-dbcc-4393-9230-2098510ce3c1` | **Deprecated** |
| `sound` | `0cd6aa63-c297-42ed-8725-c16d31913a98` | Acoustical/sound engineer |
| `mix` | `3e3102e1-1896-4f50-b5b2-dd9824e46efe` | Mix engineer |
| `recording` | `a01ee869-80a8-45ef-9447-c59e91aa7926` | Recording engineer |
| `programming` | `36c50022-44e0-488d-994b-33f11d20301e` | Synth/drum machine programming |
| `editor` | `40dff87a-e475-4aa6-b615-9935b564d756` | Audio editor |
| `balance` | `0748fa55-56b5-4ad5-8ce8-15b97f82a0c2` | Balance engineer |

#### Artist -> Release relationships
| Relationship | UUID | Description |
|-------------|------|-------------|
| `producer` | `8bf377ba-8d71-4ecc-97f2-7bb2d8a2a75f` | Producer at release level |
| `engineer` | `87e9224f-c6c5-42a5-86b9-70f92349a0cf` | Engineer at release level |
| `mastering` | `84453d28-c3e8-4864-9aae-25aa968bcf9e` | Mastering engineer |
| `sound` | `271306ca-c77f-4fe0-94bc-dd4b87ae0205` | Sound engineer |
| `mix` | `6cc958c0-533b-4540-a281-058fbb941890` | Mix engineer |
| `recording` | `023a6c6d-80af-4f88-ae69-f5f6213f9bf4` | Recording engineer |

### Attributes on Relationships
Relationships can have attributes:
- `additional` - "additional producer"
- `assistant` - "assistant engineer"
- `associate` - "associate producer"
- `co` - "co-producer"
- `executive` - "executive producer"
- `instrument` - specific instrument for programming

Attributes appear in JSON response as:
```json
{
  "attributes": ["executive"],
  "attribute-ids": {"executive": "e0039285-6667-4f94-80d6-aa6520c6d359"},
  "attribute-values": {},
  "attribute-credits": {}
}
```

### How to Query for an Engineer/Producer's Discography

#### Step 1: Search for the person
```
GET https://musicbrainz.org/ws/2/artist?query=artist:"Rick+Rubin"&fmt=json
```
Returns `id` (MBID).

#### Step 2: Get release-level credits
```
GET https://musicbrainz.org/ws/2/artist/{mbid}?inc=release-rels&fmt=json
```
Returns all Artist->Release relationships. Each relation has:
```json
{
  "type": "producer",
  "target-type": "release",
  "direction": "forward",
  "attributes": ["executive"],
  "release": {
    "id": "...",
    "title": "Yeezus",
    "date": "2013-06-18",
    "country": "US",
    "release-events": [{"date": "2013-06-18", "area": {"name": "United States"}}],
    "text-representation": {"language": "eng", "script": "Latn"}
  }
}
```

#### Step 3: Get recording-level credits (more granular)
```
GET https://musicbrainz.org/ws/2/artist/{mbid}?inc=recording-rels&fmt=json
```
Returns Artist->Recording relationships. Must look up each recording to find its releases.

#### Include relationship combinations
```
GET /ws/2/artist/{mbid}?inc=artist-rels+release-rels+recording-rels+work-rels&fmt=json
```

### Limitations
1. **Rate limiting:** ~1 req/sec. Exceeding gets 503 errors.
2. **No direct "get all albums by producer" endpoint.** Must use relationship includes.
3. **Large payloads:** Prolific people return massive JSON (Rick Rubin = ~680KB).
4. **Multiple release versions:** Single album may have many releases. Group by release-group for unique albums.
5. **Complex traversal:** Recording-level credits require additional lookups.

---

## 2. Discogs API

### Overview
- **Base URL:** `https://api.discogs.com/`
- **Authentication:** OAuth or personal access token (optional but recommended)
- **Rate Limit:** 25 requests/minute unauthenticated, 60/min with token
- **Docs:** https://www.discogs.com/developers (behind Cloudflare protection)

### Endpoints for Production Credits

#### Search for artist
```
GET https://api.discogs.com/database/search?q=Rick+Rubin&type=artist
```
Returns artist `id`.

#### Get artist releases (the key endpoint)
```
GET https://api.discogs.com/artists/{id}/releases?sort=year&sort_order=desc
```
Returns:
```json
{
  "pagination": {"page": 1, "pages": 34, "per_page": 50, "items": 1697},
  "releases": [
    {
      "id": 3919078,
      "title": "Snipe Hunter",
      "type": "master",
      "artist": "Tyler Childers",
      "role": "Producer",
      "year": 2025,
      "resource_url": "https://api.discogs.com/masters/3919078"
    }
  ]
}
```

**Key fields:**
- `type`: `"master"` = canonical album; `"release"` = specific pressing
- `role`: `"Producer"`, `"Engineer"`, `"Remix"`, `"Main"`
- `artist`: Primary performing artist
- `year`: Release year

### Limitations
1. **Role granularity is coarse.** Simple strings without attributes.
2. **No recording/track-level credits** in this endpoint. Must fetch each release individually for track credits.
3. **Rate limits:** 25/min unauthenticated, 60/min with token.
4. **Data quality varies:** Community-contributed.

---

## 3. Comparative Analysis

| Aspect | MusicBrainz | Discogs |
|--------|-------------|---------|
| Production credit depth | 5/5 (recording-level + attributes) | 3/5 (release-level, coarse) |
| Query ease for discographies | 2/5 (complex) | 5/5 (single endpoint) |
| Year/artist in response | 4/5 | 5/5 |
| Rate limits | ~1/sec | 25-60/min |
| Coverage | ~3.5M releases | ~17M releases |

### Recommendation by Use Case

| Use Case | Recommended API |
|----------|----------------|
| "Get all albums by producer with year & artist" | **Discogs** |
| "Get track-level detailed credits" | **MusicBrainz** |
| "Get co-producer / assistant engineer credits" | **MusicBrainz** |
| "Build comprehensive production database" | **Both / hybrid** |

---

## 4. Example Implementation Paths

### Discogs (Simplest)
```python
import requests, time

def get_discogs_discography(artist_name):
    headers = {"User-Agent": "MyApp/1.0"}
    search = requests.get(
        "https://api.discogs.com/database/search",
        params={"q": artist_name, "type": "artist"},
        headers=headers
    ).json()
    artist_id = search["results"][0]["id"]
    
    releases = []
    url = f"https://api.discogs.com/artists/{artist_id}/releases?sort=year&sort_order=desc"
    while url:
        resp = requests.get(url, headers=headers).json()
        for r in resp.get("releases", []):
            if r.get("role") in ("Producer", "Engineer"):
                releases.append({
                    "title": r["title"],
                    "artist": r.get("artist"),
                    "year": r.get("year"),
                    "role": r["role"],
                    "type": r.get("type")
                })
        url = resp["pagination"].get("urls", {}).get("next")
        time.sleep(1.5)
    return releases
```

### MusicBrainz (Detailed)
```python
import requests, time

def get_mb_release_credits(artist_name):
    headers = {"User-Agent": "MyApp/1.0"}
    search = requests.get(
        "https://musicbrainz.org/ws/2/artist",
        params={"query": f'artist:"{artist_name}"', "fmt": "json"},
        headers=headers
    ).json()
    mbid = search["artists"][0]["id"]
    
    artist = requests.get(
        f"https://musicbrainz.org/ws/2/artist/{mbid}?inc=release-rels&fmt=json",
        headers=headers
    ).json()
    
    releases = []
    for rel in artist.get("relations", []):
        if rel.get("target-type") != "release":
            continue
        release = rel["release"]
        releases.append({
            "title": release["title"],
            "date": release.get("date"),
            "role": rel["type"],
            "attributes": rel.get("attributes", []),
        })
    return releases
```

---

## 5. Other APIs

### Spotify / Apple Music
- **Do NOT contain production/engineering credits.** Only performer-level data.

### AllMusic / Rovi
- Commercial, paid license required.

### TheAudioDB
- Free but much smaller coverage.

---

*Research compiled June 25, 2026*
