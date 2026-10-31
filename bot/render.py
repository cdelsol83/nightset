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
:root{--bg:#0f0c18;--card:#1a1626;--fg:#f3effa;--muted:#a69fb8;--line:#2d2740;--chip:#262036;
--accent:#ff8a5c;--accent2:#d36ef0;--btnfg:#160f1f}
@media (prefers-color-scheme:light){:root{--bg:#faf7f3;--card:#fff;--fg:#1d1726;--muted:#6c6478;
--line:#ebe4dc;--chip:#f3ecf6;--accent:#e2602f;--accent2:#9b3fc0;--btnfg:#fff}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--accent)}main,.bar,footer{max-width:1040px;margin:auto;padding:0 16px}
.bar{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding-top:18px;padding-bottom:6px}
.logo{font-weight:800;font-size:1.25rem;letter-spacing:.01em;color:var(--fg);text-decoration:none;display:flex;align-items:center;gap:8px}
.logo i{width:14px;height:14px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));box-shadow:0 0 14px var(--accent2)}
.citynav{display:flex;gap:6px;font-size:.85rem;overflow-x:auto;scrollbar-width:none;max-width:100%}.citynav a{color:var(--muted);text-decoration:none;white-space:nowrap;padding:4px 8px;border-radius:99px}
.citynav a:hover{color:var(--fg);background:var(--chip)}
.hero{padding:36px 0 18px}.hero h1{font-size:clamp(2rem,6vw,3.2rem);line-height:1.05;margin:0 0 10px;letter-spacing:-.02em}
.grad{background:linear-gradient(90deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p{color:var(--muted);margin:0;font-size:1.05rem}
h2{font-size:1.35rem;margin:34px 0 12px}
.filters{display:flex;flex-direction:column;gap:8px;margin:14px 0 6px}.row{display:flex;gap:6px;overflow-x:auto;padding-bottom:4px;scrollbar-width:none}
.chip{border:1px solid var(--line);background:var(--chip);color:var(--fg);border-radius:99px;padding:6px 13px;font:inherit;font-size:.88rem;white-space:nowrap;cursor:pointer}
.chip[aria-pressed=true]{background:linear-gradient(90deg,var(--accent),var(--accent2));color:var(--btnfg);border-color:transparent;font-weight:600}
.count{color:var(--muted);font-size:.85rem;margin:6px 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px;display:flex;flex-direction:column;gap:9px}
.card h3{margin:0;font-size:1.08rem;line-height:1.25}.card h3 a{color:var(--fg);text-decoration:none}
.area{color:var(--muted);font-size:.85rem}
.week{display:flex;gap:4px}.week span{flex:1;text-align:center;font-size:.7rem;font-weight:700;padding:5px 0;border-radius:7px;
background:var(--chip);color:var(--muted);opacity:.55}.week span.on{opacity:1;color:var(--fg)}
.week span.on.today{background:linear-gradient(90deg,var(--accent),var(--accent2));color:var(--btnfg)}
.when{margin:0;font-size:.88rem;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.tags{display:flex;flex-wrap:wrap;gap:5px}.tag{background:var(--chip);border-radius:99px;padding:2px 9px;font-size:.76rem;color:var(--muted)}
.tag.hot{color:var(--fg)}.actions{display:flex;gap:8px;margin-top:auto;padding-top:4px}
.btn{flex:1;text-align:center;text-decoration:none;border-radius:10px;padding:9px 10px;font-weight:600;font-size:.9rem;border:1px solid var(--line);color:var(--fg)}
.btn.primary{background:linear-gradient(90deg,var(--accent),var(--accent2));color:var(--btnfg);border:0}
.checked{color:var(--muted);font-size:.75rem;margin:0}.checked a{color:var(--muted)}
.featured{font-size:.7rem;color:var(--accent);margin-left:6px}.empty{color:var(--muted);display:none}
.cities{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px}
.city{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px}
.city h3{margin:0 0 6px}.city ul{margin:0;padding:0;list-style:none;font-size:.9rem}.city li{padding:4px 0}
details.more{margin:30px 0;border-top:1px solid var(--line);padding-top:14px}details.more summary{cursor:pointer;color:var(--muted)}
.prose{max-width:720px}.prose h2{font-size:1.15rem}.sub{color:var(--muted);margin:0}
footer{padding:40px 16px;color:var(--muted);font-size:.85rem}footer nav{display:flex;gap:14px;flex-wrap:wrap;margin-top:6px}
footer a{color:var(--muted)}
"""

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}
_DAY = r"(mon|tue|wed|thu|fri|sat|sun)(?:day|s|sday|nesday|r|rs|rsday|urday)?s?\.?"

JS = """<script>
(function(){var day='all',vibe='all',city='all',cards=[].slice.call(document.querySelectorAll('.card'));
var today=['sun','mon','tue','wed','thu','fri','sat'][new Date().getDay()];
document.querySelectorAll('.week .d-'+today).forEach(function(s){s.classList.add('today')});
document.querySelectorAll('[data-day=tonight]').forEach(function(b){b.dataset.day=today});
function show(){var n=0;cards.forEach(function(c){var ok=(day=='all'||(' '+c.dataset.days+' ').indexOf(' '+day+' ')>=0)
&&(vibe=='all'||(' '+c.dataset.tags+' ').indexOf(' '+vibe+' ')>=0)&&(city=='all'||c.dataset.city==city);
c.hidden=!ok;if(ok)n++});var k=document.querySelector('.count');if(k)k.textContent=n+(n==1?' venue':' venues');
var e=document.querySelector('.empty');if(e)e.style.display=n?'none':'block'}
document.querySelectorAll('.chip').forEach(function(b){b.addEventListener('click',function(){
var g=b.parentNode;g.querySelectorAll('.chip').forEach(function(x){x.setAttribute('aria-pressed','false')});
b.setAttribute('aria-pressed','true');if('day' in b.dataset)day=b.dataset.day;if('vibe' in b.dataset)vibe=b.dataset.vibe;
if('city' in b.dataset)city=b.dataset.city;show()})});
var start=document.querySelector('[aria-pressed=true][data-day]');if(start)day=start.dataset.day;show()})();
</script>"""


def days_of(text):
    """Days a schedule names, e.g. 'Thu-Sat 6-9pm; Sun brunch' -> ['thu','fri','sat','sun']. [] = unclear."""
    t = str(text).lower()
    if re.search(r"\b(daily|nightly|every (day|night)|most nights|7 (days|nights)|seven (days|nights)|365)\b", t):
        return list(DAYS)
    found = set()
    for m in re.finditer(rf"\b{_DAY}\s*(?:-|–|—|to|through|thru)\s*{_DAY}\b", t):
        i, j = DAYS.index(m.group(1)), DAYS.index(m.group(2))
        found.update(DAYS[(i + k) % 7] for k in range((j - i) % 7 + 1))
    found.update(m.group(1) for m in re.finditer(rf"\b{_DAY}\b", t))
    if re.search(r"\bweekends?\b", t):
        found.update(("sat", "sun"))
    return [d for d in DAYS if d in found]


def short(text, n=4):
    """First few comma/'and' separated items: long genre lists become chip-sized."""
    text = re.sub(r"\(.*?\)", "", str(text))
    parts = [p.strip(" .") for p in re.split(r",|\band\b|;|/", text) if p.strip(" .")]
    return [p[:28] for p in parts[:n]]


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


def venue_card(r, city=""):
    e = html.escape
    site, phone, bid = clean_website(r.get("website")), phone_of(r), r.get("_id")
    name = e(r["name"])
    if site and bid:
        name = f'<a href="{{home}}go/{bid}/" rel="nofollow">{name}</a>'
    if r["name"].lower() in config.FEATURED:
        name += "<span class=featured>FEATURED</span>"
    area = fact(r, "area")
    facts = r.get("facts", {})
    tags = [t for t in facts.get("tags", []) or [] if t in config.VIBES]
    chips = [f"<span class='tag hot'>{e(g)}</span>" for g in short(fact(r, "genres"), 2) if g != "-"]
    cover = fact(r, "cover")
    if cover != "-":
        chips.append(f"<span class='tag hot'>{'No cover' if cover.lower().startswith('free') else e(cover[:20]) + ' cover'}</span>")
    chips += [f"<span class=tag>{e(t)}</span>" for t in tags if not (t == "no cover" and cover != "-")][:4]
    buttons = []
    if phone and bid:
        buttons.append(f'<a class="btn primary" href="{{home}}call/{bid}/" rel="nofollow">Call</a>')
    if site and bid:
        buttons.append(f'<a class=btn href="{{home}}go/{bid}/" rel="nofollow">Website</a>')
    days = days_of(facts.get("music_nights", ""))
    week = "".join(f'<span class="d-{d}{" on" if d in days else ""}">{DAY_NAMES[d][:2]}</span>' for d in DAYS) if days else ""
    checked = dt.date.fromisoformat(r["checked"]).strftime("%b %-d") if r.get("checked") else "recently"
    return (f'<article class=card data-days="{" ".join(days)}" '
            f'data-tags="{e(" ".join(t.replace(" ", "-") for t in tags))}" data-city="{biz_id(city)}">'
            f'<div><h3>{name}</h3>' + (f'<span class=area>{e(area)}</span>' if area != "-" else "") + "</div>"
            + (f'<div class=week aria-label="Music nights">{week}</div>' if week else "")
            + f'<p class=when title="{e(fact(r, "music_nights"))}">{e(fact(r, "music_nights"))}</p>'
            f'<div class=tags>{"".join(chips)}</div>'
            + (f'<div class=actions>{"".join(buttons)}</div>' if buttons else "")
            + f'<p class=checked>Checked {checked} · <a href="{e(r["source"])}" rel="nofollow">venue schedule</a></p></article>')


def filters(records, cities=None, default_day="all"):
    def chip(label, attr, value, on):
        return f'<button class=chip data-{attr}="{value}" aria-pressed="{"true" if on else "false"}">{label}</button>'
    days = (chip("Any day", "day", "all", default_day == "all") + chip("Tonight", "day", "tonight", default_day == "tonight")
            + "".join(chip(DAY_NAMES[d], "day", d, False) for d in DAYS))
    used = {t for r in records for t in r.get("facts", {}).get("tags", []) or []}
    vibes = chip("Any vibe", "vibe", "all", True) + "".join(
        chip(html.escape(t.capitalize()), "vibe", t.replace(" ", "-"), False) for t in config.VIBES if t in used)
    rows = [f"<div class=row>{days}</div>", f"<div class=row>{vibes}</div>"]
    if cities:
        rows.insert(0, "<div class=row>" + chip("All cities", "city", "all", True) + "".join(
            chip(html.escape(c), "city", biz_id(c), False) for c in cities) + "</div>")
    return f'<div class=filters>{"".join(rows)}</div><p class=count></p>'


def cards(records, home, city=""):
    return ('<div class=grid>' + "".join(venue_card(r, city).replace("{home}", home) for r in records)
            + '</div><p class=empty>Nothing matches. Try another night or vibe.</p>')


def layout(title, description, canonical, body, extra_head="", home="./"):
    e = html.escape
    verify = ""
    if config.GOOGLE_SITE_VERIFICATION:
        verify = f'<meta name="google-site-verification" content="{e(config.GOOGLE_SITE_VERIFICATION)}">'
    nav = "".join(f'<a href="{home}#{biz_id(c)}">{e(c)}</a>' for c in config.CITIES)
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><meta name=theme-color content="#0f0c18">
<title>{e(title)}</title><meta name=description content="{e(description)}">
<link rel=canonical href="{e(canonical)}">{verify}<style>{CSS}</style>{beacon()}{extra_head}</head>
<body><div class=bar><a class=logo href="{home}"><i></i>{e(config.SITE_NAME)}</a><nav class=citynav>{nav}</nav></div>
<main>{body}</main>
<footer>Schedules come from each venue's own site and change often, so check before you go.
<nav><a href="{home}about/">About</a><a href="{home}for-venues/">For venues</a><a href="{home}contact/">Contact</a>
<a href="{home}privacy/">Privacy</a></nav></footer>{JS}</body></html>"""


def split_title(title):
    head, _, sub = title.partition(":")
    return head.strip(), sub.strip()


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
    head, sub = split_title(p["title"])
    body = (f'<section class=hero><h1>{e(head)}</h1><p>{e(sub.capitalize() if sub else p["description"])}</p></section>'
            f'{filters(p["records"])}{cards(p["records"], "../", p.get("city", ""))}'
            f'<details class=more><summary>More about this guide · updated {e(p["updated"])}</summary>'
            f'<div class=prose>{markdown(p["body_md"])}</div></details>')
    head_ld = f'<script type="application/ld+json">{json.dumps(ld)}</script>'
    return layout(f"{p['title']} | {config.SITE_NAME}", p["description"], url, body, head_ld, home="../")


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
                        "source": r["source"], "_record": r}
    return sorted(out.values(), key=lambda v: (v["city"], v["name"]))


def mailto(subject):
    return f"mailto:{config.CONTACT_EMAIL}?subject={urllib.parse.quote(subject)}"


def info_page(slug, title, description, body):
    url = f"{config.SITE_URL}/{slug}/"
    return layout(f"{title} | {config.SITE_NAME}", description, url, f"<section class=prose><h1>{html.escape(title)}</h1>{body}</section>", home="../")


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
    all_venues = venues(pages)
    cities = [c for c in config.CITIES if any(v["city"] == c for v in all_venues)]
    grid = "".join(venue_card(v["_record"], v["city"]).replace("{home}", "") for v in all_venues)
    tiles = []
    for c in config.CITIES:
        mine = [p for p in reversed(pages) if p.get("city") == c]
        links = "".join(f'<li><a href="{e(p["slug"])}/">{e(split_title(p["title"])[1].capitalize() or p["title"])}</a></li>'
                        if split_title(p["title"])[0].startswith("Live music in") else
                        f'<li><a href="{e(p["slug"])}/">{e(split_title(p["title"])[0])}</a></li>' for p in mine)
        n = sum(v["city"] == c for v in all_venues)
        tiles.append(f'<div class=city id="{biz_id(c)}"><h3>{e(c)}</h3><p class=area>'
                     f'{f"{n} venues" if n else "Coming soon"}</p><ul>{links}</ul></div>')
    body = (f'<section class=hero><h1>Live music <span class=grad>tonight</span><br>on the Gulf Coast</h1>'
            f'<p>Restaurants, bars and breweries with bands, by night and by vibe.</p></section>'
            + (f'{filters([v["_record"] for v in all_venues], cities, "tonight")}<div class=grid>{grid}</div>'
               '<p class=empty>Nothing listed for that night yet. Try another day.</p>' if all_venues else "")
            + f'<h2>Guides by city</h2><div class=cities>{"".join(tiles)}</div>')
    return layout(f"{config.SITE_NAME}: live music tonight on the Gulf Coast", config.SITE_TAGLINE, config.SITE_URL + "/", body)


def build():
    pages = store.pages()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    links = contacts(pages)
    (OUT / "index.html").write_text(render_index(pages))
    for bid, c in links.items():
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
    (OUT / "venues.json").write_text(json.dumps([{k: v for k, v in x.items() if k != "_record"} for x in venues(pages)], indent=1, ensure_ascii=False))
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
