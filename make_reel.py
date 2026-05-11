#!/usr/bin/env python3
"""
るーにゃ リール動画生成スクリプト
5枚の画像から 9:16（1080x1920）縦型リール動画を生成する
ffmpeg でリサイズ・テキストオーバーレイ・クリップ結合を行う
"""

import subprocess
from pathlib import Path

DIR    = Path("./first_post")
CLIPS  = DIR / "clips"
OUTPUT = DIR / "reel_final.mp4"
CLIPS.mkdir(exist_ok=True)

W, H = 1080, 1920                           # 9:16 Instagram Reel
FONT = "C\\:/Windows/Fonts/meiryo.ttc"      # ffmpeg 用 Windows パス

# ─── シーン定義 ────────────────────────────────────────────────
# texts: (テキスト, y位置比率, フォントサイズ, 文字色)
SCENES = [
    {"image": DIR / "scene1_back_cafe.png",    "duration": 3,  "clip": CLIPS / "clip1.mp4"},
    {"image": DIR / "scene2_table_coffee.png", "duration": 5,  "clip": CLIPS / "clip2.mp4"},
    {"image": DIR / "scene3_window_city.png",  "duration": 7,  "clip": CLIPS / "clip3.mp4"},
    {"image": DIR / "scene4_side_profile.png", "duration": 5,  "clip": CLIPS / "clip4.mp4"},
    {"image": DIR / "scene5_endcard.png",      "duration": 3,  "clip": CLIPS / "clip5.mp4"},
]


def make_clip(scene: dict) -> bool:
    """1シーンを ffmpeg でクリップ化（9:16リサイズ・無音トラック付き）"""
    img  = scene["image"]
    clip = scene["clip"]
    dur  = scene["duration"]

    if not img.exists():
        print(f"  ❌ 画像なし: {img.name}")
        return False

    # 9:16 にリサイズ・クロップ（Instagram Reel 仕様）
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(img),
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",  # 無音トラック
        "-t", str(dur),
        "-vf", vf,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-shortest",
        str(clip),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode == 0:
        print(f"  ✅ クリップ生成: {clip.name} ({dur}秒)")
        return True
    else:
        print(f"  ❌ 失敗: {clip.name}")
        print(result.stderr[-500:])
        return False


def concat_clips(clips: list[Path]) -> bool:
    """ffmpeg concat で全クリップを結合"""
    list_file = CLIPS / "filelist.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in clips),
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(OUTPUT),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode == 0:
        size_mb = OUTPUT.stat().st_size / 1024 / 1024
        print(f"✅ リール完成: {OUTPUT}  ({size_mb:.1f} MB)")
        return True
    else:
        print(f"❌ concat 失敗:\n{result.stderr[-500:]}")
        return False


def main():
    print("=" * 50)
    print("🎬 るーにゃ リール動画生成")
    print(f"   解像度: {W}x{H}  /  出力: {OUTPUT.name}")
    print("=" * 50)

    clips = []
    for i, scene in enumerate(SCENES, 1):
        print(f"\n[シーン {i}/5]")
        ok = make_clip(scene)
        if ok:
            clips.append(scene["clip"])

    print(f"\n[結合] {len(clips)}/5 クリップ")
    if not clips:
        print("❌ クリップがありません")
        return

    concat_clips(clips)
    print("=" * 50)


if __name__ == "__main__":
    main()
