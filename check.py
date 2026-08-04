import json
import os
import re
import subprocess
import time
import urllib.request

URL = "https://papercranewholesale.com/"
SEEN_FILE = "seen.json"
INTERVAL = 60      # seconds between checks
RUN_MINUTES = 70   # how long this job stays alive

LOT_RE = re.compile(
    r"/shop/([a-z0-9\-]+?)-"
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
)


def clean_topic(raw):
    t = (raw or "").strip()
    for junk in ("https://", "http://", "ntfy.sh/"):
        if t.startswith(junk):
            t = t[len(junk):]
    return t.strip("/").strip()


TOPIC = clean_topic(os.environ.get("NTFY_TOPIC"))
if not TOPIC:
    raise SystemExit("NTFY_TOPIC secret is empty or missing.")


def fetch_lots():
    req = urllib.request.Request(
        URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; lot-watcher/1.0)"},
    )
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    return {uid: slug for slug, uid in LOT_RE.findall(html)}


def notify(title, body, url):
    payload = json.dumps(
        {
            "topic": TOPIC,
            "title": title,
            "message": body,
            "click": url,
            "tags": ["shirt"],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://ntfy.sh/",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=15).read()


def pretty(slug):
    return slug.replace("-", " ").strip().title()


def link(slug, uid):
    return "https://papercranewholesale.com/shop/{}-{}".format(slug, uid)


def save_and_push(ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(ids), f, indent=0)
    try:
        subprocess.run(["git", "add", SEEN_FILE], check=True)
        subprocess.run(["git", "commit", "-m", "update seen lots"], check=True)
        subprocess.run(["git", "pull", "--rebase"], check=True)
        subprocess.run(["git", "push"], check=True)
    except subprocess.CalledProcessError as err:
        print("git step failed, retrying next time:", err)


try:
    with open(SEEN_FILE) as f:
        seen = set(json.load(f))
    seeding = False
except (FileNotFoundError, json.JSONDecodeError):
    seen = set()
    seeding = True

deadline = time.time() + RUN_MINUTES * 60
checks = 0

while time.time() < deadline:
    checks += 1
    try:
        lots = fetch_lots()
    except Exception as err:
        print("check {} failed: {}".format(checks, err))
        time.sleep(INTERVAL)
        continue

    if not lots:
        print("check {}: nothing parsed, layout may have changed".format(checks))
        time.sleep(INTERVAL)
        continue

    new = [uid for uid in lots if uid not in seen]

    if seeding:
        print("Seeding {} lots, no alerts sent.".format(len(lots)))
    elif new:
        try:
            if len(new) > 8:
                notify(
                    "PaperCrane: {} new lots".format(len(new)),
                    "Big drop just went up. Tap to browse.",
                    URL,
                )
            else:
                for uid in new:
                    notify("New PaperCrane lot", pretty(lots[uid]), link(lots[uid], uid))
            print("ALERTED on {} new lot(s)".format(len(new)))
        except Exception as err:
            print("notify failed, will retry:", err)
            time.sleep(INTERVAL)
            continue

    if new or seeding:
        seen.update(lots)
        save_and_push(seen)
        seeding = False

    print("check {}: {} live, {} new".format(checks, len(lots), len(new)))
    time.sleep(INTERVAL)

print("Run finished after {} checks.".format(checks))
