#!/usr/bin/env python3
"""
るーにゃ 自動コンテンツ生成パイプライン
- シナリオ自動生成（Claude API）
- 画像生成（gpt-image-2）
- 動画化（ElevenLabs Seedance）
- Google Drive保存
- Discord通知
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
import io
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import googleapiclient.discovery
from googleapiclient.http import MediaFileUpload

# 環境変数の読み込み
load_dotenv()

# API設定
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")

# キャラクター設定
CHARACTER = {
    "name": os.getenv("CHARACTER_NAME", "るーにゃ"),
    "age": int(os.getenv("CHARACTER_AGE", "21")),
    "birthday": os.getenv("CHARACTER_BIRTHDAY", "12月20日"),
    "description": os.getenv("CHARACTER_DESCRIPTION", "21歳の大学3年生。上京してキャンパスデビューしたものの、ぼっち気味。"),

    # ビジュアル設定（画像生成に使用）
    "visual": {
        "hair": "medium-length light brown semi-long hair, natural and slightly wavy",
        "face": "pretty Japanese woman, naturally attractive facial features, soft and approachable, clean skin, minimal makeup with light foundation and subtle lip gloss",
        "height": "157cm tall, slim average build, not muscular but not overweight, well-proportioned",
        "figure": "bust 82cm D-cup, waist 60cm, hips 84cm, feminine silhouette",
        "fashion": "trendy contemporary Japanese fashion, stylish casual outfits seen in Tokyo street style magazines",
        "vibe": "girl-next-door charm, looks like a real university student, Instagram-worthy but not overly perfect",
    }
}

class RunyanContentGenerator:
    def __init__(self):
        self.openai_client = OpenAI(api_key=OPENAI_API_KEY)
        self.output_dir = Path("./generated_content")
        self.output_dir.mkdir(exist_ok=True)
        
    def generate_scenario(self) -> dict:
        """Claude APIを使ってシナリオを自動生成"""
        print("📝 シナリオ生成中...")
        
        prompt = f"""
あなたは{CHARACTER['name']}というキャラクターのシナリオライターです。

【キャラクター設定】
- 名前: {CHARACTER['name']}
- 年齢: {CHARACTER['age']}歳
- 誕生日: {CHARACTER['birthday']}
- 説明: {CHARACTER['description']}
- コンセプト: 実はぼっちだけど、Instagramでは背伸びした大人っぽい自分を魕せたい
- 内容: 大学生の日常（授業、アルバイト、友達との時間）+ 本音トーク（たまに）

【タスク】
1日のInstagram短編リール用のシナリオを作成してください（15秒～30秒程度）

【メイクスタイルの選択ルール】
シナリオの場面に合わせて以下から1つ選んでください：
- "gachi": ガチメイク（デート・夜遊び・おしゃれなカフェ・イベント等）
- "natural": ナチュラルメイク（授業・買い物・友達とランチ・アルバイト等）
- "suppin": すっぴん（家・起き抜け・勉強・だらだら系の場面等）

【出力形式】
{{
    "title": "シナリオのタイトル",
    "scenario": "具体的なシナリオ（日本語）",
    "caption": "Instagramのキャプション案",
    "mood": "雰囲気（happy/thoughtful/excited等）",
    "setting": "舞台設定（カフェ/大学/アルバイト先等）",
    "makeup_style": "gachi / natural / suppin のいずれか",
    "key_dialogue": "キーセリフ（あれば）",
    "hashtags": ["#るーにゃ", "#大学生", ...]
}}

今から生成してください。JSONのみを返してください。
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a creative scenario writer. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1000
            )
            
            # マークダウンコードブロックを除去してJSONパース
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            scenario_json = json.loads(content)
            return scenario_json
        
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析エラー: {e}")
            return None
        except Exception as e:
            print(f"❌ シナリオ生成エラー: {e}")
            return None

    def generate_image(self, scenario: dict) -> str:
        """参照画像をベースに gpt-image-2 で画像を生成（顔固定）"""
        print("🎨 画像生成中...")

        # メイクスタイルに対応する参照画像を選択
        makeup_style = scenario.get("makeup_style", "natural")
        reference_images = {
            "gachi":   Path("./キャラ画像/runyan_gachi.png"),
            "natural": Path("./キャラ画像/runyan_natural.png"),
            "suppin":  Path("./キャラ画像/runyan_suppin.png"),
        }
        reference_path = reference_images.get(makeup_style, reference_images["natural"])

        prompt = f"""
Keep the exact same person as in the reference image — same face, same hair, same makeup style.
Only change the scene, background, clothing, and pose to match the following:

SCENE:
- Setting: {scenario.get('setting', 'university campus')}
- Mood: {scenario.get('mood', 'casual')}
- Scenario: {scenario.get('scenario', '')}

PHOTO STYLE:
- Realistic Instagram lifestyle photo
- Natural lighting, good composition
- Real photographic quality, not illustrated or anime style
"""

        try:
            with open(reference_path, "rb") as image_file:
                response = self.openai_client.images.edit(
                    model="gpt-image-2",
                    image=image_file,
                    prompt=prompt,
                    size="1024x1024",
                )

            # base64 デコードして画像ファイルとして保存
            import base64
            image_data = base64.b64decode(response.data[0].b64_json)
            image_path = self.output_dir / f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            with open(image_path, "wb") as f:
                f.write(image_data)

            print(f"✅ 画像生成完了: {image_path}")
            return str(image_path)

        except Exception as e:
            print(f"❌ 画像生成エラー: {e}")
            return None

    def create_video_from_image(self, image_path: str, scenario: dict) -> str:
        """ElevenLabs Kling O3 で画像から動画を生成"""
        print("🎬 動画生成中（Kling O3）...")

        try:
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
            }

            prompt = (
                f"{scenario.get('scenario', '')} "
                f"Mood: {scenario.get('mood', 'casual')}. "
                f"Setting: {scenario.get('setting', '')}. "
                f"Natural movement, realistic, Instagram reel style, 15 seconds."
            )

            # 画像ファイルと生成パラメータをマルチパートで送信
            with open(image_path, "rb") as img_file:
                files = {
                    "image": (Path(image_path).name, img_file, "image/png"),
                }
                data = {
                    "model_id": "kling-o3",
                    "prompt": prompt,
                    "duration": "15",
                    "aspect_ratio": "9:16",  # Instagram リール縦型
                }
                response = requests.post(
                    "https://api.elevenlabs.io/v1/video-generation",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=30,
                )

            if response.status_code not in (200, 201):
                print(f"❌ 動画生成リクエスト失敗: {response.status_code} - {response.text}")
                return None

            generation_id = response.json().get("id")
            print(f"  動画生成ジョブ開始: {generation_id}")

            # 生成完了まで最大10分ポーリング
            import time
            for _ in range(60):
                time.sleep(10)
                status_res = requests.get(
                    f"https://api.elevenlabs.io/v1/video-generation/{generation_id}",
                    headers=headers,
                    timeout=30,
                )
                status_data = status_res.json()
                status = status_data.get("status")
                print(f"  ステータス: {status}")

                if status == "completed":
                    video_url = status_data.get("video_url") or status_data.get("url")
                    video_res = requests.get(video_url, timeout=120)
                    video_path = self.output_dir / f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                    with open(video_path, "wb") as f:
                        f.write(video_res.content)
                    print(f"✅ 動画生成完了: {video_path}")
                    return str(video_path)

                if status in ("failed", "error"):
                    print(f"❌ 動画生成失敗: {status_data}")
                    return None

            print("❌ 動画生成タイムアウト（10分超過）")
            return None

        except Exception as e:
            print(f"❌ 動画生成エラー: {e}")
            return None

    def save_to_google_drive(self, file_path: str) -> str:
        """Google Driveに動画を保存"""
        print("☁️ Google Drive保存中...")
        
        try:
            # Google Drive APIの認証
            SCOPES = ['https://www.googleapis.com/auth/drive']
            creds = None
            
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', SCOPES)
            elif os.path.exists(GOOGLE_CREDENTIALS_PATH):
                flow = InstalledAppFlow.from_client_secrets_file(
                    GOOGLE_CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            
            drive_service = googleapiclient.discovery.build('drive', 'v3', credentials=creds)
            
            # フォルダID（"runyan-content"フォルダ）の取得または作成
            folder_name = "runyan-content"
            query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
            results = drive_service.files().list(q=query, spaces='drive', pageSize=1, fields='files(id)').execute()
            
            folders = results.get('files', [])
            if folders:
                folder_id = folders[0]['id']
            else:
                file_metadata = {
                    'name': folder_name,
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                folder = drive_service.files().create(body=file_metadata, fields='id').execute()
                folder_id = folder.get('id')
            
            # ファイルをアップロード
            file_metadata = {
                'name': Path(file_path).name,
                'parents': [folder_id]
            }
            media = MediaFileUpload(file_path, mimetype='video/mp4')
            file = drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            file_id = file.get('id')
            file_link = file.get('webViewLink')
            print(f"✅ Google Drive保存完了: {file_link}")
            return file_link
        
        except Exception as e:
            print(f"❌ Google Drive保存エラー: {e}")
            return None

    def send_discord_notification(self, scenario: dict, video_path: str, drive_link: str):
        """Discord Webhookで通知を送信"""
        print("💬 Discord通知送信中...")
        
        try:
            embed = {
                "title": f"🎬 今日のコンテンツ: {scenario.get('title', 'るーにゃの日常')}",
                "description": scenario.get('scenario', ''),
                "color": 0xFF1493,  # Deep Pink
                "fields": [
                    {
                        "name": "📝 タイトル",
                        "value": scenario.get('title', 'N/A'),
                        "inline": False
                    },
                    {
                        "name": "🎯 ムード",
                        "value": scenario.get('mood', 'N/A'),
                        "inline": True
                    },
                    {
                        "name": "🎭 舞台",
                        "value": scenario.get('setting', 'N/A'),
                        "inline": True
                    },
                    {
                        "name": "💬 キャプション案",
                        "value": scenario.get('caption', 'N/A')[:250],
                        "inline": False
                    },
                    {
                        "name": "🔗 Google Drive リンク",
                        "value": f"[動画を見る]({drive_link})",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "投稿前に確認してください（✅ または ❌ でリアクション）"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            payload = {
                "embeds": [embed]
            }
            
            response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print("✅ Discord通知送信完了")
            else:
                print(f"❌ Discord通知送信失敗: {response.status_code}")
        
        except Exception as e:
            print(f"❌ Discord通知エラー: {e}")

    def run_scenario_mode(self):
        """シナリオのみ生成してDiscordに投稿・ファイル保存（毎朝自動実行）"""
        print("=" * 50)
        print(f"📝 シナリオ確認モード開始 ({datetime.now()})")
        print("=" * 50)

        scenario = self.generate_scenario()
        if not scenario:
            print("❌ シナリオ生成失敗")
            return

        # シナリオをファイルに保存（次のステップで使用）
        scenario_path = Path("./current_scenario.json")
        with open(scenario_path, "w", encoding="utf-8") as f:
            json.dump(scenario, f, ensure_ascii=False, indent=2)
        print(f"✅ シナリオ保存: {scenario_path}")

        # Discord にシナリオを投稿して確認を求める
        makeup_labels = {"gachi": "ガチメイク", "natural": "ナチュラルメイク", "suppin": "すっぴん"}
        makeup = makeup_labels.get(scenario.get("makeup_style", "natural"), "ナチュラルメイク")

        embed = {
            "title": f"📋 今日のシナリオ確認: {scenario.get('title')}",
            "description": scenario.get("scenario", ""),
            "color": 0xFFAA00,
            "fields": [
                {"name": "🎭 舞台", "value": scenario.get("setting", "N/A"), "inline": True},
                {"name": "🌈 ムード", "value": scenario.get("mood", "N/A"), "inline": True},
                {"name": "💄 メイク", "value": makeup, "inline": True},
                {"name": "💬 キャプション案", "value": scenario.get("caption", "N/A")[:250], "inline": False},
            ],
            "footer": {"text": "✅ OKなら GitHub Actions で「Generate」ワークフローを手動実行してください"},
        }
        requests.post(DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        print("✅ Discord にシナリオを投稿しました")

    def run_generate_mode(self):
        """保存済みシナリオから画像・動画を生成（手動実行）"""
        print("=" * 50)
        print(f"🎬 コンテンツ生成モード開始 ({datetime.now()})")
        print("=" * 50)

        # 保存済みシナリオを読み込み
        scenario_path = Path("./current_scenario.json")
        if not scenario_path.exists():
            print("❌ current_scenario.json が見つかりません。先にシナリオモードを実行してください")
            return
        with open(scenario_path, "r", encoding="utf-8") as f:
            scenario = json.load(f)

        # 環境変数で指定された上書き入力を反映
        if os.getenv("OVERRIDE_TITLE"):
            scenario["title"] = os.getenv("OVERRIDE_TITLE")
        if os.getenv("OVERRIDE_SCENARIO"):
            scenario["scenario"] = os.getenv("OVERRIDE_SCENARIO")
        if os.getenv("OVERRIDE_SETTING"):
            scenario["setting"] = os.getenv("OVERRIDE_SETTING")
        if os.getenv("OVERRIDE_MAKEUP"):
            scenario["makeup_style"] = os.getenv("OVERRIDE_MAKEUP")

        print(f"✅ シナリオ読み込み: {scenario.get('title')}")

        # 画像生成
        image_path = self.generate_image(scenario)
        if not image_path:
            print("❌ 画像生成失敗")
            return

        # 動画生成
        video_path = self.create_video_from_image(image_path, scenario)
        if not video_path:
            print("❌ 動画生成失敗")
            return

        # Google Drive保存（テスト中はスキップ）
        drive_link = f"（Google Drive未設定）{video_path}"

        # Discord に最終通知
        self.send_discord_notification(scenario, video_path, drive_link)

        print("\n" + "=" * 50)
        print("✅ コンテンツ生成完了！Discord で確認してください")
        print("=" * 50)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "scenario"
    generator = RunyanContentGenerator()
    if mode == "generate":
        generator.run_generate_mode()
    else:
        generator.run_scenario_mode()
