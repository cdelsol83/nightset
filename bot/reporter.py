"""Reporter: what's live and what the quality gate blocked -> Telegram."""
import datetime as dt

import config
import render
import store
import telegram


def report(period="day"):
    today = dt.date.today()
    since = (today - dt.timedelta(days=1 if period == "day" else 7)).isoformat()
    pages = store.pages()
    new = [p for p in pages if p["published"] >= since]
    topics = store.load("topics.json", [])
    venues = render.venues(pages)
    lines = [f"🎶 {config.SITE_NAME}: {'daily' if period == 'day' else 'weekly'} report ({today})", "",
             f"📄 Guides: {len(pages)} live, {len(new)} new"
             + (f" ({', '.join(p['title'] for p in new[:3])})" if new else ""),
             f"🎸 Venues: {len(venues)} across " + ", ".join(
                 f"{c} {sum(v['city'] == c for v in venues)}" for c in config.CITIES)]
    rejected = [t for t in topics if t["status"] == "rejected"]
    if rejected:
        lines.append(f"🚫 Skipped {len(rejected)} guides with too few confirmed venues so far")
    lines.append("👀 Visits and taps: Cloudflare > Analytics & Logs > Web Analytics (paths /go/ and /call/)")
    text = "\n".join(lines)
    telegram.send(text)
    return text
