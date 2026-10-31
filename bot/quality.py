"""Quality gate. A page is published only if every check passes; failures are logged, not shipped."""
import re

import config

# Pages name real venues, so they compare facts and never pick winners.
RANKING = r"\b(best (overall|budget|value|for|pick)|top (pick|choice|rated)|our (pick|favorite|top)|we recommend|editor'?s choice|runner[- ]up)\b"
UNKNOWN = ("", "unknown", "n/a", "none", "not stated", "varies")


def words(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def shingles(text, k=5):
    w = words(text)
    return {" ".join(w[i:i + k]) for i in range(max(len(w) - k + 1, 0))}


def similarity(a, b):
    sa, sb = shingles(a), shingles(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def schedule_verified(record):
    """A stated recurring music schedule, sourced from the venue's own site (not a directory)."""
    nights = str(record.get("facts", {}).get("music_nights", "")).strip().lower()
    source = str(record.get("source", "")).strip().lower()
    if nights in UNKNOWN or not re.match(r"https?://[^\s/]+\.[^\s/]+", source):
        return False
    return not any(s in source for s in config.NOT_VENUE_SOURCES)


def check(page, existing):
    """Return a list of failure reasons (empty list = publish)."""
    fails = []
    records = page.get("records", [])
    if len(records) < config.MIN_RECORDS:
        fails.append(f"only {len(records)} venues (< {config.MIN_RECORDS})")
    unverified = [r["name"] for r in records if not schedule_verified(r)]
    if unverified:
        fails.append(f"music schedule not confirmed on the venue's own site: {', '.join(unverified)}")
    body = page.get("body_md", "")
    n = len(words(body))
    if n < config.MIN_WORDS:
        fails.append(f"body is {n} words (< {config.MIN_WORDS})")
    for other in existing:
        if other["slug"] == page["slug"]:
            continue
        s = similarity(body, other.get("body_md", ""))
        if s > config.MAX_SIMILARITY:
            fails.append(f"{s:.0%} similar to existing page '{other['slug']}'")
    if re.search(r"\b(as an ai|i cannot|i'm unable|lorem ipsum)\b", body, re.I):
        fails.append("contains model boilerplate")
    if re.search(RANKING, body, re.I):
        fails.append("ranks or recommends named venues (pages must stay neutral)")
    return fails
