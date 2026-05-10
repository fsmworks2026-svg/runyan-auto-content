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
        """Claude APIを使ってシナリオを自動生成（2025-2026トレンド対応）"""
        print("📝 シナリオ生成中...")
        
        # 日付から曜日を取得（テーマ選択用）
        today = datetime.now()
        day_of_week = today.weekday()  # 0=月, 6=日
        
        # 週別コンテンツテーマ（多様性を確保）
        theme_schedule = {
            0: "グルメ・カフェ（月：新しい場所チャレンジ）",
            1: "ファッション・コーディネート（火：推しコーデ）",
            2: "美容・メイク（水：ビューティティップス）",
            3: "推し活・グッズ（木：推し活ライフ）",
            4: "ルームツアー・ライフスタイル（金：一人暮らしの工夫）",
            5: "友達との時間・本音（土：友情エピソード＆本音）",
            6: "素の日常・だらだら（日：ぼっち時間あるある）"
        }
        daily_theme = theme_schedule.get(day_of_week, "大学生の日常")
        
        prompt = f"""
あなたは{CHARACTER['name']}という21歳の大学3年生キャラクターのシナリオライターです。
Instagramでのリール投稿用のコンテンツを作成しています。

【キャラクター設定】
- 名前: {CHARACTER['name']}
- 年齢: {CHARACTER['age']}歳
- 背景: 上京してぼっち気味だが、Instagramでは背伸びした大人っぽい自分を演出したい
- リアル：実は孤独感を感じることもある大学生
- Instagram面：トレンドに敏感で、友達がいっぱいいるように見える投稿をしたい

【本日のテーマ】
{daily_theme}

【2025-2026年Instagramトレンド対応】
✅ 「保存される理由」を必ず1つ以上含める：
   - コーディネート参考になる
   - カフェ・スポット情報
   - メイク・美容のコツ
   - 推し活の工夫
   - 一人暮らしのアイデア
   - 共感できるあるあるネタ

✅ 「シェアされる驚き・共感」を含める：
   - 予期しない展開やオチ
   - 思わず笑ってしまう瞬間
   - 心が動く本音の一言
   - 友達と「あ、わかる！」となる瞬間

✅ インタラクティブ要素（視聴者が「参加」できる）：
   - 「このどちらが好き？」という選択肢
   - 「当てはまる？」という質問投げかけ
   - 「試してみてほしい」というCTA（行動喚起）
   - ビフォーアフター表現

✅ 「素の瞬間」も月1～2回はいれる（親近感）：
   - ぼっち気味な本音をチラ見せ
   - 失敗談
   - 疲れてる日の日常
   - 本当の気持ち

【メイクスタイルの選択ルール】
- "gachi": ガチメイク（デート・夜遊び・おしゃれなカフェ・イベント等）
- "natural": ナチュラルメイク（授業・買い物・友達とランチ・アルバイト等）
- "suppin": すっぴん（家・起き抜け・勉強・だらだら系の場面等）

【ハッシュタグのコツ】
- キャプションの最初の数行に「重要キーワード」を自然に組み込む
- ハッシュタグは最初に3～5個をキャプション内に自然に挿入
- 推し活・界隈用語は2026年トレンド
- 例：「#るーにゃ #大学生日常 #新大久保カフェ」

【出力形式】
{{
    "title": "シナリオのタイトル",
    "scenario": "具体的なシナリオ（日本語）。現実感を大切に。",
    "caption": "Instagramのキャプション案。最初に重要キーワード・ハッシュタグを配置。共感できる言い回しで。",
    "mood": "雰囲気（happy/thoughtful/excited/funny/relatable等）",
    "setting": "舞台設定",
    "makeup_style": "gachi / natural / suppin のいずれか",
    "key_dialogue": "キーセリフ（視聴者が「あ、わかる」となるセリフ）",
    "save_reason": "このコンテンツが『保存されるポイント』（ユーザーが後で見返したくなる理由）",
    "share_element": "このコンテンツが『シェアされやすい要素』（驚き・共感・笑い）",
    "interactive_element": "視聴者を参加させる要素（質問・選択肢・CTA等）",
    "hashtags": ["#るーにゃ", "#大学生", "#新大久保", ...],
    "engagement_signals": "保存・シェアを促すための工夫の説明"
}}

今から生成してください。JSONのみを返してください。完全で有効なJSONを返してください。
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
        """参照画像をベースに gpt-image-1 で画像を生成（顔固定）"""
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
                    model="gpt-image-1",
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
        """Discord Webhookで通知を送信（2025-2026トレンド対応）"""
        print("💬 Discord通知送信中...")
        
        try:
            # エンゲージメント指標の計算
            save_reason = scenario.get("save_reason", "情報価値あり")
            share_element = scenario.get("share_element", "共感性あり")
            interactive = scenario.get("interactive_element", "なし")
            engagement_signals = scenario.get("engagement_signals", "標準レベル")
            
            # 難易度・効果予測の計算
            difficulty_score = 0
            expected_reach = "📊 標準"
            
            if interactive and interactive != "なし":
                difficulty_score += 1
                expected_reach = "📊 高リーチ期待"
            if save_reason and save_reason not in ["N/A", "なし"]:
                difficulty_score += 1
            if share_element and share_element not in ["N/A", "なし"]:
                difficulty_score += 1
            
            embed = {
                "title": f"🎬 {scenario.get('title', 'るーにゃの日常')}",
                "description": scenario.get('scenario', '')[:200] + "...",
                "color": 0xFF1493,  # Deep Pink
                "fields": [
                    # 基本情報
                    {
                        "name": "📝 シナリオタイトル",
                        "value": scenario.get('title', 'N/A'),
                        "inline": False
                    },
                    {
                        "name": "🎯 テーマ",
                        "value": scenario.get('mood', 'N/A'),
                        "inline": True
                    },
                    {
                        "name": "🎭 舞台",
                        "value": scenario.get('setting', 'N/A'),
                        "inline": True
                    },
                    
                    # ✨ エンゲージメント指標（2025-2026対応）
                    {
                        "name": "💾 保存されるポイント",
                        "value": save_reason if save_reason else "参考価値あり",
                        "inline": False
                    },
                    {
                        "name": "🔄 シェア可能性",
                        "value": f"✅ {share_element}" if share_element else "❌ 低い",
                        "inline": False
                    },
                    {
                        "name": "🎪 インタラクティブ要素",
                        "value": f"✅ {interactive}" if interactive and interactive != "なし" else "❌ なし",
                        "inline": False
                    },
                    
                    # キャプションと行動喚起
                    {
                        "name": "📸 キャプション案",
                        "value": scenario.get('caption', 'N/A')[:300] + ("..." if len(scenario.get('caption', '')) > 300 else ""),
                        "inline": False
                    },
                    
                    # パフォーマンス予測
                    {
                        "name": expected_reach,
                        "value": f"アルゴリズム評価: {engagement_signals}",
                        "inline": False
                    },
                    
                    # 動画リンク
                    {
                        "name": "🔗 動画を確認",
                        "value": f"[Google Driveで確認]({drive_link})",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "✅ 投稿OK / ❌ 修正希望 / 💭 修正案がある場合は返信してください"
                },
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # ハッシュタグを別フィールドで表示
            if scenario.get("hashtags"):
                hashtags_str = " ".join(scenario.get("hashtags", [])[:8])
                embed["fields"].append({
                    "name": "#️⃣ 推奨ハッシュタグ",
                    "value": hashtags_str,
                    "inline": False
                })
            
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
        image_path = self.generate_image(scenario)
        if not image_path:
            print("❌ 画像生成失敗")
            return

        # Step 3: 動画化
        video_path = self.create_video_from_image(image_path, scenario)
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
