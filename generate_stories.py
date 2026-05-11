#!/usr/bin/env python3
"""
るーにゃ ストーリーズ自動生成スクリプト
daily_context.py で確定した設定を参照し、4スロットのストーリーズ画像を生成する。
- 衣装・部屋・顔隠しはすべて daily_context に従う
- 朝・深夜スロットはすっぴん＋顔隠し構図
- 夕方スロットが部屋着の場合もすっぴん＋顔隠し
"""

import os
import base64
import json
import requests
from pathlib import Path
from datetime import date, timedelta
from dotenv import load_dotenv
from openai import OpenAI

import daily_context as dc
from strip_metadata import strip_image
from datetime import datetime

load_dotenv()

client          = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL", "")

CHARA_DIR      = Path("./キャラ画像")
OUTPUT_DIR     = Path("./stories_output")
OUTPUT_DIR.mkdir(exist_ok=True)

# メイク別参照画像
REFERENCE_IMAGES = {
    "natural": CHARA_DIR / "runyan_natural.png",
    "suppin":  CHARA_DIR / "runyan_suppin.png",
    "gachi":   CHARA_DIR / "runyan_gachi.png",
}

# キャラクター共通プロンプト（main.py と統一）
CHARA_BASE = """Same person as in the reference image.
Ru-nya, 21-year-old Japanese woman.
Consistent facial features. Same hairstyle, same bangs, same eye shape.
Soft slightly droopy eyes. Natural Japanese facial structure.
Small face, gentle jawline. Fair smooth skin.
Long dark brown semi-long hair with natural loose waves. Thin airy bangs.
Photorealistic. Japanese cinematic realism. Warm natural light.
Instagram story aesthetic. Vertical 9:16."""


def _build_outfit_text(slot: dict, ctx: dict) -> str:
    """スロットの outfit_type から実際の服装説明を返す"""
    ot = slot["outfit_type"]
    if ot == "pajamas":
        return ctx["pajamas"]
    if ot == "room":
        return ctx["room_wear"]
    return ctx["casual_outfit"]  # casual


def _build_room_description(ctx: dict) -> str:
    return f"{ctx['room_base']} {ctx['room_clutter']}. {ctx['room_seasonal']}."


def _needs_face_conceal(slot: dict) -> bool:
    """顔隠しが必要なスロットかどうか（すっぴん = 朝・深夜、部屋着の夕方）"""
    return slot["no_makeup"] or slot["outfit_type"] == "room"


def _makeup_for_slot(slot: dict) -> str:
    return "suppin" if _needs_face_conceal(slot) else "natural"


def generate_story_image(slot: dict, ctx: dict, today_str: str, target_date: date = None) -> Path | None:
    """1スロット分のストーリーズ画像を生成して保存する"""
    slot_id   = slot["id"]
    outfit    = _build_outfit_text(slot, ctx)
    makeup    = _makeup_for_slot(slot)
    ref_path  = REFERENCE_IMAGES.get(makeup, REFERENCE_IMAGES["natural"])

    # メイク説明
    makeup_text = {
        "suppin":  "No makeup. Bare natural skin. Clean fresh face. Natural lip color.",
        "natural": "Natural casual chic makeup. Soft rosy cheeks. Coral-beige lips. Light eye makeup.",
        "gachi":   "Glamorous full makeup. Bold eye makeup. Defined lips. Contoured skin.",
    }[makeup]

    # 顔隠し構図（すっぴんスロット）
    conceal_text = ""
    if _needs_face_conceal(slot):
        conceal_text = f"\nFace concealment: {ctx['face_conceal']}\n"

    # 室内シーンは部屋の固定セットを追加
    room_text = ""
    if slot["outfit_type"] in ("pajamas", "room"):
        room_text = f"\nRoom setting: {_build_room_description(ctx)}\n"

    prompt = f"""{CHARA_BASE}

{makeup_text}

Wearing {outfit}.

Scene:
{slot['scene_hint']}
Season: {ctx['season_jp']} — {ctx['season_weather']}
{room_text}{conceal_text}"""

    print(f"  🎨 [{slot['label']}] 画像生成中...")

    try:
        with open(ref_path, "rb") as img_file:
            response = client.images.edit(
                model="gpt-image-2",
                image=img_file,
                prompt=prompt,
                size="1024x1536",
            )
    except Exception as e:
        print(f"  ⚠️  edit モード失敗: {e} → generate モードで再試行")
        try:
            response = client.images.generate(
                model="gpt-image-2",
                prompt=prompt,
                n=1,
                size="1024x1536",
            )
        except Exception as e2:
            print(f"  ❌ generate モードも失敗: {e2}")
            return None

    out_path = OUTPUT_DIR / f"story_{today_str}_{slot_id}.png"
    try:
        item = response.data[0]
        if hasattr(item, "b64_json") and item.b64_json:
            out_path.write_bytes(base64.b64decode(item.b64_json))
        elif hasattr(item, "url") and item.url:
            out_path.write_bytes(requests.get(item.url, timeout=60).content)
        else:
            print(f"  ❌ 画像データが取得できません")
            return None
        # AI生成メタデータを除去して iPhone 15 Pro EXIF に置き換える（PNG→JPEG）
        # 撮影時刻 = 投稿ウィンドウ開始時刻の少し前（自然に見えるよう）
        pw = slot["post_window"]
        d  = target_date or date.today()
        shoot_dt = datetime(d.year, d.month, d.day, pw[0], 0, 0)
        out_path = strip_image(out_path, shoot_time=shoot_dt)
        print(f"  ✅ 保存完了: {out_path.name}")
        return out_path
    except Exception as e:
        print(f"  ❌ 保存失敗: {e}")
        return None


def pick_caption(slot: dict, ctx: dict) -> str:
    """日付シードでキャプションをローテーション"""
    doy = date.today().timetuple().tm_yday
    captions = {
        "morning": [
            f"おはよ〜 今日は{ctx['afternoon']['label']}だ ☕",
            "寝坊しかけた やばい 🌅",
            "今日もがんばろ〜",
        ],
        "afternoon": [
            f"{ctx['afternoon']['label']}中 💪",
            "今日もなんとかやってる",
            "お昼どうしよ〜",
        ],
        "evening": [
            f"{ctx['evening']['label']}終わり〜 お疲れ様でした 🛤️",
            "帰り道のコンビニ寄ってく 🏪",
            "今日も一日お疲れ 🌇",
        ],
        "night": [
            "おやすみ〜 明日もがんばろ 🌙",
            "もう寝る時間だ〜",
            "今日は疲れたな…おやすみ 💤",
        ],
    }
    options = captions.get(slot["id"], ["おつかれ〜"])
    return options[doy % len(options)]


def send_discord(slot: dict, caption: str, image_path: Path) -> bool:
    """Discord Webhook に画像を multipart 送信する"""
    if not DISCORD_WEBHOOK:
        print("  ⚠️  DISCORD_WEBHOOK_URL が未設定")
        return False

    embed = {
        "title":       f"{slot['emoji']} ストーリーズ - {slot['label']}",
        "description": caption,
        "color":       0xFF69B4,
        "fields": [
            {"name": "📝 キャプション案", "value": caption,              "inline": False},
            {"name": "✨ シーン",         "value": slot["scene_hint"][:80], "inline": False},
            {"name": "🕐 投稿ウィンドウ",
             "value": f"{slot['post_window'][0]}〜{slot['post_window'][1]}時（±20分）",
             "inline": True},
        ],
        "footer": {"text": "ストーリーズ | 24時間で消えます"},
    }

    try:
        with open(image_path, "rb") as f:
            resp = requests.post(
                DISCORD_WEBHOOK,
                data={"payload_json": json.dumps({"embeds": [embed]})},
                files={"file": (image_path.name, f, "image/png")},
                timeout=30,
            )
        if resp.status_code in (200, 204):
            print(f"  ✅ Discord 送信完了")
            return True
        print(f"  ❌ Discord 送信失敗: {resp.status_code} {resp.text[:200]}")
        return False
    except Exception as e:
        print(f"  ❌ Discord 送信エラー: {e}")
        return False


def generate_all(target_date: date = None, notify_discord: bool = True) -> list[Path]:
    """全スロットのストーリーズ画像を生成して Path のリストを返す"""
    d         = target_date or date.today()
    today_str = d.strftime("%Y%m%d")
    ctx       = dc.load_or_create(d, openai_client=client)
    slots     = ctx["story_slots"]
    results   = []

    print("=" * 55)
    print(f"📱 ストーリーズ生成 ({ctx['date_display']})")
    print(f"   季節: {ctx['season_jp']}  /  出力先: {OUTPUT_DIR.resolve()}")
    print("=" * 55)

    for slot in slots:
        print(f"\n[{slot['emoji']} {slot['label']}]")

        # strip_image が PNG→JPEG 変換するため .jpg も確認する
        existing     = OUTPUT_DIR / f"story_{today_str}_{slot['id']}.png"
        existing_jpg = OUTPUT_DIR / f"story_{today_str}_{slot['id']}.jpg"
        found = existing_jpg if existing_jpg.exists() else (existing if existing.exists() else None)
        if found:
            print(f"  ✅ 既存ファイルあり（スキップ）: {found.name}")
            results.append(found)
            continue

        image_path = generate_story_image(slot, ctx, today_str, target_date=d)
        if not image_path:
            print(f"  ❌ 生成失敗")
            continue

        if notify_discord:
            caption = pick_caption(slot, ctx)
            send_discord(slot, caption, image_path)

        results.append(image_path)

    print("\n" + "=" * 55)
    print(f"📊 完了: {len(results)}/{len(slots)} スロット")
    print("=" * 55)
    return results


if __name__ == "__main__":
    import sys
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    generate_all(target_date=target, notify_discord=True)
