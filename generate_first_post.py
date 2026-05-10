#!/usr/bin/env python3
"""
るーにゃ 最初の投稿（自己紹介リール）画像生成スクリプト
4シーン + ベースキャラ画像（キャラ画像/runyan_natural.png）を生成する
"""

import os
import base64
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 出力フォルダ
output_dir = Path("./first_post")
chara_dir = Path("./キャラ画像")
output_dir.mkdir(exist_ok=True)
chara_dir.mkdir(exist_ok=True)

# ① Character Lock（全シーン毎回完全コピペ・変更禁止）
CHARACTER_LOCK = """Same person in all images.

A 21-year-old Japanese woman named Ru-nya.
Identical facial features across all scenes.
Soft droopy eyes, natural Japanese facial structure.
Small face, gentle jawline, subtle nose bridge.
Long dark brown semi-long hair with natural loose waves.
Thin straight bangs with slightly separated strands.
Fair smooth skin.

Makeup:
casual chic natural makeup,
soft rosy cheeks,
coral-beige lips,
light eye makeup,
fresh youthful university student vibe.

Fashion:
simple clean feminine outfit,
beige, ivory, white, light gray tones,
minimal accessories,
Instagram influencer aesthetic.

Mood:
soft vulnerable atmosphere,
natural realistic emotion,
slightly lonely but beautiful.

Photorealistic.
Japanese cinematic realism.
Vertical 9:16.
Shot on 50mm lens.
Shallow depth of field.
Warm natural lighting.
Instagram reel aesthetic."""

# ② 服装固定（同日撮影・全シーン統一）
OUTFIT_LOCK = (
    "wearing the same ivory knit sweater, "
    "same beige wide-leg trousers, "
    "same small gold hoop earrings, "
    "same outfit as all other scenes."
)

# ③ Scene Block（シーンごとの差分のみ・短く書く）
SCENES = [
    {
        "filename": "scene1_back_cafe.png",
        "prompt": f"""{CHARACTER_LOCK}

{OUTFIT_LOCK}

Scene:
Sitting alone at a cafe window seat in Tokyo, Japan.
Shot from behind, face not visible, back of head only.
Coffee cup on the table beside her.
Quiet Tokyo street visible outside the window.
Golden hour sunlight through the window.""",
    },
    {
        "filename": "scene2_table_coffee.png",
        "prompt": f"""{CHARACTER_LOCK}

{OUTFIT_LOCK}

Scene:
Close-up of her hands on a cafe table in Tokyo.
Latte art coffee cup and open notebook.
Ivory knit sweater sleeve visible.
Soft warm light, shallow depth of field.""",
    },
    {
        "filename": "scene3_window_city.png",
        "prompt": f"""{CHARACTER_LOCK}

Scene:
View through a Tokyo cafe window.
Blurred Japanese street outside — narrow roads, Japanese storefronts.
NOT European or American scenery.
Faint reflection of a woman sitting alone in the glass.
Golden hour light.""",
    },
    {
        "filename": "scene4_side_profile.png",
        "prompt": f"""{CHARACTER_LOCK}

{OUTFIT_LOCK}

Scene:
Side profile, turning slightly toward camera.
Tokyo cafe window with soft bokeh background.
Warm window light on her face.
Calm expression, slightly lonely, not smiling.
Smartphone selfie angle, slightly below eye level.""",
    },
]

# ベースキャラ画像（参照用・ナチュラルメイク版）
BASE_CHARACTER_SCENE = {
    "filename": "runyan_natural.png",
    "prompt": f"""{CHARACTER_LOCK}

{OUTFIT_LOCK}

Scene:
Front-facing portrait, looking directly at camera, calm gentle expression.
Tokyo cafe interior background, soft bokeh.
Character reference shot.""",
}


def generate_base_image(prompt: str, output_path: Path, label: str) -> bool:
    """ベースキャラ画像のみテキストから生成（1回だけ使用）"""
    print(f"  🎨 ベース生成中: {label}...")
    try:
        response = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1536",
            n=1,
        )
        image_data = base64.b64decode(response.data[0].b64_json)
        output_path.write_bytes(image_data)
        print(f"  ✅ 保存完了 [gpt-image-1]: {output_path}")
        return True
    except Exception as e:
        print(f"  ❌ ベース画像生成失敗: {e}")
        return False


def generate_image_from_reference(reference_path: Path, scene_prompt: str, output_path: Path, label: str) -> bool:
    """ベース参照画像を固定したまま、シーンだけ変えて生成（同一人物を維持）"""
    print(f"  🎨 シーン生成中: {label}...")

    # 顔・髪・メイクを固定するプレフィックス（顔一致率を最大化するキーワード）
    fixed_prefix = (
        "Same person as previous image. "
        "Keep identical facial features. "
        "Same eye shape and face proportions. "
        "Soft droopy eyes. "
        "Natural Japanese facial structure. "
        "Same hairstyle and bangs. "
        "Same hair color and length, same makeup style. "
        "Do NOT change the character's appearance. "
        "Only change the scene, background, clothing, and pose as described below. "
    )
    full_prompt = fixed_prefix + scene_prompt

    try:
        with open(reference_path, "rb") as img_file:
            response = client.images.edit(
                model="gpt-image-1",
                image=img_file,
                prompt=full_prompt,
                size="1024x1536",
            )
        image_data = base64.b64decode(response.data[0].b64_json)
        output_path.write_bytes(image_data)
        print(f"  ✅ 保存完了: {output_path}")
        return True
    except Exception as e:
        print(f"  ❌ 生成失敗: {e}")
        return False


def main():
    print("=" * 55)
    print("📸 るーにゃ 最初の投稿 画像生成（参照画像固定モード）")
    print(f"出力先（4シーン）: {output_dir.resolve()}")
    print(f"出力先（ベース）  : {chara_dir.resolve()}")
    print("=" * 55)

    results = {}
    base_path = chara_dir / BASE_CHARACTER_SCENE["filename"]

    # ベースキャラ画像が未生成の場合のみ生成
    print("\n[ベースキャラ画像]")
    if base_path.exists():
        print(f"  ✅ 既存ファイルを使用: {base_path}")
        results["ベース画像"] = "✅（既存）"
    else:
        ok = generate_base_image(BASE_CHARACTER_SCENE["prompt"], base_path, "ナチュラルメイク基準顔")
        results["ベース画像"] = "✅" if ok else "❌"

    if not base_path.exists():
        print("  ❌ ベース画像がないため4シーン生成をスキップ")
        return

    # 4シーンをベース画像から生成（同一人物を維持）
    print("\n[4シーン生成（ベース参照固定）]")
    for i, scene in enumerate(SCENES, 1):
        path = output_dir / scene["filename"]
        ok = generate_image_from_reference(base_path, scene["prompt"], path, f"シーン{i}")
        results[f"シーン{i}"] = "✅" if ok else "❌"

    # 結果サマリー
    print("\n" + "=" * 55)
    print("🎉 生成完了 サマリー")
    for label, status in results.items():
        print(f"  {status} {label}")
    print("=" * 55)
    print(f"\n📁 ファイル確認:")
    print(f"  first_post\\       ← 最初の投稿4シーン")
    print(f"  キャラ画像\\        ← パイプライン用ベース画像")


if __name__ == "__main__":
    main()
