import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import builder  # noqa: E402
import config  # noqa: E402
import quality  # noqa: E402
import render  # noqa: E402
import store  # noqa: E402


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "data")
    monkeypatch.setattr(render, "OUT", tmp_path / "site")
    monkeypatch.setattr(config, "DEMO", True)
    monkeypatch.setattr(config, "CLOUDFLARE_ANALYTICS_TOKEN", "")
    return tmp_path


def venue(name="Pelican Grill", nights="Thu-Sat 6-9pm", source="https://pelicangrill.example/music"):
    return {"name": name, "facts": {"music_nights": nights, "tags": ["waterfront"]}, "source": source,
            "website": "https://pelicangrill.example/", "phone": "941-555-0100"}


def test_only_schedules_from_the_venues_own_site_count():
    assert quality.schedule_verified(venue())
    assert not quality.schedule_verified(venue(nights="unknown"))
    assert not quality.schedule_verified(venue(nights=""))
    assert not quality.schedule_verified(venue(source="https://www.yelp.com/biz/pelican"))
    assert not quality.schedule_verified(venue(source="https://www.swflmusic.com/venue/pelican"))
    assert not quality.schedule_verified(venue(source="pelicangrill"))


def test_topics_start_with_city_overviews_then_each_theme_everywhere():
    topics = builder.sync_topics([])
    assert [t["city"] for t in topics[:len(config.CITIES)]] == list(config.CITIES)
    assert all(t["title"].startswith("Live music in") for t in topics[:len(config.CITIES)])
    assert len(topics) == len(config.CITIES) * (1 + len(config.THEMES))
    assert builder.sync_topics(topics) == topics


def test_nightly_build_publishes_guides_and_venue_data(sandbox):
    results = builder.run()
    assert [r["action"] for r in results] == ["published"] * config.PAGES_PER_NIGHT
    render.build()
    page = store.pages()[0]
    html = (sandbox / "site" / page["slug"] / "index.html").read_text()
    bid = render.biz_id(page["records"][0]["name"])
    assert f'href="../go/{bid}/"' in html and f'href="../call/{bid}/"' in html
    assert "Music nights" in html and '"@type": "ItemList"' in html
    assert all("made-up tag" not in r["facts"]["tags"] for r in page["records"])
    venues = json.loads((sandbox / "site" / "venues.json").read_text())
    assert venues and {"name", "city", "facts", "checked", "source"} <= set(venues[0])
    assert "Disallow: /go/" in (sandbox / "site" / "robots.txt").read_text()
    sitemap = (sandbox / "site" / "sitemap.xml").read_text()
    assert "/go/" not in sitemap and "/for-venues/</loc>" in sitemap
    index = (sandbox / "site" / "index.html").read_text()
    assert f"<h2>{page['city']}</h2>" in index


def test_unconfirmed_venues_are_dropped_before_publishing(sandbox, monkeypatch):
    good = [venue(f"V{i}") for i in range(5)]
    bad = venue("Gone Bar", source="https://www.tripadvisor.com/x")
    monkeypatch.setattr(builder.llm, "ask_json", lambda *a, **k: ({"description": "d", "records": good + [bad]}, []))
    monkeypatch.setattr(builder.llm, "ask", lambda *a, **k: ("word " * 400, []))
    page = builder.make_page("Jazz dinner spots in Venice, FL", "Venice")
    assert [r["name"] for r in page["records"]] == [f"V{i}" for i in range(5)]
    assert all(r["checked"] == builder.today() for r in page["records"])


def test_stale_page_is_rechecked_and_failed_recheck_waits_a_week(sandbox, monkeypatch):
    builder.run()
    page = store.pages()[0]
    page["updated"] = "2000-01-01"
    store.save(f"pages/{page['slug']}.json", page)
    assert builder.stale_page(store.pages())["slug"] == page["slug"]
    monkeypatch.setattr(builder, "make_page", lambda *a, **k: {**page, "records": []})
    assert builder.refresh_once()["action"] == "rejected"
    assert store.load(f"pages/{page['slug']}.json")["records"]  # old page kept
    assert builder.stale_page(store.pages()) is None


def test_ranking_language_is_blocked():
    page = {"slug": "x", "records": [venue(f"V{i}") for i in range(5)], "body_md": "word " * 400}
    assert quality.check(page, []) == []
    assert any("neutral" in f for f in quality.check({**page, "body_md": page["body_md"] + " our pick"}, []))


def test_info_pages(sandbox):
    render.build()
    for slug in ("about", "contact", "privacy", "for-venues"):
        assert (sandbox / "site" / slug / "index.html").exists()
    assert "mailto:hello@nightset.org?subject=Remove%20my%20venue" in (sandbox / "site" / "contact" / "index.html").read_text()
