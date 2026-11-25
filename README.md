# Zud's Daily

One EPUB a day, compiled by Hermes for the Xteink X4 Pro (CrossPoint firmware).
Replaces the RSSPub instance that used to serve `feed.izzudd.my.id`.

Live: <https://feed.izzudd.my.id> · OPDS: <https://feed.izzudd.my.id/opds>

## How it works

```
Hermes cron (03:00 WIB)
  └─ researches the day's material (web_search / web_extract)
  └─ writes issues/<YYYY-MM-DD>.json
  └─ tools/digest.py build issues/<date>.json
        → public/epubs/zud-daily-<date>.epub
        → rebuilds public/index.html, public/opds.xml, public/opds, public/latest.epub
  └─ git commit + push  →  Coolify redeploys the nginx app
```

Built with `build_pack: dockerfile` (nginx:alpine + `public/` copied in), so the
site is plain static files behind Traefik. No app logic on the server.

## Layout

- `public/` — web root: `index.html`, `opds.xml` + `opds`, `latest.epub`, `epubs/*.epub`
- `issues/` — the source JSON for each issue (what Hermes writes)
- `tools/digest.py` — EPUB 3 builder + index/OPDS regeneration
- `Dockerfile`, `nginx.conf` — the container

## Issue JSON

```json
{
  "date": "2026-11-25",
  "headline": "one-line theme of the day",
  "intro": "2-4 sentences on what today's batch is about.",
  "sections": [
    {"name": "AI & research", "blurb": "optional one-liner",
     "articles": [
       {"title": "...", "source": "arXiv", "url": "https://...",
        "why": "one line on why it matters", "body": ["para", "para"]}
     ]}
  ]
}
```

Style rules the builder assumes: `body` paragraphs are plain text (escaping is
automatic, links only via `url`), 3–6 items per section, keep each item to 2–4
short paragraphs so it stays skimmable on a 4.3" panel.

## Ops

- Rebuild the index/OPDS only: `python3 tools/digest.py index`
- Rebuild one issue: `python3 tools/digest.py build issues/2026-11-25.json`
- Old RSSPub digests (Nov 18–24) are kept as `public/epubs/rss-digest-*.epub`
  and still appear in the OPDS list.
