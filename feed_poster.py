#!/usr/bin/env python3
"""
Instagram フィード画像投稿モジュール。
resumable upload → FINISHED 待機 → media_publish の流れで画像をフィードに投稿する。
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from datetime import date, datetime
from strip_metadata import strip_image


def post_feed_image(image_path: Path, caption: str, ig_user_id: str, page_token: str) -> str:
    """
    Instagram Graph API でフィード画像を投稿する。
    resumable upload で直接バイナリ送信するため公開 URL が不要。
    """
    file_size = image_path.stat().st_size

    # 1. コンテナ作成（resumable）
    print("  📤 フィードアップロードセッション開始...")
    res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media",
        params={
            "media_type":   "IMAGE",
            "upload_type":  "resumable",
            "caption":      caption,
            "access_token": page_token,
        },
    )
    if res.status_code != 200:
        raise Exception(f"コンテナ作成失敗: {res.status_code} {res.text}")

    data         = res.json()
    container_id = data["id"]
    upload_uri   = data.get("uri")
    if not upload_uri:
        raise Exception(f"upload_uri 取得失敗: {data}")
    print(f"  コンテナID: {container_id}")

    # 2. バイナリ送信
    print(f"  ⬆️  画像バイナリ送信中 ({file_size // 1024}KB)...")
    with open(image_path, "rb") as f:
        up_res = requests.post(
            upload_uri,
            headers={
                "Authorization": f"OAuth {page_token}",
                "offset":        "0",
                "file_size":     str(file_size),
            },
            data=f,
            timeout=120,
        )
    if up_res.status_code not in (200, 201):
        raise Exception(f"バイナリ送信失敗: {up_res.status_code} {up_res.text}")
    print("  ✅ バイナリ送信完了")

    # 3. FINISHED 待機（最大10分）
    print("  ⏳ Instagram 処理待機中...")
    for i in range(60):
        time.sleep(10)
        st_res = requests.get(
            f"https://graph.facebook.com/v25.0/{container_id}",
            params={"fields": "status_code", "access_token": page_token},
        )
        status = st_res.json().get("status_code", "")
        print(f"    ステータス: {status} ({i + 1}/18)")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise Exception(f"コンテナエラー: {st_res.json()}")
    else:
        raise Exception("コンテナ処理タイムアウト（3分超過）")

    # 4. 公開
    print("  🚀 Instagram フィードに投稿中...")
    pub_res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media_publish",
        params={"creation_id": container_id, "access_token": page_token},
    )
    if pub_res.status_code != 200:
        raise Exception(f"投稿失敗: {pub_res.status_code} {pub_res.text}")

    post_id = pub_res.json()["id"]
    print(f"✅ Instagram フィード投稿完了: {post_id}")
    return post_id


def check_and_post_feed() -> bool:
    """今日のフィード投稿をチェックして実行する。投稿した場合 True を返す。"""
    ig_user_id  = os.environ["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
    page_token  = os.environ["INSTAGRAM_PAGE_ACCESS_TOKEN"]
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

    import daily_context as dc
    import generate_feed as gf
    from datetime import timezone, timedelta

    JST = timezone(timedelta(hours=9))
    today_str = datetime.now(JST).strftime("%Y%m%d")

    # 承認確認（approved_dates.json で管理）
    approved_path = Path("./approved_dates.json")
    approved_dates = json.loads(approved_path.read_text(encoding="utf-8")) if approved_path.exists() else []
    if today_str not in approved_dates:
        print(f"本日({today_str})は未承認。スキップ。")
        return False

    # 今日のコンテキストを読み込む
    ctx_path = Path(f"./daily_contexts/context_{today_str}.json")
    if not ctx_path.exists():
        print(f"コンテキストなし: {today_str}")
        return False
    ctx = json.loads(ctx_path.read_text(encoding="utf-8"))

    if not ctx.get("has_feed"):
        print("今日はフィード投稿予定なし")
        return False

    # 現在時刻が feed_post_window 内かチェック
    now_hour = datetime.now(JST).hour
    pw = ctx.get("feed_post_window", [])
    if len(pw) == 2 and not (pw[0] <= now_hour < pw[1]):
        print(f"現在時刻 {now_hour}時 は投稿ウィンドウ外（{pw[0]}〜{pw[1]}時）。スキップ。")
        return False

    # 投稿済みチェック
    log_path      = Path("./feed_posted_log.json")
    log           = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}
    if log.get(today_str):
        print(f"本日({today_str})は投稿済み。スキップ。")
        return False

    # フィード画像を取得
    feed_image = _find_feed_image(ctx)
    if not feed_image:
        print("❌ フィード画像が見つかりません")
        return False

    caption = gf.pick_feed_caption(ctx)

    try:
        post_id = post_feed_image(feed_image, caption, ig_user_id, page_token)

        # 投稿済みを記録
        log[today_str] = post_id
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

        if webhook_url:
            requests.post(webhook_url, json={
                "content": f"✅ Instagram フィード投稿完了！: {post_id}"
            })
        return True
    except Exception as e:
        print(f"❌ フィード投稿エラー: {e}")
        if webhook_url:
            requests.post(webhook_url, json={"content": f"❌ フィード投稿失敗: {e}"})
        sys.exit(1)


def _find_feed_image(ctx: dict) -> Path | None:
    """フィード用画像ファイルを探す（food → generated_content の最新 jpg の順）"""
    today_str = ctx["date"]
    feed_dir  = Path("./feed_output")

    for suffix in (".jpg", ".png"):
        p = feed_dir / f"feed_food_{today_str}{suffix}"
        if p.exists():
            return p

    # person タイプ: reel_output のリール画像を流用
    reel_dir = Path("./reel_output")
    for suffix in (".jpg", ".png"):
        p = reel_dir / f"reel_{today_str}{suffix}"
        if p.exists():
            return p

    return None


if __name__ == "__main__":
    check_and_post_feed()
