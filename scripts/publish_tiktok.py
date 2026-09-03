import os
import sys
import requests


TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
CREATOR_INFO_URL = (
    "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
)


def required_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Nedostaje GitHub secret: {name}")
    return value


def refresh_access_token():
    client_key = required_env("TIKTOK_CLIENT_KEY")
    client_secret = required_env("TIKTOK_CLIENT_SECRET")
    refresh_token = required_env("TIKTOK_REFRESH_TOKEN")

    response = requests.post(
        TOKEN_URL,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Cache-Control": "no-cache",
        },
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            f"TikTok OAuth nije vratio JSON. HTTP {response.status_code}"
        )

    if not response.ok or not data.get("access_token"):
        error = data.get("error", "unknown_error")
        description = data.get(
            "error_description",
            data.get("message", "Nema dodatnog opisa.")
        )
        raise RuntimeError(
            f"TikTok OAuth greska: {error} - {description}"
        )

    new_refresh_token = data.get("refresh_token", "")
    refresh_rotated = (
        bool(new_refresh_token)
        and new_refresh_token != refresh_token
    )

    return {
        "access_token": data["access_token"],
        "scope": data.get("scope", ""),
        "refresh_rotated": refresh_rotated,
    }


def query_creator_info(access_token):
    response = requests.post(
        CREATOR_INFO_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        },
        json={},
        timeout=30,
    )

    try:
        payload = response.json()
    except ValueError:
        raise RuntimeError(
            f"Creator Info nije vratio JSON. HTTP {response.status_code}"
        )

    error = payload.get("error", {})
    error_code = error.get("code", "unknown")

    if not response.ok or error_code != "ok":
        message = error.get("message", "Nema dodatnog opisa.")
        log_id = error.get("log_id", "")
        raise RuntimeError(
            f"TikTok Creator Info greska: "
            f"{error_code} - {message} - log_id={log_id}"
        )

    return payload.get("data", {})


def main():
    print("=== TimeMachineGarage TikTok Sandbox test ===")
    print("1) Provjeravam OAuth i osvjezavam access token...")

    token_data = refresh_access_token()

    print("   OAuth: OK")
    print(f"   Scopeovi: {token_data['scope']}")

    if token_data["refresh_rotated"]:
        print(
            "   UPOZORENJE: TikTok je vratio novi refresh token."
        )
        print(
            "   Token nije ispisan. Prije pune automatizacije "
            "rijesit cemo njegovo sigurno spremanje."
        )
    else:
        print("   Refresh token nije promijenjen.")

    print("")
    print("2) Provjeravam TikTok Creator Info...")

    creator = query_creator_info(token_data["access_token"])

    privacy_options = creator.get("privacy_level_options", [])
    max_duration = creator.get("max_video_post_duration_sec", "N/A")

    print("   Creator Info: OK")
    print(
        "   Dostupne privacy opcije: "
        + ", ".join(privacy_options)
    )
    print(f"   Maksimalno trajanje videa: {max_duration} s")

    print("")
    print("=== TEST USPJESAN ===")
    print("Nijedan video nije objavljen na TikTok.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("")
        print(f"GRESKA: {exc}")
        sys.exit(1)
