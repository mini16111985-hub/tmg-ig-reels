import json
import os
import time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "reels.json"
POSTED_FILE = ROOT / "config" / "posted_reels.json"

IG_USER_ID = os.environ["IG_USER_ID"]
IG_ACCESS_TOKEN = os.environ["IG_ACCESS_TOKEN"]
GITHUB_PAGES_BASE = os.environ["GITHUB_PAGES_BASE"]

API_VERSION = "v23.0"

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def pick_next_reel():
    reels = load_json(CONFIG_FILE)
    posted = set(load_json(POSTED_FILE))
    for reel in reels:
        if reel["slug"] not in posted:
            return reel
    return None

def create_container(video_url, caption):
    url = f"https://graph.facebook.com/{API_VERSION}/{IG_USER_ID}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN,
    }
    r = requests.post(url, data=payload, timeout=60)
    r.raise_for_status()
    return r.json()["id"]

def wait_until_ready(container_id, tries=20, delay=20):
    url = f"https://graph.facebook.com/{API_VERSION}/{container_id}"
    params = {
        "fields": "status_code",
        "access_token": IG_ACCESS_TOKEN
    }
    for _ in range(tries):
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        status = r.json().get("status_code")
        print("Container status:", status)
        if status == "FINISHED":
            return
        if status == "ERROR":
            raise RuntimeError("Instagram processing returned ERROR")
        time.sleep(delay)
    raise TimeoutError("Container not ready in time")

def publish_container(container_id):
    url = f"https://graph.facebook.com/{API_VERSION}/{IG_USER_ID}/media_publish"
    payload = {
        "creation_id": container_id,
        "access_token": IG_ACCESS_TOKEN,
    }
    r = requests.post(url, data=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def main():
    reel = pick_next_reel()
    if not reel:
        print("No reels left to publish.")
        return

    slug = reel["slug"]
    video_url = f"{GITHUB_PAGES_BASE}/reels/generated/{slug}.mp4"

    container_id = create_container(video_url, reel["caption"])
    wait_until_ready(container_id)
    result = publish_container(container_id)
    print("Published:", result)

    posted = load_json(POSTED_FILE)
    posted.append(slug)
    save_json(POSTED_FILE, posted)

if __name__ == "__main__":
    main()
