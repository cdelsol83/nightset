"""Render data/pages/*.json into a static site in site/ (index, guides, venues.json, sitemap, robots)."""
import datetime as dt
import html
import json
import re
import shutil
import urllib.parse
from pathlib import Path

import config
import quality
import store

OUT = Path(__file__).resolve().parent / "site"

CSS = """
:root{--bg:#fbf9f6;--fg:#1c1a22;--muted:#6a6672;--line:#e6e1da;--accent:#7a3fb0;--tag:#f0e9f7}
@media (prefers-color-scheme:dark){:root{--bg:#141219;--fg:#ece9f1;--muted:#a49fae;--line:#2c2833;--accent:#c39bf0;--tag:#2a2236}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:17px/1.6 system-ui,-apple-system,Segoe UI,sans-serif}
main,header,footer{max-width:860px;margin:auto;padding:0 16px}
header{padding-top:24px}header a{color:inherit;text-decoration:none;font-weight:700;letter-spacing:.02em}
a{color:var(--accent)}h1{line-height:1.2;font-size:2rem}
.meta,footer{color:var(--muted);font-size:.9rem}
.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.92rem}
th,td{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}
td.contact{white-space:nowrap}.tag{display:inline-block;background:var(--tag);border-radius:10px;
padding:0 8px;margin:2px 2px 0 0;font-size:.8rem;white-space:nowrap}.featured{font-size:.75rem;color:var(--muted)}
ul.pages{padding-left:0;list-style:none}ul.pages li{padding:10px 0;border-bottom:1px solid var(--line)}
footer{padding:32px 16px}.footnav{margin-top:8px}
"""

# Directories are not a venue's own site; never send visitors there.
AGGREGATORS = ("yelp.", "tripadvisor.", "opentable.", "facebook.", "instagram.", "google.",
               "mapquest.", "yellowpages.") + config.NOT_VENUE_SOURCES


def md_inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<em>\1</em>", text)
    return re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', text)


def markdown(md):
    """Minimal Markdown: headings, paragraphs, bullet/numbered lists, bold, italic, links."""
    out, para, lst = [], [], None

    def flush():
        nonlocal lst
        if para:
            out.append("<p>" + md_inline(" ".join(para)) + "</p>")
            para.clear()
        if lst:
            out.append(f"</{lst}>")
            lst = None

    for line in md.splitlines():
        s = line.strip()
        m = re.match(r"(#{1,4})\s+(.*)", s)
        item = re.match(r"(?:[-*]|\d+\.)\s+(.*)", s)
        if not s:
            flush()
        elif m:
            flush()
            level = min(len(m.group(1)) + 1, 4)  # the page title is the only <h1>
            out.append(f"<h{level}>{md_inline(m.group(2))}</h{level}>")
        elif item:
            if para:
                out.append("<p>" + md_inline(" ".join(para)) + "</p>")
                para.clear()
            kind = "ol" if s[0].isdigit() else "ul"
            if lst != kind:
                if lst:
                    out.append(f"</{lst}>")
                out.append(f"<{kind}>")
                lst = kind
            out.append(f"<li>{md_inline(item.group(1))}</li>")
        else:
            if lst:
                out.append(f"</{lst}>")
                lst = None
            para.append(s)
    flush()
    return "\n".join(out)


def biz_id(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def clean_phone(raw):
    """(display, tel) for a US number, else None."""
    digits = re.sub(r"\D", "", str(raw or ""))
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}", f"tel:+1{digits}"


def clean_website(url):
    url = str(url or "").strip()
    if not re.match(r"https?://[^\s/]+\.[^\s/]+", url) or any(a in url.lower() for a in AGGREGATORS):
        return None
    return url


def phone_of(r):
    return clean_phone(r.get("phone") or r.get("facts", {}).get("phone"))


def beacon():
    if not config.CLOUDFLARE_ANALYTICS_TOKEN:
        return ""
    data = html.escape(json.dumps({"token": config.CLOUDFLARE_ANALYTICS_TOKEN}))
    return f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon="{data}"></script>'


def render_redirect(name, target, label):
    """A tiny page that Cloudflare counts as a view, then forwards the visitor. One per business."""
    e = html.escape
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><meta name=robots content="noindex,nofollow">
<meta http-equiv=refresh content="2;url={e(target)}"><title>{e(label)} {e(name)}</title>{beacon()}</head>
<body style="font:17px system-ui,sans-serif;padding:24px">
<p>{e(label)} <a href="{e(target)}" rel="nofollow">{e(name)}</a>…</p>
<script>setTimeout(function(){{location.replace({json.dumps(target)})}},500)</script></body></html>"""


def visible(records):
    return [r for r in records if quality.schedule_verified(r)]


def contacts(pages):
    """id -> {name, website, phone} for every listed venue with a usable website or phone."""
    out = {}
    for p in pages:
        for r in visible(p["records"]):
            site, phone = clean_website(r.get("website")), phone_of(r)
            if not (site or phone):
                continue
            key = base = biz_id(r["name"])
            n = 2
            while key in out and (out[key]["website"], out[key]["phone"]) != (site, phone):
                key, n = f"{base}-{n}", n + 1
            out[key] = {"name": r["name"], "website": site, "phone": phone}
            r["_id"] = key
    return out


def fact(r, key):
    v = r.get("facts", {}).get(key, "")
    v = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
    return "-" if v.strip().lower() in ("", "unknown") else v


def records_table(records):
    e = html.escape
    rows = []
    for r in records:
        site, phone, bid = clean_website(r.get("website")), phone_of(r), r.get("_id")
        name = e(r["name"])
        if site and bid:
            name = f'<a href="../go/{bid}/" rel="nofollow">{name}</a>'
        if r["name"].lower() in config.FEATURED:
            name += " <span class=featured>Featured</span>"
        area = fact(r, "area")
        where = f"<br><span class=meta>{e(area)}</span>" if area != "-" else ""
        tags = "".join(f"<span class=tag>{e(t)}</span>" for t in r.get("facts", {}).get("tags", []) or [])
        contact = []
        if phone and bid:
            contact.append(f'<a href="../call/{bid}/" rel="nofollow">{phone[0]}</a>')
        if site and bid:
            contact.append(f'<a href="../go/{bid}/" rel="nofollow">Website</a>')
        checked = f'<a href="{e(r["source"])}" rel="nofollow">{e(r.get("checked", "schedule"))}</a>'
        rows.append(
            f"<tr><td>{name}{where}</td><td>{e(fact(r, 'music_nights'))}</td><td>{e(fact(r, 'genres'))}</td>"
            f"<td>{e(fact(r, 'cover'))}</td><td>{e(fact(r, 'setting'))}<br>{tags}</td>"
            f"<td class=contact>{'<br>'.join(contact) or '-'}</td><td>{checked}</td></tr>")
    return ('<div class=tablewrap><table><thead><tr><th>Venue</th><th>Music nights</th><th>Genres</th>'
            '<th>Cover</th><th>Setting &amp; vibe</th><th>Contact</th><th>Checked</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def layout(title, description, canonical, body, extra_head="", home="./"):
    e = html.escape
    verify = ""
    if config.GOOGLE_SITE_VERIFICATION:
        verify = f'<meta name="google-site-verification" content="{e(config.GOOGLE_SITE_VERIFICATION)}">'
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name=description content="{e(description)}">
<link rel=canonical href="{e(canonical)}">{verify}<style>{CSS}</style>{beacon()}{extra_head}</head>
<body><header><a href="{home}">{e(config.SITE_NAME)}</a></header><main>{body}</main>
<footer>{e(config.SITE_TAGLINE)} Schedules are checked on each venue's own site; they change, so
confirm before you go.<nav class=footnav><a href="{home}about/">About</a> · <a href="{home}for-venues/">For venues</a>
· <a href="{home}contact/">Contact</a> · <a href="{home}privacy/">Privacy</a></nav></footer></body></html>"""


def render_page(p):
    p = {**p, "records": visible(p["records"])}
    e = html.escape
    url = f"{config.SITE_URL}/{p['slug']}/"
    items = []
    for i, r in enumerate(p["records"], 1):
        item = {"@type": "LocalBusiness", "name": r["name"]}
        if r.get("location"):
            item["address"] = r["location"]
        if clean_website(r.get("website")):
            item["url"] = r["website"]
        items.append({"@type": "ListItem", "position": i, "item": item})
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": p["title"], "itemListElement": items}
    body = (f"<h1>{e(p['title'])}</h1>"
            f"<p class=meta>Updated {e(p['updated'])} · {len(p['records'])} venues, each schedule checked "
            "on the venue's own site</p>"
            f"{records_table(p['records'])}{markdown(p['body_md'])}")
    head = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    return layout(f"{p['title']} | {config.SITE_NAME}", p["description"], url, body, head, home="../")


def venues(pages):
    """Every listed venue once (newest check wins): the data the plan-my-night tool will filter."""
    out = {}
    for p in pages:
        for r in visible(p["records"]):
            key = biz_id(r["name"])
            if key in out and out[key]["checked"] > r.get("checked", ""):
                continue
            out[key] = {"id": key, "name": r["name"], "city": p.get("city", ""), "location": r.get("location", ""),
                        "facts": {k: v for k, v in r.get("facts", {}).items()},
                        "website": clean_website(r.get("website")) or "", "checked": r.get("checked", ""),
                        "source": r["source"]}
    return sorted(out.values(), key=lambda v: (v["city"], v["name"]))


def mailto(subject):
    return f"mailto:{config.CONTACT_EMAIL}?subject={urllib.parse.quote(subject)}"


def info_page(slug, title, description, body):
    url = f"{config.SITE_URL}/{slug}/"
    return layout(f"{title} | {config.SITE_NAME}", description, url, f"<h1>{html.escape(title)}</h1>{body}", home="../")


def info_pages():
    """slug -> (title, description, html) for About, Contact, Privacy and For venues."""
    e, site, email = html.escape, html.escape(config.SITE_NAME), html.escape(config.CONTACT_EMAIL)
    cities = ", ".join(config.CITIES)
    return {
        "about": ("About", f"About {config.SITE_NAME} and how venues are checked.", f"""
<p>{site} is a guide to live music at restaurants, bars, breweries and halls in {e(cities)}. Pages are
organised by town and by the kind of night you want: waterfront, date night, family, no cover, jazz dinner.</p>
<h2>How a venue gets listed</h2>
<ul><li>It hosts live music on a <strong>recurring schedule</strong>, and that schedule is stated on the
<strong>venue's own website or calendar</strong>. Each listing links to that page and shows the date we checked it.</li>
<li>Pages are re-checked about once a month. Bands and nights change, so check the venue's page the day you go.</li>
<li>Listings are free, and pages do not rank or rate venues.</li></ul>
<p>Pages are researched with the help of AI tools and checked against each venue's own site.</p>
<p>Questions or corrections: <a href="mailto:{email}">{email}</a>.</p>"""),
        "contact": ("Contact", f"Contact {config.SITE_NAME}.", f"""
<p>Email <a href="mailto:{email}">{email}</a>. We read every message.</p>
<ul><li><a href="{e(mailto("Correction to a listing"))}">Report a schedule that changed</a> or a venue that closed.</li>
<li><a href="{e(mailto("Add a music night"))}">Tell us about a music night we're missing</a>.</li>
<li><a href="{e(mailto("Remove my venue"))}">Ask for your venue to be removed</a>. We remove it promptly.</li></ul>"""),
        "privacy": ("Privacy Policy", f"How {config.SITE_NAME} handles visitor data.", f"""
<p class=meta>Last updated {e(dt.date.today().isoformat())}</p>
<h2>What we collect</h2>
<p>We use <strong>Cloudflare Web Analytics</strong> to count visits. It does not use cookies and does not
collect personal information; it records things like the page viewed, referring site, country and
browser type. When you tap a venue's phone number or website link, the visit to that link's page on
our site is counted the same way, so we can see how many people contact each venue.</p>
<p>We have no accounts, forms or newsletters, so we do not collect names, email addresses or payment
details. If you email us, we use your message only to reply to you.</p>
<h2>Featured listings</h2>
<p>Venues may pay to be marked "Featured". It is always labelled and never changes which venues are listed.</p>
<h2>Selling data</h2>
<p>We do not sell or share personal information.</p>
<h2>Contact</h2>
<p>Privacy questions: <a href="mailto:{email}">{email}</a>.</p>"""),
        "for-venues": ("For venues", f"How restaurants, bars and halls get their live music listed on {config.SITE_NAME}.", f"""
<p>{site} helps people find live music by night and by vibe in {e(cities)}. Listings are free and are
based on the schedule on your own website or events page.</p>
<h2>Get listed or keep your listing right</h2>
<ul><li>Put your recurring music nights on your website (days, hours, cover, genre). That's what we check.</li>
<li><a href="{e(mailto("Please list our music nights"))}">Ask to be listed</a>: send your website and the page
with your music schedule.</li>
<li><a href="{e(mailto("Update our listing"))}">Update your listing</a> (new nights, cover, phone).</li>
<li><a href="{e(mailto("Remove my venue"))}">Ask to be removed</a>.</li></ul>"""),
    }


def render_index(pages):
    e = html.escape
    sections = []
    for city in config.CITIES:
        mine = [p for p in reversed(pages) if p.get("city") == city]
        if not mine:
            continue
        items = "".join(f'<li><a href="{e(p["slug"])}/">{e(p["title"])}</a><br>'
                        f'<span class=meta>{e(p["description"])}</span></li>' for p in mine)
        sections.append(f"<h2>{e(city)}</h2><ul class=pages>{items}</ul>")
    body = (f"<h1>{e(config.SITE_NAME)}</h1><p>{e(config.SITE_TAGLINE)}</p>"
            + ("".join(sections) or "<p>The first guides are being checked now.</p>"))
    return layout(f"{config.SITE_NAME}: live music on the Gulf Coast", config.SITE_TAGLINE, config.SITE_URL + "/", body)


def build():
    pages = store.pages()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    (OUT / "index.html").write_text(render_index(pages))
    for bid, c in contacts(pages).items():
        if c["website"]:
            (OUT / "go" / bid).mkdir(parents=True)
            (OUT / "go" / bid / "index.html").write_text(render_redirect(c["name"], c["website"], "Opening"))
        if c["phone"]:
            (OUT / "call" / bid).mkdir(parents=True)
            (OUT / "call" / bid / "index.html").write_text(render_redirect(c["name"], c["phone"][1], "Calling"))
    for p in pages:
        d = OUT / p["slug"]
        d.mkdir()
        (d / "index.html").write_text(render_page(p))
    for slug, (title, description, body) in info_pages().items():
        (OUT / slug).mkdir()
        (OUT / slug / "index.html").write_text(info_page(slug, title, description, body))
    (OUT / "venues.json").write_text(json.dumps(venues(pages), indent=1, ensure_ascii=False))
    urls = [(config.SITE_URL + "/", pages[-1]["updated"] if pages else "")] + [
        (f"{config.SITE_URL}/{p['slug']}/", p["updated"]) for p in pages] + [
        (f"{config.SITE_URL}/{slug}/", "") for slug in info_pages()]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{html.escape(u)}</loc>" + (f"<lastmod>{m}</lastmod>" if m else "")
                  + "</url>\n" for u, m in urls)
        + "</urlset>\n")
    (OUT / "robots.txt").write_text(f"User-agent: *\nDisallow: /go/\nDisallow: /call/\nAllow: /\nSitemap: {config.SITE_URL}/sitemap.xml\n")
    return len(pages)
