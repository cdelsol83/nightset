"""State lives in plain JSON files under data/ so the nightly job can commit it to git."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "data"


def path(*parts):
    return ROOT.joinpath(*parts)


def load(name, default=None):
    p = path(name)
    if not p.exists():
        return default
    return json.loads(p.read_text())


def save(name, obj):
    p = path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def pages():
    """All published pages, oldest first."""
    d = path("pages")
    items = [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))] if d.exists() else []
    return sorted(items, key=lambda p: p["published"])


def outreach():
    d = path("outreach")
    return [json.loads(p.read_text()) for p in sorted(d.glob("*.json"))] if d.exists() else []
