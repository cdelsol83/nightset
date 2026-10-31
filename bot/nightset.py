"""Nightset command line. See ../README.md.

  python nightset.py build           re-check one stale guide, research + publish new ones, render site/
  python nightset.py render          re-render site/ from data/ without calling the model
  python nightset.py report [week]   send the report to Telegram
  python nightset.py status          what's configured and what's in the pipeline
"""
import sys

import builder
import config
import render
import reporter
import store
import telegram


def status():
    topics = builder.sync_topics(store.load("topics.json", []))
    checks = {
        "xAI key": "set" if config.XAI_API_KEY else "MISSING",
        "Telegram": "set" if telegram.enabled() else "not set",
        "analytics": "set" if config.CLOUDFLARE_ANALYTICS_TOKEN else "not set",
        "guides live": len(store.pages()),
        "venues": len(render.venues(store.pages())),
        "topics queued": sum(t["status"] == "queued" for t in topics),
    }
    for k, v in checks.items():
        print(f"{k:>14}: {v}")


def main(argv):
    cmd = argv[1].strip().lower() if len(argv) > 1 else "status"
    if cmd == "build":
        results = builder.run()
        n = render.build()
        for r in results:
            print(r)
            if r["action"] in ("published", "refreshed"):
                telegram.send(f"🎶 Nightset {r['action']}: {r['title']} ({r['records']} venues)")
            elif r["action"] == "rejected":
                telegram.send(f"🚫 Nightset skipped \"{r['title']}\": " + "; ".join(r["reasons"])[:600])
        print(f"site/ rendered with {n} guides")
    elif cmd == "render":
        print(f"site/ rendered with {render.build()} guides")
    elif cmd == "report":
        print(reporter.report("week" if argv[2:3] == ["week"] else "day"))
    elif cmd == "status":
        status()
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
