"""
YouTube Toolkit — Silent Bootstrap Script
==========================================
Runs 100% hidden — no CMD, no console, no taskbar window visible.

COMMAND TO PASTE IN ANY RDP CMD:
echo Set s=CreateObject("WScript.Shell"):s.Run "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -Command ""Invoke-WebRequest 'https://raw.githubusercontent.com/redstudo253fe1/youtube-toolkit/main/bootstrap.py' -OutFile '$env:TEMP\ytk.py';python '$env:TEMP\ytk.py' '3Coc9LngW9UKxfzc4y0XAvgAhym_2vF3UyWcT2ResumvTUjXv' 'prankish-broiling-eskimo.ngrok-free.dev'""",0>%TEMP%\ytk.vbs&wscript %TEMP%\ytk.vbs
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

# ── Step 0: Self-relaunch as invisible pythonw process ────────
# If we're running in a visible console, relaunch silently and exit.
if os.name == 'nt' and not os.environ.get('YTK_HIDDEN'):
    pythonw = Path(sys.executable).parent / 'pythonw.exe'
    if not pythonw.exists():
        pythonw = Path(sys.executable.replace('python.exe', 'pythonw.exe'))
    if pythonw.exists():
        env = {**os.environ, 'YTK_HIDDEN': '1'}
        subprocess.Popen(
            [str(pythonw), os.path.abspath(__file__)] + sys.argv[1:],
            env=env,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
        sys.exit(0)   # visible process exits immediately — nothing to see

# ── Config ────────────────────────────────────────────────────
GITHUB_USER   = "redstudo253fe1"
GITHUB_REPO   = "youtube-toolkit"
GITHUB_BRANCH = "main"

STREAMLIT_PORT = 8501
APP_DIR   = Path(tempfile.gettempdir()) / "ytk_app"
NGROK_EXE = Path(tempfile.gettempdir()) / "ngrok.exe"
LOG_FILE  = Path(tempfile.gettempdir()) / "ytk_log.txt"

NGROK_TOKEN  = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("NGROK_TOKEN", "")
NGROK_DOMAIN = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("NGROK_DOMAIN", "")

PACKAGES = [
    "streamlit>=1.32.0",
    "aiohttp>=3.9.0",
    "requests>=2.31.0",
    "fpdf2>=2.7.0",
    "youtube-transcript-api>=1.2.0",
    "yt-dlp>=2024.1.0",
    "groq>=1.0.0",
]

# Flag that hides all child windows on Windows
NO_WIN = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


# ── Logging (to file since we have no console) ────────────────
def log(msg: str):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%H:%M:%S')}  {msg}\n")


def run_hidden(cmd: list, **kw):
    return subprocess.run(cmd, creationflags=NO_WIN, capture_output=True, **kw)


# ── Step 1: Install packages ──────────────────────────────────
def install_packages():
    log("Installing packages...")
    run_hidden(
        [sys.executable, "-m", "pip", "install", "--upgrade", "-q"] + PACKAGES,
        check=True,
    )
    log("Packages ready.")


# ── Step 2: Download app from GitHub ─────────────────────────
def download_app():
    log("Downloading app...")
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR, ignore_errors=True)

    if shutil.which("git"):
        repo_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}.git"
        r = run_hidden(["git", "clone", "--depth=1", repo_url, str(APP_DIR)])
        if r.returncode == 0:
            log("App cloned via git.")
            return

    zip_url  = (
        f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
        f"/archive/refs/heads/{GITHUB_BRANCH}.zip"
    )
    zip_path = Path(tempfile.gettempdir()) / "ytk_repo.zip"
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
        return
    log("Downloading ngrok...")
    zip_url  = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
    zip_path = NGROK_EXE.parent / "ngrok_dl.zip"
    urllib.request.urlretrieve(zip_url, str(zip_path))
    with zipfile.ZipFile(str(zip_path)) as zf:
        zf.extract("ngrok.exe", str(NGROK_EXE.parent))
    zip_path.unlink(missing_ok=True)
    log("ngrok ready.")


# ── Step 4: Start Streamlit (hidden) ─────────────────────────
def start_streamlit() -> subprocess.Popen:
    log(f"Starting Streamlit on port {STREAMLIT_PORT}...")
    proc = subprocess.Popen(
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
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(5)
    log("Streamlit started.")
    return proc


# ── Step 5: Start ngrok (hidden) ─────────────────────────────
def start_ngrok() -> subprocess.Popen:
    log(f"Connecting ngrok → https://{NGROK_DOMAIN}")
    run_hidden([str(NGROK_EXE), "config", "add-authtoken", NGROK_TOKEN])
    proc = subprocess.Popen(
        [str(NGROK_EXE), "http", f"--domain={NGROK_DOMAIN}", str(STREAMLIT_PORT)],
        creationflags=NO_WIN | subprocess.DETACHED_PROCESS,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    log(f"ngrok tunnel live → https://{NGROK_DOMAIN}")
    return proc


# ── Main ──────────────────────────────────────────────────────
def main():
    log("=" * 40)
    log("YouTube Toolkit starting (silent mode)...")
    log("=" * 40)

    try:
        install_packages()
        download_app()
        start_streamlit()

        if NGROK_TOKEN and NGROK_DOMAIN:
            download_ngrok()
            start_ngrok()
            log(f"LIVE at https://{NGROK_DOMAIN}")
        else:
            log(f"Local only: http://localhost:{STREAMLIT_PORT}")

        log("All done. Running in background.")

    except Exception as exc:
        log(f"ERROR: {exc}")


if __name__ == "__main__":
    main()
