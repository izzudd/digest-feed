#!/usr/bin/env python3
"""Build the daily digest EPUB + site index + OPDS catalog.

Usage:
    python3 tools/digest.py build issues/2026-11-25.json
    python3 tools/digest.py index          # rebuild index.html + opds.xml from public/epubs

Issue JSON shape:
{
  "date": "2026-11-25",
  "headline": "one-line theme of the day",
  "intro": "2-4 sentences: what today's batch is about and why it matters to Z.",
  "sections": [
    {"name": "AI & research",
     "blurb": "optional one-liner shown under the section head",
     "articles": [
       {"title": "...", "source": "arXiv", "url": "https://...",
        "why": "one line, why Z should care",
        "body": ["paragraph", "paragraph"]}
     ]}
  ]
}
"""
import html
import json
import os
import re
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
EPUBS = PUBLIC / "epubs"
BASE_URL = "https://feed.izzudd.my.id"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

CSS = """@charset "utf-8";
body { font-family: serif; line-height: 1.45; margin: 0 1em; }
h1 { font-size: 1.5em; line-height: 1.2; margin: 0.2em 0 0.1em; }
h2 { font-size: 1.2em; line-height: 1.25; margin: 1.4em 0 0.25em; page-break-after: avoid; }
h3 { font-size: 1.05em; margin: 1.2em 0 0.2em; }
p { margin: 0 0 0.65em; text-align: left; }
.kicker { font-family: sans-serif; font-size: 0.78em; letter-spacing: 0.06em;
          text-transform: uppercase; color: #555; margin: 0 0 0.2em; }
.why { font-style: italic; margin: 0 0 0.6em; }
.src { font-family: sans-serif; font-size: 0.75em; color: #444; margin: 0 0 1em; }
.lede { font-size: 0.95em; color: #222; }
hr { border: 0; border-top: 1px solid #bbb; margin: 1.4em 0; }
.cover { text-align: center; }
.cover p { font-family: sans-serif; }
.toc { page-break-after: always; }
ul { margin: 0 0 0.8em 1.1em; padding: 0; }
li { margin: 0 0 0.3em; }
.tiny { font-family: sans-serif; font-size: 0.72em; color: #555; }
"""


def esc(s):
    return html.escape(s, quote=False)


def esc_attr(s):
    return html.escape(s, quote=True)


def xhtml(title, body, css="../style.css"):
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:epub="http://www.idpf.org/2007/ops" lang="en" xml:lang="en">\n'
        f"<head><meta charset=\"utf-8\"/><title>{esc(title)}</title>"
        f'<link rel="stylesheet" type="text/css" href="{css}"/></head>\n'
        f"<body>\n{body}\n</body></html>\n"
    )


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:40] or "x"


def make_cover(issue, path):
    from PIL import Image, ImageDraw, ImageFont

    W, H = 480, 800
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    m = 34
    d.rectangle([m - 14, m - 14, W - m + 14, H - m + 14], outline=0, width=3)

    def font(size, bold=False):
        try:
            return ImageFont.truetype(FONT_BOLD if bold else FONT, size)
        except Exception:
            return ImageFont.load_default()

    y = 78
    d.text((m, y), "ZUD'S DAILY", font=font(20, True), fill=0)
    y += 34
    d.text((m, y), "signal, not noise", font=font(15), fill=60)
    y += 60
    d.line([m, y, W - m, y], fill=0, width=2)

    dt = datetime.strptime(issue["date"], "%Y-%m-%d")
    y += 40
    d.text((m, y), dt.strftime("%A"), font=font(22), fill=0)
    y += 38
    d.text((m, y), dt.strftime("%d %B %Y"), font=font(30, True), fill=0)

    # headline, wrapped
    y += 70
    head = issue.get("headline", "")
    words, line, lines = head.split(), "", []
    for w in words:
        trial = (line + " " + w).strip()
        if d.textlength(trial, font=font(19)) > W - 2 * m:
            lines.append(line)
            line = w
        else:
            line = trial
    if line:
        lines.append(line)
    for ln in lines[:9]:
        d.text((m, y), ln, font=font(19), fill=25)
        y += 27

    # picks: one line per section, fills the panel instead of leaving a void
    y += 34
    d.text((m, y), "INSIDE", font=font(13, True), fill=0)
    y += 24
    picks = []
    for s in issue.get("sections", []):
        arts = s.get("articles", [])
        if arts:
            picks.append((s["name"], arts[0]["title"]))
    for name, atitle in picks[:5]:
        text = f"{name}: {atitle}"
        line, lines2 = "", []
        for w in text.split():
            trial = (line + " " + w).strip()
            if d.textlength(trial, font=font(15)) > W - 2 * m - 12:
                lines2.append(line)
                line = w
            else:
                line = trial
        if line:
            lines2.append(line)
        d.text((m, y), "·", font=font(15), fill=0)
        for k, ln in enumerate(lines2[:2]):
            d.text((m + 12, y), ln, font=font(15), fill=35)
            y += 20
        y += 6

    n = sum(len(s.get("articles", [])) for s in issue.get("sections", []))
    ns = len(issue.get("sections", []))
    d.line([m, H - 118, W - m, H - 118], fill=0, width=1)
    d.text((m, H - 100),
           f"{n} item{'s' if n != 1 else ''}  ·  {ns} section{'s' if ns != 1 else ''}",
           font=font(15), fill=45)
    d.text((m, H - 72), "feed.izzudd.my.id", font=font(14), fill=90)
    img.save(path, "PNG", optimize=True)


def build_epub(issue_path):
    issue_path = Path(issue_path)
    issue = json.loads(issue_path.read_text(encoding="utf-8"))
    date = issue["date"]
    name = f"zud-daily-{date}"
    out = EPUBS / f"{name}.epub"
    EPUBS.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".epub.tmp")
    isbn = "urn:uuid:" + str(uuid.uuid5(uuid.NAMESPACE_URL, BASE_URL + "/" + name))
    title = f"Zud's Daily — {date}"
    sections = issue.get("sections", [])

    # ---- pages -------------------------------------------------------------
    pages = []  # (id, filename, title, xhtml)

    opening = ['<h1>Today at a glance</h1>']
    if issue.get("headline"):
        opening.append(f'<p class="lede"><strong>{esc(issue["headline"])}</strong></p>')
    if issue.get("intro"):
        for para in issue["intro"].split("\n\n"):
            opening.append(f"<p>{esc(para.strip())}</p>")
    opening.append("<h2>In this issue</h2><ul>")
    for s in sections:
        for a in s.get("articles", []):
            opening.append(f"<li>{esc(a['title'])} <span class=\"tiny\">— {esc(a.get('source',''))}</span></li>")
    opening.append("</ul>")
    pages.append(("opening", "00-opening.xhtml", "Today at a glance",
                  xhtml("Today at a glance", "\n".join(opening))))

    for i, s in enumerate(sections, start=1):
        sid = f"s{i}-{slug(s['name'])}"
        body = [f"<h1>{esc(s['name'])}</h1>"]
        if s.get("blurb"):
            body.append(f'<p class="why">{esc(s["blurb"])}</p>')
        for j, a in enumerate(s.get("articles", [])):
            if j:
                body.append("<hr/>")
            body.append(f'<p class="kicker">{esc(a.get("source", ""))}</p>')
            body.append(f"<h2>{esc(a['title'])}</h2>")
            if a.get("why"):
                body.append(f'<p class="why">{esc(a["why"])}</p>')
            for para in a.get("body", []):
                body.append(f"<p>{esc(para)}</p>")
            if a.get("url"):
                link = esc(a["url"])
                body.append(f'<p class="src">source: {link}</p>')
        pages.append((sid, f"{i:02d}-{slug(s['name'])}.xhtml", s["name"],
                      xhtml(s["name"], "\n".join(body))))

    footer = (
        '<h1>Colophon</h1>'
        f"<p>Compiled {esc(issue.get('compiled_at', datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')))} "
        "by Hermes for Zud. Every item links to its original source; summaries are Hermes's own, "
        "written from the linked material.</p>"
        f'<p class="src">New issue daily, 03:00 WIB · {BASE_URL} · OPDS {BASE_URL}/opds</p>'
    )
    pages.append(("colophon", f"{len(sections)+1:02d}-colophon.xhtml", "Colophon",
                  xhtml("Colophon", footer)))

    # ---- package -----------------------------------------------------------
    manifest, spine, navitems, ncxnav = [], [], [], []
    for pid, fname, ptitle, _ in pages:
        manifest.append(f'<item id="{pid}" href="{fname}" media-type="application/xhtml+xml"/>')
        spine.append(f'<itemref idref="{pid}"/>')
        navitems.append(f'<li><a href="{fname}">{esc(ptitle)}</a></li>')
        ncxnav.append(
            f'<navPoint id="np-{pid}" playOrder="{len(ncxnav)+1}">'
            f'<navLabel><text>{esc(ptitle)}</text></navLabel>'
            f'<content src="{fname}"/></navPoint>')
    manifest.append('<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>')
    manifest.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
    manifest.append('<item id="css" href="style.css" media-type="text/css"/>')
    manifest.append('<item id="cover-img" href="cover.png" media-type="image/png" properties="cover-image"/>')
    manifest.append('<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>')
    spine.insert(0, '<itemref idref="cover"/>')

    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">\n'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        f'<dc:identifier id="bookid">{isbn}</dc:identifier>\n'
        f"<dc:title>{esc(title)}</dc:title>\n"
        "<dc:creator>Hermes (compiled for Zud)</dc:creator>\n"
        "<dc:language>en</dc:language>\n"
        f'<dc:date>{date}</dc:date>\n'
        "<dc:publisher>feed.izzudd.my.id</dc:publisher>\n"
        f'<meta property="dcterms:modified">{datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</meta>\n'
        "</metadata>\n"
        f"<manifest>\n{chr(10).join(manifest)}\n</manifest>\n"
        f'<spine toc="ncx">\n{chr(10).join(spine)}\n</spine>\n'
        "</package>\n"
    )

    nav = xhtml("Contents",
                '<nav epub:type="toc" id="toc"><h1>Contents</h1><ol>'
                + "".join(navitems) + "</ol></nav>")

    ncx = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">\n'
        '<head><meta name="dtb:uid" content="' + isbn + '"/></head>\n'
        f"<docTitle><text>{esc(title)}</text></docTitle>\n"
        f"<navMap>\n{chr(10).join(ncxnav)}\n</navMap>\n</ncx>\n"
    )

    cover_xhtml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" lang="en" xml:lang="en">\n'
        '<head><meta charset="utf-8"/><title>Cover</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        '<body class="cover"><div>'
        '<img src="cover.png" alt="cover" style="max-width:100%"/>'
        "</div></body></html>\n"
    )

    with zipfile.ZipFile(tmp, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0" encoding="utf-8"?>\n'
                   '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                   '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                   'media-type="application/oebps-package+xml"/></rootfiles></container>\n',
                   compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/style.css", CSS, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("OEBPS/cover.xhtml", cover_xhtml, compress_type=zipfile.ZIP_DEFLATED)
        for _, fname, _, content in pages:
            z.writestr(f"OEBPS/{fname}", content, compress_type=zipfile.ZIP_DEFLATED)

    # cover needs the image written into the zip too (PIL writes to a temp png)
    cover_tmp = EPUBS / f".cover-{date}.png"
    make_cover(issue, cover_tmp)
    with zipfile.ZipFile(tmp, "a") as z:
        z.write(cover_tmp, "OEBPS/cover.png", compress_type=zipfile.ZIP_DEFLATED)
    cover_tmp.unlink(missing_ok=True)

    tmp.replace(out)
    print(f"built {out} ({out.stat().st_size/1024:.0f} KB, "
          f"{sum(len(s.get('articles',[])) for s in sections)} items)")
    build_index()
    return out


def issue_meta(path):
    """Read date + headline + counts from an epub filename + issues/*.json if present."""
    date = re.search(r"(\d{4}-\d{2}-\d{2})", path.name)
    date = date.group(1) if date else path.stem
    meta = {"date": date, "headline": "", "items": None}
    src = ROOT / "issues" / f"{date}.json"
    if src.exists():
        try:
            d = json.loads(src.read_text(encoding="utf-8"))
            meta["headline"] = d.get("headline", "")
            meta["items"] = sum(len(s.get("articles", [])) for s in d.get("sections", []))
        except Exception:
            pass
    return meta


def build_index():
    files = sorted(EPUBS.glob("*.epub"), reverse=True)
    rows = []
    for f in files:
        m = issue_meta(f)
        kb = f.stat().st_size / 1024
        head = f' <span class="h">{esc(m["headline"])}</span>' if m["headline"] else ""
        rows.append(
            f'<li><a href="epubs/{f.name}">{m["date"]}</a>{head}'
            f'<span class="m">{kb:.0f} KB</span></li>')

    index = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Zud's Daily — compiled by Hermes</title>
<style>
:root {{ color-scheme: light dark }}
body {{ font: 16px/1.5 -apple-system,system-ui,sans-serif; max-width: 40rem;
        margin: 3rem auto; padding: 0 1.2rem; }}
h1 {{ font-size: 1.5rem; margin: 0 0 .2rem }}
.sub {{ color: #666; margin: 0 0 2rem }}
ul {{ list-style: none; padding: 0 }}
li {{ border-bottom: 1px solid #ddd8; padding: .6rem 0 }}
a {{ font-weight: 600 }}
.m {{ float: right; color: #777; font-size: .85rem }}
.h {{ color: #555; font-size: .9rem }}
code {{ background: #8881; padding: .1rem .3rem; border-radius: 3px }}
</style></head>
<body>
<h1>Zud's Daily</h1>
<p class="sub">One EPUB a day, compiled by Hermes: research, engineering and
software strategy. Built for the Xteink X4 Pro. New issue 03:00 WIB.</p>
<ul>
{chr(10).join(rows) if rows else '<li>no issues yet</li>'}
</ul>
<h2>On the reader</h2>
<p>OPDS catalog: <code>{BASE_URL}/opds</code><br/>
Latest file: <code>{BASE_URL}/latest.epub</code></p>
</body></html>
"""
    (PUBLIC / "index.html").write_text(index, encoding="utf-8")

    entries = []
    for f in files[:20]:
        m = issue_meta(f)
        entries.append(
            "<entry>"
            f"<title>Zud's Daily — {m['date']}</title>"
            f"<id>{BASE_URL}/epubs/{f.name}</id>"
            f"<updated>{m['date']}T00:00:00Z</updated>"
            '<content type="text">Daily digest compiled by Hermes.</content>'
            f'<link rel="http://opds-spec.org/acquisition/open-access" '
            f'href="{BASE_URL}/epubs/{f.name}" type="application/epub+zip"/>'
            "</entry>")
    opds = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<id>" + BASE_URL + "/opds</id>"
        "<title>Zud's Daily</title>"
        f"<updated>{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}</updated>"
        '<author><name>Hermes</name></author>'
        f'<link rel="self" href="{BASE_URL}/opds" type="application/atom+xml"/>'
        '<link rel="start" href="' + BASE_URL + '/opds" type="application/atom+xml"/>'
        + "".join(entries) + "</feed>\n"
    )
    (PUBLIC / "opds.xml").write_text(opds, encoding="utf-8")
    (PUBLIC / "opds").write_text(opds, encoding="utf-8")

    # latest.epub must be a real copy, not a symlink (static server)
    if files:
        latest = PUBLIC / "latest.epub"
        data = files[0].read_bytes()
        if not latest.exists() or latest.read_bytes() != data:
            latest.write_bytes(data)
    print(f"index.html + opds.xml refreshed ({len(files)} issues)")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "index"
    if cmd == "build":
        build_epub(sys.argv[2])
    elif cmd == "index":
        build_index()
    else:
        raise SystemExit(__doc__)
