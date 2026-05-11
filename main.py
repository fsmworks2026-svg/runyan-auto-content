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
        """Claude APIを使ってシナリオを自動生成（2025-2026 Instagramトレンド対応）"""
        print("📝 シナリオ生成中...")

        # THEME_OVERRIDE が指定されていればそれを使用、なければ曜日テーマを自動選択
        theme_override = os.getenv("THEME_OVERRIDE", "").strip()
        if theme_override:
            daily_theme = theme_override
            print(f"  テーマ上書き: {daily_theme}")
        else:
            from zoneinfo import ZoneInfo
            day_of_week = datetime.now(ZoneInfo("Asia/Tokyo")).weekday()  # 0=月, 6=日（JST基準）
            theme_schedule = {
                0: "グルメ・カフェ（月：新しい場所チャレンジ）",
                1: "ファッション・コーディネート（火：推しコーデ）",
                2: "美容・メイク（水：ビューティティップス）",
                3: "推し活・グッズ（木：推し活ライフ）",
                4: "ルームツアー・ライフスタイル（金：一人暮らしの工夫）",
                5: "友達との時間・本音（土：友情エピソード＆本音）",
                6: "素の日常・だらだら（日：ぼっち時間あるある）",
            }
            daily_theme = theme_schedule.get(day_of_week, "大学生の日常")

        prompt = f"""
あなたは{CHARACTER['name']}という21歳の大学3年生キャラクターのシナリオライターです。
Instagramでのリール投稿用のコンテンツを作成しています。

【キャラクター設定】
- 名前: {CHARACTER['name']}
- 年齢: {CHARACTER['age']}歳
- 誕生日: {CHARACTER['birthday']}
- 背景: 上京してぼっち気味だが、Instagramでは背伸びした大人っぽい自分を演出したい
- コンセプト: 実はぼっちだけど、Instagramでは背伸びした大人っぽい自分を魕せたい
- 内容: 大学生の日常（授業、アルバイト、友達との時間）+ 本音トーク（たまに）

【本日のテーマ】
{daily_theme}

【2025-2026年Instagramトレンド対応】
✅ 「保存される理由」を必ず1つ以上含める：
   - コーディネート参考になる
   - カフェ・スポット情報
   - メイク・美容のコツ
   - 共感できるあるあるネタ

✅ 「シェアされる驚き・共感」を含める：
   - 予期しない展開やオチ
   - 心が動く本音の一言
   - 友達と「あ、わかる！」となる瞬間

✅ インタラクティブ要素：
   - 「このどちらが好き？」という選択肢
   - 「当てはまる？」という質問投げかけ

【メイクスタイルの選択ルール】
- "gachi": ガチメイク（デート・夜遊び・おしゃれなカフェ・イベント等）
- "natural": ナチュラルメイク（授業・買い物・友達とランチ・アルバイト等）
- "suppin": すっぴん（家・起き抜け・勉強・だらだら系の場面等）

【撮影スタイルの選択ルール】
- "selfie": 一人のシーン（自撮り・前カメラ・腕を伸ばした感じ）
- "friend_shot": 友達・複数人のいるシーン（友達に撮ってもらった自然な感じ）

【ハッシュタグの禁止事項】
以下のようなAI・キャラクター系のハッシュタグは絶対に使わないこと：
- #AIキャラクター #AI美女 #AIグラビア #AIアート #AIイラスト #AIタレント
- #バーチャルキャラクター #CGキャラクター #デジタルキャラクター
リアルな大学生として自然なハッシュタグのみ使用すること。

【出力形式】
{{
    "title": "シナリオのタイトル",
    "scenario": "具体的なシナリオ（日本語）",
    "caption": "Instagramのキャプション案。最初に重要キーワード・ハッシュタグを配置。",
    "mood": "雰囲気（happy/thoughtful/excited/funny/relatable等）",
    "setting": "舞台設定",
    "makeup_style": "gachi / natural / suppin のいずれか",
    "photo_style": "selfie / friend_shot のいずれか",
    "outfit": "その日の服装を英語で簡潔に記述（例: ivory knit top, beige wide pants, white sneakers）。4枚全ショット共通で使用する。",
    "key_dialogue": "キーセリフ（視聴者が「あ、わかる」となるセリフ）",
    "save_reason": "このコンテンツが保存されるポイント",
    "share_element": "シェアされやすい要素（驚き・共感・笑い）",
    "interactive_element": "視聴者を参加させる要素（質問・選択肢等）",
    "main_shot": "リールのカバー画像になる最も映えるメインシーンを日本語で具体的に描写（例：カフェの窓際でコーヒーを両手で持ちながら外を眺めている）",
    "best_posting_time": "シナリオの時間帯に合わせた最適なInstagram投稿時間帯（例：18:00〜20:00）と理由を一言で",
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
                max_tokens=1200
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

    def generate_image(self, scenario: dict, shot_description: str = None, shot_index: int = 0) -> str:
        """参照画像をベースに gpt-image-1 で画像を生成（顔固定）"""
        label = f"({shot_index + 1}/4) " if shot_description else ""
        print(f"🎨 画像生成中... {label}")

        # メイクスタイルに対応する参照画像を選択
        makeup_style = scenario.get("makeup_style", "natural")
        reference_images = {
            "gachi":   Path("./キャラ画像/runyan_gachi.png"),
            "natural": Path("./キャラ画像/runyan_natural.png"),
            "suppin":  Path("./キャラ画像/runyan_suppin.png"),
        }
        reference_path = reference_images.get(makeup_style, reference_images["natural"])

        # メイクスタイルごとの短い固定描写
        makeup_lines = {
            "gachi": "Glamorous full makeup.\nBold eye makeup.\nDefined lips.\nContoured skin.",
            "natural": "Natural casual chic makeup.\nSoft rosy cheeks.\nCoral-beige lips.\nLight eye makeup.\nFresh youthful university student vibe.",
            "suppin": "No makeup.\nBare natural skin.\nClean fresh face.\nNatural lip color.",
        }
        makeup_text = makeup_lines.get(makeup_style, makeup_lines["natural"])

        # 撮影スタイル
        photo_style = scenario.get("photo_style", "selfie")
        if photo_style == "friend_shot":
            camera_text = "Candid shot by a friend.\nNatural perspective.\nSlightly off-center."
        else:
            camera_text = "Selfie.\nFront camera.\nArm extended.\nSlight downward angle."

        # 服装（4枚共通）と Scene
        outfit = scenario.get("outfit", "simple feminine outfit, beige or ivory tones, soft knitwear")
        scene_text = shot_description if shot_description else scenario.get("setting", "university campus")

        prompt = f"""Same person in all images.

Ru-nya, 21-year-old Japanese woman.

Consistent facial features across all scenes.
Same hairstyle, same bangs, same eye shape, same face proportions.

Soft slightly droopy eyes.
Natural Japanese facial structure.
Small face, gentle jawline.
Fair smooth skin.

Long dark brown semi-long hair with natural loose waves.
Thin airy bangs.

{makeup_text}

Wearing {outfit}.
Same outfit as all other images.

Photorealistic.
Japanese cinematic realism.
Warm natural light.
50mm lens.
Shallow depth of field.
Soft bokeh.
Instagram reel aesthetic.
Vertical 9:16.

{camera_text}

Scene:
{scene_text}
Mood: {scenario.get('mood', 'casual')}
"""

        try:
            with open(reference_path, "rb") as image_file:
                response = self.openai_client.images.edit(
                    model="gpt-image-2",
                    image=image_file,
                    prompt=prompt,
                    size="1024x1536",
                )

            # base64 デコードして画像ファイルとして保存
            import base64
            image_data = base64.b64decode(response.data[0].b64_json)
            image_path = self.output_dir / f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{shot_index + 1}.png"
            # ベース参照画像フォルダへの誤書き込みを防ぐガード
            assert "キャラ画像" not in str(image_path), "ベース画像フォルダへの書き込みは禁止されています"
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

    def send_discord_image(self, scenario: dict, image_paths: list, video_prompt: str = None):
        """生成した画像（複数）を Discord に送信する"""
        print(f"💬 Discord に画像を送信中... ({len(image_paths)}枚)")
        try:
            caption = scenario.get("caption", "")
            hashtags = " ".join(scenario.get("hashtags", []))
            content = f"**{scenario.get('title')}**\n{caption}\n{hashtags}"
            if video_prompt:
                content += f"\n\n🎬 **ElevenLabs/Kling 動画プロンプト:**\n```\n{video_prompt}\n```\n📤 動画完成後は <#1503066020745576660> にアップロードしてください"

            # Discord は1リクエストで最大10ファイル添付可能
            files = {}
            opened = []
            for i, path in enumerate(image_paths):
                f = open(path, "rb")
                opened.append(f)
                files[f"files[{i}]"] = (f"image_{i + 1}.png", f, "image/png")

            response = requests.post(
                DISCORD_WEBHOOK_URL,
                data={"content": content},
                files=files,
            )

            for f in opened:
                f.close()

            if response.status_code in (200, 204):
                print(f"✅ Discord に {len(image_paths)} 枚の画像を送信しました")
            else:
                print(f"❌ Discord 送信失敗: {response.status_code} {response.text}")
        except Exception as e:
            print(f"❌ Discord 画像送信エラー: {e}")

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
        photo_labels = {"selfie": "📱 自撮り", "friend_shot": "👫 友達に撮ってもらう"}
        photo_style_label = photo_labels.get(scenario.get("photo_style", "selfie"), "📱 自撮り")

        save_reason = scenario.get("save_reason", "")
        share_element = scenario.get("share_element", "")
        interactive = scenario.get("interactive_element", "")

        fields = [
            {"name": "🎭 舞台", "value": scenario.get("setting", "N/A"), "inline": True},
            {"name": "🌈 ムード", "value": scenario.get("mood", "N/A"), "inline": True},
            {"name": "💄 メイク", "value": makeup, "inline": True},
            {"name": "📸 撮影スタイル", "value": photo_style_label, "inline": True},
            {"name": "💬 キャプション案", "value": scenario.get("caption", "N/A")[:250], "inline": False},
        ]
        best_posting_time = scenario.get("best_posting_time", "")
        if best_posting_time:
            fields.append({"name": "🕐 最適な投稿時間", "value": best_posting_time, "inline": False})
        if save_reason:
            fields.append({"name": "💾 保存されるポイント", "value": save_reason, "inline": False})
        if share_element:
            fields.append({"name": "🔄 シェア要素", "value": share_element, "inline": False})
        if interactive:
            fields.append({"name": "🎪 インタラクティブ要素", "value": interactive, "inline": False})

        embed = {
            "title": f"📋 今日のシナリオ確認: {scenario.get('title')}",
            "description": scenario.get("scenario", ""),
            "color": 0xFFAA00,
            "fields": fields,
            "footer": {"text": "「OK」で承認 / 修正内容をコメントで投稿してください（10分以内に自動反映）"},
        }

        # ?wait=true でメッセージIDを取得して保存
        res = requests.post(DISCORD_WEBHOOK_URL + "?wait=true", json={"embeds": [embed]})
        if res.status_code == 200:
            message_id = res.json().get("id")
            scenario["discord_message_id"] = message_id
            scenario["discord_status"] = "pending"
            with open(scenario_path, "w", encoding="utf-8") as f:
                json.dump(scenario, f, ensure_ascii=False, indent=2)
            print(f"✅ Discord にシナリオを投稿しました（メッセージID: {message_id}）")
        else:
            print(f"❌ Discord 投稿失敗: {res.status_code}")

    def generate_video_prompt(self, scenario: dict) -> str:
        """ElevenLabs/Kling向けの動画生成プロンプトを生成"""
        photo_style = scenario.get("photo_style", "selfie")
        camera_note = (
            "handheld candid style, filmed by a friend, natural perspective"
            if photo_style == "friend_shot"
            else "selfie style, front camera, arm extended"
        )

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at writing prompts for AI video generation (Kling). Write concise, effective prompts in English describing natural movement and camera work. Output only the prompt text.",
                },
                {
                    "role": "user",
                    "content": f"""Write an image-to-video prompt for Kling based on this Instagram reel scenario:

Title: {scenario.get('title')}
Setting: {scenario.get('setting')}
Mood: {scenario.get('mood')}
Main scene: {scenario.get('main_shot', scenario.get('shots', [''])[0] if scenario.get('shots') else '')}
Camera style: {camera_note}

Requirements:
- Natural realistic movement (slight head turn, hair movement, breathing)
- Subtle camera motion matching the style
- 5-10 seconds
- Vertical 9:16 format
- Japanese cinematic lifestyle aesthetic

Output only the prompt, no explanation.""",
                },
            ],
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()

    def run_generate_mode(self):
        """保存済みシナリオからメイン画像1枚を生成してDiscordに通知"""
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

        # メインショットを生成
        main_shot = scenario.get("main_shot", scenario.get("shots", [""])[0] if scenario.get("shots") else "")
        image_path = self.generate_image(scenario, shot_description=main_shot, shot_index=0)
        if not image_path:
            print("❌ 画像生成が失敗しました")
            return

        # ElevenLabs/Kling 用の動画プロンプトを生成
        print("📝 動画プロンプト生成中...")
        try:
            video_prompt = self.generate_video_prompt(scenario)
        except Exception as e:
            print(f"⚠️ 動画プロンプト生成失敗: {e}")
            video_prompt = f"{scenario.get('setting')} scene, natural movement, cinematic style, 9:16 vertical"

        # 画像と動画プロンプトを Discord に送信
        self.send_discord_image(scenario, [image_path], video_prompt=video_prompt)

        print("\n" + "=" * 50)
        print("✅ 画像生成完了！ElevenLabsで動画を作成してください")
        print(f"   動画完成後: Discord #video-uploads チャンネルに投稿してください")
        print("=" * 50)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "scenario"
    generator = RunyanContentGenerator()
    if mode == "generate":
        generator.run_generate_mode()
    else:
        generator.run_scenario_mode()
