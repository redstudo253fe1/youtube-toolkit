"""Groq Whisper API engine — cloud transcription with chunking for large files."""
import os
import re
import time
import json
import tempfile
import subprocess
from pathlib import Path

# Groq free tier limits
GROQ_MAX_FILE_MB = 25
GROQ_CHUNK_DURATION_SEC = 600  # 10 min chunks
GROQ_OVERLAP_SEC = 5


def _get_ffmpeg():
    """Find ffmpeg binary."""
    for name in ('ffmpeg', 'ffmpeg.exe'):
        for d in os.environ.get('PATH', '').split(os.pathsep):
            p = Path(d) / name
            if p.exists():
                return str(p)
    # Check bundled location
    base = Path(getattr(__import__('sys'), '_MEIPASS', '.'))
    for p in [base / 'ffmpeg.exe', base / 'ffmpeg']:
        if p.exists():
            return str(p)
    # Check ffmpeg-downloader location
    ffdl_path = Path.home() / 'AppData' / 'Local' / 'ffmpegio' / 'ffmpeg-downloader' / 'ffmpeg' / 'bin' / 'ffmpeg.exe'
    if ffdl_path.exists():
        return str(ffdl_path)
    return 'ffmpeg'


def _get_ffmpeg_dir():
    """Find directory containing ffmpeg binary."""
    ffmpeg = _get_ffmpeg()
    if ffmpeg != 'ffmpeg':
        return str(Path(ffmpeg).parent)
    return None


def _preprocess_audio(input_path, ffmpeg='ffmpeg'):
    """Convert to 16kHz mono FLAC (optimal for Whisper, small file size)."""
    tmp = tempfile.NamedTemporaryFile(suffix='.flac', delete=False)
    tmp.close()
    subprocess.run([
        ffmpeg, '-hide_banner', '-loglevel', 'error',
        '-i', str(input_path),
        '-ar', '16000', '-ac', '1', '-c:a', 'flac',
        '-y', tmp.name
    ], check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return tmp.name


def _split_audio(audio_path, chunk_sec, overlap_sec, ffmpeg='ffmpeg'):
    """Split audio into chunks using ffmpeg. Returns list of (tmp_path, offset_sec)."""
    # Get duration
    result = subprocess.run([
        ffmpeg, '-hide_banner', '-i', audio_path,
    ], capture_output=True, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    dur_match = re.search(r'Duration:\s*(\d+):(\d+):(\d+)\.(\d+)', result.stderr)
    if not dur_match:
        raise RuntimeError("Could not detect audio duration")
    h, m, s, _ = [int(x) for x in dur_match.groups()]
    total_sec = h * 3600 + m * 60 + s

    step = chunk_sec - overlap_sec
    chunks = []
    pos = 0
    idx = 0
    while pos < total_sec:
        tmp = tempfile.NamedTemporaryFile(suffix=f'_chunk{idx}.flac', delete=False)
        tmp.close()
        end = min(pos + chunk_sec, total_sec)
        subprocess.run([
            ffmpeg, '-hide_banner', '-loglevel', 'error',
            '-ss', str(pos), '-t', str(end - pos),
            '-i', audio_path,
            '-ar', '16000', '-ac', '1', '-c:a', 'flac',
            '-y', tmp.name
        ], check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        chunks.append((tmp.name, pos))
        pos += step
        idx += 1

    return chunks, total_sec


def _merge_overlap_text(prev_text, curr_text, overlap_words=15):
    """Remove overlapping text between consecutive chunks."""
    if not prev_text or not curr_text:
        return curr_text
    prev_words = prev_text.split()
    curr_words = curr_text.split()
    best = 0
    search = min(len(prev_words), len(curr_words), overlap_words * 3)
    for length in range(1, search + 1):
        if prev_words[-length:] == curr_words[:length]:
            best = length
    if best > 0:
        return ' '.join(curr_words[best:])
    return curr_text


def download_youtube_audio_for_groq(url, on_status=None):
    """Download YouTube audio optimized for Groq (small file)."""
    import yt_dlp
    tmp_dir = Path(tempfile.mkdtemp(prefix='groq_'))

    if on_status:
        on_status("Downloading audio from YouTube...")

    ydl_opts = {
        'format': 'worstaudio/worst',
        'outtmpl': str(tmp_dir / 'audio.%(ext)s'),
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3',
                            'preferredquality': '64'}],
        'quiet': True, 'no_warnings': True,
    }
    ffmpeg_dir = _get_ffmpeg_dir()
    if ffmpeg_dir:
        ydl_opts['ffmpeg_location'] = ffmpeg_dir

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)

    audio_path = None
    for ext in ['mp3', 'wav', 'webm', 'opus', 'm4a', 'flac']:
        p = tmp_dir / f'audio.{ext}'
        if p.exists():
            audio_path = str(p)
            break

    if not audio_path:
        raise FileNotFoundError("Audio download failed")

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    if on_status:
        on_status(f"Audio: {duration // 60}m{duration % 60}s | {size_mb:.1f}MB")

    return audio_path, title, duration


def transcribe_with_groq(audio_path, api_key, model='whisper-large-v3',
                         language=None, on_status=None, on_segment=None):
    """Transcribe audio using Groq API. Auto-chunks if file > 25MB.

    Args:
        audio_path: Path to audio file
        api_key: Groq API key
        model: 'whisper-large-v3' or 'whisper-large-v3-turbo'
        language: ISO-639-1 code or None for auto-detect
        on_status: callback(msg)
        on_segment: callback(segment_dict)

    Returns:
        (segments_list, detected_language, stats_dict)
    """
    from groq import Groq

    client = Groq(api_key=api_key)
    ffmpeg = _get_ffmpeg()
    start_time = time.time()

    file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)

    if on_status:
        on_status(f"File size: {file_size_mb:.1f}MB | Model: {model}")

    all_segments = []
    detected_lang = language or 'unknown'
    total_duration = 0

    if file_size_mb < GROQ_MAX_FILE_MB:
        # ── Direct transcription (under 25MB) ─────────────────
        if on_status:
            on_status("Sending to Groq API (direct)...")

        kwargs = {
            'model': model,
            'response_format': 'verbose_json',
            'temperature': 0.0,
            'timestamp_granularities': ['segment'],
        }
        if language:
            kwargs['language'] = language

        with open(audio_path, 'rb') as f:
            ext = Path(audio_path).suffix.lstrip('.')
            mime = {'mp3': 'audio/mpeg', 'wav': 'audio/wav', 'flac': 'audio/flac',
                    'm4a': 'audio/mp4', 'ogg': 'audio/ogg', 'webm': 'audio/webm'
                    }.get(ext, 'audio/mpeg')
            result = client.audio.transcriptions.create(
                file=(Path(audio_path).name, f, mime),
                **kwargs
            )

        detected_lang = getattr(result, 'language', language or 'unknown')
        total_duration = getattr(result, 'duration', 0) or 0

        if hasattr(result, 'segments') and result.segments:
            for seg in result.segments:
                s = {'start': seg['start'], 'end': seg['end'],
                     'text': seg['text'].strip(), 'language': detected_lang}
                all_segments.append(s)
                if on_segment:
                    on_segment(s)
        elif hasattr(result, 'text') and result.text:
            s = {'start': 0, 'end': total_duration, 'text': result.text.strip(),
                 'language': detected_lang}
            all_segments.append(s)
            if on_segment:
                on_segment(s)

    else:
        # ── Chunked transcription (over 25MB) ─────────────────
        if on_status:
            on_status(f"File too large ({file_size_mb:.0f}MB). Preprocessing & chunking...")

        processed = _preprocess_audio(audio_path, ffmpeg)
        proc_size = os.path.getsize(processed) / (1024 * 1024)

        if on_status:
            on_status(f"Compressed to {proc_size:.1f}MB (FLAC 16kHz mono)")

        if proc_size < GROQ_MAX_FILE_MB:
            # Compression was enough
            if on_status:
                on_status("Under 25MB after compression. Sending to Groq...")
            kwargs = {
                'model': model,
                'response_format': 'verbose_json',
                'temperature': 0.0,
                'timestamp_granularities': ['segment'],
            }
            if language:
                kwargs['language'] = language

            with open(processed, 'rb') as f:
                result = client.audio.transcriptions.create(
                    file=('audio.flac', f, 'audio/flac'), **kwargs)

            detected_lang = getattr(result, 'language', language or 'unknown')
            total_duration = getattr(result, 'duration', 0) or 0
            if hasattr(result, 'segments') and result.segments:
                for seg in result.segments:
                    s = {'start': seg['start'], 'end': seg['end'],
                         'text': seg['text'].strip(), 'language': detected_lang}
                    all_segments.append(s)
                    if on_segment:
                        on_segment(s)

            os.unlink(processed)
        else:
            # Need to split into chunks
            chunks, total_sec = _split_audio(processed, GROQ_CHUNK_DURATION_SEC,
                                             GROQ_OVERLAP_SEC, ffmpeg)
            total_duration = total_sec
            os.unlink(processed)

            if on_status:
                on_status(f"Split into {len(chunks)} chunks ({GROQ_CHUNK_DURATION_SEC // 60}min each)")

            prev_text = ''
            for i, (chunk_path, offset_sec) in enumerate(chunks):
                chunk_size = os.path.getsize(chunk_path) / (1024 * 1024)
                if on_status:
                    on_status(f"Chunk {i + 1}/{len(chunks)} ({chunk_size:.1f}MB, offset {offset_sec}s)...")

                kwargs = {
                    'model': model,
                    'response_format': 'verbose_json',
                    'temperature': 0.0,
                    'timestamp_granularities': ['segment'],
                }
                if language:
                    kwargs['language'] = language

                # Retry with backoff for rate limits
                for attempt in range(5):
                    try:
                        with open(chunk_path, 'rb') as f:
                            result = client.audio.transcriptions.create(
                                file=('chunk.flac', f, 'audio/flac'), **kwargs)
                        break
                    except Exception as e:
                        if 'rate' in str(e).lower() or '429' in str(e):
                            wait = 30 * (attempt + 1)
                            if on_status:
                                on_status(f"Rate limited. Waiting {wait}s...")
                            time.sleep(wait)
                        else:
                            raise

                if i == 0:
                    detected_lang = getattr(result, 'language', language or 'unknown')

                chunk_text = getattr(result, 'text', '') or ''

                if hasattr(result, 'segments') and result.segments:
                    # Remove overlap with previous chunk
                    cleaned_text = _merge_overlap_text(prev_text, chunk_text)
                    skip_chars = len(chunk_text) - len(cleaned_text)

                    char_count = 0
                    for seg in result.segments:
                        seg_text = seg['text'].strip()
                        char_count += len(seg_text) + 1
                        if char_count <= skip_chars:
                            continue  # skip overlapping segment
                        s = {'start': seg['start'] + offset_sec,
                             'end': seg['end'] + offset_sec,
                             'text': seg_text, 'language': detected_lang}
                        all_segments.append(s)
                        if on_segment:
                            on_segment(s)

                prev_text = chunk_text
                os.unlink(chunk_path)

                # Small delay between chunks to avoid rate limiting
                if i < len(chunks) - 1:
                    time.sleep(1)

    elapsed = time.time() - start_time
    speed = total_duration / elapsed if elapsed > 0 else 0
    word_count = sum(len(s['text'].split()) for s in all_segments)

    stats = {
        'segments': len(all_segments),
        'words': word_count,
        'duration': total_duration,
        'speed': speed,
        'elapsed': elapsed,
        'model': model,
        'language': detected_lang,
    }

    if on_status:
        on_status(f"Done! {len(all_segments)} segments, {word_count:,} words in {elapsed:.1f}s ({speed:.1f}x realtime)")

    return all_segments, detected_lang, stats


def save_api_key(key):
    """Save Groq API key locally."""
    config_dir = Path.home() / '.youtube_toolkit'
    config_dir.mkdir(exist_ok=True)
    (config_dir / 'groq_key.txt').write_text(key.strip())


def load_api_key():
    """Load saved Groq API key."""
    p = Path.home() / '.youtube_toolkit' / 'groq_key.txt'
    if p.exists():
        key = p.read_text().strip()
        if key.startswith('gsk_'):
            return key
    return ''
