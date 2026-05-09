"""
るーにゃ Discord ボット
- シナリオ投稿を検知して ✅/❌ リアクションを自動追加
- ✅ → GitHub Actions Step2 を起動
- ❌ → スキップ
- 返信コメント → 修正内容を反映して Step2 を起動
"""
import discord
import requests
import os

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GITHUB_PAT = os.getenv("GITHUB_PAT")
GITHUB_REPO = "fsmworks2026-svg/runyan-auto-content"
SCENARIO_CHANNEL_ID = int(os.getenv("DISCORD_SCENARIO_CHANNEL_ID", "1502679588894019595"))

# 現在監視中のシナリオメッセージID（再起動時はスキャンで復元）
current_scenario_message_id = None

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.messages = True

client = discord.Client(intents=intents)


def trigger_step2(overrides: dict = None) -> bool:
    """GitHub Actions の Step2 ワークフローを起動する"""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/runyan-generate.yml/dispatches"
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json",
    }
    inputs = {}
    if overrides:
        for key, value in overrides.items():
            if value:
                inputs[f"override_{key}"] = value

    res = requests.post(url, json={"ref": "master", "inputs": inputs}, headers=headers)
    return res.status_code == 204


def is_scenario_message(message: discord.Message) -> bool:
    """シナリオ投稿かどうかを判定する"""
    return bool(
        message.embeds
        and any("今日のシナリオ確認" in (e.title or "") for e in message.embeds)
    )


@client.event
async def on_ready():
    global current_scenario_message_id
    print(f"✅ るーにゃBot 起動: {client.user}")

    # 起動時にチャンネルの直近メッセージからシナリオを復元
    channel = client.get_channel(SCENARIO_CHANNEL_ID)
    if channel:
        async for message in channel.history(limit=20):
            if is_scenario_message(message):
                current_scenario_message_id = message.id
                print(f"  シナリオメッセージを復元: {message.id}")
                break


@client.event
async def on_message(message: discord.Message):
    global current_scenario_message_id

    if message.channel.id != SCENARIO_CHANNEL_ID:
        return

    # シナリオ投稿を検知 → リアクションを自動追加
    if is_scenario_message(message):
        current_scenario_message_id = message.id
        await message.add_reaction("✅")
        await message.add_reaction("❌")
        return

    # ユーザーからのシナリオへの返信（修正コメント）
    if (
        not message.author.bot
        and message.reference
        and message.reference.message_id == current_scenario_message_id
    ):
        await message.reply("✏️ 修正内容を確認しました！反映して生成を開始します...")
        success = trigger_step2({"scenario": message.content})
        if success:
            await message.reply("🎬 5〜10分後に Discord へ届きます！")
        else:
            await message.reply("❌ GitHub Actions の起動に失敗しました。管理者に確認してください。")


@client.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.user_id == client.user.id:
        return
    if payload.channel_id != SCENARIO_CHANNEL_ID:
        return
    if payload.message_id != current_scenario_message_id:
        return

    channel = client.get_channel(payload.channel_id)

    if str(payload.emoji) == "✅":
        await channel.send("✅ OK確認！画像・動画の生成を開始します...")
        success = trigger_step2()
        if success:
            await channel.send("🎬 5〜10分後に Discord へ届きます！")
        else:
            await channel.send("❌ GitHub Actions の起動に失敗しました。")

    elif str(payload.emoji) == "❌":
        await channel.send("⏭️ 今日のコンテンツはスキップします。")


client.run(DISCORD_BOT_TOKEN)
