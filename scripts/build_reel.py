import json
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
CONFIG_FILE = ROOT / "config" / "reels.json"
OUTPUT_DIR = ROOT / "reels" / "generated"
AUDIO_FILE = ROOT / "audio" / "background_music.mp3"

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
FPS = 30

# Stari format ostaje podržan
LEGACY_IMAGE_DURATION = 3
LEGACY_TOTAL_IMAGES = 4

# TMG Reels v2
# Slika 1 -> Slika 2 -> Slika 3 -> Slika 4 -> ponovno Slika 1
V2_DURATIONS = [1.5, 1.8, 2.1, 2.6, 2.0]
V2_IMAGE_ORDER = [0, 1, 2, 3, 0]


def load_config(slug: str):
    data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

    for item in data:
        if item["slug"] == slug:
            return item

    raise ValueError(f"Slug not found: {slug}")


def escape_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .replace("%", "\\%")
        .replace("\n", "\\n")
    )


def run_cmd(cmd):
    print("RUNNING:", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, check=True)


def build_v2_plan(cfg, images):
    if len(images) < 4:
        raise SystemExit(
            "TMG Reels v2 needs at least 4 PNG images."
        )

    text_lines = cfg.get("text_lines", [])

    if len(text_lines) < 3:
        raise SystemExit(
            "TMG Reels v2 needs at least 3 text_lines entries in reels.json."
        )

    hook = cfg["hook"]

    series = cfg.get(
        "series",
        "FORGOTTEN JDM LEGENDS"
    )

    cta = cfg.get(
        "cta",
        "FOLLOW @TIMEMACHINEGARAGE"
    )

    segment_images = [
        images[i]
        for i in V2_IMAGE_ORDER
    ]

    segment_texts = [
        hook,
        text_lines[0],
        text_lines[1],
        text_lines[2],
        f"{series}\n{cta}",
    ]

    font_sizes = [
        72,
        64,
        64,
        60,
        58,
    ]

    return (
        segment_images,
        V2_DURATIONS,
        segment_texts,
        font_sizes,
    )


def build_legacy_plan(cfg, images):
    if len(images) < LEGACY_TOTAL_IMAGES:
        raise SystemExit(
            f"Need at least {LEGACY_TOTAL_IMAGES} images for the legacy reel."
        )

    segment_images = images[:LEGACY_TOTAL_IMAGES]

    durations = [
        LEGACY_IMAGE_DURATION
    ] * LEGACY_TOTAL_IMAGES

    segment_texts = cfg["text_lines"][
        :LEGACY_TOTAL_IMAGES
    ]

    font_sizes = [
        58
    ] * len(segment_texts)

    return (
        segment_images,
        durations,
        segment_texts,
        font_sizes,
    )


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python scripts/build_reel.py <slug>"
        )

    slug = sys.argv[1]

    cfg = load_config(slug)

    image_dir = ASSETS_DIR / slug

    images = sorted(
        image_dir.glob("*.png")
    )

    # Ako JSON ima "hook",
    # koristi novi TMG Reels v2 format.
    # Ako nema, koristi stari format.
    is_v2 = bool(
        cfg.get("hook")
    )

    if is_v2:
        (
            segment_images,
            durations,
            texts,
            font_sizes,
        ) = build_v2_plan(
            cfg,
            images,
        )

    else:
        (
            segment_images,
            durations,
            texts,
            font_sizes,
        ) = build_legacy_plan(
            cfg,
            images,
        )

    total_duration = sum(
        durations
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_video = (
        OUTPUT_DIR
        / f"{slug}_temp.mp4"
    )

    output_file = (
        OUTPUT_DIR
        / f"{slug}.mp4"
    )

    concat_file = (
        ROOT
        / "images.txt"
    )

    lines = []

    for img, duration in zip(
        segment_images,
        durations,
    ):
        lines.append(
            f"file '{img.as_posix()}'"
        )

        lines.append(
            f"duration {duration}"
        )

    # FFmpeg concat zahtijeva
    # ponavljanje zadnje slike
    lines.append(
        f"file '{segment_images[-1].as_posix()}'"
    )

    concat_file.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    drawtexts = []

    start = 0.0

    for (
        txt,
        duration,
        fontsize,
    ) in zip(
        texts,
        durations,
        font_sizes,
    ):

        end = start + duration

        drawtexts.append(
            "drawtext="
            f"text='{escape_text(txt)}':"
            "fontcolor=white:"
            f"fontsize={fontsize}:"
            "line_spacing=10:"
            "box=1:"
            "boxcolor=black@0.48:"
            "boxborderw=22:"
            "x=(w-text_w)/2:"
            "y=h-500:"
            f"enable='between(t,{start:.2f},{end - 0.01:.2f})'"
        )

        start = end

    vf_parts = [
        (
            f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
            "force_original_aspect_ratio=decrease"
        ),
        (
            f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:"
            "(ow-iw)/2:(oh-ih)/2:black"
        ),
        "format=yuv420p",
        *drawtexts,
    ]

    vf = ",".join(
        vf_parts
    )

    cmd_video = [
        "ffmpeg",
        "-y",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        str(concat_file),

        "-vf",
        vf,

        "-t",
        str(total_duration),

        "-r",
        str(FPS),

        "-c:v",
        "libx264",

        "-profile:v",
        "high",

        "-level:v",
        "4.1",

        "-pix_fmt",
        "yuv420p",

        "-preset",
        "medium",

        "-crf",
        "20",

        "-movflags",
        "+faststart",

        "-an",

        str(temp_video),
    ]

    run_cmd(
        cmd_video
    )

    cmd_final = [
        "ffmpeg",
        "-y",

        "-i",
        str(temp_video),

        "-stream_loop",
        "-1",

        "-i",
        str(AUDIO_FILE),

        "-map",
        "0:v:0",

        "-map",
        "1:a:0",

        "-t",
        str(total_duration),

        "-c:v",
        "libx264",

        "-profile:v",
        "high",

        "-level:v",
        "4.1",

        "-pix_fmt",
        "yuv420p",

        "-preset",
        "medium",

        "-crf",
        "20",

        "-c:a",
        "aac",

        "-b:a",
        "192k",

        "-ar",
        "44100",

        "-ac",
        "2",

        "-movflags",
        "+faststart",

        str(output_file),
    ]

    run_cmd(
        cmd_final
    )

    print(
        f"Built: {output_file}"
    )

    print(
        "Format:",
        (
            "TMG Reels v2"
            if is_v2
            else "legacy"
        ),
    )


if __name__ == "__main__":
    main()
