#!/usr/bin/env python3
"""
るーにゃ 最初の投稿 リール動画生成スクリプト
ElevenLabs でシーンごとに動画化 → ffmpeg で1本のリールに結合する
"""

import os
import time
import subprocess
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
HEADERS = {"xi-api-key": ELEVENLABS_API_KEY}

FIRST_POST_DIR = Path("./first_post")
CLIPS_DIR = FIRST_POST_DIR / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_REEL = FIRST_POST_DIR / "reel_final.mp4"

# シーン定義（画像・アニメーションプロンプト・尺）
SCENES = [
    {
        "image":    FIRST_POST_DIR / "scene1_back_cafe.png",
        "clip_out": CLIPS_DIR / "clip1.mp4",
        "prompt":   (
            "A young woman sitting alone at a cafe window seat, seen from behind. "
            "Slow gentle camera drift forward. Soft natural light through the window. "
            "Calm and slightly lonely atmosphere. Cinematic, Instagram reel style."
        ),
        "duration": 5,
    },
    {
        "image":    FIRST_POST_DIR / "scene2_table_coffee.png",
        "clip_out": CLIPS_DIR / "clip2.mp4",
        "prompt":   (
            "Close-up of a cafe table with latte art and open notebook. "
            "Gentle steam rising from the coffee cup, subtle camera tilt down. "
            "Warm cozy mood. Cinematic, Instagram aesthetic."
        ),
        "duration": 4,
    },
    {
        "image":    FIRST_POST_DIR / "scene3_window_city.png",
        "clip_out": CLIPS_DIR / "clip3.mp4",
        "prompt":   (
            "View through a cafe window, blurred Tokyo street outside. "
            "Slow zoom out, people passing by outside the window. "
            "Golden hour light, melancholic yet beautiful. Cinematic style."
        ),
        "duration": 4,
    },
    {
        "image":    FIRST_POST_DIR / "scene4_side_profile.png",
        "clip_out": CLIPS_DIR / "clip4.mp4",
        "prompt":   (
            "A young woman turning slightly toward camera with a soft, gentle expression. "
            "Slow smooth zoom in toward her face. Warm window light. "
            "Intimate selfie-style feel. Instagram reel style."
        ),
        "duration": 5,
    },
]


def request_video(scene: dict) -> str | None:
    """ElevenLabs に動画生成リクエストを送信してジョブIDを返す"""
    image_path = scene["image"]
    if not image_path.exists():
        print(f"  ❌ 画像が見つかりません: {image_path}")
        return None

    with open(image_path, "rb") as img_file:
        response = requests.post(
            "https://api.elevenlabs.io/v1/video-generation",
            headers=HEADERS,
            files={"image": (image_path.name, img_file, "image/png")},
            data={
                "model_id":    "kling-o3",
                "prompt":      scene["prompt"],
                "duration":    str(scene["duration"]),
                "aspect_ratio": "9:16",
            },
            timeout=30,
        )

    if response.status_code not in (200, 201):
        print(f"  ❌ リクエスト失敗: {response.status_code} {response.text}")
        return None

    generation_id = response.json().get("id")
    print(f"  📤 ジョブ開始: {generation_id}")
    return generation_id


def poll_and_download(generation_id: str, output_path: Path, timeout_min: int = 10) -> bool:
    """生成完了を待ってダウンロード"""
    max_attempts = timeout_min * 6  # 10秒間隔
    for attempt in range(max_attempts):
        time.sleep(10)
        res = requests.get(
            f"https://api.elevenlabs.io/v1/video-generation/{generation_id}",
            headers=HEADERS,
            timeout=30,
        )
        data = res.json()
        status = data.get("status", "unknown")
        print(f"  ⏳ [{attempt + 1}/{max_attempts}] ステータス: {status}")

        if status == "completed":
            video_url = data.get("video_url") or data.get("url")
            if not video_url:
                print("  ❌ 動画URLが取得できません")
                return False
            video_data = requests.get(video_url, timeout=120).content
            output_path.write_bytes(video_data)
            print(f"  ✅ ダウンロード完了: {output_path}")
            return True

        if status in ("failed", "error"):
            print(f"  ❌ 生成失敗: {data}")
            return False

    print(f"  ❌ タイムアウト（{timeout_min}分超過）")
    return False


def concat_clips(clip_paths: list[Path], output: Path) -> bool:
    """ffmpeg で複数クリップを1本に結合"""
    list_file = CLIPS_DIR / "filelist.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in clip_paths),
        encoding="utf-8",
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-c:v", "libx264", "-crf", "23",
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(output),
    ]
    print(f"\n🎞️  結合コマンド: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"✅ リール完成: {output}")
        return True
    else:
        print(f"❌ ffmpeg 失敗:\n{result.stderr}")
        return False


def main():
    print("=" * 55)
    print("🎬 るーにゃ リール動画生成開始")
    print("=" * 55)

    clip_paths = []

    for i, scene in enumerate(SCENES, 1):
        print(f"\n--- シーン {i} / {len(SCENES)} ---")

        # 既にクリップが存在すればスキップ
        if scene["clip_out"].exists():
            print(f"  ✅ 既存クリップを使用: {scene['clip_out']}")
            clip_paths.append(scene["clip_out"])
            continue

        # 動画生成リクエスト
        gen_id = request_video(scene)
        if not gen_id:
            print(f"  ❌ シーン{i} をスキップ")
            continue

        # ポーリング＆ダウンロード
        ok = poll_and_download(gen_id, scene["clip_out"])
        if ok:
            clip_paths.append(scene["clip_out"])
        else:
            print(f"  ❌ シーン{i} の動画取得に失敗")

    # 全クリップ結合
    print(f"\n[結合] {len(clip_paths)} クリップ → {OUTPUT_REEL.name}")
    if len(clip_paths) == 0:
        print("❌ 結合できるクリップがありません")
        return

    success = concat_clips(clip_paths, OUTPUT_REEL)

    print("\n" + "=" * 55)
    if success:
        size_mb = OUTPUT_REEL.stat().st_size / 1024 / 1024
        print(f"🎉 リール完成！")
        print(f"   ファイル: {OUTPUT_REEL}")
        print(f"   サイズ  : {size_mb:.1f} MB")
    else:
        print("❌ リール生成に失敗しました")
    print("=" * 55)


if __name__ == "__main__":
    main()
