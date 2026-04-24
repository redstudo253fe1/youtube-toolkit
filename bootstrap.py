"""
YouTube Toolkit — Bootstrap Script
===================================
Paste this ONE command in any RDP CMD to auto-install and start the app:

  powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest 'https://raw.githubusercontent.com/YOUR_GITHUB/youtube-toolkit/main/bootstrap.py' -OutFile '$env:TEMP\ytk.py'; python '$env:TEMP\ytk.py' 'YOUR_NGROK_TOKEN' 'YOUR_NGROK_DOMAIN.ngrok-free.app'"

Usage:
  python bootstrap.py <NGROK_TOKEN> <NGROK_DOMAIN>

  NGROK_TOKEN  — your ngrok auth token (free at dashboard.ngrok.com)
  NGROK_DOMAIN — your free static domain (e.g. your-app.ngrok-free.app)
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

# ── Config ────────────────────────────────────────────────────
GITHUB_USER   = "redstudo253fe1"
GITHUB_REPO   = "youtube-toolkit"
GITHUB_BRANCH = "main"

STREAMLIT_PORT = 8501
APP_DIR  = Path(tempfile.gettempdir()) / "ytk_app"
NGROK_EXE = Path(tempfile.gettempdir()) / "ngrok.exe"

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


# ── Helpers ───────────────────────────────────────────────────
def banner(msg: str):
    print(f"\n{'─'*52}")
    print(f"  {msg}")
    print('─'*52)


def run(cmd: list, **kw):
    return subprocess.run(cmd, **kw)


# ── Step 1: Install Python packages ──────────────────────────
def install_packages():
    banner("Installing packages…")
    run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "-q"] + PACKAGES,
        check=True,
    )
    print("  ✅ Packages ready")


# ── Step 2: Download app from GitHub ─────────────────────────
def download_app():
    banner("Downloading app from GitHub…")

    if APP_DIR.exists():
        shutil.rmtree(APP_DIR, ignore_errors=True)

    # Try git clone first (fast, incremental)
    if shutil.which("git"):
        repo_url = f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}.git"
        result = run(["git", "clone", "--depth=1", repo_url, str(APP_DIR)],
                     capture_output=True)
        if result.returncode == 0:
            print("  ✅ App cloned via git")
            return

    # Fallback: download zip from GitHub
    zip_url  = (
        f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}"
        f"/archive/refs/heads/{GITHUB_BRANCH}.zip"
    )
    zip_path = Path(tempfile.gettempdir()) / "ytk_repo.zip"
    print(f"  Downloading from {zip_url}")
    urllib.request.urlretrieve(zip_url, str(zip_path))

    extract_dir = Path(tempfile.gettempdir()) / "ytk_extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)

    with zipfile.ZipFile(str(zip_path)) as zf:
        zf.extractall(str(extract_dir))

    # The zip extracts to REPO-BRANCH/ folder
    extracted_folder = extract_dir / f"{GITHUB_REPO}-{GITHUB_BRANCH}"
    if extracted_folder.exists():
        shutil.copytree(str(extracted_folder), str(APP_DIR))

    zip_path.unlink(missing_ok=True)
    shutil.rmtree(extract_dir, ignore_errors=True)
    print("  ✅ App downloaded via zip")


# ── Step 3: Download ngrok ────────────────────────────────────
def download_ngrok():
    if NGROK_EXE.exists():
        print("  ✅ ngrok already present")
        return
    banner("Downloading ngrok…")
    zip_url  = "https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"
    zip_path = NGROK_EXE.parent / "ngrok_dl.zip"
    urllib.request.urlretrieve(zip_url, str(zip_path))
    with zipfile.ZipFile(str(zip_path)) as zf:
        zf.extract("ngrok.exe", str(NGROK_EXE.parent))
    zip_path.unlink(missing_ok=True)
    print("  ✅ ngrok downloaded")


# ── Step 4: Start Streamlit ───────────────────────────────────
def start_streamlit() -> subprocess.Popen:
    banner(f"Starting Streamlit on port {STREAMLIT_PORT}…")
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
    )
    # Give Streamlit a moment to start
    time.sleep(5)
    print(f"  ✅ Streamlit running on localhost:{STREAMLIT_PORT}")
    return proc


# ── Step 5: Start ngrok tunnel ────────────────────────────────
def start_ngrok() -> subprocess.Popen:
    banner(f"Connecting ngrok → https://{NGROK_DOMAIN}")

    # Authenticate token (silent)
    run([str(NGROK_EXE), "config", "add-authtoken", NGROK_TOKEN],
        capture_output=True)

    proc = subprocess.Popen(
        [str(NGROK_EXE), "http", f"--domain={NGROK_DOMAIN}", str(STREAMLIT_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(3)
    return proc


# ── Main ──────────────────────────────────────────────────────
def main():
    print("\n" + "█" * 52)
    print("   YouTube Toolkit — Auto Setup")
    print("█" * 52)

    if GITHUB_USER == "YOUR_GITHUB_USERNAME":
        print("\n  ⚠️  Edit bootstrap.py first:")
        print("     Set GITHUB_USER to your GitHub username")
        print("     Set GITHUB_REPO to your repo name\n")
        sys.exit(1)

    install_packages()
    download_app()

    st_proc = start_streamlit()

    ng_proc = None
    if NGROK_TOKEN and NGROK_DOMAIN:
        download_ngrok()
        ng_proc = start_ngrok()
        print(f"\n{'█'*52}")
        print(f"   🌐  YOUR APP IS LIVE AT:")
        print(f"\n       https://{NGROK_DOMAIN}\n")
        print(f"   Open this on your phone or any browser!")
        print(f"{'█'*52}\n")
    else:
        print(f"\n  Local access: http://localhost:{STREAMLIT_PORT}")
        print("  (Pass NGROK_TOKEN and NGROK_DOMAIN as args for public URL)\n")

    print("  Press Ctrl+C to stop\n")

    try:
        st_proc.wait()
    except KeyboardInterrupt:
        print("\n  Shutting down…")
        st_proc.terminate()
        if ng_proc:
            ng_proc.terminate()
    finally:
        print("  Stopped.")


if __name__ == "__main__":
    main()
