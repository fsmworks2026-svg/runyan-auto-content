#!/usr/bin/env python3
"""
Instagram Stories 自動投稿モジュール。
daily_context の post_window に基づき、現在時刻に対応するスロットの画像を投稿する。
承認状態は approved_slots.json でスロット別に管理する（True = 承認済み）。
"""

import os
import sys
import time
import json
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))


def post_story_image(image_path: Path, ig_user_id: str, page_token: str, public_url: str = "") -> str:
    """
    Instagram Graph API で Stories に画像を投稿する。
    Stories 画像は image_url（公開URL）が必須仕様のため、GitHub raw content URL を使用する。
    """
    if not public_url:
        raise Exception("Stories 画像投稿には公開 URL（image_url）が必要です")

    # 1. コンテナ作成（image_url で公開URL を渡す）
    print("  📤 Storiesコンテナ作成...")
    res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media",
        params={
            "media_type":   "STORIES",
            "image_url":    public_url,
            "access_token": page_token,
        },
        timeout=30,
    )
    if res.status_code != 200:
        raise Exception(f"コンテナ作成失敗: {res.status_code} {res.text}")

    container_id = res.json()["id"]
    print(f"  コンテナID: {container_id}")

    # 2. FINISHED 待機（最大3分）
    print("  ⏳ Instagram 処理待機中...")
    for i in range(18):
        time.sleep(10)
        st = requests.get(
            f"https://graph.facebook.com/v25.0/{container_id}",
            params={"fields": "status_code", "access_token": page_token},
        ).json()
        status = st.get("status_code", "")
        print(f"    ステータス: {status} ({i + 1}/18)")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise Exception(f"コンテナエラー: {st}")
    else:
        raise Exception("コンテナ処理タイムアウト（3分超過）")

    # 3. 投稿
    print("  🚀 Instagram Stories に投稿中...")
    pub_res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media_publish",
        params={"creation_id": container_id, "access_token": page_token},
    )
    if pub_res.status_code != 200:
        raise Exception(f"投稿失敗: {pub_res.status_code} {pub_res.text}")

    post_id = pub_res.json()["id"]
    print(f"✅ ストーリーズ投稿完了: {post_id}")
    return post_id


def check_and_post_story():
    """現在の JST 時刻に対応するストーリーズスロットを投稿する。
    FORCE_SLOT 環境変数が指定されている場合は時間チェックをスキップして強制投稿する（テスト用）。
    """
    ig_user_id  = os.environ["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
    page_token  = os.environ["INSTAGRAM_PAGE_ACCESS_TOKEN"]
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    force_slot  = os.environ.get("FORCE_SLOT", "").strip()

    now_jst   = datetime.now(JST)
    now_hour  = now_jst.hour
    today_str = now_jst.strftime("%Y%m%d")

    print(f"JST {now_jst.strftime('%Y-%m-%d %H:%M')}（{today_str}）")
    if force_slot:
        print(f"⚡ FORCE_SLOT モード: {force_slot}")

    # スロット別承認状態を読み込む（FORCE_SLOT 時はスキップ）
    approved_slots_map = {}
    if not force_slot:
        slots_path = Path("./approved_slots.json")
        all_slots  = json.loads(slots_path.read_text(encoding="utf-8")) if slots_path.exists() else {}
        approved_slots_map = all_slots.get(today_str, {})

    # 今日の daily_context を読み込む
    ctx_path = Path(f"./daily_contexts/context_{today_str}.json")
    if not ctx_path.exists():
        print(f"コンテキストなし: {ctx_path.name}")
        sys.exit(0)
    ctx = json.loads(ctx_path.read_text(encoding="utf-8"))

    # 投稿済みスロットのログを読み込む
    log_path = Path("./stories_posted_log.json")
    log = json.loads(log_path.read_text(encoding="utf-8")) if log_path.exists() else {}
    posted_today = log.get(today_str, [])

    # スロット選択（FORCE_SLOT 時は時間チェックをスキップ）
    slot_to_post = None
    if force_slot:
        slot_to_post = next((s for s in ctx.get("story_slots", []) if s["id"] == force_slot), None)
        if not slot_to_post:
            print(f"❌ FORCE_SLOT '{force_slot}' が見つかりません。morning/noon/evening/night のいずれかを指定してください。")
            sys.exit(1)
    else:
        for slot in ctx.get("story_slots", []):
            if slot["id"] in posted_today:
                continue
            start, end = slot["post_window"]
            end_clamp  = 24 if end >= 24 else end
            if start <= now_hour < end_clamp:
                # スロット別承認チェック（True のみ投稿可）
                approval = approved_slots_map.get(slot["id"])
                if approval is not True:
                    status = "未承認（pending）" if approval is None else "却下（❌）"
                    print(f"{slot['emoji']} {slot['label']} スロットは{status}。スキップ。")
                    sys.exit(0)
                slot_to_post = slot
                break

    if not slot_to_post:
        print(f"現在時刻 {now_hour}時 に該当するスロットなし（または投稿済み）")
        sys.exit(0)

    print(f"\n{slot_to_post['emoji']} {slot_to_post['label']} スロット を投稿します")

    # 画像ファイルを探す（.jpg 優先）
    stories_dir = Path("./stories_output")
    image_path  = None
    for suffix in (".jpg", ".png"):
        p = stories_dir / f"story_{today_str}_{slot_to_post['id']}{suffix}"
        if p.exists():
            image_path = p
            break

    if not image_path:
        msg = f"ストーリーズ画像が見つかりません: story_{today_str}_{slot_to_post['id']}"
        print(f"❌ {msg}")
        if webhook_url:
            requests.post(webhook_url, json={"content": f"❌ {msg}"})
        sys.exit(1)

    # GitHub raw content URL（リポジトリが public なので公開アクセス可能）
    GH_RAW_BASE = "https://raw.githubusercontent.com/fsmworks2026-svg/runyan-auto-content/master"
    public_url  = f"{GH_RAW_BASE}/stories_output/{image_path.name}"
    print(f"  🔗 image_url: {public_url}")

    try:
        post_id = post_story_image(image_path, ig_user_id, page_token, public_url=public_url)

        # 投稿済みを記録
        posted_today.append(slot_to_post["id"])
        log[today_str] = posted_today
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

        if webhook_url:
            requests.post(webhook_url, json={
                "content": (
                    f"📱 ストーリーズ投稿完了 "
                    f"{slot_to_post['emoji']} {slot_to_post['label']}: {post_id}"
                )
            })

    except Exception as e:
        print(f"❌ ストーリーズ投稿エラー: {e}")
        if webhook_url:
            requests.post(webhook_url, json={
                "content": f"❌ ストーリーズ投稿失敗（{slot_to_post['label']}）: {e}"
            })
        sys.exit(1)


if __name__ == "__main__":
    check_and_post_story()
