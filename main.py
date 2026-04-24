"""YouTube Toolkit - All-in-one GUI application."""
import sys
import os

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# When running as PyInstaller bundle, set the path for bundled data
if getattr(sys, 'frozen', False):
    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')

from youtube_toolkit.gui.app import run

if __name__ == "__main__":
    run()
