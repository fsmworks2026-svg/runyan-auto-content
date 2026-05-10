#!/usr/bin/env python3
"""
るーにゃ 最初の投稿（自己紹介リール）を Discord に送信して確認するスクリプト
"""

import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# 最初の投稿のキャプション
CAPTION = """はじめまして、るーにゃです🐱

21歳 / 文系女子大3年 / 東京在住

きれいめが好きで大人っぽく見られたいんだけど、
実際はぼっち気味で毎日バタバタしてます🫥

バイトのこと、大学のこと、たまに本音も。
ゆるく更新していくので、よかったら仲良くしてください☕

─────────────────
#大学生 #上京女子 #女子大生の日常
#きれいめコーデ #ひとり暮らし
#るーにゃ"""

SCENES = [
    {"path": Path("./first_post/scene1_back_cafe.png"),    "label": "シーン1：後ろ姿・カフェ窓際"},
    {"path": Path("./first_post/scene2_table_coffee.png"), "label": "シーン2：テーブル・コーヒーとノート"},
    {"path": Path("./first_post/scene3_window_city.png"),  "label": "シーン3：窓の外・街並みぼかし"},
    {"path": Path("./first_post/scene4_side_profile.png"), "label": "シーン4：振り返り・横顔"},
]


def send_header():
    """投稿概要をEmbedで送信"""
    embed = {
        "title": "📋 最初の投稿（自己紹介リール）確認",
        "description": CAPTION,
        "color": 0xFF69B4,
        "fields": [
            {"name": "👤 アカウント名", "value": "@runyan_1220", "inline": True},
            {"name": "💄 メイク",       "value": "おしゃれカジュアルナチュラル", "inline": True},
            {"name": "📸 シーン数",     "value": "4枚", "inline": True},
        ],
        "footer": {"text": "✅ OK / ❌ 修正 をコメントしてください"},
    }
    res = requests.post(DISCORD_WEBHOOK_URL + "?wait=true", json={"embeds": [embed]})
    if res.status_code == 200:
        print("✅ ヘッダー送信完了")
    else:
        print(f"❌ ヘッダー送信失敗: {res.status_code} {res.text}")


def send_image(scene: dict, index: int):
    """画像1枚をDiscordに送信"""
    path = scene["path"]
    label = scene["label"]

    if not path.exists():
        print(f"  ❌ ファイルが見つかりません: {path}")
        return

    print(f"  📤 送信中: {label}...")
    with open(path, "rb") as f:
        res = requests.post(
            DISCORD_WEBHOOK_URL,
            data={"content": f"**{label}**"},
            files={"file": (path.name, f, "image/png")},
        )
    if res.status_code in (200, 204):
        print(f"  ✅ 送信完了: {label}")
    else:
        print(f"  ❌ 送信失敗: {res.status_code} {res.text}")


def main():
    print("=" * 50)
    print("💬 Discord 送信開始")
    print("=" * 50)

    # 1. 概要Embed送信
    send_header()

    # 2. 4シーン画像を順番に送信
    print("\n[画像送信]")
    for i, scene in enumerate(SCENES, 1):
        send_image(scene, i)

    print("\n" + "=" * 50)
    print("🎉 Discord 送信完了！確認してください")
    print("=" * 50)


if __name__ == "__main__":
    main()
