"""
runyan Bot setup & launcher.
Standard library only - no third-party packages needed for setup.
"""
import os
import sys
import subprocess
import urllib.request
import urllib.error
import json
import zipfile
import io
import time
import calendar
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
GH_REPO     = "fsmworks2026-svg/runyan-auto-content"
ENV_PATH    = PROJECT_DIR / ".env"
REQ_FILE    = PROJECT_DIR / "requirements-bot.txt"
BOT_SCRIPT  = PROJECT_DIR / "discord_bot.py"


# ─── GitHub API helpers ───────────────────────────────────────────────────────

def gh_request(url, pat, method="GET", data=None):
    headers = {
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github.v3+json",
    }
    body = json.dumps(data).encode() if data else None
    req  = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            body = res.read()
            return res.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, {}


def download_bytes(url, pat):
    """Download with auth; urllib follows the redirect to S3 automatically."""
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {pat}",
        "Accept": "application/vnd.github.v3+json",
    })
    with urllib.request.urlopen(req) as res:
        return res.read()


# ─── Main ─────────────────────────────────────────────────────────────────────

print()
print("====================================")
print("  runyan Bot")
print("====================================")
print()

# 1. Install dependencies
print("[1/3] Checking dependencies...")
result = subprocess.run(
    [sys.executable, "-m", "pip", "install", "-r", str(REQ_FILE),
     "-q", "--disable-pip-version-check"],
    capture_output=True, text=True
)
if result.returncode != 0:
    print("ERROR: pip install failed.")
    print(result.stderr)
    input("Press Enter to exit")
    sys.exit(1)
print("  OK")

# 2. Get .env (first time only)
print("[2/3] Checking .env...")
if not ENV_PATH.exists():
    print("  .env not found. Fetching from GitHub automatically.")
    print()
    pat = input("  Paste your GitHub PAT (only needed once): ").strip()
    print()

    # Trigger workflow
    print("  Starting GitHub Actions...")
    before_time = time.time()
    status, _ = gh_request(
        f"https://api.github.com/repos/{GH_REPO}/actions/workflows/setup-bot-env.yml/dispatches",
        pat, method="POST", data={"ref": "master"}
    )
    if status != 204:
        print(f"  ERROR: Failed to start workflow (HTTP {status}).")
        print("  Check that your PAT has 'repo' and 'workflow' permissions.")
        input("Press Enter to exit")
        sys.exit(1)

    # Wait for completion (up to 3 minutes)
    print("  Waiting for workflow to complete (up to 3 min)...")
    run_id = None
    for i in range(36):
        time.sleep(5)
        try:
            _, data = gh_request(
                f"https://api.github.com/repos/{GH_REPO}/actions/workflows"
                f"/setup-bot-env.yml/runs?per_page=5",
                pat
            )
            for run in data.get("workflow_runs", []):
                # parse UTC timestamp correctly
                created = calendar.timegm(
                    time.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ")
                )
                if created > before_time - 30 and run["status"] == "completed":
                    run_id = run["id"]
                    break
            if run_id:
                break
            runs = data.get("workflow_runs", [])
            if runs:
                print(f"    ... {runs[0].get('status', '?')} ({i * 5}s)")
        except Exception:
            pass

    if not run_id:
        print("  ERROR: Timed out. Please run again.")
        input("Press Enter to exit")
        sys.exit(1)

    # Download artifact
    print("  Downloading artifact...")
    try:
        _, arts_data = gh_request(
            f"https://api.github.com/repos/{GH_REPO}/actions/runs/{run_id}/artifacts",
            pat
        )
        art = next(
            (a for a in arts_data.get("artifacts", []) if a["name"] == "bot-env"),
            None
        )
        if not art:
            raise RuntimeError("bot-env artifact not found")

        zip_bytes = download_bytes(art["archive_download_url"], pat)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            z.extractall(PROJECT_DIR)

        print("  OK: .env downloaded!")
    except Exception as e:
        print(f"  ERROR: {e}")
        input("Press Enter to exit")
        sys.exit(1)
else:
    print("  OK: .env found")

# 3. Launch bot
print()
print("====================================")
print("  Launching bot... (Ctrl+C to stop)")
print("====================================")
print()

os.chdir(PROJECT_DIR)
try:
    subprocess.run([sys.executable, str(BOT_SCRIPT)])
except KeyboardInterrupt:
    pass
