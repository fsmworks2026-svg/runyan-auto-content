# るーにゃBot セットアップスクリプト（Windows用）
# 新しいPCで初回実行してください。
#
# 使い方:
#   右クリック →「PowerShell で実行」
#   または: powershell -ExecutionPolicy Bypass -File setup_bot.ps1

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$EnvFile    = Join-Path $ProjectDir ".env"
$BotScript  = Join-Path $ProjectDir "discord_bot.py"
$ReqFile    = Join-Path $ProjectDir "requirements-bot.txt"

$ActionsUrl = "https://github.com/fsmworks2026-svg/runyan-auto-content/actions/workflows/setup-bot-env.yml"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  るーにゃBot セットアップ" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python 確認 ──────────────────────────────
Write-Host "[1/3] Python を確認中..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python が見つかりません。" -ForegroundColor Red
    Write-Host "   https://www.python.org/downloads/ からインストールしてください。"
    Read-Host "Enterキーで終了"
    exit 1
}
$pyVer = python --version 2>&1
Write-Host "   ✅ $pyVer"

# ── 2. 依存ライブラリ インストール ──────────────
Write-Host ""
Write-Host "[2/3] 依存ライブラリをインストール中..." -ForegroundColor Yellow
pip install -r $ReqFile --quiet
Write-Host "   ✅ discord.py / requests / python-dotenv インストール完了"

# ── 3. .env ファイル 確認 ──────────────────────
Write-Host ""
Write-Host "[3/3] .env ファイルを確認中..." -ForegroundColor Yellow

if (-not (Test-Path $EnvFile)) {
    Write-Host ""
    Write-Host "  ⚠️  .env ファイルが見つかりません。" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  以下の手順でトークンを取得してください:" -ForegroundColor White
    Write-Host ""
    Write-Host "  ① ブラウザで下記URLを開く:"
    Write-Host "     $ActionsUrl" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  ② 右上の「Run workflow」ボタンをクリック → 「Run workflow」"
    Write-Host ""
    Write-Host "  ③ 実行完了後（緑チェック）、ジョブをクリック"
    Write-Host "     → 下部の「Artifacts」から「bot-env」をダウンロード"
    Write-Host ""
    Write-Host "  ④ ダウンロードしたZIPを展開し、中の .env を"
    Write-Host "     以下のフォルダに配置:"
    Write-Host "     $ProjectDir" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  ⑤ このスクリプトをもう一度実行してください。"
    Write-Host ""

    # ブラウザで直接開く
    $open = Read-Host "今すぐブラウザで開きますか？ (Y/n)"
    if ($open -ne "n" -and $open -ne "N") {
        Start-Process $ActionsUrl
    }
    Read-Host "Enterキーで終了"
    exit 0
}

Write-Host "   ✅ .env が見つかりました"

# ── 起動 ────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  ✅ セットアップ完了！Botを起動します" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  停止するには Ctrl+C を押してください。"
Write-Host ""

python $BotScript
