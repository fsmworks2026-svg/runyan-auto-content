#!/usr/bin/env python3
"""
Discordリアクション・コマンドをリアルタイムで検知してGitHub Actionsを起動するローカルBot。
PC起動中に常駐させ、承認/スキップ/修正/新規作成を即時処理する。

【必要な環境変数（プロジェクトルートの .env に設定）】
  DISCORD_BOT_TOKEN              : DiscordボットのBotトークン
  GITHUB_PAT                     : GitHub Personal Access Token（repo + workflow 権限）
  DISCORD_SCENARIO_CHANNEL_ID    : 監視するDiscordチャンネルID（省略時 1502679588894019595）

【起動方法】
  pip install discord.py requests python-dotenv
  python discord_bot.py
"""

import discord
import requests
import json
import base64
import os
import sys
from datetime import datetime, timezone, timedelta

# .env ファイルがあれば読み込む
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────
# 設定
# ─────────────────────────────────────────
BOT_TOKEN  = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_SCENARIO_CHANNEL_ID", "1502679588894019595"))
GH_PAT     = os.getenv("GITHUB_PAT")
GH_REPO    = "fsmworks2026-svg/runyan-auto-content"

JST = timezone(timedelta(hours=9))

if not BOT_TOKEN or not GH_PAT:
    print("❌ 環境変数 DISCORD_BOT_TOKEN / GITHUB_PAT が未設定です")
    sys.exit(1)

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

client = discord.Client(intents=intents)


# ─────────────────────────────────────────
# GitHub Contents API ヘルパー
# ─────────────────────────────────────────
def _gh_headers() -> dict:
    return {
        "Authorization": f"token {GH_PAT}",
        "Accept": "application/vnd.github.v3+json",
    }


def trigger_workflow(workflow_file: str, inputs: dict = None) -> bool:
    """GitHub Actions workflow_dispatch でワークフローを起動する"""
    res = requests.post(
        f"https://api.github.com/repos/{GH_REPO}/actions/workflows/{workflow_file}/dispatches",
        headers=_gh_headers(),
        json={"ref": "master", "inputs": inputs or {}},
    )
    if res.status_code != 204:
        print(f"  ❌ {workflow_file} 起動失敗: {res.status_code} {res.text}")
        return False
    return True


def get_github_file(path: str) -> tuple:
    """GitHub Contents API でファイルを取得。(内容, SHA) を返す。404 の場合 (None, None)"""
    res = requests.get(
        f"https://api.github.com/repos/{GH_REPO}/contents/{path}",
        headers=_gh_headers(),
    )
    if res.status_code == 404:
        return None, None
    res.raise_for_status()
    data    = res.json()
    content = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
    return content, data["sha"]


def put_github_file(path: str, content, sha, message: str):
    """GitHub Contents API でファイルを作成・更新する"""
    encoded = base64.b64encode(
        json.dumps(content, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    body = {"message": message, "content": encoded}
    if sha:
        body["sha"] = sha
    res = requests.put(
        f"https://api.github.com/repos/{GH_REPO}/contents/{path}",
        headers=_gh_headers(),
        json=body,
    )
    res.raise_for_status()


# ─────────────────────────────────────────
# ステータス更新ヘルパー
# ─────────────────────────────────────────
def get_briefing_message_id() -> str | None:
    """
    current_scenario.json から pending 状態のブリーフィングメッセージIDを取得する。
    承認済み・スキップ済み・再生成中の場合は None を返す。
    """
    scenario, _ = get_github_file("current_scenario.json")
    if not scenario:
        return None
    if scenario.get("discord_status") == "pending":
        return str(scenario.get("discord_message_id", ""))
    return None


def approve_briefing() -> bool:
    """
    ✅ 検知時: discord_status を approved に更新し、approved_dates.json に日付を追加する。
    GitHub Contents API 経由でリポジトリを直接更新するため git 操作は不要。
    """
    scenario, sha = get_github_file("current_scenario.json")
    if not scenario:
        print("  ❌ current_scenario.json が存在しません")
        return False

    briefing_date             = scenario.get("briefing_date", "")
    scenario["discord_status"] = "approved"
    put_github_file(
        "current_scenario.json", scenario, sha,
        "chore: ✅ ブリーフィングを承認（ローカルBot）",
    )
    print(f"  current_scenario.json → approved")

    # approved_dates.json に日付を追加（stories_poster / feed_poster から参照される）
    if briefing_date:
        approved, sha2 = get_github_file("approved_dates.json")
        if approved is None:
            approved, sha2 = [], None
        if briefing_date not in approved:
            approved.append(briefing_date)
            put_github_file(
                "approved_dates.json", approved, sha2,
                f"chore: 承認日付を追加 {briefing_date}（ローカルBot）",
            )
            print(f"  approved_dates.json に {briefing_date} を追加")

    return True


def skip_briefing():
    """❌ 検知時: discord_status を skipped に更新する"""
    scenario, sha = get_github_file("current_scenario.json")
    if not scenario:
        return
    scenario["discord_status"] = "skipped"
    put_github_file(
        "current_scenario.json", scenario, sha,
        "chore: ❌ 今日のコンテンツをスキップ（ローカルBot）",
    )
    print("  current_scenario.json → skipped")


def set_regenerating():
    """修正コマンド検知時: discord_status を regenerating に更新する"""
    scenario, sha = get_github_file("current_scenario.json")
    if not scenario:
        return
    scenario["discord_status"] = "regenerating"
    put_github_file(
        "current_scenario.json", scenario, sha,
        "chore: 修正シナリオ再生成中（ローカルBot）",
    )
    print("  current_scenario.json → regenerating")


def update_last_command_id(message_id: str):
    """
    新規: コマンド処理後に last_command_id.json を更新する。
    バックアップポーリングが同じコマンドを再処理しないようにする。
    """
    state, sha = get_github_file("last_command_id.json")
    if state is None:
        state, sha = {"last_id": "0"}, None
    state["last_id"] = message_id
    put_github_file(
        "last_command_id.json", state, sha,
        "chore: Discord 新規コマンド処理済みIDを更新（ローカルBot）",
    )


# ─────────────────────────────────────────
# Discord イベントハンドラ
# ─────────────────────────────────────────
@client.event
async def on_ready():
    print(f"✅ Discordボット起動完了: {client.user}")
    print(f"   監視チャンネルID: {CHANNEL_ID}")
    print(f"   リポジトリ: {GH_REPO}")


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    """ブリーフィングメッセージへのリアクションを監視する（✅ / ❌）"""
    if payload.channel_id != CHANNEL_ID:
        return
    # bot 自身のリアクションは無視
    if payload.user_id == client.user.id:
        return

    message_id  = str(payload.message_id)
    briefing_id = get_briefing_message_id()

    if not briefing_id or message_id != briefing_id:
        return

    emoji = str(payload.emoji)
    now   = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    print(f"\n[{now}] リアクション検知: {emoji} (メッセージID: {message_id})")

    if emoji == "✅":
        print("  → コンテンツ生成を起動します")
        if approve_briefing():
            ok = trigger_workflow("runyan-generate.yml")
            print(f"  runyan-generate.yml: {'✅ 起動成功' if ok else '❌ 起動失敗'}")

    elif emoji == "❌":
        print("  → 今日のコンテンツをスキップします")
        skip_briefing()


@client.event
async def on_message(message: discord.Message):
    """チャンネルメッセージを監視する（「新規:」「修正:」コマンド）"""
    if message.author.bot:
        return
    if message.channel.id != CHANNEL_ID:
        return

    content = message.content.strip()
    now     = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")

    # ── 「新規:」コマンド（スポット投稿）──
    if content.startswith("新規:"):
        theme = content[3:].strip()
        print(f"\n[{now}] 新規リール作成コマンド検出: {theme}")
        ok = trigger_workflow(
            "runyan-scenario.yml",
            {"theme_override": theme, "is_spot_reel": "true"},
        )
        if ok:
            print(f"  ✅ runyan-scenario.yml 起動成功（テーマ: {theme}）")
            try:
                update_last_command_id(str(message.id))
                print(f"  last_command_id.json → {message.id}")
            except Exception as e:
                print(f"  ⚠️ last_command_id.json 更新失敗（無視）: {e}")
        return

    # ── ストーリーズ個別作り直しコマンド ──
    # 書式: 「朝作り直し: [指示]」「昼作り直し: [指示]」「夕方作り直し: [指示]」「夜作り直し: [指示]」
    STORY_REDO = {"朝作り直し:": "morning", "昼作り直し:": "afternoon", "夕方作り直し:": "evening", "夜作り直し:": "night"}
    for prefix, slot_id in STORY_REDO.items():
        if content.startswith(prefix):
            hint = content[len(prefix):].strip()
            print(f"\n[{now}] ストーリーズ再生成コマンド検出: slot={slot_id} hint={hint!r}")
            ok = trigger_workflow(
                "runyan-redo-story.yml",
                {"slot": slot_id, "override_hint": hint, "target_date": ""},
            )
            print(f"  runyan-redo-story.yml: {'✅ 起動成功' if ok else '❌ 起動失敗'}")
            return

    # ── 「修正:」コマンド または ブリーフィングへの返信 ──
    briefing_id = get_briefing_message_id()
    if not briefing_id:
        return

    is_reply      = (message.reference is not None and
                     str(message.reference.message_id) == briefing_id)
    is_correction = content.startswith("修正:")

    if is_reply or is_correction:
        print(f"\n[{now}] 修正コマンド検出: {content}")
        set_regenerating()
        ok = trigger_workflow("runyan-scenario.yml", {"theme_override": content})
        print(f"  runyan-scenario.yml: {'✅ 起動成功' if ok else '❌ 起動失敗'}")


if __name__ == "__main__":
    print("Discordボット起動中...")
    client.run(BOT_TOKEN)
