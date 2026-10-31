"""Builder: each night, re-check one stale page and research + write new pages, then gate them."""
import datetime as dt
import json
import re

import config
import llm
import quality
import store

RESEARCH_PROMPT = """Page: "{title}" on {site}, a guide to live music in {area}.
Look in {city} and nearby ({nearby}).
{rules}
Use web search to collect {min_n}-12 venues that fit this page. For each venue return:
  "name", "location" (street address if stated), "facts": the facts listed above,
  "website": the venue's own website or "", "phone": the venue's phone number as published on its
  own site or "", and "source": the venue's own page where you confirmed the music schedule.
Never invent values; use "unknown" when a fact isn't stated.
Return JSON: {{"description": one-sentence meta description, "records": [...]}}"""

WRITE_PROMPT = """Write a short guide for a page titled "{title}" on {site}.
Readers are deciding where to go for live music, often tonight, usually on a phone. Keep it brief and
scannable. Never state or imply anything negative about a named venue. Use ONLY the facts in this
JSON; do not add any fact not present in it:
{records}
Structure (Markdown): a 2-sentence intro; "## By night" (one short bullet per night of the week that
has music, naming the venues); "## Good to know" (3 short bullets: cover, setting, food or ages);
"## FAQ" (3 questions as ### headings, one-sentence answers). Never rank, rate or recommend venues,
and never use "best", "top" or "our pick". Do not list every venue's details; the site shows them
as cards. 180-320 words."""


def slugify(title):
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]


def today():
    return dt.date.today().isoformat()


def all_topics():
    """City overviews first, then each theme across every city."""
    out = [{"title": config.OVERVIEW.format(city=c), "city": c} for c in config.CITIES]
    for theme in config.THEMES:
        out += [{"title": theme.format(city=c), "city": c} for c in config.CITIES]
    return out


def sync_topics(topics):
    """Add topics from config that the queue doesn't know yet, keeping their order."""
    seen = {slugify(t["title"]) for t in topics}
    return topics + [{**t, "status": "queued"} for t in all_topics() if slugify(t["title"]) not in seen]


def make_page(title, city, published=None):
    research, citations = llm.ask_json(RESEARCH_PROMPT.format(
        title=title, site=config.SITE_NAME, area=config.AREA, city=city,
        nearby=config.CITIES.get(city, ""), min_n=config.MIN_RECORDS,
        rules=config.VENUE_RULES.format(city=city, vibes=", ".join(config.VIBES))))
    records = [r for r in research.get("records", []) if isinstance(r, dict) and r.get("name")
               and quality.schedule_verified(r)]  # unconfirmed schedules never ship
    for r in records:
        facts = r.setdefault("facts", {})
        tags = facts.get("tags") if isinstance(facts.get("tags"), list) else []
        facts["tags"] = [t for t in tags if t in config.VIBES]
        r["checked"] = today()
    body, _ = llm.ask(WRITE_PROMPT.format(
        title=title, site=config.SITE_NAME, records=json.dumps(records, indent=1)), tools=())
    return {
        "slug": slugify(title),
        "title": title,
        "city": city,
        "description": research.get("description", ""),
        "records": records,
        "body_md": body.strip(),
        "citations": citations,
        "published": published or today(),
        "updated": today(),
    }


def stale_page(pages):
    """Oldest page past STALE_AFTER_DAYS, skipping ones whose re-check failed in the last week."""
    cutoff = (dt.date.today() - dt.timedelta(days=config.STALE_AFTER_DAYS)).isoformat()
    week = (dt.date.today() - dt.timedelta(days=7)).isoformat()
    old = [p for p in pages if p["updated"] < cutoff and p.get("refresh_failed", "") < week]
    return min(old, key=lambda p: p["updated"]) if old else None


def refresh_once():
    pages = store.pages()
    old = stale_page(pages)
    if not old:
        return None
    page = make_page(old["title"], old.get("city", ""), published=old["published"])
    fails = quality.check(page, pages)
    if fails:  # keep the old page and try again in a week
        old["refresh_failed"] = today()
        store.save(f"pages/{old['slug']}.json", old)
        return {"action": "rejected", "title": page["title"], "reasons": fails}
    store.save(f"pages/{page['slug']}.json", page)
    return {"action": "refreshed", "title": page["title"], "records": len(page["records"])}


def publish_once():
    topics = sync_topics(store.load("topics.json", []))
    topic = next((t for t in topics if t["status"] == "queued"), None)
    if topic is None:
        store.save("topics.json", topics)
        return {"action": "skipped", "reason": "no topics left"}
    page = make_page(topic["title"], topic["city"])
    fails = quality.check(page, store.pages())
    topic["status"] = "rejected" if fails else "published"
    if fails:
        topic["reasons"] = fails
    store.save("topics.json", topics)
    if fails:
        return {"action": "rejected", "title": page["title"], "reasons": fails}
    store.save(f"pages/{page['slug']}.json", page)
    return {"action": "published", "title": page["title"], "records": len(page["records"])}


def run():
    """One night: at most one re-check, the rest of PAGES_PER_NIGHT go to new pages."""
    results = []
    refreshed = refresh_once()
    if refreshed:
        results.append(refreshed)
    while len(results) < config.PAGES_PER_NIGHT:
        results.append(publish_once())
        if results[-1]["action"] == "skipped":
            break
    return results
