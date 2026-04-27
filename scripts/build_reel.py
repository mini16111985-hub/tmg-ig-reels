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
IMAGE_DURATION = 3
TOTAL_IMAGES = 4
TOTAL_DURATION = IMAGE_DURATION * TOTAL_IMAGES


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
    )


def run_cmd(cmd):
    print("RUNNING:", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, check=True)


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/build_reel.py <slug>")

    slug = sys.argv[1]
    cfg = load_config(slug)

    image_dir = ASSETS_DIR / slug
    images = sorted(image_dir.glob("*.png"))

    if len(images) < TOTAL_IMAGES:
        raise SystemExit(f"Need at least {TOTAL_IMAGES} images in {image_dir}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    temp_video = OUTPUT_DIR / f"{slug}_temp.mp4"
    output_file = OUTPUT_DIR / f"{slug}.mp4"
    concat_file = ROOT / "images.txt"

    selected_images = images[:TOTAL_IMAGES]

    lines = []
    for img in selected_images:
        lines.append(f"file '{img.as_posix()}'")
        lines.append(f"duration {IMAGE_DURATION}")
    lines.append(f"file '{selected_images[-1].as_posix()}'")

    concat_file.write_text("\n".join(lines), encoding="utf-8")

    texts = cfg["text_lines"][:TOTAL_IMAGES]

    drawtexts = []
    for i, txt in enumerate(texts):
        start = i * IMAGE_DURATION
        end = start + IMAGE_DURATION
        drawtexts.append(
            "drawtext="
            f"text='{escape_text(txt)}':"
            "fontcolor=white:"
            "fontsize=58:"
            "line_spacing=8:"
            "box=1:"
            "boxcolor=black@0.40:"
            "boxborderw=20:"
            "x=(w-text_w)/2:"
            "y=h-430:"
            f"enable='between(t,{start},{end - 0.01})'"
        )

    vf_parts = [
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease",
        f"pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2:black",
        "format=yuv420p",
        *drawtexts,
    ]
    vf = ",".join(vf_parts)

    cmd_video = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-vf", vf,
        "-t", str(TOTAL_DURATION),
        "-r", str(FPS),
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level:v", "4.1",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "20",
        "-movflags", "+faststart",
        "-an",
        str(temp_video),
    ]

    run_cmd(cmd_video)

    cmd_final = [
        "ffmpeg",
        "-y",
        "-i", str(temp_video),
        "-stream_loop", "-1",
        "-i", str(AUDIO_FILE),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", str(TOTAL_DURATION),
        "-c:v", "libx264",
        "-profile:v", "high",
        "-level:v", "4.1",
        "-pix_fmt", "yuv420p",
        "-preset", "medium",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        "-movflags", "+faststart",
        str(output_file),
    ]

    run_cmd(cmd_final)

    print(f"Built: {output_file}")


if __name__ == "__main__":
    main()
