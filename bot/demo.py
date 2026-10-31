"""Canned model answers for MOGUL_DEMO=1: run the whole pipeline offline.

All venues are fictional placeholders (sources point at example.com). Never deploy demo pages.
"""
import json
import random
import re

WORDS = ["Pelican", "Mangrove", "Tarpon", "Sandbar", "Heron", "Driftwood", "Coquina", "Sunset",
         "Palmetto", "Osprey", "Gulfside", "Seagrape", "Banyan", "Manatee", "Citrus", "Coral"]
KINDS = ["Grill", "Tavern", "Brewing Co", "Raw Bar", "Cafe", "Social Hall", "Tiki Bar", "Bistro"]


def answer(prompt):
    if "collect" in prompt and "venues that fit" in prompt:
        return json.dumps(research(re.search(r'Page: "(.+?)"', prompt).group(1)))
    if "Write a short guide" in prompt:
        title = re.search(r'titled "(.+?)"', prompt).group(1)
        records = json.loads(prompt.split("fact not present in it:\n", 1)[1].split("\nStructure", 1)[0])
        return body(title, records)
    raise ValueError("demo has no canned answer for this prompt")


def research(title):
    rng = random.Random(title)
    records = []
    for _ in range(rng.randint(6, 8)):
        name = f"[Demo] {rng.choice(WORDS)} {rng.choice(KINDS)}"
        slug = re.sub("[^a-z]+", "-", name.lower()).strip("-")
        records.append({
            "name": name, "location": f"{rng.randint(100, 999)} Example Ave",
            "facts": {
                "music_nights": rng.choice(["Thu-Sat 6-9pm", "Fri-Sun 7-10pm", "Wed jazz 6:30-9:30pm",
                                            "Daily 5-8pm", "Sun brunch 11am-2pm"]),
                "genres": rng.choice(["Jazz", "Blues, classic rock", "Acoustic covers", "Country", "Reggae"]),
                "cover": rng.choice(["Free", "$10", "unknown"]),
                "setting": rng.choice(["waterfront", "outdoor", "indoor", "mixed"]),
                "venue_type": rng.choice(["restaurant", "bar", "brewery"]),
                "food": rng.choice(["full menu", "bar food"]), "ages": rng.choice(["all ages", "21+"]),
                "area": rng.choice(["Downtown", "On the beach", "Old town"]),
                "tags": rng.sample(["date night", "family friendly", "waterfront", "no cover", "dinner menu",
                                    "made-up tag"], 2),
            },
            "website": f"https://example.com/demo/{slug}",
            "phone": f"(555) {rng.randint(200, 999)}-{rng.randint(1000, 9999)}",
            "source": f"https://example.com/demo/{slug}/music",
        })
    return {"description": f"{len(records)} venues for {title.lower()}, with music nights, cover and "
                           "setting checked on each venue's own site.", "records": records}


def body(title, records):
    lines = [f"Planning a night out? These {len(records)} venues have live music on a regular schedule, "
             "and each schedule below comes from the venue's own website.", "",
             "## By night of the week", ""]
    lines += [f"- **{r['name']}**: {r['facts']['music_nights']} ({r['facts']['genres'].lower()})." for r in records]
    free = [r["name"] for r in records if r["facts"]["cover"] == "Free"]
    lines += ["", "## At a glance", "",
              f"- **No cover listed:** {', '.join(free) or 'none of the venues checked'}.",
              f"- **Waterfront settings:** {', '.join(r['name'] for r in records if r['facts']['setting'] == 'waterfront') or 'none'}.",
              "", "## Before you go", ""]
    lines += [f"- {r['name']} serves {r['facts']['food']} and is {r['facts']['ages']}; it is a "
              f"{r['facts']['venue_type']} with {r['facts']['setting']} seating." for r in records]
    lines += ["- Schedules change with the season, so check the venue's own page the day you go.",
              "- Weekend nights fill up early in winter and spring, when visitors are in town; arrive "
              "before the first set if you want a table near the band.",
              "- Outdoor and waterfront stages may move inside or cancel for summer storms, which "
              "usually roll through in the late afternoon and clear by evening.",
              "- Parking near the water and downtown fills quickly on music nights, so allow extra "
              "time, share a ride, or check whether the venue lists nearby lots on its own site.",
              "", "## FAQ", "", "### Do I need a reservation?",
              "For dinner on a music night, calling ahead is a good idea, especially on weekends.",
              "", "### Is there a cover charge?",
              "Most venues listed here state no cover; any listed cover is shown in the table.",
              "", "### Are kids welcome?",
              "Venues marked all ages welcome families; the ones marked 21+ do not."]
    return "\n".join(lines)
