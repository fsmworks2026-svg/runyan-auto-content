#!/usr/bin/env python3
"""
るーにゃ ストーリーズ自動生成スクリプト
daily_context.py で確定した設定を参照し、4スロットのストーリーズ画像を生成する。
- 衣装・部屋・顔隠しはすべて daily_context に従う
- 朝・深夜スロットはすっぴん＋顔隠し構図
- 夕方スロットが部屋着の場合もすっぴん＋顔隠し
"""

import os
import random
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

client            = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
DISCORD_WEBHOOK   = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

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


def _select_room_image(slot: dict, room_style: str = "mirror") -> Path | None:
    """
    スロットの衣装タイプと時間帯から部屋背景画像を返す。
    屋外・カジュアル系はNoneを返す。
    room_style: "mirror"（姿見）または "sofa"（ソファ）
    """
    room_dir = Path("./部屋画像")
    outfit_type = slot.get("outfit_type", "casual")

    # 時間帯判定（post_windowの開始時刻で夜かどうかを判断）
    start_hour = slot.get("post_window", [12, 14])[0]
    is_night = start_hour >= 17 or start_hour <= 4

    if outfit_type == "pajamas":
        # パジャマ = 寝室（朝か夜）
        suffix = "night" if is_night else "morning"
        return room_dir / f"bedroom_entrance_{suffix}.png"

    if outfit_type == "room":
        suffix = "night" if is_night else "morning"
        if room_style == "sofa":
            return room_dir / f"living_sofa_{suffix}.png"
        return room_dir / f"living_mirror_{suffix}.png"

    # casual（屋外・通学・カフェ等）は部屋画像なし
    return None


def _needs_face_conceal(slot: dict) -> bool:
    """顔隠しが必要なスロットかどうか（すっぴんのみ）"""
    return slot["no_makeup"]


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
        "suppin":  "Absolutely no makeup at all. Bare skin with zero cosmetics. Pale unpigmented lips, no lip color or tint whatsoever. Natural sparse brows with no eyebrow pencil or filling. No blush, no eye makeup, no concealer. Fresh bare just-woke-up face.",
        "natural": "Natural casual chic makeup. Soft rosy cheeks. Coral-beige lips. Light eye makeup.",
        "gachi":   "Glamorous full makeup. Bold eye makeup. Defined lips. Contoured skin.",
    }[makeup]

    # 撮影スタイル＋部屋アングル（outfit_typeで分岐）
    outfit_type = slot.get("outfit_type", "casual")
    start_hour  = slot.get("post_window", [12, 14])[0]
    is_night    = start_hour >= 17 or start_hour <= 4

    if outfit_type == "casual":
        room_text   = ""
        room_style  = "mirror"  # casual では未使用
        camera_text = "\nSelfie stick shot. Front camera, wider angle. Natural casual angle, not tripod-level perfect framing.\n"
        conceal_text = ""  # 外出＋メイクあり → 顔隠し不要

    elif outfit_type == "room":
        room_style = random.choice(["mirror", "sofa"])
        if room_style == "mirror":
            room_text    = (
                "\nRoom setting: Japanese 1LDK apartment living room. "
                "Full-length mirror with rounded light oak wood frame leaning against the white wall. "
                "Light oak flooring. Small green plant in white pot beside the mirror. "
                "Dining table and chair partially visible on the right edge. "
                "Kitchen with white refrigerator visible in the mirror reflection. "
                "Postcard prints on the wall to the right of the mirror.\n"
            )
            camera_text  = "\nMirror selfie. Character standing directly in front of the full-length mirror, arm raised holding phone toward mirror. Phone back covers upper face in reflection.\n"
            conceal_text = ""  # 鏡セルフィー: スマホが顔を自然に隠す（追加テキスト不要）

        else:
            room_text    = (
                "\nRoom setting: Japanese 1LDK apartment living room. "
                "Beige fabric 2-seater sofa against the wall. Character sitting on the sofa. "
                "Light oak low table in front with a phone or manga on it. "
                "Lace curtains on the window. Warm ambient lighting.\n"
            )
            camera_text  = "\nFront camera selfie sitting on the sofa. Arm extended toward camera. Slightly downward angle. Relaxed casual pose on couch.\n"
            conceal_text = ""  # 部屋着＋メイクあり → 顔隠し不要

    else:
        # パジャマ（朝・夜の寝室）
        if is_night:
            room_text = (
                "\nRoom setting: Japanese apartment bedroom at night. "
                "Window with sheer lace curtains on the left. "
                "Wooden desk and chair on the left side, small white table lamp on the desk glowing warm amber — main light source. "
                "Flower vase and closed laptop on the desk. "
                "Single bed with white bedding and orange fluffy blanket on the right side. Wooden headboard. "
                "Small nightstand beside the bed. Wooden bookshelf to the right of the bed with books. "
                "Round fluffy rug on the floor. Air conditioner on the upper wall. "
                "Small photo prints on the right wall. Entire room bathed in warm amber lamplight.\n"
            )
        else:
            room_text = (
                "\nRoom setting: Japanese apartment bedroom in the morning. "
                "Window with sheer lace curtains on the left, bright natural morning sunlight flooding in. "
                "Wooden desk and chair on the left, laptop and flower vase on the desk. Small white table lamp on the desk. "
                "Single bed with white bedding and salmon-pink fluffy blanket on the right side. Wooden headboard. "
                "Small wooden nightstand beside the bed with a tiny stuffed cat and flowers. "
                "Small wooden bookshelf/cabinet between the desk area and the bed. "
                "Round fluffy rug on the floor. Air conditioner on the upper wall. "
                "Small photo prints on the right wall. Airy bright morning atmosphere.\n"
            )
        room_style   = "mirror"  # pajamas では未使用
        # 入口付近に立って外向きにセルフィー → bedroom_entrance 参照画像のアングルと一致する
        camera_text  = (
            "\nSelfie taken while standing at the bedroom doorway, facing outward. "
            "Phone held at arm's length, front camera angled slightly downward. "
            "The bedroom interior — bed, pillow, shelves — visible behind the character. "
            "Casual relaxed pose, natural Instagram selfie framing.\n"
        )
        conceal_text = (
            "\nFace concealment: A cute pastel pink star-shaped sticker is placed "
            "over the eyes area in the photo, covering from the eyebrows to the nose bridge. "
            "Like an Instagram story decoration. The rest of the face (lips, chin) is visible.\n"
        )

    # 部屋参照画像がある場合、プロンプトに役割を明示する
    room_image_path = _select_room_image(slot, room_style=room_style)
    ref_role_text = (
        "\nReference images: the first image is the character to reproduce exactly. "
        "The second image is the room background — keep this background completely unchanged. "
        "Do not alter any furniture, lighting, colors, or room elements. "
        "Simply place the character from the first image naturally inside this exact background.\n"
    ) if room_image_path and room_image_path.exists() else ""

    prompt = f"""{CHARA_BASE}

{makeup_text}

Wearing {outfit}.

Scene:
{slot['scene_hint']}
Season: {ctx['season_jp']} — {ctx['season_weather']}
{room_text}{camera_text}{conceal_text}{ref_role_text}"""

    # room_image_path は上の ref_role_text 生成時に決定済み（casual の場合は None）
    if outfit_type == "casual":
        room_image_path = None

    style_label = f" [{room_style}]" if outfit_type == "room" else ""
    print(f"  🎨 [{slot['label']}]{style_label} 画像生成中...")
    if room_image_path and room_image_path.exists():
        print(f"  🏠 部屋背景: {room_image_path.name}")

    try:
        char_file = open(ref_path, "rb")
        if room_image_path and room_image_path.exists():
            room_file = open(room_image_path, "rb")
            images_input = [char_file, room_file]
        else:
            images_input = char_file
            room_file = None

        response = client.images.edit(
            model="gpt-image-2",
            image=images_input,
            prompt=prompt,
            size="1024x1536",
        )
        char_file.close()
        if room_file:
            room_file.close()
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
                DISCORD_WEBHOOK + "?wait=true",
                data={"payload_json": json.dumps({"embeds": [embed]})},
                files={"file": (image_path.name, f, "image/png")},
                timeout=30,
            )
        if resp.status_code not in (200, 204):
            print(f"  ❌ Discord 送信失敗: {resp.status_code} {resp.text[:200]}")
            return False

        print(f"  ✅ Discord 送信完了")

        # ✅ リアクションを追加（Bot Token が設定されている場合）
        if DISCORD_BOT_TOKEN and resp.status_code == 200:
            msg_data   = resp.json()
            channel_id = msg_data.get("channel_id", "")
            message_id = msg_data.get("id", "")
            if channel_id and message_id:
                requests.put(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/✅/@me",
                    headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
                    timeout=10,
                )

        return True
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
