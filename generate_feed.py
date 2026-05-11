#!/usr/bin/env python3
"""
るーにゃ フィード投稿画像生成モジュール。
- feed_type="food"   → 人物なし食べ物・カフェ写真を gpt-image-2 で生成
- feed_type="person" → リール画像をそのまま流用（追加生成なし）
"""

import os
import base64
import json
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from strip_metadata import strip_image

load_dotenv()

client          = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")

OUTPUT_DIR = Path("./feed_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# フード写真の共通スタイル指示
FOOD_PROMPT_BASE = (
    "Photorealistic food photography. Shot on iPhone 15 Pro. "
    "Soft natural window light. Warm and inviting atmosphere. "
    "Instagram feed aesthetic. Square 1:1 crop. "
    "No people. No text. No watermarks. "
    "High detail, appetizing, lifestyle photography style."
)

# フィードキャプションのテンプレート（日付のmod で選択）
FOOD_CAPTIONS = [
    "今日はここ来てみた ☕",
    "お気に入りのカフェ🤍",
    "これは頼んで正解だった",
    "おやつタイム 🍰",
    "今日のランチ 🍽️",
    "このカフェまた来たい",
    "映えすぎて笑った",
    "疲れたときのご褒美 ☕",
]


def generate_food_image(scene_prompt: str, today_str: str) -> Path | None:
    """人物なしの食べ物・カフェ画像を生成する"""
    prompt = f"{FOOD_PROMPT_BASE}\n\nScene: {scene_prompt}"
    print("  🍰 フード画像生成中...")
    try:
        response = client.images.generate(
            model="gpt-image-2",
            prompt=prompt,
            n=1,
            size="1024x1024",
        )
        item = response.data[0]
        out_path = OUTPUT_DIR / f"feed_food_{today_str}.png"

        if hasattr(item, "b64_json") and item.b64_json:
            out_path.write_bytes(base64.b64decode(item.b64_json))
        elif hasattr(item, "url") and item.url:
            out_path.write_bytes(requests.get(item.url, timeout=60).content)
        else:
            print("  ❌ 画像データ取得失敗")
            return None

        # AI メタデータを除去して iPhone EXIF に置き換え
        out_path = strip_image(out_path, shoot_time=datetime.now())
        print(f"  ✅ フード画像保存: {out_path.name}")
        return out_path

    except Exception as e:
        print(f"  ❌ フード画像生成失敗: {e}")
        return None


def generate_feed_image(ctx: dict, reel_image_path: str | Path | None = None) -> Path | None:
    """
    フィード投稿用画像を返す。
    - feed_type="food"   → 新規に食べ物画像を生成して返す
    - feed_type="person" → reel_image_path をそのまま返す
    - feed_type="none"   → None を返す
    """
    feed_type = ctx.get("feed_type", "none")
    today_str = ctx["date"]

    if feed_type == "none":
        return None

    if feed_type == "food":
        scene = ctx.get("feed_food_scene", "")
        return generate_food_image(scene, today_str)

    # person: リール画像を流用
    if reel_image_path:
        p = Path(reel_image_path)
        if p.exists():
            print(f"  ✅ フィード: リール画像を流用 ({p.name})")
            return p

    print("  ⚠️  person タイプだがリール画像パスが見つかりません → スキップ")
    return None


def pick_feed_caption(ctx: dict) -> str:
    """フィード投稿のキャプションを返す"""
    from datetime import date
    feed_type = ctx.get("feed_type", "none")

    if feed_type == "food":
        doy = date.today().timetuple().tm_yday
        return FOOD_CAPTIONS[doy % len(FOOD_CAPTIONS)]

    # person: シナリオのキャプションを流用
    scenario_path = Path("./current_scenario.json")
    if scenario_path.exists():
        scenario = json.loads(scenario_path.read_text(encoding="utf-8"))
        caption  = scenario.get("caption", "")
        hashtags = " ".join(scenario.get("hashtags", []))
        return f"{caption}\n\n{hashtags}".strip()

    return ""


def send_discord_feed(image_path: Path, ctx: dict, caption: str = "") -> bool:
    """Discord Webhook にフィード画像を送信して確認を求める"""
    if not DISCORD_WEBHOOK:
        print("  ⚠️  DISCORD_WEBHOOK_URL 未設定")
        return False

    feed_type  = ctx.get("feed_type", "none")
    type_label = "🍰 フィード（料理・カフェ）" if feed_type == "food" else "📸 フィード（人物）"
    pw         = ctx.get("feed_post_window", [])
    pw_text    = f"{pw[0]}〜{pw[1]}時（±20分）" if len(pw) == 2 else "未設定"

    embed = {
        "title":       f"{type_label} — {ctx['date_display']}",
        "description": caption or "(キャプション未設定)",
        "color":       0xFF9500,
        "fields": [
            {"name": "🕐 投稿ウィンドウ", "value": pw_text, "inline": True},
        ],
        "footer": {"text": "フィード投稿確認"},
    }
    try:
        with open(image_path, "rb") as f:
            mime = "image/jpeg" if image_path.suffix.lower() == ".jpg" else "image/png"
            resp = requests.post(
                DISCORD_WEBHOOK,
                data={"payload_json": json.dumps({"embeds": [embed]})},
                files={"file": (image_path.name, f, mime)},
                timeout=30,
            )
        if resp.status_code in (200, 204):
            print("  ✅ Discord フィード送信完了")
            return True
        print(f"  ❌ Discord フィード送信失敗: {resp.status_code} {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"  ❌ Discord フィード送信エラー: {e}")
        return False


if __name__ == "__main__":
    import sys
    import daily_context as dc
    from datetime import date

    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    ctx    = dc.load_or_create(target, openai_client=client)

    print(f"フィード設定: has_feed={ctx['has_feed']}, feed_type={ctx['feed_type']}")
    if ctx["has_feed"]:
        img = generate_feed_image(ctx)
        if img:
            cap = pick_feed_caption(ctx)
            send_discord_feed(img, ctx, caption=cap)
