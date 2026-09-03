import os
import sys
import time
import requests

from publish_tiktok import refresh_access_token


UPLOAD_INIT_URL = (
    "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"
)

STATUS_URL = (
    "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
)


def required_env(name):
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(f"Nedostaje varijabla: {name}")

    return value


def parse_tiktok_response(response, action):
    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError(
            f"{action}: TikTok nije vratio JSON. "
            f"HTTP {response.status_code}"
        )

    error = payload.get("error", {})
    code = error.get("code", "unknown")

    if not response.ok or code != "ok":
        message = error.get("message", "Nema dodatnog opisa.")
        log_id = error.get("log_id", "")

        raise RuntimeError(
            f"{action}: {code} - {message} - log_id={log_id}"
        )

    return payload


def initialize_draft(access_token, video_url):
    response = requests.post(
        UPLOAD_INIT_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url,
            }
        },
        timeout=30,
    )

    payload = parse_tiktok_response(
        response,
        "Pokretanje TikTok draft uploada"
    )

    publish_id = payload.get("data", {}).get("publish_id")

    if not publish_id:
        raise RuntimeError(
            "TikTok nije vratio publish_id."
        )

    return publish_id


def get_status(access_token, publish_id):
    response = requests.post(
        STATUS_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={
            "publish_id": publish_id
        },
        timeout=30,
    )

    payload = parse_tiktok_response(
        response,
        "TikTok status"
    )

    return payload.get("data", {})


def main():
    video_url = required_env("TIKTOK_VIDEO_URL")

    print("=== TimeMachineGarage TikTok DRAFT test ===")
    print("")
    print("Video:")
    print(video_url)
    print("")

    print("1) Osvjezavam TikTok access token...")

    token_data = refresh_access_token()
    access_token = token_data["access_token"]

    print("   OAuth: OK")

    if token_data["refresh_rotated"]:
        print(
            "   UPOZORENJE: TikTok je vratio novi refresh token."
        )
    else:
        print("   Refresh token nije promijenjen.")

    print("")
    print("2) Saljem zahtjev za TikTok draft...")

    publish_id = initialize_draft(
        access_token,
        video_url
    )

    print("   TikTok je prihvatio zahtjev.")
    print("   Publish ID je dobiven.")
    print("")

    print("3) Cekam da TikTok obradi video...")

    for attempt in range(1, 21):
        status_data = get_status(
            access_token,
            publish_id
        )

        status = status_data.get(
            "status",
            "UNKNOWN"
        )

        print(
            f"   Provjera {attempt}/20 -> {status}"
        )

        if status == "SEND_TO_USER_INBOX":
            print("")
            print("=== DRAFT USPJESNO POSLAN ===")
            print(
                "TikTok bi sada trebao prikazati "
                "obavijest u korisnickom inboxu."
            )
            print(
                "Otvori TikTok aplikaciju i tamo "
                "dovrsi uređivanje/objavu."
            )
            return

        if status == "PUBLISH_COMPLETE":
            print("")
            print("=== TIKTOK OBRADA ZAVRSENA ===")
            return

        if status == "FAILED":
            reason = status_data.get(
                "fail_reason",
                "Nepoznat razlog"
            )

            raise RuntimeError(
                f"TikTok obrada nije uspjela: {reason}"
            )

        time.sleep(15)

    print("")
    print(
        "TikTok jos obrađuje video. "
        "Provjeri TikTok inbox za nekoliko minuta."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("")
        print(f"GRESKA: {exc}")
        sys.exit(1)
