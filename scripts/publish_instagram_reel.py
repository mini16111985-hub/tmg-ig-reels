import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "reels.json"
POSTED_FILE = ROOT / "config" / "posted_reels.json"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def pick_next_slug():
    reels = load_json(CONFIG_FILE)
    posted = set(load_json(POSTED_FILE))
    reel_map = {item["slug"]: item for item in reels}

    assets_dir = ROOT / "assets"
    available_slugs = sorted([p.name for p in assets_dir.iterdir() if p.is_dir()])

    for slug in available_slugs:
        if slug in reel_map and slug not in posted:
            return reel_map[slug]

    return None


def create_container(video_url: str, caption: str, ig_user_id: str, access_token: str):
    url = f"https://graph.facebook.com/v23.0/{ig_user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": "true",
        "access_token": access_token,
    }

    r = requests.post(url, data=payload, timeout=120)
    print("CREATE CONTAINER STATUS:", r.status_code)
    print("CREATE CONTAINER RESPONSE:", r.text)
    r.raise_for_status()
    return r.json()["id"]


def wait_until_ready(container_id: str, access_token: str, max_attempts: int = 20, delay: int = 15):
    url = f"https://graph.facebook.com/v23.0/{container_id}"
    params = {
        "fields": "status_code,status,error_message",
        "access_token": access_token,
    }

    for attempt in range(1, max_attempts + 1):
        r = requests.get(url, params=params, timeout=120)
        print(f"STATUS CHECK #{attempt}: {r.status_code}")
        print("STATUS RESPONSE:", r.text)
        r.raise_for_status()

        data = r.json()
        status = data.get("status_code")
        print("container status:", status)

        if status == "FINISHED":
            return

        if status == "ERROR":
            error_message = data.get("error_message") or data.get("status") or str(data)
            raise RuntimeError(f"Instagram processing returned ERROR: {error_message}")

        time.sleep(delay)

    raise TimeoutError("Instagram container was not ready in time.")


def publish_container(container_id: str, ig_user_id: str, access_token: str):
    url = f"https://graph.facebook.com/v23.0/{ig_user_id}/media_publish"
    payload = {
        "creation_id": container_id,
        "access_token": access_token,
    }

    r = requests.post(url, data=payload, timeout=120)
    print("PUBLISH STATUS:", r.status_code)
    print("PUBLISH RESPONSE:", r.text)
    r.raise_for_status()
    return r.json()


def main():
    access_token = os.environ["IG_ACCESS_TOKEN"]
    ig_user_id = os.environ["IG_USER_ID"]
    github_pages_base = os.environ["GITHUB_PAGES_BASE"].rstrip("/")

    reel = pick_next_slug()
    if not reel:
        print("No reel left to publish.")
        return

    slug = reel["slug"]
    caption = reel["caption"]
    video_url = f"{github_pages_base}/reels/generated/{slug}.mp4"

    print("SELECTED SLUG:", slug)
    print("VIDEO URL:", video_url)

    container_id = create_container(video_url, caption, ig_user_id, access_token)
    wait_until_ready(container_id, access_token)
    publish_container(container_id, ig_user_id, access_token)

    posted = load_json(POSTED_FILE)
    if slug not in posted:
        posted.append(slug)
        save_json(POSTED_FILE, posted)

    print(f"Published: {slug}")


if __name__ == "__main__":
    main()
