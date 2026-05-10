#!/usr/bin/env python3
"""Discord #video-uploads チャンネルを監視して Instagram にリール投稿するモジュール"""

import os
import sys
import time
import json
import requests
from pathlib import Path


def check_and_post_video() -> bool:
    """新しい動画を検出してInstagramにリール投稿する。投稿した場合True を返す。"""
    bot_token = os.environ["DISCORD_BOT_TOKEN"]
    channel_id = os.environ["DISCORD_VIDEO_CHANNEL_ID"]
    ig_user_id = os.environ["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
    page_token = os.environ["INSTAGRAM_PAGE_ACCESS_TOKEN"]
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

    # 最後に処理した動画のメッセージIDを読み込む
    state_path = Path("last_video_id.json")
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"last_id": "0"}
    last_id = state.get("last_id", "0")

    # チャンネルのメッセージを取得
    headers = {"Authorization": f"Bot {bot_token}"}
    res = requests.get(
        f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10",
        headers=headers,
    )
    if res.status_code != 200:
        print(f"❌ Discord API エラー: {res.status_code} {res.text}")
        sys.exit(1)

    messages = res.json()

    # 古い順に確認し、未処理の動画を探す
    for msg in reversed(messages):
        if int(msg["id"]) <= int(last_id):
            continue
        if msg.get("author", {}).get("bot"):
            continue

        for attachment in msg.get("attachments", []):
            content_type = attachment.get("content_type", "")
            if not content_type.startswith("video/"):
                continue

            video_url = attachment["url"]
            print(f"✅ 動画を検出: {attachment.get('filename')} ({attachment.get('size', 0) // 1024}KB)")

            # シナリオからキャプションを取得
            caption = _load_caption()

            # Instagramにリール投稿
            try:
                post_reel_to_instagram(video_url, caption, ig_user_id, page_token)

                # Discord に完了通知
                if webhook_url:
                    requests.post(webhook_url, json={
                        "content": f"✅ Instagram リール投稿完了！\n📎 {attachment.get('filename')}"
                    })
            except Exception as e:
                print(f"❌ Instagram投稿エラー: {e}")
                if webhook_url:
                    requests.post(webhook_url, json={"content": f"❌ Instagram投稿失敗: {e}"})
                sys.exit(1)

            # 処理済みとして記録
            state["last_id"] = msg["id"]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            return True

    print("新しい動画は見つかりませんでした")
    return False


def _load_caption() -> str:
    """current_scenario.json からキャプションとハッシュタグを読み込む"""
    scenario_path = Path("./current_scenario.json")
    if not scenario_path.exists():
        return ""
    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario = json.load(f)
    caption = scenario.get("caption", "")
    hashtags = " ".join(scenario.get("hashtags", []))
    return f"{caption}\n\n{hashtags}".strip()


def post_reel_to_instagram(video_url: str, caption: str, ig_user_id: str, page_token: str) -> str:
    """動画URLをInstagramにリールとして投稿してpost_idを返す"""

    # 1. メディアコンテナを作成
    print("  Instagramメディアコンテナを作成中...")
    res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": page_token,
        },
    )
    if res.status_code != 200:
        raise Exception(f"メディアコンテナ作成失敗: {res.status_code} {res.text}")
    container_id = res.json()["id"]
    print(f"  コンテナID: {container_id}")

    # 2. コンテナ処理完了をポーリング（最大5分）
    print("  動画処理待機中...")
    for i in range(30):
        time.sleep(10)
        status_res = requests.get(
            f"https://graph.facebook.com/v25.0/{container_id}",
            params={"fields": "status_code", "access_token": page_token},
        )
        if status_res.status_code == 200:
            status = status_res.json().get("status_code", "")
            print(f"    ステータス: {status} ({i + 1}/30)")
            if status == "FINISHED":
                break
            if status == "ERROR":
                raise Exception(f"コンテナ処理エラー: {status_res.json()}")
    else:
        raise Exception("コンテナ処理タイムアウト（5分超過）")

    # 3. 公開
    print("  Instagramに投稿中...")
    res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media_publish",
        params={
            "creation_id": container_id,
            "access_token": page_token,
        },
    )
    if res.status_code != 200:
        raise Exception(f"投稿失敗: {res.status_code} {res.text}")

    post_id = res.json()["id"]
    print(f"✅ Instagram リール投稿完了: {post_id}")
    return post_id


if __name__ == "__main__":
    check_and_post_video()
