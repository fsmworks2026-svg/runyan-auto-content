@echo off
chcp 65001 >nul 2>&1
set "__BATFILE=%~f0"
set "__BOTDIR=%~dp0"
if "%__BOTDIR:~-1%"=="\" set "__BOTDIR=%__BOTDIR:~0,-1%"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[IO.File]::ReadAllText($env:__BATFILE,'UTF-8') -split '(?m)^:PS_SCRIPT\r?$',2 | Select-Object -Last 1 | Invoke-Expression"
pause
goto :eof
:PS_SCRIPT
$ProjectDir = $env:__BOTDIR
$GH_REPO    = 'fsmworks2026-svg/runyan-auto-content'
$EnvPath    = "$ProjectDir\.env"

Write-Host ''
Write-Host '======================================' -ForegroundColor Cyan
Write-Host '  るーにゃBot' -ForegroundColor Cyan
Write-Host '======================================'
Write-Host ''

# ── 1. Python 確認 ─────────────────────────────────
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host 'Python が見つかりません。' -ForegroundColor Red
    Write-Host 'https://www.python.org からインストール後、再実行してください。'
    Read-Host 'Enterで終了'; exit 1
}
Write-Host "[OK] $(python --version 2>&1)"

# ── 2. 依存ライブラリ ──────────────────────────────
Write-Host '依存ライブラリを確認中...'
pip install -r "$ProjectDir\requirements-bot.txt" -q --disable-pip-version-check
Write-Host '[OK] 完了'

# ── 3. .env 取得（初回のみ）────────────────────────
if (-not (Test-Path $EnvPath)) {
    Write-Host ''
    Write-Host '.env がありません。GitHubから自動取得します。' -ForegroundColor Yellow
    Write-Host ''
    $PAT = Read-Host 'GitHub PAT を貼り付けてください（初回のみ）'
    Write-Host ''

    $headers = @{
        Authorization = "token $PAT"
        Accept        = 'application/vnd.github.v3+json'
    }

    # ワークフローを起動
    Write-Host 'GitHub Actions を起動中...'
    $beforeTime = [DateTime]::UtcNow.AddSeconds(-5)
    try {
        Invoke-RestMethod -Method Post -UseBasicParsing `
            -Uri "https://api.github.com/repos/$GH_REPO/actions/workflows/setup-bot-env.yml/dispatches" `
            -Headers $headers -ContentType 'application/json' -Body '{"ref":"master"}' | Out-Null
    } catch {
        Write-Host "起動失敗: $_" -ForegroundColor Red
        Write-Host 'GitHub PAT に repo + workflow 権限があるか確認してください。'
        Read-Host 'Enterで終了'; exit 1
    }

    # 完了を待機（最大3分）
    Write-Host '完了を待機中（最大3分）...'
    $runId = $null
    for ($i = 0; $i -lt 36; $i++) {
        Start-Sleep 5
        try {
            $runs = (Invoke-RestMethod -UseBasicParsing `
                -Uri "https://api.github.com/repos/$GH_REPO/actions/workflows/setup-bot-env.yml/runs?per_page=5" `
                -Headers $headers).workflow_runs
            $target = $runs | Where-Object {
                [DateTime]::Parse($_.created_at) -gt $beforeTime
            } | Select-Object -First 1
            if ($target) {
                Write-Host "  ... $($target.status) ($($i * 5)秒)"
                if ($target.status -eq 'completed') { $runId = $target.id; break }
            }
        } catch {}
    }
    if (-not $runId) {
        Write-Host 'タイムアウト。もう一度試してください。' -ForegroundColor Red
        Read-Host 'Enterで終了'; exit 1
    }

    # Artifact をダウンロード
    Write-Host 'Artifact をダウンロード中...'
    try {
        $art = (Invoke-RestMethod -UseBasicParsing `
            -Uri "https://api.github.com/repos/$GH_REPO/actions/runs/$runId/artifacts" `
            -Headers $headers).artifacts |
            Where-Object name -eq 'bot-env' | Select-Object -First 1
        if (-not $art) { throw 'bot-env artifact が見つかりません' }

        # GitHub は S3 へリダイレクトするため Location ヘッダを取得してから直接ダウンロード
        $zipPath  = [IO.Path]::Combine($env:TEMP, "bot_env_$([IO.Path]::GetRandomFileName()).zip")
        $redirRes = Invoke-WebRequest -UseBasicParsing -Uri $art.archive_download_url `
            -Headers $headers -MaximumRedirection 0 -ErrorAction SilentlyContinue
        $dlUrl    = if ($redirRes.Headers['Location']) { $redirRes.Headers['Location'] } else { $art.archive_download_url }
        Invoke-WebRequest -Uri $dlUrl -OutFile $zipPath -UseBasicParsing

        Expand-Archive -Path $zipPath -DestinationPath $ProjectDir -Force
        Remove-Item $zipPath -ErrorAction SilentlyContinue
        Write-Host '[OK] .env を取得しました！' -ForegroundColor Green
    } catch {
        Write-Host "取得失敗: $_" -ForegroundColor Red
        Write-Host 'もう一度バットファイルを実行してください（Artifact は24時間有効）。'
        Read-Host 'Enterで終了'; exit 1
    }
}

# ── 4. Bot 起動 ────────────────────────────────────
Write-Host ''
Write-Host '======================================' -ForegroundColor Green
Write-Host '  Bot を起動します（Ctrl+C で停止）' -ForegroundColor Green
Write-Host '======================================'
Write-Host ''
Set-Location $ProjectDir
python "$ProjectDir\discord_bot.py"
