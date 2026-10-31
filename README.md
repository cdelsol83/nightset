# Nightset

Live music at restaurants, bars, breweries and halls on Florida's Gulf Coast, by night and by vibe:
St. Petersburg, Bradenton, Sarasota, Venice, Punta Gorda and Fort Myers. Site: https://nightset.org

## How it works

A small bot in `bot/` (adapted from Mogul) runs on GitHub Actions:

- **Nightly build** (`bot/nightset.py build`): re-checks the oldest guide older than 30 days, then
  researches new guides with Grok web search until `PAGES_PER_NIGHT` is reached. Order: one city
  overview per city, then each theme (waterfront, date night, jazz dinner, family, no cover...) in
  every city.
- **Trust rule:** a venue is listed only when its recurring music schedule is stated on the venue's
  **own** website or calendar (`quality.schedule_verified`). Review sites, "tonight" calendars and
  ticket sites never count. Each listing shows the date it was checked and links to that page.
- **Quality gate** (`bot/quality.py`): at least 5 confirmed venues, 350+ words, not a near-duplicate,
  and no ranking language. Guides that fail are skipped and reported to Telegram.
- **Site:** static HTML in `bot/site/`, deployed to GitHub Pages. Website and phone taps go through
  counted `/go/` and `/call/` pages (Cloudflare Web Analytics). `venues.json` holds every venue once,
  ready for the phase 2 "plan my night" filter.
- **Daily report** to Telegram (weekly on Mondays). Send-only: the bot never reads Telegram updates,
  so it can share a bot with Mogul.

State lives in `bot/data/` and is committed by the workflow.

## Settings

Edit `bot/config.py`: cities, themes, vibe tags, venue rules, `PAGES_PER_NIGHT`,
`CLOUDFLARE_ANALYTICS_TOKEN`, `GOOGLE_SITE_VERIFICATION`.

Secrets (Settings > Secrets and variables > Actions): `XAI_API_KEY`, `TELEGRAM_TOKEN`,
`TELEGRAM_CHAT_ID`. Variable `NIGHTSET_ENABLED=true` turns on the schedule.

## Local

    cd bot
    MOGUL_DEMO=1 python nightset.py build   # offline, fictional venues
    python -m pytest -q tests
