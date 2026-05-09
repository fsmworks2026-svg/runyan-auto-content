#!/usr/bin/env python3
"""
るーにゃ 自動コンテンツ生成パイプライン
- シナリオ自動生成（Claude API）
- 画像生成（ChatGPT Image 2.0）
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

【出力形式】
{{
    "title": "シナリオのタイトル",
    "scenario": "具体的なシナリオ（日本語）",
    "caption": "Instagramのキャプション案",
    "mood": "雰囲気（happy/thoughtful/excited等）",
    "setting": "舞台設定（カフェ/大学/アルバイト先等）",
    "key_dialogue": "キーセリフ（あれば）",
    "hashtags": ["#るーにゃ", "#大学生", ...]
}}

今から生成してください。JSONのみを返してください。
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a creative scenario writer. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1000
            )
            
            # JSONパース
            scenario_json = json.loads(response.choices[0].message.content)
            return scenario_json
        
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析エラー: {e}")
            return None
        except Exception as e:
            print(f"❌ シナリオ生成エラー: {e}")
            return None

    def generate_image(self, scenario: dict) -> str:
        """ChatGPT Image 2.0で画像を生成"""
        print("🎨 画像生成中...")
        
        v = CHARACTER["visual"]
        prompt = f"""
A realistic Instagram photo of a 21-year-old Japanese university student named {CHARACTER['name']}.

CHARACTER APPEARANCE (keep consistent):
- Hair: {v['hair']}
- Face: {v['face']}
- Body: {v['height']}, {v['figure']}
- Fashion: {v['fashion']}
- Overall vibe: {v['vibe']}

SCENE:
- Setting: {scenario.get('setting', 'university campus')}
- Mood: {scenario.get('mood', 'casual')}
- Scenario: {scenario.get('scenario', '')}

PHOTO STYLE:
- Shot like a real Instagram lifestyle photo
- Natural lighting, good composition
- NOT overly edited or artificial looking
- Realistic proportions, authentic feel
- Subject is a pretty Japanese young woman, naturally beautiful, not exaggerated anime style
"""
        
        try:
            response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="hd",
                n=1
            )
            
            image_url = response.data[0].url
            print(f"✅ 画像生成完了: {image_url}")
            return image_url
        
        except Exception as e:
            print(f"❌ 画像生成エラー: {e}")
            return None

    def create_video_from_image(self, image_url: str, scenario: dict) -> str:
        """ElevenLabsのSeedanceで動画を生成"""
        print("🎬 動画生成中...")
        
        # 注: 実装にはElevenLabs Seedance APIの詳細が必要
        # 現在はプレースホルダー実装
        
        try:
            # 動画生成APIの呼び出し（ElevenLabs Seedance）
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            
            payload = {
                "image_url": image_url,
                "prompt": scenario.get('scenario', ''),
                "quality": "high",
                "format": "mp4"
            }
            
            # 仮のエンドポイント（実際にはElevenLabsドキュメント参照）
            response = requests.post(
                "https://api.elevenlabs.io/v1/generate-video",
                json=payload,
                headers=headers,
                timeout=300
            )
            
            if response.status_code == 200:
                video_data = response.content
                video_path = self.output_dir / f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                with open(video_path, 'wb') as f:
                    f.write(video_data)
                print(f"✅ 動画生成完了: {video_path}")
                return str(video_path)
            else:
                print(f"❌ 動画生成失敗: {response.status_code} - {response.text}")
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

    def run(self):
        """全体パイプラインの実行"""
        print("=" * 50)
        print(f"🌟 るーにゃ自動コンテンツ生成開始 ({datetime.now()})")
        print("=" * 50)
        
        # Step 1: シナリオ生成
        scenario = self.generate_scenario()
        if not scenario:
            print("❌ シナリオ生成失敗")
            return
        
        print(f"✅ シナリオ: {scenario.get('title')}")
        
        # Step 2: 画像生成
        image_url = self.generate_image(scenario)
        if not image_url:
            print("❌ 画像生成失敗")
            return
        
        # Step 3: 動画化
        video_path = self.create_video_from_image(image_url, scenario)
        if not video_path:
            print("❌ 動画生成失敗")
            return
        
        # Step 4: Google Drive保存
        drive_link = self.save_to_google_drive(video_path)
        if not drive_link:
            print("❌ Google Drive保存失敗")
            return
        
        # Step 5: Discord通知（投稿前確認）
        self.send_discord_notification(scenario, video_path, drive_link)
        
        print("\n" + "=" * 50)
        print("✅ コンテンツ生成完了！")
        print("Discord で確認して、✅ または ❌ でリアクションしてください")
        print("=" * 50)

if __name__ == "__main__":
    generator = RunyanContentGenerator()
    generator.run()
