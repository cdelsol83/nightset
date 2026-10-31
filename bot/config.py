"""Nightset settings. Edit these, then run `python nightset.py status` to check what's configured."""
import os

SITE_NAME = "Nightset"
SITE_URL = "https://nightset.org"  # custom domain (set in Settings > Pages > Custom domain)
SITE_TAGLINE = "Live music at restaurants, bars, breweries and halls on Florida's Gulf Coast, by night and by vibe."
AREA = "Florida's Gulf Coast"
CONTACT_EMAIL = "hello@nightset.org"
# Google Search Console "HTML tag" verification (the content="..." value; public, not a secret)
GOOGLE_SITE_VERIFICATION = ""
# Cloudflare Web Analytics site token for nightset.org (public). Empty = no analytics yet.
CLOUDFLARE_ANALYTICS_TOKEN = ""

# City -> nearby areas the research may include on that city's pages
CITIES = {
    "St. Petersburg": "St. Pete Beach, Gulfport, Treasure Island, Madeira Beach",
    "Bradenton": "Anna Maria Island, Holmes Beach, Palmetto, Lakewood Ranch",
    "Sarasota": "Siesta Key, Lido Key, Longboat Key",
    "Venice": "Nokomis, Englewood, Osprey",
    "Punta Gorda": "Port Charlotte, Boca Grande",
    "Fort Myers": "Fort Myers Beach, Cape Coral, Sanibel, Estero",
}
# What people actually search for: one theme in one city per page. Each theme is written for
# every city before the next theme starts. Themes with too few venues in a city are skipped.
THEMES = [
    "Waterfront and outdoor live music in {city}, FL",
    "Date night with live music in {city}, FL",
    "Jazz dinner spots in {city}, FL",
    "Family-friendly live music in {city}, FL",
    "Live music with no cover charge in {city}, FL",
    "Brunch with live music in {city}, FL",
    "Breweries with live music in {city}, FL",
    "Blues and rock bars with live bands in {city}, FL",
    "Open mic and jam nights in {city}, FL",
    "Country music and line dancing in {city}, FL",
    "Latin and salsa nights in {city}, FL",
    "Concert halls and listening rooms in {city}, FL",
]
# Tags a venue can carry. The plan-my-night filter (phase 2) is built on these.
VIBES = ["date night", "family friendly", "conversation friendly", "dance floor", "lively",
         "waterfront", "outdoor seating", "dog friendly", "no cover", "dinner menu", "late night",
         "21+", "listening room"]
# Written first, ahead of the auto-generated queue: one city overview each
OVERVIEW = "Live music in {city}, FL: weekly music nights at restaurants and bars"

VENUE_RULES = """Each entry is a real venue (restaurant, bar, brewery, winery, hall, theater or club)
in or near {city} that hosts live music on a RECURRING schedule (weekly or several times a week).
Required facts:
  "music_nights": the recurring schedule exactly as the venue states it (days and hours, e.g.
     "Thu-Sat 6-9pm; Sun jazz brunch 11am-2pm"),
  "genres": what is usually played, "cover": "Free", a price, or "unknown",
  "setting": indoor / outdoor / waterfront / mixed, "venue_type": restaurant, bar, brewery, hall...,
  "food": full menu / bar food / none / unknown, "ages": all ages / 21+ / unknown,
  "area": town or neighborhood, "tags": a JSON list using ONLY these words: {vibes}.
The "source" URL must be the venue's OWN website or its own events/calendar page, and that page
must state the music schedule. Never use review sites, local "tonight" calendars, ticket resellers
or other directories as the source. Skip venues whose schedule you can only find elsewhere, and
skip one-off concerts. Only add a tag when the venue's own page supports it. Never state or imply
anything negative about a venue. Do not invent reviews, ratings or prices."""

# Sources that are never a venue's own page
NOT_VENUE_SOURCES = (
    "yelp.", "tripadvisor.", "google.", "opentable.", "facebook.com/events", "bandsintown.",
    "songkick.", "eventbrite.", "allevents.", "gotonight.", "swflmusic.", "rager.live",
    "stpetemusic.live", "livemusictampa.", "hapjam.", "swfllive.", "thetampacalendar.",
    "baselocal.", "eatplayswfl.", "visitsarasota.", "visitstpeteclearwater.", "patch.com",
    "heraldtribune.", "tampabay.com", "news-press.", "creativeloafing.", "jambase.", "ticketmaster.",
)

# --- Builder quality gate: a page that fails ANY of these is not published ---
PAGES_PER_NIGHT = 2
MIN_RECORDS = 5
MIN_WORDS = 350
MAX_SIMILARITY = 0.55
STALE_AFTER_DAYS = 30       # music schedules change: each page is re-checked about monthly

# Featured / sponsored venue names (lowercase) -> shown with a "Featured" label. Empty for now.
FEATURED = {}

# --- Model / APIs (secrets come from environment variables, never this file) ---
XAI_MODEL = os.environ.get("MOGUL_MODEL") or "grok-4.7"
XAI_API_KEY = os.environ.get("XAI_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Demo mode: canned model answers, no network. `MOGUL_DEMO=1 python nightset.py build`
DEMO = os.environ.get("MOGUL_DEMO") == "1"
