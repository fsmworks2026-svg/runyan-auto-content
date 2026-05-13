#!/usr/bin/env python3
"""
Discord #video-uploads チャンネルを監視して Instagram にリール投稿するモジュール。
動画は Discord からダウンロード → ffmpeg でメタデータ除去 → Instagram resumable upload
で直接バイナリ送信する（公開URLを経由しないためメタデータが残らない）。
"""

import os
import sys
import time
import json
import tempfile
import requests
from pathlib import Path

from datetime import datetime
from strip_metadata import strip_video


def check_and_post_video() -> bool:
    """新しい動画を検出してInstagramにリール投稿する。投稿した場合Trueを返す。
    投稿ウィンドウ外でも処理済み動画の保存は行う。
    """
    bot_token   = os.environ["DISCORD_BOT_TOKEN"]
    channel_id  = os.environ["DISCORD_VIDEO_CHANNEL_ID"]
    ig_user_id  = os.environ["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
    page_token  = os.environ["INSTAGRAM_PAGE_ACCESS_TOKEN"]
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

    from zoneinfo import ZoneInfo
    _jst   = ZoneInfo("Asia/Tokyo")
    _now   = datetime.now(_jst)
    _today = _now.strftime("%Y%m%d")
    # reel_post_window は参照のみ（ログ表示用）。投稿はブロックしない。
    # cron が JST 10-22 限定なので、アップロードされたその日のうちに投稿するのが正しい動作。
    _ctx_path = Path(f"./daily_contexts/context_{_today}.json")
    if _ctx_path.exists():
        _ctx = json.loads(_ctx_path.read_text(encoding="utf-8"))
        pw   = _ctx.get("reel_post_window", [])
        if len(pw) == 2:
            in_window = pw[0] <= _now.hour < pw[1]
            print(f"reel_post_window: {pw[0]}〜{pw[1]}時（現在 {_now.hour}時）{'✅ 内' if in_window else '⚠️ 外だが投稿続行'}（cron JST 10-22 が外枠）")

    # 最後に処理した動画のメッセージIDを読み込む
    state_path = Path("last_video_id.json")
    state   = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"last_id": "0"}
    last_id = state.get("last_id", "0")

    headers = {"Authorization": f"Bot {bot_token}"}
    res = requests.get(
        f"https://discord.com/api/v10/channels/{channel_id}/messages?limit=10",
        headers=headers,
    )
    if res.status_code != 200:
        print(f"❌ Discord API エラー: {res.status_code} {res.text}")
        sys.exit(1)

    for msg in reversed(res.json()):
        if int(msg["id"]) <= int(last_id):
            continue
        if msg.get("author", {}).get("bot"):
            continue

        for attachment in msg.get("attachments", []):
            if not attachment.get("content_type", "").startswith("video/"):
                continue

            filename = attachment.get("filename", "video.mp4")
            size_kb  = attachment.get("size", 0) // 1024
            print(f"✅ 動画を検出: {filename} ({size_kb}KB)")

            caption = _load_caption()

            # 処理済み動画の保存先（reel_output/ に永続保存）
            reel_dir       = Path("./reel_output")
            reel_dir.mkdir(exist_ok=True)
            processed_path = reel_dir / f"reel_{_today}.mov"

            try:
                if processed_path.exists():
                    print(f"  ✅ 処理済み動画が既に存在: {processed_path.name}")
                else:
                    # Discord からダウンロードしてメタデータを除去・永続保存
                    with tempfile.TemporaryDirectory() as tmpdir:
                        raw_path   = Path(tmpdir) / filename
                        clean_path = Path(tmpdir) / f"clean_{Path(filename).stem}_iphone.mov"

                        print("  ⬇️  動画ダウンロード中...")
                        _download_file(attachment["url"], raw_path)

                        print("  🧹 メタデータを iPhone 15 Pro に書き換え中...")
                        strip_video(raw_path, clean_path, shoot_time=datetime.now(_jst))

                        import shutil
                        shutil.copy(clean_path, processed_path)
                    print(f"  💾 処理済み動画を保存: {processed_path.name}")
                    if webhook_url:
                        requests.post(webhook_url, json={"content": f"💾 動画処理完了・保存済み: {processed_path.name}"})

                # Instagram resumable upload で投稿
                post_id = _post_reel_resumable(processed_path, caption, ig_user_id, page_token)

                # 投稿完了後に処理済みファイルを削除（動画 + リール画像）
                for _del in [processed_path, reel_dir / f"reel_{_today}.jpg", reel_dir / f"reel_{_today}.png"]:
                    if _del.exists():
                        _del.unlink()
                        print(f"  🗑️  投稿済みファイルを削除: {_del.name}")

                if webhook_url:
                    requests.post(webhook_url, json={
                        "content": f"✅ Instagram リール投稿完了！\n📎 {filename}"
                    })

            except Exception as e:
                print(f"❌ 処理/投稿エラー: {e}")
                if webhook_url:
                    requests.post(webhook_url, json={"content": f"❌ リール処理/投稿失敗: {e}"})
                sys.exit(1)

            state["last_id"] = msg["id"]
            state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            return True

    print("新しい動画は見つかりませんでした")
    return False


def _download_file(url: str, path: Path):
    """URLからファイルをストリームダウンロード"""
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            f.write(chunk)


def _load_caption() -> str:
    """current_scenario.json からキャプションとハッシュタグを読み込む"""
    path = Path("./current_scenario.json")
    if not path.exists():
        return ""
    scenario = json.loads(path.read_text(encoding="utf-8"))
    caption   = scenario.get("caption", "")
    hashtags  = " ".join(scenario.get("hashtags", []))
    return f"{caption}\n\n{hashtags}".strip()


def _post_reel_resumable(video_path: Path, caption: str, ig_user_id: str, page_token: str) -> str:
    """
    Instagram Graph API の resumable upload でリールを投稿する。
    動画ファイルのバイナリを直接送信するため公開URLが不要。
    """
    file_size = video_path.stat().st_size

    # 1. アップロードセッション開始（resumable）
    print("  📤 Instagramアップロードセッション開始...")
    res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media",
        params={
            "media_type":    "REELS",
            "upload_type":   "resumable",
            "content_type":  "video/quicktime",  # .mov ファイルのため明示指定
            "caption":       caption,
            "share_to_feed": "true",
            "access_token":  page_token,
        },
    )
    if res.status_code != 200:
        raise Exception(f"アップロードセッション開始失敗: {res.status_code} {res.text}")

    data         = res.json()
    container_id = data["id"]
    upload_uri   = data.get("uri")
    if not upload_uri:
        raise Exception(f"upload_uri が取得できません: {data}")
    print(f"  コンテナID: {container_id}")

    # 2. 動画バイナリを送信
    print(f"  ⬆️  動画バイナリ送信中（{file_size // 1024}KB）...")
    with open(video_path, "rb") as f:
        upload_res = requests.post(
            upload_uri,
            headers={
                "Authorization": f"OAuth {page_token}",
                "offset":        "0",
                "file_size":     str(file_size),
            },
            data=f,
            timeout=300,
        )
    if upload_res.status_code not in (200, 201):
        raise Exception(f"動画バイナリ送信失敗: {upload_res.status_code} {upload_res.text}")
    print("  ✅ バイナリ送信完了")

    # 3. 処理完了をポーリング（最大5分）
    print("  ⏳ Instagram処理待機中...")
    for i in range(30):
        time.sleep(10)
        status_res = requests.get(
            f"https://graph.facebook.com/v25.0/{container_id}",
            params={"fields": "status_code", "access_token": page_token},
        )
        status = status_res.json().get("status_code", "")
        print(f"    ステータス: {status} ({i + 1}/30)")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise Exception(f"コンテナ処理エラー: {status_res.json()}")
    else:
        raise Exception("コンテナ処理タイムアウト（5分超過）")

    # 4. 公開
    print("  🚀 Instagram に投稿中...")
    pub_res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media_publish",
        params={"creation_id": container_id, "access_token": page_token},
    )
    if pub_res.status_code != 200:
        raise Exception(f"投稿失敗: {pub_res.status_code} {pub_res.text}")

    post_id = pub_res.json()["id"]
    print(f"✅ Instagram リール投稿完了: {post_id}")
    return post_id


if __name__ == "__main__":
    check_and_post_video()
