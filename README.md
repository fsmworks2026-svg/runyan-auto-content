# るーにゃ 自動コンテンツ生成パイプライン

21歳の大学3年生「るーにゃ」のInstagram用コンテンツを完全自動生成します。

## 📋 概要

- **シナリオ自動生成**: Claude API
- **画像生成**: ChatGPT Image 2.0
- **動画化**: ElevenLabs Seedance
- **ストレージ**: Google Drive
- **通知**: Discord Webhook
- **自動スケジューリング**: GitHub Actions（毎日午前10時）

## 🚀 セットアップ手順

### 1. リポジトリをクローン

```bash
git clone https://github.com/[あなたのID]/runyan-auto-content.git
cd runyan-auto-content
```

### 2. 環境変数設定

```bash
cp .env.example .env
```

`.env` ファイルに以下を入力：

```
OPENAI_API_KEY=your_openai_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
DISCORD_WEBHOOK_URL=your_discord_webhook_url
GOOGLE_CREDENTIALS_PATH=./credentials.json
```

### 3. Google Drive認証

1. `credentials.json` をダウンロード（Google Cloud Console から）
2. プロジェクトルートに配置

### 4. ローカル実行（テスト）

```bash
pip install -r requirements.txt
python main.py
```

### 5. GitHub Secrets設定

リポジトリ設定 → Secrets に以下を追加：

| Secret名 | 値 |
|---------|-----|
| `OPENAI_API_KEY` | OpenAI API キー |
| `ELEVENLABS_API_KEY` | ElevenLabs API キー |
| `DISCORD_WEBHOOK_URL` | Discord Webhook URL |
| `GOOGLE_CREDENTIALS_JSON` | `credentials.json` の内容（JSONそのもの） |

### 6. GitHub Actions実行確認

```
Actions タブ → Runyan Daily Content Generation → 実行
```

## 📱 使用フロー

```
1. 毎日午前10時、GitHub Actionsが自動起動
   ↓
2. Claude APIでシナリオ生成
   ↓
3. ChatGPT Image 2.0で画像生成
   ↓
4. ElevenLabs Seedanceで動画化
   ↓
5. Google Driveに自動保存
   ↓
6. Discord通知（リンク付き）
   ↓
7. 伏見さんが確認 → ✅ または ❌
   ↓
8. ✅ なら Instagram自動投稿（後で実装）
```

## 🎯 キャラクター設定

```
名前: るーにゃ
年齢: 21歳
誕生日: 12月20日
設定: 大学3年生、上京後ぼっち気味、Instagram では背伸びした大人っぽい自分を演出
```

## 🔧 カスタマイズ

### シナリオ生成プロンプトの変更

`main.py` の `generate_scenario()` メソッド内の `prompt` を編集。

### 画像生成スタイルの変更

`generate_image()` メソッドの `prompt` 内で、スタイル指定を変更。

例：
```python
prompt = f"""
Create a professional Instagram photo of {CHARACTER['name']}...
Style: [ここを変更] 
"""
```

## ⚠️ 注意事項

- **API代について**:
  - ChatGPT Plus（月$20）でカバー
  - ElevenLabs Starter（月$5）でカバー
  - 合計月額$25程度（クレジットカード登録必須）

- **動画生成時間**: 
  - Seedance は時間がかかるため、タイムアウト設定に注意

- **Google Drive容量**:
  - 月1,500MB 程度消費（150本の動画）

## 📊 ログ確認

```bash
# ローカル実行ログ
python main.py 2>&1 | tee runyan.log

# GitHub Actions ログ
# Actions タブから確認
```

## 🛠️ トラブルシューティング

### エラー: `OPENAI_API_KEY not found`

→ `.env` ファイルが正しく設定されているか確認

### エラー: `Google Drive API error`

→ `credentials.json` が正しく配置されているか、スコープが正しいか確認

### エラー: `Discord webhook failed`

→ Discord Webhook URL が有効か、チャンネルが存在するか確認

## 🔐 セキュリティ

- **API キー**: GitHub Secrets に保存（コミットしない）
- **credentials.json**: `.gitignore` に追加
- **Webhook URL**: 絶対に公開しない

```
# .gitignore に追加
.env
credentials.json
token.json
generated_content/
__pycache__/
```

## 📞 サポート

問題が発生した場合：

1. ログを確認
2. API キーの有効期限確認
3. GitHub Secrets の設定確認
4. Discord チャンネルの権限確認

## 📝 ロードマップ

- [x] シナリオ自動生成
- [x] 画像生成
- [x] 動画化
- [x] Google Drive 保存
- [x] Discord 通知
- [ ] Instagram 自動投稿
- [ ] エンゲージメント分析
- [ ] A/B テスト

---

**作成日**: 2026年5月9日  
**管理者**: 伏見さん  
**GitHub**: https://github.com/[あなたのID]/runyan-auto-content
