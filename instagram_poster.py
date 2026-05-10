#!/usr/bin/env python3
"""Instagram カルーセル投稿モジュール

GitHub公開リポジトリを画像ホスティングに使用し、
Instagram Content Publishing API でカルーセル投稿する。
"""

import os
import time
import base64
import requests
from pathlib import Path
from datetime import datetime


def upload_to_github(image_path: str) -> str:
    """画像をGitHub公開リポジトリにアップロードして公開URLを返す"""
    github_pat = os.environ["GH_PAT"]
    images_repo = os.environ.get("INSTAGRAM_IMAGES_REPO", "fsmworks2026-svg/runyan-images")

    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{Path(image_path).name}"

    with open(image_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    res = requests.put(
        f"https://api.github.com/repos/{images_repo}/contents/images/{filename}",
        headers={
            "Authorization": f"token {github_pat}",
            "Accept": "application/vnd.github.v3+json",
        },
        json={
            "message": f"chore: 画像追加 {filename}",
            "content": content,
        },
    )
    if res.status_code not in (200, 201):
        raise Exception(f"GitHub画像アップロード失敗: {res.status_code} {res.text}")

    url = f"https://raw.githubusercontent.com/{images_repo}/main/images/{filename}"
    print(f"    アップロード完了: {url}")
    return url


def wait_for_container(container_id: str, page_token: str, max_attempts: int = 18) -> None:
    """コンテナのステータスが FINISHED になるまでポーリング（最大3分）"""
    for i in range(max_attempts):
        res = requests.get(
            f"https://graph.facebook.com/v25.0/{container_id}",
            params={"fields": "status_code", "access_token": page_token},
        )
        if res.status_code == 200:
            status = res.json().get("status_code", "")
            print(f"  コンテナステータス: {status} ({i + 1}/{max_attempts})")
            if status == "FINISHED":
                return
            if status == "ERROR":
                raise Exception(f"コンテナ処理エラー: {res.json()}")
        time.sleep(10)
    raise Exception("コンテナ処理タイムアウト（3分超過）")


def post_carousel_to_instagram(image_paths: list, caption: str) -> str:
    """複数画像をInstagramカルーセルとして投稿してpost_idを返す"""
    ig_user_id = os.environ["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
    page_token = os.environ["INSTAGRAM_PAGE_ACCESS_TOKEN"]

    # 1. 画像をGitHubにアップロードして公開URLを取得
    print(f"  GitHub公開リポジトリに画像アップロード中... ({len(image_paths)}枚)")
    image_urls = []
    for path in image_paths:
        url = upload_to_github(path)
        image_urls.append(url)
        time.sleep(2)  # GitHub API レート制限対策

    # 2. 各画像のカルーセルアイテムコンテナを作成
    print("  カルーセルアイテムを作成中...")
    item_ids = []
    for url in image_urls:
        res = requests.post(
            f"https://graph.facebook.com/v25.0/{ig_user_id}/media",
            params={
                "image_url": url,
                "is_carousel_item": "true",
                "access_token": page_token,
            },
        )
        if res.status_code != 200:
            raise Exception(f"カルーセルアイテム作成失敗: {res.status_code} {res.text}")
        item_ids.append(res.json()["id"])
        time.sleep(1)

    # 3. カルーセルコンテナを作成
    print("  カルーセルコンテナを作成中...")
    res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media",
        params={
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": page_token,
        },
    )
    if res.status_code != 200:
        raise Exception(f"カルーセルコンテナ作成失敗: {res.status_code} {res.text}")
    container_id = res.json()["id"]

    # 4. Instagramがメディアを取得・処理するまで待機
    wait_for_container(container_id, page_token)

    # 5. 投稿を公開
    print("  Instagramに投稿中...")
    res = requests.post(
        f"https://graph.facebook.com/v25.0/{ig_user_id}/media_publish",
        params={
            "creation_id": container_id,
            "access_token": page_token,
        },
    )
    if res.status_code != 200:
        raise Exception(f"Instagram投稿失敗: {res.status_code} {res.text}")

    post_id = res.json()["id"]
    print(f"✅ Instagram投稿完了: {post_id}")
    return post_id
