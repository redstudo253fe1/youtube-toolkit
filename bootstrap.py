"""
YouTube Toolkit — Bootstrap
============================
Called by launcher.ps1 (which runs this with pythonw.exe = no console).
Writes all progress to %TEMP%\\ytk_log.txt
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
import zipfile
from pathlib import Path

LOG_FILE = Path(tempfile.gettempdir()) / "ytk_log.txt"


def log(msg: str):
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(f"{time.strftime('%H:%M:%S')}  {msg}\n")
    except Exception:
        pass


# ── Immediate startup log (so we know it ran) ─────────────────
log("=" * 44)
log("bootstrap.py started")
log(f"Python: {sys.executable}")
log(f"Args: {sys.argv[1:]}")
log(f"CWD: {os.getcwd()}")

# ── Config ────────────────────────────────────────────────────
GITHUB_USER   = "redstudo253fe1"
GITHUB_REPO   = "youtube-toolkit"
GITHUB_BRANCH = "main"

STREAMLIT_PORT = 8501
APP_DIR   = Path(tempfile.gettempdir()) / "ytk_app"
NGROK_EXE = Path(tempfile.gettempdir()) / "ngrok.exe"

NGROK_TOKEN  = sys.argv[1] if len(sys.argv) > 1 else ""
NGROK_DOMAIN = sys.argv[2] if len(sys.argv) > 2 else ""

PACKAGES = [
    "streamlit>=1.32.0",
    "aiohttp>=3.9.0",
    "requests>=2.31.0",
    "fpdf2>=2.7.0",
    "youtube-transcript-api>=1.2.0",
    "yt-dlp>=2024.1.0",
    "groq>=1.0.0",
]

# Windows: hide child process windows
NO_WIN = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def run_hidden(cmd, check=False):
    return subprocess.run(
        cmd,
        creationflags=NO_WIN,
        capture_output=True,
        text=True,
        check=check,
    )


# ── Step 1: Install packages ──────────────────────────────────
def install_packages():
    log("Installing packages (pip)...")
    r = run_hidden(
        [sys.executable, "-m", "pip", "install", "--upgrade", "-q"] + PACKAGES
    )
    if r.returncode != 0:
        log(f"pip stderr: {r.stderr[:400]}")
        raise RuntimeError("pip install failed")
    log("Packages ready.")


# ── Step 2: Download app from GitHub ──────────────────────────
def download_app():
    log("Downloading app from GitHub...")
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR, ignore_errors=True)

    # Try git clone
    if shutil.which("git"):
        url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}.git"
        r = run_hidden(["git", "clone", "--depth=1", url, str(APP_DIR)])
        if r.returncode == 0:
            log("App cloned via git.")
            return
        log(f"git clone failed: {r.stderr[:200]}")

    # Fallback: zip download
    zip_url = (
        f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
        f"/archive/refs/heads/{GITHUB_BRANCH}.zip"
    )
    zip_path = Path(tempfile.gettempdir()) / "ytk_repo.zip"
    log(f"Downloading zip: {zip_url}")
    urllib.request.urlretrieve(zip_url, str(zip_path))

    extract_dir = Path(tempfile.gettempdir()) / "ytk_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    with zipfile.ZipFile(str(zip_path)) as zf:
        zf.extractall(str(extract_dir))

    extracted = extract_dir / f"{GITHUB_REPO}-{GITHUB_BRANCH}"
    if extracted.exists():
        shutil.copytree(str(extracted), str(APP_DIR))

    zip_path.unlink(missing_ok=True)
    shutil.rmtree(extract_dir, ignore_errors=True)
    log("App downloaded via zip.")


# ── Step 3: Download ngrok ────────────────────────────────────
def download_ngrok():
    if NGROK_EXE.exists():
        log("ngrok.exe already present.")
        return
    log("Downloading ngrok...")
    zip_url = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
    zip_path = NGROK_EXE.parent / "ngrok_dl.zip"
    urllib.request.urlretrieve(zip_url, str(zip_path))
    with zipfile.ZipFile(str(zip_path)) as zf:
        zf.extract("ngrok.exe", str(NGROK_EXE.parent))
    zip_path.unlink(missing_ok=True)
    log("ngrok ready.")


# ── Step 4: Start Streamlit (hidden background process) ──────
def start_streamlit():
    log(f"Starting Streamlit on port {STREAMLIT_PORT}...")
    out = open(Path(tempfile.gettempdir()) / "ytk_streamlit.log", "a", encoding="utf-8")
    subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            str(APP_DIR / "streamlit_app.py"),
            f"--server.port={STREAMLIT_PORT}",
            "--server.headless=true",
            "--server.address=localhost",
            "--browser.gatherUsageStats=false",
            "--theme.base=dark",
        ],
        cwd=str(APP_DIR),
        creationflags=NO_WIN | subprocess.DETACHED_PROCESS,
        stdout=out,
        stderr=out,
        stdin=subprocess.DEVNULL,
    )
    time.sleep(6)
    log("Streamlit started.")


# ── Step 5: Start ngrok (hidden background process) ─────────
def start_ngrok():
    log(f"Connecting ngrok → https://{NGROK_DOMAIN}")
    run_hidden([str(NGROK_EXE), "config", "add-authtoken", NGROK_TOKEN])
    out = open(Path(tempfile.gettempdir()) / "ytk_ngrok.log", "a", encoding="utf-8")
    subprocess.Popen(
        [str(NGROK_EXE), "http", f"--domain={NGROK_DOMAIN}", str(STREAMLIT_PORT)],
        creationflags=NO_WIN | subprocess.DETACHED_PROCESS,
        stdout=out,
        stderr=out,
        stdin=subprocess.DEVNULL,
    )
    time.sleep(3)
    log(f"ngrok tunnel should be LIVE at https://{NGROK_DOMAIN}")


# ── Main ──────────────────────────────────────────────────────
def main():
    try:
        install_packages()
        download_app()
        start_streamlit()
        if NGROK_TOKEN and NGROK_DOMAIN:
            download_ngrok()
            start_ngrok()
            log(f"ALL DONE → https://{NGROK_DOMAIN}")
        else:
            log(f"Local only: http://localhost:{STREAMLIT_PORT}")
    except Exception as exc:
        log(f"FATAL ERROR: {exc}")
        log(traceback.format_exc())


if __name__ == "__main__":
    main()
