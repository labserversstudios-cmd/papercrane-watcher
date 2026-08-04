import json
import os
import re
import urllib.request

URL = "https://papercranewholesale.com/"
TOPIC = os.environ.get("NTFY_TOPIC") or "CHANGE-ME"
SEEN_FILE = "seen.json"

# Every lot link looks like /shop/<slug>-<uuid>
LOT_RE = re.compile(
    r"/shop/([a-z0-9\-]+?)-"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


def fetch_lots():
    req = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; lot-watcher/1.0)"},
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    return {uid: slug for slug, uid in LOT_RE.findall(html)}


def notify(title, body, url):
    req = urllib.request.Request(
        "https://ntfy.sh/" + TOPIC,
        data=body.encode("utf-8"),
        headers={"Title": title, "Click": url, "Tags": "shirt"},
    )
    urllib.request.urlopen(req, timeout=15).read()


def pretty(slug):
    return slug.replace("-", " ").strip().title()


def link(slug, uid):
    return "https://papercranewholesale.com/shop/{}-{}".format(slug, uid)


lots = fetch_lots()
if not lots:
    raise SystemExit("No lots found. Page layout probably changed.")

try:
    with open(SEEN_FILE) as f:
        seen = set(json.load(f))
    first_run = False
except (FileNotFoundError, json.JSONDecodeError):
    seen = set()
    first_run = True

new = [uid for uid in lots if uid not in seen]

if first_run:
    print("First run: seeding {} lots, no alerts sent.".format(len(lots)))
elif len(new) > 8:
    # A big drop landed. One summary instead of 30 buzzes.
    notify(
        "PaperCrane: {} new lots".format(len(new)),
        "Big drop just went up. Tap to browse.",
        URL,
    )
    print("ALERT: bulk drop of {} lots".format(len(new)))
else:
    for uid in new:
        slug = lots[uid]
        notify("New PaperCrane lot", pretty(slug), link(slug, uid))
        print("ALERT: {}".format(pretty(slug)))

with open(SEEN_FILE, "w") as f:
    json.dump(sorted(lots), f, indent=0)

print("{} lots live, {} new this run.".format(len(lots), len(new)))
