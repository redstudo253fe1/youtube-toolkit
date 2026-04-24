"""Shared utilities for YouTube Toolkit."""
import re
import os


def extract_video_id(url_or_id: str) -> str:
    patterns = [
        r'(?:youtube\.com/watch\?v=)([\w-]{11})',
        r'(?:youtu\.be/)([\w-]{11})',
        r'(?:youtube\.com/embed/)([\w-]{11})',
        r'(?:youtube\.com/shorts/)([\w-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    if re.match(r'^[\w-]{11}$', url_or_id.strip()):
        return url_or_id.strip()
    return url_or_id.strip()


def is_youtube_url(text: str) -> bool:
    return any(x in text for x in ['youtube.com', 'youtu.be'])


def format_timestamp(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hrs > 0:
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"


def format_srt_time(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def get_video_title(video_id: str) -> str:
    """Get video title using yt-dlp (handles cookies, anti-429)."""
    try:
        from yt_dlp import YoutubeDL
        ydl_opts = {
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
        }
        # Try browser cookies for auth (suppress warnings during probing)
        import logging
        _yt_logger = logging.getLogger('yt-dlp')
        _prev = _yt_logger.level
        _yt_logger.setLevel(logging.CRITICAL)
        for browser in ('firefox', 'chrome', 'edge'):
            try:
                test_opts = {**ydl_opts, 'cookiesfrombrowser': (browser,)}
                with YoutubeDL(test_opts) as ydl:
                    list(ydl.cookiejar)
                ydl_opts['cookiesfrombrowser'] = (browser,)
                break
            except Exception:
                continue
        _yt_logger.setLevel(_prev)
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}",
                download=False,
            )
            return info.get('title', f"Video_{video_id}")
    except Exception:
        return f"Video_{video_id}"


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name)[:100]


LANG_NAMES = {
    "en": "English", "hi": "Hindi", "ur": "Urdu", "ar": "Arabic",
    "bn": "Bengali", "pa": "Punjabi", "ta": "Tamil", "te": "Telugu",
    "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada", "ml": "Malayalam",
    "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese",
    "ru": "Russian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
    "tr": "Turkish", "it": "Italian", "nl": "Dutch", "pl": "Polish",
    "id": "Indonesian", "th": "Thai", "vi": "Vietnamese", "fa": "Persian",
}


def lang_name(code):
    return LANG_NAMES.get(code, code)
