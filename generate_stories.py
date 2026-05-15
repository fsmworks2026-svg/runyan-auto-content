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
from datetime import date, timedelta, datetime, timezone
from dotenv import load_dotenv
from openai import OpenAI

import daily_context as dc
from strip_metadata import strip_image

_JST = timezone(timedelta(hours=9))

def _today_jst() -> date:
    """GitHub Actions (UTC) / ローカル共通で JST の今日を返す"""
    return datetime.now(_JST).date()

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
    # casual: outfit_detail（Vision抽出済み詳細）→ outfit → casual_outfit の優先順
    scenario_path = Path("./current_scenario.json")
    if scenario_path.exists():
        try:
            sc = json.loads(scenario_path.read_text(encoding="utf-8"))
            if sc.get("outfit_detail"):
                return sc["outfit_detail"]
            if sc.get("outfit"):
                return sc["outfit"]
        except Exception:
            pass
    return ctx["casual_outfit"]


def _build_room_description(ctx: dict) -> str:
    return f"{ctx['room_base']} {ctx['room_clutter']}. {ctx['room_seasonal']}."


def _select_room_image(slot: dict, room_style: str = "mirror") -> Path | None:
    """
    スロットの衣装タイプと時間帯から部屋背景画像を返す。
    屋外・カジュアル系はNoneを返す。
    room_style: "mirror"（姿見）または "sofa"（ソファ）
    scene_hint にキーワードが含まれる場合は背景を上書き。
      ソファ / リビング → living_sofa_{suffix}
      鏡 / 姿見      → living_mirror_{suffix}
      洗面台 / 洗面所  → washroom_mirror
      （なし / 寝室 / ベッド → bedroom_entrance_{suffix}）
    """
    room_dir = Path("./部屋画像")
    outfit_type = slot.get("outfit_type", "casual")

    # 時間帯判定（post_windowの開始時刻で夜かどうかを判断）
    start_hour = slot.get("post_window", [12, 14])[0]
    is_night = start_hour >= 17 or start_hour <= 4
    suffix = "night" if is_night else "morning"

    if outfit_type == "pajamas":
        hint = slot.get("scene_hint", "")
        if any(kw in hint for kw in ("ソファ", "リビング")):
            return room_dir / f"living_sofa_{suffix}.png"
        if any(kw in hint for kw in ("鏡", "姿見")):
            return room_dir / f"living_mirror_{suffix}.png"
        if any(kw in hint for kw in ("洗面台", "洗面所")):
            return room_dir / "washroom_mirror.png"
        # デフォルト: 寝室
        return room_dir / f"bedroom_entrance_{suffix}.png"

    if outfit_type == "room":
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
        room_style   = "mirror"  # _select_room_image のデフォルト用途のみ（casual では未使用）
        camera_text  = "\nSelfie stick shot. Front camera, wider angle. Natural casual angle, not tripod-level perfect framing.\n"
        conceal_text = ""

    elif outfit_type == "room":
        room_style = random.choice(["mirror", "sofa"])
        if room_style == "mirror":
            camera_text  = "\nMirror selfie. Character standing directly in front of the full-length mirror, arm raised holding phone toward mirror. Phone back covers upper face in reflection.\n"
            conceal_text = ""
        else:
            camera_text  = "\nFront camera selfie sitting on the sofa. Arm extended toward camera. Slightly downward angle. Relaxed casual pose on couch.\n"
            conceal_text = ""

    else:
        # パジャマ（朝・夜）- room_style は _select_room_image のデフォルト用途のみ
        room_style = "mirror"

    # 部屋参照画像の選択
    room_image_path = _select_room_image(slot, room_style=room_style)
    if outfit_type == "casual":
        room_image_path = None

    # 朝パジャマ: 前日夜画像をパジャマ参照として事前検索（プロンプト生成前に確定する）
    prev_night_ref_path = None
    if outfit_type == "pajamas" and slot_id == "morning":
        from datetime import timedelta as _td_pj
        _today_dt    = date.fromisoformat(f"{today_str[:4]}-{today_str[4:6]}-{today_str[6:]}")
        _yesterday   = (_today_dt - _td_pj(days=1)).strftime("%Y%m%d")
        for suffix in (".jpg", ".png"):
            candidate = OUTPUT_DIR / f"story_{_yesterday}_night{suffix}"
            if candidate.exists():
                prev_night_ref_path = candidate
                break

    # パジャマスロットは日本語プロンプトで統一（背景を先に指定してアンカーにする）
    if outfit_type == "pajamas":
        hint = slot.get("scene_hint", "")

        # scene_hint のキーワードで pj_style を決定（override_hint 対応）
        if any(kw in hint for kw in ("洗面台", "洗面所", "バスタオル", "お風呂上がり", "washroom")):
            pj_style = "washroom_mirror"
        elif any(kw in hint for kw in ("ソファ", "リビング")):
            pj_style = "sofa_coffee"
        elif any(kw in hint for kw in ("鏡", "姿見")):
            pj_style = "mirror_selfie"
        elif is_night:
            pj_style = random.choice(["bed_selfie", "mirror_selfie"])
        else:
            pj_style = random.choice(["bed_selfie", "mirror_selfie", "sofa_coffee"])

        # pj_style に合わせて room_image_path を確定（ランダム選択時も背景と一致させる）
        suffix_pj = "night" if is_night else "morning"
        if pj_style == "washroom_mirror":
            room_image_path = Path("./部屋画像") / "washroom_mirror.png"
        elif pj_style == "sofa_coffee":
            room_image_path = Path("./部屋画像") / f"living_sofa_{suffix_pj}.png"
        elif pj_style == "mirror_selfie":
            room_image_path = Path("./部屋画像") / f"living_mirror_{suffix_pj}.png"

        time_context = "夜寝る前の雰囲気、暖かいランプの明かり" if is_night else "朝起きたばかり"
        if pj_style == "washroom_mirror":
            pj_camera = (
                "その子が洗面台の鏡の前に立ち、スマホを持ち上げてミラーセルフィーを撮っている。"
                "お風呂上がりで、白いバスタオルを胸元でしっかり巻いている。"
                "頭にはパステルカラーのヘアバンドをつけ、髪が濡れてしっとりしている。"
                "肌はお風呂上がりのほんのり赤み。洗面台の暖かい照明。スマホが顔の下半分を隠している。"
            )
        elif pj_style == "bed_selfie":
            pj_camera = "その子がベッドに座り、スマホのインカメラで自撮りをしている。"
        elif pj_style == "mirror_selfie":
            pj_camera = "その子が部屋の鏡の前に立ち、スマホを持ち上げてミラーセルフィーを撮っている。鏡のフレームが画角の端に見える。"
        else:  # sofa_coffee
            if is_night:
                pj_camera = "その子がリビングのソファに座り、夜のリラックスタイムにスマホのインカメラで自撮りをしている。暖かい間接照明の雰囲気。"
            else:
                pj_camera = "その子がリビングのソファに座り、朝のコーヒーを飲みながらスマホのインカメラで自撮りをしている。テーブルにコーヒーカップ。朝の生活感のある雰囲気。"

        hint_line = f"\n追加指示: {hint}" if hint else ""

        # 朝スロットで前日夜画像がある場合: 3枚目=パジャマ参照、ない場合: テキスト指定
        if prev_night_ref_path:
            pajamas_line = "3枚目の写真と完全に同じパジャマ・同じデザイン・同じ色を着ていること。ただしポーズ・構図・小道具は3枚目と異なるものにすること。"
        else:
            pajamas_line = f"{outfit}を着ている。"

        if pj_style == "washroom_mirror":
            # 洗面台鏡越しシーン専用プロンプト（背景参照写真の洗面所を厳守）
            prompt = f"""2枚目の写真の洗面台・鏡・照明・棚・壁・床をそのままコピーすること。洗面所の空間・インテリア・照明の色温度は一切変えないこと。2枚目の写真と同一の洗面所でなければならない。

1枚目の写真と同じ人物が、2枚目の洗面台の鏡の中に反射として映っている。
21歳の日本人女性、るーにゃ。顔の特徴・髪型・目の形を忠実に再現すること。
ダークブラウンのセミロングヘア、ゆるいウェーブ、薄いエアリーな前髪。

完全にすっぴん。化粧は一切なし。リップカラーなし・眉毛メイクなし・アイメイクなし。素肌そのまま。
お風呂上がりで、白いバスタオルを胸元でしっかり巻いている。
頭にはパステルカラーのヘアバンドをつけ、髪が濡れてしっとりしている。
肌はお風呂上がりのほんのり赤み。

洗面台の鏡の前に立ち、スマホを鏡に向けて撮影している。スマホが顔の下半分を隠している。{hint_line}
顔はすっぴんなので、鼻の上から目の下にかけて写真の上にデジタルで重ねた2DのInstagram風の星スタンプが浮いている。肌に溶け込まず、写真の上にフラットに乗っている2Dグラフィックのスタンプ。

フォトリアリスティック。縦9:16。Instagramストーリーズ。"""
        else:
            prompt = f"""2枚目の写真の部屋をそのまま背景として使うこと。家具・照明・色・インテリアは一切変えないこと。

この部屋に、1枚目の写真と同じ人物を配置してください。
21歳の日本人女性、るーにゃ。顔の特徴・髪型・目の形を忠実に再現すること。
ダークブラウンのセミロングヘア、ゆるいウェーブ、薄いエアリーな前髪。

完全にすっぴん。化粧は一切なし。リップカラーなし・眉毛メイクなし・アイメイクなし。素肌そのまま。
{pajamas_line}{time_context}。

{pj_camera}{hint_line}
顔はすっぴんなので、鼻の上から目の下にかけて写真の上にデジタルで重ねた2DのInstagram風の星スタンプが浮いている。肌に溶け込まず、写真の上にフラットに乗っている2Dグラフィックのスタンプ。

フォトリアリスティック。縦9:16。Instagramストーリーズ。
季節：{ctx['season_jp']} — {ctx['season_weather']}"""

    else:
        # casual / room スロットも日本語プロンプトに統一
        if outfit_type == "casual":
            # リール画像がある場合は服装参照あり（2枚目）、ない場合はテキストのみ
            reel_dir = Path("./reel_output")
            _has_outfit_ref = any(
                (reel_dir / f"reel_{today_str}{s}").exists() for s in (".jpg", ".png")
            )
            outfit_ref_line = (
                "2枚目の写真と完全に同じ服装・アクセサリーで生成すること。色・デザイン・素材感を忠実に再現すること。ただしポーズ・構図・小道具は2枚目と異なるものにすること。"
                if _has_outfit_ref else
                f"{outfit}を着ている。"
            )
            prompt = f"""1枚目の写真と同じ人物で生成してください。
21歳の日本人女性、るーにゃ。顔の特徴・髪型・目の形を忠実に再現すること。
ダークブラウンのセミロングヘア、ゆるいウェーブ、薄いエアリーな前髪。

ナチュラルメイク。ソフトな頬紅、コーラルベージュリップ、ライトアイメイク。
{outfit_ref_line}

{slot['scene_hint']}
季節：{ctx['season_jp']} — {ctx['season_weather']}

自撮りで撮影。自然なカジュアルアングル。
フォトリアリスティック。縦9:16。Instagramストーリーズ。"""

        else:  # room（ミラー or ソファ）
            room_camera = (
                "部屋の姿見の前に立ち、スマホを鏡に向けてミラーセルフィーを撮っている。スマホが顔の上部を自然に隠す。鏡のフレームが画角の端に見える。"
                if room_style == "mirror" else
                "ソファに座ってスマホのインカメラで自撮りをしている。腕を少し伸ばして。リラックスしたカジュアルなポーズ。"
            )
            room_lighting = (
                "部屋全体に暖かいアンバー色の間接照明とキャンドルの光が灯っている。人物にも同じ暖色系の柔らかい光を当てること。顔や肌に暖かいオレンジがかった光が反射している。"
                if is_night else
                "明るく柔らかい自然光が差し込んでいる。人物にも同じ色温度の光を当てること。"
            )
            prompt = f"""2枚目の写真の部屋をそのまま背景として使うこと。家具・照明・色・インテリアは一切変えないこと。

この部屋に、1枚目の写真と同じ人物を配置してください。
21歳の日本人女性、るーにゃ。顔の特徴・髪型・目の形を忠実に再現すること。
ダークブラウンのセミロングヘア、ゆるいウェーブ、薄いエアリーな前髪。

ナチュラルメイク。ソフトな頬紅、コーラルベージュリップ、ライトアイメイク。
{outfit}を着ている。

{slot['scene_hint']}
季節：{ctx['season_jp']} — {ctx['season_weather']}

{room_camera}
{room_lighting}
フォトリアリスティック。縦9:16。Instagramストーリーズ。"""

    if outfit_type == "pajamas":
        style_label = f" [{pj_style}]"
    elif outfit_type == "room":
        style_label = f" [{room_style}]"
    else:
        style_label = ""
    print(f"  🎨 [{slot['label']}]{style_label} 画像生成中...")
    if room_image_path and room_image_path.exists():
        print(f"  🏠 部屋背景: {room_image_path.name}")

    # 服装参照画像の確定
    # casual: 当日リール画像を服装参照として使用
    # pajamas 朝スロット: 前日夜画像をパジャマ参照として使用
    outfit_ref_path = None
    if outfit_type == "casual":
        reel_dir = Path("./reel_output")
        for _s in (".jpg", ".png"):
            candidate = reel_dir / f"reel_{today_str}{_s}"
            if candidate.exists():
                outfit_ref_path = candidate
                print(f"  👗 服装参照: {candidate.name}")
                break
    elif prev_night_ref_path:
        outfit_ref_path = prev_night_ref_path
        print(f"  🌙 前日夜パジャマ参照: {prev_night_ref_path.name}")

    try:
        char_file       = open(ref_path, "rb")
        room_file       = open(room_image_path, "rb") if room_image_path and room_image_path.exists() else None
        outfit_ref_file = open(outfit_ref_path, "rb") if outfit_ref_path else None

        # 画像順序: [キャラ, 部屋背景, 服装参照] の順で渡す
        # プロンプトの「2枚目=部屋」「3枚目=服装参照」と対応させる
        if room_file and outfit_ref_file:
            images_input = [char_file, room_file, outfit_ref_file]
        elif outfit_ref_file:
            images_input = [char_file, outfit_ref_file]
        elif room_file:
            images_input = [char_file, room_file]
        else:
            images_input = char_file

        response = client.images.edit(
            model="gpt-image-2",
            image=images_input,
            prompt=prompt,
            size="1024x1536",
        )
        char_file.close()
        if room_file:
            room_file.close()
        if outfit_ref_file:
            outfit_ref_file.close()
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
        d  = target_date or _today_jst()
        shoot_dt = datetime(d.year, d.month, d.day, pw[0], 0, 0)
        out_path = strip_image(out_path, shoot_time=shoot_dt)
        print(f"  ✅ 保存完了: {out_path.name}")
        return out_path
    except Exception as e:
        print(f"  ❌ 保存失敗: {e}")
        return None


def pick_caption(slot: dict, ctx: dict) -> str:
    """日付シードでキャプションをローテーション"""
    doy = _today_jst().timetuple().tm_yday
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

        msg_data   = resp.json() if resp.status_code == 200 else {}
        channel_id = msg_data.get("channel_id", "")
        message_id = msg_data.get("id", "")

        # ✅ / ❌ リアクションを追加（Bot Token が設定されている場合）
        if DISCORD_BOT_TOKEN and channel_id and message_id:
            headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
            for emoji_str in ["✅", "❌"]:
                requests.put(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}"
                    f"/reactions/{requests.utils.quote(emoji_str)}/@me",
                    headers=headers,
                    timeout=10,
                )

        # story_message_ids.json / approved_slots.json を更新（redo時の追跡）
        if message_id:
            slot_id   = slot["id"]
            today_str = _today_jst().strftime("%Y%m%d")

            ids_path     = Path("./story_message_ids.json")
            existing_ids = json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.exists() else {}
            day_ids      = existing_ids.get(today_str, {})
            if channel_id:
                day_ids["channel_id"] = channel_id
            day_ids[slot_id]          = message_id
            existing_ids[today_str]   = day_ids
            ids_path.write_text(json.dumps(existing_ids, ensure_ascii=False, indent=2), encoding="utf-8")

            slots_path     = Path("./approved_slots.json")
            existing_slots = json.loads(slots_path.read_text(encoding="utf-8")) if slots_path.exists() else {}
            day_slots      = existing_slots.get(today_str, {})
            day_slots[slot_id]         = None  # 再承認待ちにリセット
            existing_slots[today_str]  = day_slots
            slots_path.write_text(json.dumps(existing_slots, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  📋 story_message_ids / approved_slots 更新（{slot_id}: {message_id}）")

        return True
    except Exception as e:
        print(f"  ❌ Discord 送信エラー: {e}")
        return False


def generate_all(target_date: date = None, notify_discord: bool = True) -> list[Path]:
    """全スロットのストーリーズ画像を生成して Path のリストを返す"""
    d         = target_date or _today_jst()
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
    target = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now(_JST).date()
    generate_all(target_date=target, notify_discord=True)
