# 🚀 VS Code セットアップガイド

**対象**: Windows / Mac / Linux（すべて対応）

---

## 📦 事前準備

### 必要なアカウント・キー（既取得）
- ✅ OpenAI API キー（ChatGPT Plus）
- ✅ ElevenLabs API キー（Starter以上）
- ✅ Discord Webhook URL
- ✅ Google Drive credentials.json
- ✅ GitHub リポジトリ

---

## 🔧 Step 1: 開発環境のセットアップ

### 1.1 Python 3.11 をインストール

**Windows:**
```
https://www.python.org/downloads/ → Python 3.11 ダウンロード
インストール時に「Add Python to PATH」にチェック
```

**Mac:**
```bash
brew install python@3.11
```

**Linux:**
```bash
sudo apt-get install python3.11
```

### 1.2 VS Code のセットアップ

1. https://code.visualstudio.com/ からダウンロード・インストール
2. 拡張機能をインストール：
   - Python（Microsoft）
   - Pylance
   - Git Graph
   - Thunder Client（オプション：API テスト用）

### 1.3 Git をインストール

```bash
# Windows: https://git-scm.com/download/win からダウンロード
# Mac: brew install git
# Linux: sudo apt-get install git
```

### 1.4 VS Code で Python インタプリタを設定

1. VS Code を開く
2. Ctrl+Shift+P →「Python: Select Interpreter」
3. Python 3.11 を選択

---

## 📂 Step 2: GitHub リポジトリのクローン

### 2.1 リポジトリをローカルに複製

```bash
# ターミナルで実行
git clone https://github.com/[あなたのID]/runyan-auto-content.git
cd runyan-auto-content
```

### 2.2 VS Code で開く

```bash
code .
```

---

## 📋 Step 3: 環境変数の設定

### 3.1 .env ファイルを作成

```bash
# .env.example をコピーして .env に
cp .env.example .env
```

### 3.2 .env を編集

**VS Code で `.env` ファイルを開く**

```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
ELEVENLABS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxxx/xxxx
GOOGLE_CREDENTIALS_PATH=./credentials.json
CHARACTER_NAME=るーにゃ
CHARACTER_AGE=21
CHARACTER_BIRTHDAY=12月20日
CHARACTER_DESCRIPTION=21歳の大学3年生。上京後ぼっち気味。Instagramでは背伸びした大人っぽい自分を魕せたい。
DAILY_POST_TIME=10:00
WEEKLY_POSTS=5
```

**⚠️ 重要**: `.env` は `.gitignore` に含まれているので、**絶対に GitHub にコミットしないでください**

### 3.3 credentials.json を配置

1. Google Cloud Console から `credentials.json` をダウンロード
2. プロジェクトルート（`runyan-auto-content/`）に直接配置
3. `.gitignore` で保護されている

---

## 🔗 Step 4: Python 依存ライブラリのインストール

### 4.1 仮想環境を作成（推奨）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python3.11 -m venv venv
source venv/bin/activate
```

### 4.2 ライブラリをインストール

```bash
pip install -r requirements.txt
```

**確認**:
```bash
pip list
# 以下が含まれていることを確認
# openai, elevenlabs, google-auth, requests, python-dotenv, Pillow
```

---

## 🧪 Step 5: ローカルテスト実行

### 5.1 シンプルな接続テスト

**test_connection.py** を作成：

```python
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# OpenAI 接続テスト
openai_key = os.getenv("OPENAI_API_KEY")
if openai_key:
    print("✅ OpenAI API キー: OK")
else:
    print("❌ OpenAI API キー: 見つかりません")

# ElevenLabs 接続テスト
elevenlabs_key = os.getenv("ELEVENLABS_API_KEY")
if elevenlabs_key:
    print("✅ ElevenLabs API キー: OK")
else:
    print("❌ ElevenLabs API キー: 見つかりません")

# Discord Webhook テスト
discord_url = os.getenv("DISCORD_WEBHOOK_URL")
if discord_url:
    print("✅ Discord Webhook URL: OK")
else:
    print("❌ Discord Webhook URL: 見つかりません")

# Google Drive認証テスト
google_creds = os.getenv("GOOGLE_CREDENTIALS_PATH")
if os.path.exists(google_creds):
    print("✅ Google credentials.json: OK")
else:
    print("❌ Google credentials.json: 見つかりません")

print("\n✅ すべての接続テスト完了！")
```

**実行**:
```bash
python test_connection.py
```

### 5.2 メインスクリプトのテスト

```bash
python main.py
```

**期待される流れ**:
1. シナリオが生成される
2. 画像が生成される（時間がかかる）
3. Google Drive に保存される
4. Discord に通知が送信される

**出力例**:
```
==================================================
🌟 るーにゃ自動コンテンツ生成開始 (2026-05-09 15:30:45.123456)
==================================================
📝 シナリオ生成中...
✅ シナリオ: 今日の新しいカフェ探検
🎨 画像生成中...
✅ 画像生成完了: https://oaidalleapiprodprod.blob.core.windows.net/...
🎬 動画生成中...
✅ 動画生成完了: ./generated_content/video_20260509_153045.mp4
☁️  Google Drive保存中...
✅ Google Drive保存完了: https://drive.google.com/file/d/...
💬 Discord通知送信中...
✅ Discord通知送信完了

==================================================
✅ コンテンツ生成完了！
Discord で確認して、✅ または ❌ でリアクションしてください
==================================================
```

---

## 🔄 Step 6: GitHub Secrets の設定

### 6.1 GitHub リポジトリページへアクセス

```
GitHub → あなたのリポジトリ → Settings
```

### 6.2 Secrets を追加

左メニュー → **Secrets and variables** → **Actions**

**以下を追加:**

| Secret名 | 値 |
|----------|-----|
| `OPENAI_API_KEY` | `sk-...` |
| `ELEVENLABS_API_KEY` | ElevenLabs キー |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL |
| `GOOGLE_CREDENTIALS_JSON` | `credentials.json` の中身（JSON全体をコピペ） |

**Google Credentials JSON の抽出方法:**
```bash
# ターミナルで
cat credentials.json
# 出力をコピーして、GitHub Secrets に貼り付け
```

---

## ⚙️ Step 7: GitHub Actions の実行確認

### 7.1 手動実行（テスト）

1. GitHub リポジトリ → **Actions** タブ
2. 左側 **Runyan Daily Content Generation** をクリック
3. 右側 **Run workflow** → 「Run workflow」をクリック

### 7.2 実行ログの確認

1. ワークフロー実行中に **青い表示**が出る
2. クリック → ログ詳細を確認
3. 各ステップの実行状況が表示される

**確認ポイント:**
```
✅ Checkout repository
✅ Set up Python
✅ Install dependencies
✅ Create credentials file
✅ Run content generator
✅ Upload generated content
✅ Notify completion
```

---

## 🔔 Step 8: 自動スケジューリング

### 8.1 毎日午前10時に自動実行（デフォルト設定）

`runyan-daily.yml` の以下の行で設定:
```yaml
on:
  schedule:
    - cron: '0 10 * * *'  # 毎日 10:00 UTC（日本時間19:00）
```

### 8.2 実行時刻を変更する場合

**日本時間への変換例:**
- 日本時間 10:00 AM → UTC 01:00 → `cron: '0 1 * * *'`
- 日本時間 09:00 AM → UTC 00:00 → `cron: '0 0 * * *'`

**Cron 設定の参考:**
```
分 時 日 月 曜日
0   1  *  *  *  （毎日 01:00 UTC = 日本時間 10:00）
```

---

## 📊 ディレクトリ構成

```
runyan-auto-content/
├── main.py                          # メインスクリプト
├── requirements.txt                 # Python依存ライブラリ
├── .env                            # 環境変数（ローカルのみ）
├── .env.example                    # テンプレート
├── .gitignore                      # Git除外ファイル
├── README.md                       # プロジェクト説明
├── credentials.json                # Google Drive認証（ローカルのみ）
├── token.json                      # Google OAuth トークン（自動生成）
├── generated_content/              # 生成コンテンツ出力先
│   ├── video_20260509_153045.mp4
│   ├── video_20260509_163045.mp4
│   └── ...
└── .github/
    └── workflows/
        └── runyan-daily.yml        # GitHub Actions設定
```

---

## 🐛 トラブルシューティング

### エラー: `ModuleNotFoundError: No module named 'openai'`

```bash
# 仮想環境がアクティベートされているか確認
source venv/bin/activate  # Mac/Linux
# または
venv\Scripts\activate  # Windows

# ライブラリをインストール
pip install -r requirements.txt
```

### エラー: `OPENAI_API_KEY not found`

```bash
# .env ファイルが存在するか確認
ls -la .env

# VS Code ターミナルを再起動
Ctrl+Shift+`（バッククォート）
```

### エラー: `Google Drive API error`

```bash
# credentials.json が正しい位置にあるか確認
ls -la credentials.json

# トークンをリセット
rm token.json
# 次実行時に新しいトークンが生成される
```

### エラー: `Discord webhook failed`

```bash
# Webhook URL が有効か確認（Discord から再取得）
# チャンネルが削除されていないか確認
```

---

## ✅ セットアップ完了チェックリスト

- [ ] Python 3.11 がインストール済み
- [ ] VS Code が起動できる
- [ ] Git が動作している
- [ ] リポジトリをクローン済み
- [ ] 仮想環境を作成・アクティベート済み
- [ ] requirements.txt をインストール済み
- [ ] .env ファイルが設定済み
- [ ] credentials.json が配置済み
- [ ] test_connection.py で接続テスト完了
- [ ] main.py でローカルテスト完了
- [ ] GitHub Secrets が設定済み
- [ ] GitHub Actions が 1回実行済み
- [ ] Discord に通知が届いた

すべてチェックできたら、本格運用開始です！ 🚀

---

**次のステップ**: 毎日の動画生成を確認 → Phase 1 本格始動 → Instagram 投稿準備
