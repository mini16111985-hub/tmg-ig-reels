import json
import subprocess
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
CONFIG_FILE = ROOT / "config" / "reels.json"
OUTPUT_DIR = ROOT / "reels" / "generated"
AUDIO_FILE = ROOT / "audio" / "background_music.mp3"

def load_config(slug: str):
    data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    for item in data:
        if item["slug"] == slug:
            return item
    raise ValueError(f"Slug not found: {slug}")

def escape_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/build_reel.py <slug>")

    slug = sys.argv[1]
    cfg = load_config(slug)

    image_dir = ASSETS_DIR / slug
    images = sorted(image_dir.glob("*.png"))
    if len(images) < 4:
        raise SystemExit(f"Need at least 4 images in {image_dir}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    temp_video = OUTPUT_DIR / f"{slug}_temp.mp4"
    output_file = OUTPUT_DIR / f"{slug}.mp4"

    concat_file = ROOT / "images.txt"
    lines = []
    for img in images[:4]:
        lines.append(f"file '{img.as_posix()}'")
        lines.append("duration 3")
    lines.append(f"file '{images[3].as_posix()}'")
    concat_file.write_text("\n".join(lines), encoding="utf-8")

    texts = cfg["text_lines"][:4]
    drawtexts = []
    for i, txt in enumerate(texts):
        start = i * 3
        end = start + 3
        drawtexts.append(
           "drawtext="
           f"text='{escape_text(txt)}':"
           "fontcolor=white:fontsize=56:"
           "box=1:boxcolor=black@0.35:boxborderw=18:"
           "x=(w-text_w)/2:y=h-430:"
           f"enable='gte(t,{start})*lt(t,{end})'"
        )

    vf = ",".join([
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        *drawtexts
    ])

    cmd_video = [
        "ffmpeg",
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-vf", vf,
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        str(temp_video)
    ]

    subprocess.run(cmd_video, check=True)

    cmd_final = [
        "ffmpeg",
        "-y",
        "-i", str(temp_video),
        "-stream_loop", "-1",
        "-i", str(AUDIO_FILE),
        "-shortest",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_file)
    ]

    subprocess.run(cmd_final, check=True)
    print(f"Built: {output_file}")

if __name__ == "__main__":
    main()
