#!/usr/bin/env python3
"""
るーにゃ 最初の投稿（自己紹介リール）画像生成スクリプト
gpt-image-2 + quality_mode="thinking" + n=4 で4シーンを1回のAPIコールで一括生成。
同一キャラクターの一貫性を最大化する。
"""

import os
import base64
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

output_dir = Path("./first_post")
chara_dir  = Path("./キャラ画像")
output_dir.mkdir(exist_ok=True)
chara_dir.mkdir(exist_ok=True)

BASE_PATH = chara_dir / "runyan_natural.png"

# 出力ファイル名（n=4 の順番と対応）
SCENE_FILENAMES = [
    "scene1_back_cafe.png",
    "scene2_table_coffee.png",
    "scene3_window_city.png",
    "scene4_side_profile.png",
]

# 4シーン一括プロンプト（quality_mode="thinking" で一貫性確保）
BATCH_PROMPT = """Same person in all 4 images.

Ru-nya, 21-year-old Japanese woman.
Consistent facial features across all scenes.
Same hairstyle, same bangs, same eye shape, same face proportions.

Soft slightly droopy eyes.
Natural Japanese facial structure.
Small face, gentle jawline.
Fair smooth skin.

Long dark brown semi-long hair with natural loose waves.
Thin airy bangs.

Natural casual chic makeup.
Soft rosy cheeks.
Coral-beige lips.
Light eye makeup.

wearing the same ivory knit top.
same outfit in all images.

Photorealistic.
Japanese cinematic realism.
Warm natural light.
50mm lens.
Shallow depth of field.
Soft bokeh.
Instagram reel aesthetic.
Vertical 9:16.

Generate exactly 4 images in this order:

Image 1 - Back Shot:
Ru-nya sitting alone at a Tokyo cafe window seat, shot from behind.
Face NOT visible, back of head only.
Coffee cup on table. Golden hour light. Tokyo street outside.

Image 2 - Table Close-up:
Close-up of her hands on the cafe table.
Latte art coffee and open notebook. Ivory knit sleeve visible.
Soft warm side light.

Image 3 - Window View:
View through the Tokyo cafe window from inside.
Blurred Japanese street outside — narrow roads, Japanese storefronts.
NOT European. Faint woman reflection in glass. Golden hour.

Image 4 - Side Profile:
Ru-nya turning slightly toward camera, side profile.
Accurate side profile, consistent facial proportions.
Tokyo cafe window bokeh background. Warm window light.
Calm expression, slightly lonely, not smiling.
Selfie angle, slightly below eye level.

All 4 images: same Tokyo cafe, same day, same character, same outfit."""


def save_image(data_item, output_path: Path) -> bool:
    """レスポンスの1アイテムを画像ファイルとして保存（b64_json / url 両対応）"""
    try:
        if hasattr(data_item, "b64_json") and data_item.b64_json:
            output_path.write_bytes(base64.b64decode(data_item.b64_json))
        elif hasattr(data_item, "url") and data_item.url:
            import requests
            output_path.write_bytes(requests.get(data_item.url, timeout=60).content)
        else:
            print(f"  ❌ 画像データが取得できません: {data_item}")
            return False
        return True
    except Exception as e:
        print(f"  ❌ 保存エラー: {e}")
        return False


def generate_scenes_thinking() -> dict:
    """gpt-image-2 Thinkingモードで4シーンを1回のAPIコールで一括生成"""
    print("  🧠 gpt-image-2 Thinking mode で4シーン一括生成中...")
    print("  （Thinkingモードは時間がかかる場合があります）")

    results = {}

    try:
        response = client.images.generate(
            model="gpt-image-2",
            prompt=BATCH_PROMPT,
            n=4,
            size="576x1024",        # 9:16 縦型
            quality_mode="thinking", # キャラクター一貫性を最大化
        )

        for i, (item, filename) in enumerate(zip(response.data, SCENE_FILENAMES), 1):
            path = output_dir / filename
            ok = save_image(item, path)
            if ok:
                print(f"  ✅ シーン{i} 保存完了: {filename}")
                results[f"シーン{i}"] = "✅"
            else:
                results[f"シーン{i}"] = "❌"

    except Exception as e:
        print(f"  ❌ Thinking mode 生成失敗: {e}")
        print("  ⚠️  quality_mode='thinking' 未対応の可能性。通常モードで再試行します...")
        results = generate_scenes_fallback()

    return results


def generate_scenes_fallback() -> dict:
    """Thinkingモード非対応時のフォールバック（参照画像ベース・個別生成）"""
    if not BASE_PATH.exists():
        print(f"  ❌ ベース画像がありません: {BASE_PATH}")
        return {f"シーン{i}": "❌" for i in range(1, 5)}

    SCENE_PROMPTS = [
        f"{BATCH_PROMPT.split('Generate exactly')[0]}\nScene:\nBack shot at Tokyo cafe, face not visible.",
        f"{BATCH_PROMPT.split('Generate exactly')[0]}\nScene:\nTable close-up, hands near latte, ivory knit sleeve.",
        f"{BATCH_PROMPT.split('Generate exactly')[0]}\nScene:\nView through Tokyo cafe window, Japanese street outside.",
        f"{BATCH_PROMPT.split('Generate exactly')[0]}\nScene:\nSide profile, selfie angle, Tokyo cafe bokeh, calm expression.",
    ]

    results = {}
    for i, (prompt, filename) in enumerate(zip(SCENE_PROMPTS, SCENE_FILENAMES), 1):
        path = output_dir / filename
        print(f"  🎨 シーン{i} 生成中（参照画像モード）...")
        try:
            with open(BASE_PATH, "rb") as img_file:
                response = client.images.edit(
                    model="gpt-image-2",
                    image=img_file,
                    prompt=prompt,
                    size="576x1024",
                )
            ok = save_image(response.data[0], path)
            results[f"シーン{i}"] = "✅" if ok else "❌"
            if ok:
                print(f"  ✅ シーン{i} 保存: {filename}")
        except Exception as e:
            print(f"  ❌ シーン{i} 失敗: {e}")
            results[f"シーン{i}"] = "❌"

    return results


def main():
    print("=" * 55)
    print("📸 るーにゃ 最初の投稿 画像生成")
    print("   モデル: gpt-image-2 (Thinking mode)")
    print(f"   出力先: {output_dir.resolve()}")
    print("=" * 55)

    # ベース画像チェック（上書き禁止）
    print("\n[ベースキャラ画像]")
    if BASE_PATH.exists():
        print(f"  ✅ 既存使用（上書き禁止）: {BASE_PATH}")
    else:
        print(f"  ⚠️  {BASE_PATH} なし（Thinkingモードでは不要・続行します）")

    # 既存シーンをスキップする確認
    missing = [fn for fn in SCENE_FILENAMES if not (output_dir / fn).exists()]
    existing = [fn for fn in SCENE_FILENAMES if (output_dir / fn).exists()]

    if existing:
        print(f"\n  スキップ（既存）: {', '.join(existing)}")
    if not missing:
        print("  全シーン既存のため生成をスキップします")
        print("  再生成したい場合は first_post フォルダのファイルを削除してください")
        return

    # 4シーン一括生成
    print(f"\n[4シーン一括生成] 未生成: {len(missing)}枚")
    results = generate_scenes_thinking()

    # サマリー
    print("\n" + "=" * 55)
    print("🎉 生成完了")
    for label, status in results.items():
        print(f"  {status} {label}")
    print("=" * 55)


if __name__ == "__main__":
    main()
