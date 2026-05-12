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
            import random
            theme_pool = [
                "新しいカフェを開拓・カフェ巡り",
                "今日のコーデ・ファッション紹介",
                "朝のスキンケア・美容ルーティン",
                "推し活（グッズ・ライブ・ファン活動）",
                "大学・授業・キャンパスライフ",
                "バイト帰り・お仕事疲れ",
                "一人暮らしの部屋・インテリア",
                "友達とのランチ・お茶・遊び",
                "休日のだらだら・家でゆっくり",
                "夜のルーティン・帰宅後の時間",
                "季節のイベント・お出かけ",
                "ショッピング・お買い物",
                "自炊・一人暮らしご飯",
                "読書・勉強・カフェ作業",
                "通学中・イヤホンで音楽",
                "本音トーク・ぼっちあるある",
                "夜遊び・友達と夜のお出かけ",
                "メイク・コスメ・ビューティ紹介",
                "カフェスイーツ・デザート巡り",
                "朝活・モーニング・早起き",
            ]

            # 直近5件を除外してランダム選択
            history_path = Path("theme_history.json")
            history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else {"recent": []}
            recent = history.get("recent", [])
            available = [t for t in theme_pool if t not in recent[-5:]]
            if not available:
                available = theme_pool  # 全テーマ使い切ったらリセット
            daily_theme = random.choice(available)

            # 履歴を更新（直近10件を保持）
            recent.append(daily_theme)
            history["recent"] = recent[-10:]
            history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  ランダムテーマ選択: {daily_theme}")

        # 現在の月から季節・気候情報を生成（JST基準）
        from zoneinfo import ZoneInfo
        current_month = datetime.now(ZoneInfo("Asia/Tokyo")).month
        season_map = {
            1:  ("冬", "寒い。最高気温5〜10℃。ダウンコート・マフラー・ニット必須"),
            2:  ("冬", "寒い。最高気温5〜10℃。ダウンコート・マフラー・ニット必須"),
            3:  ("春", "やや肌寒い。最高気温10〜15℃。薄手のコートやジャケット"),
            4:  ("春", "暖かい。最高気温15〜20℃。軽いアウター・ニット・シャツ"),
            5:  ("初夏", "暖かく半袖も出始める。最高気温20〜25℃。薄手のブラウス・カーディガン・ノースリーブ"),
            6:  ("梅雨・初夏", "蒸し暑い。最高気温25〜28℃。半袖・ワンピース・サンダル"),
            7:  ("夏", "暑い。最高気温30℃超。半袖・キャミ・ミニスカ・サンダル"),
            8:  ("真夏", "猛暑。最高気温35℃前後。できるだけ涼しい格好"),
            9:  ("初秋", "まだ暑いが少し落ち着く。最高気温25〜30℃。半袖〜薄手の羽織"),
            10: ("秋", "過ごしやすい。最高気温18〜23℃。薄手のニット・ジャケット"),
            11: ("晩秋", "肌寒い。最高気温12〜18℃。コート・ニット・ブーツ"),
            12: ("冬", "寒い。最高気温5〜12℃。ダウン・マフラー・手袋"),
        }
        season_name, season_weather = season_map.get(current_month, ("春", "暖かい"))

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

【季節・気候と服装の注意】
現在: {current_month}月（{season_name}）/ {season_weather}
- 屋外シーン: 気候に合ったアウター・全身コーディネート
- 屋内シーン（カフェ・教室・家など）: アウターは脱いだ状態。インナーやトップスが見える格好
- 季節外れの服装はNG（夏に厚手コート・冬に半袖キャミ等）

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
- "selfie": 一人（室内・屋外問わず）前カメラで腕を伸ばしたバストアップ〜全身自撮り
- "mirror_living": 一人・自宅リビング（姿見に全身を映してスマホで自撮り。コーデ確認・ファッション系に最適）
- "mirror_washroom": 一人・洗面所（洗面台の鏡に映してスマホで自撮り。スキンケア・メイク・朝ルーティン系に最適）
- "friend_shot": 友達・複数人のいるシーン（友達に撮ってもらった自然な感じ）
※ 一人で屋外・大学・カフェは "selfie"。自宅でコーデや全身を見せたいときは "mirror_living"。スキンケア・洗顔系は "mirror_washroom"。

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
    "photo_style": "selfie / mirror_living / mirror_washroom / friend_shot のいずれか",
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

    def _select_room_image(self, scenario: dict) -> Path | None:
        """
        シーンの場所・時間帯に応じた部屋背景画像を返す。
        屋外・カフェ・大学など室内部屋画像が不適切なシーンは None を返す。
        """
        room_dir = Path("./部屋画像")

        # setting と scenario テキストを結合してキーワード検索
        search_text = (
            scenario.get("setting", "") + " " +
            scenario.get("scenario", "") + " " +
            scenario.get("title", "")
        )

        # 投稿時間帯から夜かどうかを判定
        posting_time = scenario.get("best_posting_time", "")
        night_hours = ["17:", "18:", "19:", "20:", "21:", "22:", "23:", "0:", "1:"]
        is_night = any(h in posting_time for h in night_hours)

        # photo_style で明示指定されている場合は優先
        photo_style = scenario.get("photo_style", "")
        if photo_style == "mirror_living":
            suffix = "night" if is_night else "morning"
            return room_dir / f"living_mirror_{suffix}.png"
        if photo_style == "mirror_washroom":
            return room_dir / "washroom_mirror.png"

        # 洗面所（スキンケア・洗顔・メイク系）
        washroom_keywords = ["洗面", "スキンケア", "洗顔", "クレンジング", "美容ルーティン", "化粧水", "保湿"]
        if any(kw in search_text for kw in washroom_keywords):
            return room_dir / "washroom_mirror.png"

        # 寝室（就寝・起床・ベッド・夜ルーティン系）
        bedroom_keywords = ["寝室", "ベッド", "起き", "就寝", "寝る", "目覚め", "朝活", "夜のルーティン", "帰宅後", "おやすみ", "だらだら", "家でゆっくり", "休日の朝"]
        if any(kw in search_text for kw in bedroom_keywords):
            suffix = "night" if is_night else "morning"
            return room_dir / f"bedroom_entrance_{suffix}.png"

        # リビング（食事・くつろぎ・インテリア・自炊系）
        living_keywords = ["リビング", "ソファ", "ダイニング", "食事", "自炊", "ご飯", "くつろぎ", "一人暮らしの部屋", "インテリア", "おうち", "お家", "部屋でゆっくり"]
        if any(kw in search_text for kw in living_keywords):
            suffix = "night" if is_night else "morning"
            return room_dir / f"living_sofa_{suffix}.png"

        # 屋外・カフェ・大学・バイト等は部屋画像なし
        return None

    def generate_image(self, scenario: dict, shot_description: str = None, shot_index: int = 0) -> str:
        """参照画像をベースに gpt-image-2 で画像を生成（顔固定）"""
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
            camera_text = "Candid shot by a friend.\nNatural perspective.\nSlightly off-center.\nNot a selfie."
        elif photo_style == "mirror_living":
            camera_text = "Mirror selfie in living room.\nFull-length mirror leaning against wall.\nCharacter reflected in mirror holding phone up to take photo.\nFull body or 3/4 visible in reflection.\nArm slightly raised holding phone, natural pose."
        elif photo_style == "mirror_washroom":
            camera_text = "Bathroom mirror selfie.\nCharacter reflected in washroom mirror holding phone.\nBust-up to 3/4 shot in reflection.\nSink and counter visible below.\nNatural casual pose."
        else:
            camera_text = "Selfie.\nFront camera.\nArm extended.\nSlight downward angle.\nClose-up face and upper body."

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

{f"Place this character naturally inside the provided room background image. Match the lighting and perspective of the room." if self._select_room_image(scenario) else ""}
"""

        try:
            # シーンに応じた部屋背景画像を選択
            room_image_path = self._select_room_image(scenario)

            # キャラ参照画像 + 部屋画像（あれば）を渡す
            char_file = open(reference_path, "rb")
            if room_image_path and room_image_path.exists():
                room_file = open(room_image_path, "rb")
                images_input = [char_file, room_file]
                print(f"  🏠 部屋背景: {room_image_path.name}")
            else:
                images_input = char_file
                room_file = None
                print("  🌍 屋外シーン（部屋画像なし）")

            response = self.openai_client.images.edit(
                model="gpt-image-2",
                image=images_input,
                prompt=prompt,
                size="1024x1536",
            )

            char_file.close()
            if room_file:
                room_file.close()

            # base64 デコードして画像ファイルとして保存
            import base64
            image_data = base64.b64decode(response.data[0].b64_json)
            image_path = self.output_dir / f"image_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{shot_index + 1}.png"
            # ベース参照画像フォルダへの誤書き込みを防ぐガード
            assert "キャラ画像" not in str(image_path), "ベース画像フォルダへの書き込みは禁止されています"
            with open(image_path, "wb") as f:
                f.write(image_data)

            # AI生成メタデータを除去し iPhone 15 Pro の EXIF に置き換える（PNG→JPEG）
            from strip_metadata import strip_image
            image_path = strip_image(image_path)

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
        """生成した画像（複数）を Discord に送信し ✅/❌ リアクションを追加する"""
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

            # ?wait=true でメッセージIDを取得（リアクション追加に必要）
            response = requests.post(
                DISCORD_WEBHOOK_URL + "?wait=true",
                data={"content": content},
                files=files,
            )

            for f in opened:
                f.close()

            if response.status_code in (200, 201):
                print(f"✅ Discord に {len(image_paths)} 枚の画像を送信しました")
                # ✅/❌ リアクションを追加
                msg_data   = response.json()
                message_id = msg_data.get("id")
                channel_id = msg_data.get("channel_id")
                bot_token  = os.getenv("DISCORD_BOT_TOKEN", "")
                if message_id and channel_id and bot_token:
                    headers = {"Authorization": f"Bot {bot_token}"}
                    for emoji in ["✅", "❌"]:
                        requests.put(
                            f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/{requests.utils.quote(emoji)}/@me",
                            headers=headers,
                        )
                    print("  👍 ✅/❌ リアクション追加完了")
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

        # IS_SPOT_REEL=true の場合はスポット投稿フラグを付与（"新規:" コマンド経由）
        scenario["is_spot"] = os.getenv("IS_SPOT_REEL", "false").lower() == "true"

        # 既存シナリオの outfit / has_reel / has_feed を引き継ぐ
        # （修正フロー: ストーリーズ画像は再生成せずリールのみ作り直す。
        #   daily_context の casual_outfit と一致させておく）
        scenario_path = Path("./current_scenario.json")
        if scenario_path.exists():
            try:
                prev = json.load(open(scenario_path, encoding="utf-8"))
                for key in ("outfit", "has_reel", "has_feed", "feed_type", "briefing_date"):
                    if key in prev:
                        scenario.setdefault(key, prev[key])
            except Exception:
                pass
        with open(scenario_path, "w", encoding="utf-8") as f:
            json.dump(scenario, f, ensure_ascii=False, indent=2)
        print(f"✅ シナリオ保存: {scenario_path}")

        # Discord にシナリオを投稿して確認を求める
        makeup_labels = {"gachi": "ガチメイク", "natural": "ナチュラルメイク", "suppin": "すっぴん"}
        makeup = makeup_labels.get(scenario.get("makeup_style", "natural"), "ナチュラルメイク")
        photo_labels = {
            "selfie":           "📱 自撮り（インカメラ）",
            "mirror_living":    "🪞 姿見ミラーセルフィー",
            "mirror_washroom":  "🚿 洗面鏡セルフィー",
            "friend_shot":      "👫 友達に撮ってもらう",
        }
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
        camera_note = {
            "friend_shot":      "handheld candid style, filmed by a friend, natural perspective",
            "selfie_stick":     "selfie stick style, wider angle, full body or 3/4 shot, natural casual framing",
            "mirror_living":    "mirror selfie in living room, full-length mirror, character reflected holding phone",
            "mirror_washroom":  "bathroom mirror selfie, washroom setting, character reflected in mirror",
        }.get(photo_style, "selfie style, front camera, arm extended")

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

        # リール投稿チェック
        # is_spot=True（"新規:" スポット投稿）はスケジュール外 → チェックしない
        # 通常フロー（ブリーフィング・修正）は daily_context を参照して has_reel=False ならスキップ
        if not scenario.get("is_spot", False):
            from datetime import timezone as _tz, timedelta as _td
            import daily_context as _dc
            _jst   = _tz(_td(hours=9))
            _today = datetime.now(_jst).date()
            _ctx   = _dc.load_or_create(_today, openai_client=None)
            if not _ctx.get("has_reel", True):
                print("今日はリール投稿なし（スケジュール外）")
                if DISCORD_WEBHOOK_URL:
                    requests.post(DISCORD_WEBHOOK_URL, json={
                        "content": "📅 今日はリール投稿なし。ストーリーズのみです。"
                    })
                return

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


    def _send_briefing_discord(self, ctx: dict, scenario: dict, story_images: list, feed_image_path=None) -> str | None:
        """ブリーフィング情報を Discord に一括送信し、メッセージIDを返す"""
        pw = ctx["reel_post_window"]
        makeup_labels = {"gachi": "ガチメイク", "natural": "ナチュラルメイク", "suppin": "すっぴん"}
        makeup = makeup_labels.get(scenario.get("makeup_style", "natural"), "ナチュラルメイク")

        # リール・フィード投稿状況
        reel_status = f"あり（{pw[0]}〜{pw[1]}時±20分）" if ctx.get("has_reel") else "なし（ストーリーズのみ）"
        if ctx.get("has_feed"):
            feed_pw   = ctx.get("feed_post_window", [])
            feed_time = f"（{feed_pw[0]}〜{feed_pw[1]}時±20分）" if len(feed_pw) == 2 else ""
            feed_kind = "料理・カフェ写真" if ctx.get("feed_type") == "food" else "人物写真（リール流用）"
            feed_status = f"あり — {feed_kind}{feed_time}"
        else:
            feed_status = "なし"

        # ストーリーズスロットを1行ずつ組み立て
        slots_text = ""
        for slot in ctx["story_slots"]:
            pw_s = slot["post_window"]
            conceal = "（顔隠し）" if slot["no_makeup"] else ""
            slots_text += f"{slot['emoji']} {slot['label']} {pw_s[0]}〜{pw_s[1]}時{conceal}\n"

        fields = [
            # ─ 投稿予定 ─
            {"name": "🎬 リール",
             "value": reel_status,
             "inline": True},
            {"name": "🖼️ フィード",
             "value": feed_status,
             "inline": True},
            # ─ スケジュール ─
            {"name": "🗓️ スケジュール",
             "value": f"午後：{ctx['afternoon']['label']}\n夜：{ctx['evening']['label']}",
             "inline": True},
            {"name": "🌤️ 季節",
             "value": ctx["season_jp"],
             "inline": True},
            # ─ 衣装 ─
            {"name": "👗 私服（リール・外出ストーリーズ共通）",
             "value": ctx["casual_outfit"],
             "inline": False},
            {"name": "🏠 部屋着",
             "value": ctx["room_wear"],
             "inline": True},
            {"name": "😴 寝間着",
             "value": ctx["pajamas"],
             "inline": True},
            # ─ ストーリーズ ─
            {"name": "📱 ストーリーズ予定",
             "value": slots_text.strip(),
             "inline": False},
        ]

        # リールがある日だけシナリオ詳細を表示
        if ctx.get("has_reel"):
            fields.insert(4, {
                "name": "🎭 リールシナリオ",
                "value": f"**{scenario.get('title')}**\n{scenario.get('scenario', '')[:200]}",
                "inline": False,
            })
            fields.insert(5, {
                "name": "🎭 舞台 / メイク",
                "value": f"{scenario.get('setting', '')} / {makeup}",
                "inline": True,
            })

        embed = {
            "title": f"📅 明日のるーにゃ — {ctx['date_display']}",
            "color": 0x7289DA,
            "fields": fields,
            "footer": {"text": "✅ でコンテンツ確定 → 生成キュー開始（リール画像・ストーリーズ投稿）"},
        }

        # フード画像がある場合は一緒に添付
        if feed_image_path and Path(feed_image_path).exists():
            from pathlib import Path as P
            img_path = P(feed_image_path)
            mime = "image/jpeg" if img_path.suffix.lower() == ".jpg" else "image/png"
            import json as _json
            with open(img_path, "rb") as f:
                res = requests.post(
                    DISCORD_WEBHOOK_URL + "?wait=true",
                    data={"payload_json": _json.dumps({"embeds": [embed]})},
                    files={"file": (img_path.name, f, mime)},
                )
        else:
            res = requests.post(DISCORD_WEBHOOK_URL + "?wait=true", json={"embeds": [embed]})

        if res.status_code != 200:
            print(f"  ❌ Discord 送信失敗: {res.status_code}")
            return None

        msg_data   = res.json()
        message_id = msg_data.get("id")
        channel_id = msg_data.get("channel_id")
        print(f"  ✅ ブリーフィング送信完了（メッセージID: {message_id}）")

        # ✅/❌ リアクションを追加
        bot_token = os.getenv("DISCORD_BOT_TOKEN", "")
        if message_id and channel_id and bot_token:
            headers = {"Authorization": f"Bot {bot_token}"}
            for emoji in ["✅", "❌"]:
                requests.put(
                    f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}/reactions/{requests.utils.quote(emoji)}/@me",
                    headers=headers,
                )
            print("  👍 ✅/❌ リアクション追加完了")

        return message_id

    def _send_story_images_discord(self, story_images: list, ctx: dict):
        """ストーリーズ画像をスロット別に個別 Discord メッセージで送信し、
        メッセージIDを story_message_ids.json・承認初期状態を approved_slots.json に保存する。
        """
        if not DISCORD_WEBHOOK_URL or not story_images:
            return

        bot_token = os.getenv("DISCORD_BOT_TOKEN", "")
        slot_map  = {s["id"]: s for s in ctx.get("story_slots", [])}
        date_str  = ctx["date"]

        message_ids    = {}  # slot_id -> discord message_id
        approved_slots = {}  # slot_id -> None (pending)
        channel_id_ref = None

        for path in story_images:
            p = Path(str(path))
            if not p.exists():
                continue

            # ファイル名 story_YYYYMMDD_{slot_id}.jpg からスロットIDを取得
            parts = p.stem.split("_", 2)
            if len(parts) < 3:
                continue
            slot_id = parts[2]
            slot = slot_map.get(slot_id)
            if not slot:
                continue

            pw      = slot["post_window"]
            content = (
                f"{slot['emoji']} **{slot['label']}ストーリーズ確認**"
                f"（{pw[0]}〜{pw[1]}時）\n{slot.get('scene_hint', '')}"
            )
            mime = "image/jpeg" if p.suffix.lower() == ".jpg" else "image/png"

            try:
                with open(p, "rb") as f:
                    res = requests.post(
                        DISCORD_WEBHOOK_URL + "?wait=true",
                        data={"content": content},
                        files={"file": (p.name, f, mime)},
                        timeout=30,
                    )
            except Exception as e:
                print(f"  ❌ {slot_id} 送信エラー: {e}")
                continue

            if res.status_code not in (200, 204):
                print(f"  ❌ {slot_id} 送信失敗: {res.status_code}")
                continue

            msg_data   = res.json()
            msg_id     = msg_data.get("id")
            channel_id = msg_data.get("channel_id")
            if channel_id:
                channel_id_ref = channel_id
            print(f"  ✅ {slot['emoji']} {slot['label']} 送信完了（ID: {msg_id}）")

            message_ids[slot_id]    = msg_id
            approved_slots[slot_id] = None  # None = 承認待ち

            # ✅/❌ リアクションを追加（ユーザーが押しやすくするため）
            if msg_id and channel_id and bot_token:
                headers = {"Authorization": f"Bot {bot_token}"}
                for emoji in ["✅", "❌"]:
                    requests.put(
                        f"https://discord.com/api/v10/channels/{channel_id}/messages/{msg_id}"
                        f"/reactions/{requests.utils.quote(emoji)}/@me",
                        headers=headers,
                        timeout=10,
                    )

        if not message_ids:
            print("  ⚠️  送信できるストーリーズ画像がありませんでした")
            return

        # story_message_ids.json にメッセージIDを保存（チャンネルIDも記録）
        ids_path = Path("./story_message_ids.json")
        existing_ids = json.loads(ids_path.read_text(encoding="utf-8")) if ids_path.exists() else {}
        existing_ids[date_str] = {"channel_id": channel_id_ref, **message_ids}
        ids_path.write_text(json.dumps(existing_ids, ensure_ascii=False, indent=2), encoding="utf-8")

        # approved_slots.json に承認状態を初期化（null = 未承認）
        slots_path = Path("./approved_slots.json")
        existing_slots = json.loads(slots_path.read_text(encoding="utf-8")) if slots_path.exists() else {}
        existing_slots[date_str] = approved_slots
        slots_path.write_text(json.dumps(existing_slots, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"  📋 {len(message_ids)} スロットのメッセージIDを story_message_ids.json に保存")

    def _notify_video_upload_request(self, ctx: dict, scenario: dict):
        """#video-uploads チャンネルに動画アップロード依頼を Bot として送信"""
        bot_token = os.getenv("DISCORD_BOT_TOKEN", "")
        channel_id = os.getenv("DISCORD_VIDEO_CHANNEL_ID", "1503066020745576660")
        if not bot_token:
            print("  ⚠️  DISCORD_BOT_TOKEN 未設定 → 動画依頼スキップ")
            return

        pw = ctx["reel_post_window"]
        content = (
            f"📹 **本日のリール動画アップロード依頼**\n"
            f"シーン：{scenario.get('setting', '')}\n"
            f"投稿ウィンドウ：{pw[0]}〜{pw[1]}時（±20分）\n"
            f"↑ このメッセージに **返信** する形で動画ファイルをアップロードしてください"
        )
        try:
            res = requests.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {bot_token}"},
                json={"content": content},
                timeout=15,
            )
            if res.status_code in (200, 201):
                msg_id = res.json().get("id")
                print(f"  ✅ 動画依頼送信完了（メッセージID: {msg_id}）")
                # video_poster.py が参照できるよう保存
                Path("./video_upload_request.json").write_text(
                    json.dumps({"message_id": msg_id, "date": ctx["date"]}, ensure_ascii=False),
                    encoding="utf-8",
                )
            else:
                print(f"  ❌ 動画依頼送信失敗: {res.status_code}")
        except Exception as e:
            print(f"  ❌ 動画依頼送信エラー: {e}")

    def run_briefing_mode(self):
        """前日21時実行：翌日のコンテキスト・シナリオ・ストーリーズ画像を一括生成してDiscordに投稿"""
        from datetime import date, timedelta
        import daily_context as dc
        import generate_stories as gs

        target_date_str = os.environ.get("TARGET_DATE", "").strip()
        tomorrow = date.fromisoformat(target_date_str) if target_date_str else date.today() + timedelta(days=1)

        print("=" * 55)
        print(f"📅 ブリーフィングモード開始 → {tomorrow}")
        print("=" * 55)

        # 1. 日次コンテキスト生成（翌日分）
        print("\n[1/3] 日次コンテキスト生成")
        ctx = dc.load_or_create(tomorrow, openai_client=self.openai_client)
        print(f"  ✅ {ctx['date_display']} / {ctx['season_jp']}")
        print(f"  午後: {ctx['afternoon']['label']}  夜: {ctx['evening']['label']}")

        # 2. シナリオ生成（daily_context の活動をテーマに設定）
        print("\n[2/3] シナリオ生成")
        os.environ["THEME_OVERRIDE"] = f"{ctx['afternoon']['label']}・{ctx['afternoon']['scene']}"
        scenario = self.generate_scenario()
        os.environ.pop("THEME_OVERRIDE", None)

        if not scenario:
            print("❌ シナリオ生成失敗")
            return

        # daily_context の私服でシナリオ outfit を上書き（リールと外出ストーリーズを一致させる）
        scenario["outfit"]    = ctx["casual_outfit"]
        # 投稿フラグを保存して generate モードが参照できるようにする
        scenario["has_reel"]  = ctx["has_reel"]
        scenario["has_feed"]  = ctx["has_feed"]
        scenario["feed_type"] = ctx.get("feed_type", "none")

        scenario_path = Path("./current_scenario.json")
        with open(scenario_path, "w", encoding="utf-8") as f:
            json.dump(scenario, f, ensure_ascii=False, indent=2)
        print(f"  ✅ シナリオ: {scenario.get('title')}")

        # 3. ストーリーズ画像生成（Discord への個別送信はスキップ）
        print("\n[3/3] ストーリーズ画像生成")
        story_images = gs.generate_all(target_date=tomorrow, notify_discord=False)

        # フィード画像生成（food タイプの場合のみブリーフィング時に生成）
        feed_image_path = None
        if ctx.get("has_feed") and ctx.get("feed_type") == "food":
            print("\n[フィード] 料理・カフェ画像生成")
            import generate_feed as gf
            feed_image_path = gf.generate_food_image(ctx.get("feed_food_scene", ""), ctx["date"])
            if feed_image_path:
                print(f"  ✅ フィード画像: {feed_image_path.name}")
            else:
                print("  ⚠️  フィード画像生成失敗（後で手動生成可）")
        elif ctx.get("has_feed") and ctx.get("feed_type") == "person":
            print("\n[フィード] person タイプ — リール画像を後で流用（今は生成不要）")

        # 4. ブリーフィングを Discord に一括送信してメッセージIDを保存
        print("\n[Discord] ブリーフィング送信")
        message_id = self._send_briefing_discord(ctx, scenario, story_images, feed_image_path=feed_image_path)
        if message_id:
            # ストーリーズ画像を別メッセージで確認用に送信
            if story_images:
                self._send_story_images_discord(story_images, ctx)
            scenario["discord_message_id"] = message_id
            scenario["discord_status"]     = "pending"
            scenario["briefing_date"]      = ctx["date"]
            with open(scenario_path, "w", encoding="utf-8") as f:
                json.dump(scenario, f, ensure_ascii=False, indent=2)

        # 5. リールがある日だけ #video-uploads に動画依頼を送信
        if ctx.get("has_reel"):
            print("\n[Discord] 動画アップロード依頼送信")
            self._notify_video_upload_request(ctx, scenario)
        else:
            print("\n[スキップ] 今日はリールなし → 動画依頼なし")

        print("\n" + "=" * 55)
        print("✅ ブリーフィング完了 — Discord の ✅ を待っています")
        print("=" * 55)


    # ─────────────────────────────────────────
    # スポット投稿（フィード / ストーリーズ）
    # ─────────────────────────────────────────

    def _generate_spot_scenario(self, content_type: str, description: str) -> dict:
        """説明文から最小限のシナリオ辞書を GPT-4o で生成する"""
        format_hint = "縦9:16のストーリーズ" if content_type == "story" else "フィード（スクエア〜縦長）"
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": f"るーにゃ（21歳の日本人女性大学生）の{format_hint}投稿のシナリオを生成してください。"},
                {"role": "user", "content": f"""説明: {description}

以下のJSONのみを返してください:
{{
  "makeup_style": "gachi / natural / suppin のいずれか",
  "photo_style": "selfie / mirror_living / mirror_washroom / friend_shot のいずれか",
  "outfit": "服装の英語記述（例: soft pink oversized cardigan, white tee, light denim）",
  "caption": "Instagramキャプション（日本語、ハッシュタグ含む、150字以内）",
  "mood": "happy / thoughtful / excited / funny / relatable のいずれか"
}}

撮影スタイル選択ルール:
- selfie: 一人（室内・屋外）インカメラ自撮り
- mirror_living: 自宅リビング（姿見・コーデ確認）
- mirror_washroom: 洗面所（スキンケア・メイク系）
- friend_shot: 友達・複数人のシーン"""},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        data = json.loads(response.choices[0].message.content)
        return {
            "setting":           description,
            "scenario":          description,
            "title":             description[:30],
            "best_posting_time": "",
            **data,
        }

    def _send_spot_discord(self, content_type: str, description: str, image_path: Path, caption: str) -> tuple:
        """スポット確認画像を Discord に送信して (msg_id, channel_id) を返す"""
        if not DISCORD_WEBHOOK_URL:
            return None, None

        bot_token  = os.getenv("DISCORD_BOT_TOKEN", "")
        type_label = "📷 フィード" if content_type == "feed" else "📱 ストーリーズ"
        caption_preview = (caption[:100] + "…") if len(caption) > 100 else caption
        content_text = (
            f"{type_label} **スポット投稿確認**\n"
            f"**説明**: {description}\n"
            f"**キャプション案**: {caption_preview}\n"
            f"✅ で投稿 / ❌ でスキップ / **返信で作り直し**"
        )
        mime = "image/jpeg" if image_path.suffix.lower() == ".jpg" else "image/png"

        try:
            with open(image_path, "rb") as f:
                res = requests.post(
                    DISCORD_WEBHOOK_URL + "?wait=true",
                    data={"content": content_text},
                    files={"file": (image_path.name, f, mime)},
                    timeout=30,
                )
            if res.status_code not in (200, 204):
                print(f"  ❌ Discord 送信失敗: {res.status_code}")
                return None, None

            msg_data   = res.json()
            msg_id     = msg_data.get("id")
            channel_id = msg_data.get("channel_id")

            # ✅/❌ リアクションをボットが追加
            if msg_id and channel_id and bot_token:
                headers = {"Authorization": f"Bot {bot_token}"}
                for emoji in ["✅", "❌"]:
                    requests.put(
                        f"https://discord.com/api/v10/channels/{channel_id}/messages/{msg_id}"
                        f"/reactions/{requests.utils.quote(emoji)}/@me",
                        headers=headers, timeout=10,
                    )
            print(f"  ✅ Discord 送信完了（ID: {msg_id}）")
            return msg_id, channel_id

        except Exception as e:
            print(f"  ❌ Discord 送信エラー: {e}")
            return None, None

    def run_spot_mode(self, content_type: str, description: str):
        """スポット投稿：説明から画像を生成して Discord に確認を送る"""
        type_label = "フィード" if content_type == "feed" else "ストーリーズ"
        print(f"\n{'='*55}")
        print(f"🎯 スポット{type_label}生成: {description[:50]}")
        print(f"{'='*55}")

        # 1. シナリオ情報を GPT-4o で生成
        print("\n[1/3] シナリオ情報を生成中...")
        scenario = self._generate_spot_scenario(content_type, description)
        print(f"  スタイル: {scenario.get('photo_style')} / メイク: {scenario.get('makeup_style')}")

        # 2. 画像生成（spot_output/ に直接出力）
        print("\n[2/3] 画像生成中...")
        spot_dir = Path("./spot_output")
        spot_dir.mkdir(exist_ok=True)
        original_output_dir = self.output_dir
        self.output_dir = spot_dir
        image_path_str = self.generate_image(scenario, shot_description=description)
        self.output_dir = original_output_dir

        if not image_path_str:
            print("❌ 画像生成失敗")
            return

        # ファイル名を spot_{type}_{timestamp} に統一
        src = Path(image_path_str)
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = spot_dir / f"spot_{content_type}_{ts}{src.suffix}"
        src.rename(dst)
        print(f"  💾 保存: {dst}")

        # 3. Discord に送信して spot_pending.json を保存
        print("\n[3/3] Discord に送信中...")
        caption = scenario.get("caption", "")
        msg_id, channel_id = self._send_spot_discord(content_type, description, dst, caption)

        pending = {
            "type":               content_type,
            "description":        description,
            "image_path":         str(dst),
            "discord_message_id": msg_id,
            "discord_channel_id": channel_id,
            "caption":            caption,
            "status":             "pending",
        }
        Path("./spot_pending.json").write_text(
            json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n{'='*55}")
        print(f"✅ スポット生成完了 — Discord の ✅ で投稿 / 返信で作り直し")
        print(f"{'='*55}")

    def run_spot_post_mode(self, content_type: str):
        """spot_pending.json の画像を Instagram に投稿する"""
        import sys as _sys

        pending_path = Path("./spot_pending.json")
        if not pending_path.exists():
            print("spot_pending.json なし。スキップ。")
            return

        pending = json.loads(pending_path.read_text(encoding="utf-8"))
        if pending.get("status") != "pending":
            print(f"ステータス: {pending.get('status')}。スキップ。")
            return
        if pending.get("type") != content_type:
            print(f"タイプ不一致: {pending.get('type')} ≠ {content_type}")
            return

        image_path = Path(pending["image_path"])
        caption    = pending.get("caption", "")
        ig_user_id = os.environ["INSTAGRAM_BUSINESS_ACCOUNT_ID"]
        page_token = os.environ["INSTAGRAM_PAGE_ACCESS_TOKEN"]
        webhook    = os.environ.get("DISCORD_WEBHOOK_URL", "")
        type_label = "フィード" if content_type == "feed" else "ストーリーズ"

        try:
            if content_type == "feed":
                from feed_poster import post_feed_image
                post_id = post_feed_image(image_path, caption, ig_user_id, page_token)
            else:
                GH_RAW     = "https://raw.githubusercontent.com/fsmworks2026-svg/runyan-auto-content/master"
                public_url = f"{GH_RAW}/spot_output/{image_path.name}"
                from stories_poster import post_story_image
                post_id = post_story_image(image_path, ig_user_id, page_token, public_url=public_url)

            pending["status"]  = "approved"
            pending["post_id"] = post_id
            pending_path.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"✅ スポット{type_label}投稿完了: {post_id}")

            if webhook:
                requests.post(webhook, json={"content": f"✅ スポット{type_label}投稿完了: {post_id}"})

        except Exception as e:
            print(f"❌ スポット投稿エラー: {e}")
            if webhook:
                requests.post(webhook, json={"content": f"❌ スポット{type_label}投稿失敗: {e}"})
            _sys.exit(1)


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "scenario"
    generator = RunyanContentGenerator()
    if mode == "generate":
        generator.run_generate_mode()
    elif mode == "briefing":
        generator.run_briefing_mode()
    elif mode == "spot":
        content_type = sys.argv[2] if len(sys.argv) > 2 else "feed"
        description  = sys.argv[3] if len(sys.argv) > 3 else ""
        generator.run_spot_mode(content_type, description)
    elif mode == "spot_post":
        content_type = sys.argv[2] if len(sys.argv) > 2 else "feed"
        generator.run_spot_post_mode(content_type)
    else:
        generator.run_scenario_mode()
