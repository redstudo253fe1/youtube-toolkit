"""Whisper-based AI caption generator engine with callback support."""
import os
import sys
import time
import json
import shutil
import zipfile
import urllib.request
from datetime import datetime
from pathlib import Path

from .utils import format_timestamp, format_srt_time, lang_name
from .gpu import detect_device


def _get_ffmpeg_dir():
    """Find or download ffmpeg+ffprobe. Returns directory path or None."""
    if shutil.which('ffmpeg') and shutil.which('ffprobe'):
        return None

    # Check local ffmpeg folder next to the running script/exe
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent.parent.parent
    local_dir = base / "ffmpeg_bin"
    ffmpeg_local = local_dir / "ffmpeg.exe"
    ffprobe_local = local_dir / "ffprobe.exe"

    if ffmpeg_local.exists() and ffprobe_local.exists():
        return str(local_dir)

    # Check ffmpeg-downloader (pip install ffmpeg-downloader) location
    ffdl_dir = Path.home() / 'AppData' / 'Local' / 'ffmpegio' / 'ffmpeg-downloader' / 'ffmpeg' / 'bin'
    if (ffdl_dir / 'ffmpeg.exe').exists() and (ffdl_dir / 'ffprobe.exe').exists():
        return str(ffdl_dir)

    # Download
    local_dir.mkdir(exist_ok=True)
    zip_url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = local_dir / "ffmpeg.zip"

    try:
        urllib.request.urlretrieve(zip_url, str(zip_path))
        with zipfile.ZipFile(str(zip_path), 'r') as zf:
            for name in zf.namelist():
                basename = Path(name).name.lower()
                if basename == 'ffmpeg.exe':
                    with zf.open(name) as src, open(str(ffmpeg_local), 'wb') as dst:
                        dst.write(src.read())
                elif basename == 'ffprobe.exe':
                    with zf.open(name) as src, open(str(ffprobe_local), 'wb') as dst:
                        dst.write(src.read())
        zip_path.unlink()
        if ffmpeg_local.exists() and ffprobe_local.exists():
            return str(local_dir)
    except Exception:
        pass
    return None


def download_youtube_audio(video_url, output_dir, on_status=None):
    """Download audio from YouTube optimized for Whisper. Returns (audio_path, title) or (None, None)."""
    import yt_dlp

    audio_path = str(Path(output_dir) / "audio_temp.wav")
    ffmpeg_dir = _get_ffmpeg_dir()

    ydl_opts = {
        'format': 'worstaudio/worst',
        'outtmpl': str(Path(output_dir) / "audio_temp.%(ext)s"),
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
        'postprocessor_args': ['-ar', '16000', '-ac', '1'],
        'quiet': True, 'no_warnings': True,
    }
    if ffmpeg_dir:
        ydl_opts['ffmpeg_location'] = ffmpeg_dir

    if on_status:
        on_status("Downloading audio from YouTube...")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            title = info.get('title', 'Unknown')
            duration = info.get('duration', 0)

        for ext in ['wav', 'mp3', 'webm', 'opus', 'm4a']:
            p = Path(output_dir) / f"audio_temp.{ext}"
            if p.exists():
                audio_path = str(p)
                break

        size_mb = os.path.getsize(audio_path) / (1024 * 1024) if os.path.exists(audio_path) else 0
        if on_status:
            on_status(f"Audio downloaded: {format_timestamp(duration)} ({size_mb:.1f}MB)")
        return audio_path, title
    except Exception as e:
        if on_status:
            on_status(f"Error downloading: {e}")
        return None, None


def transcribe_audio(audio_path, model_size="small", multi_lang=False,
                     on_status=None, on_segment=None, on_progress=None):
    """
    Transcribe audio using faster-whisper.
    on_status(msg): status messages
    on_segment(seg_dict): called per segment
    on_progress(pct): 0-100 progress (approximate)
    Returns (segments, detected_lang).
    """
    from faster_whisper import WhisperModel

    device, compute_type, device_desc = detect_device()
    cpu_threads = os.cpu_count() or 4

    if on_status:
        on_status(f"Loading Whisper '{model_size}' model ({device_desc})...")

    model = WhisperModel(model_size, device=device, compute_type=compute_type, cpu_threads=cpu_threads)

    start_time = time.time()

    # Common transcription settings for best accuracy
    transcribe_opts = dict(
        beam_size=5,              # Higher beam = better accuracy (was 3)
        best_of=3,                # Sample multiple candidates, pick best
        word_timestamps=False,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=250,
            speech_pad_ms=200,
        ),
        condition_on_previous_text=True,  # Context-aware: uses prior text for better continuity
        no_speech_threshold=0.5,
    )

    if multi_lang:
        if on_status:
            on_status("Detecting primary language...")
        _, info = model.transcribe(audio_path, beam_size=1, vad_filter=True)
        primary_lang = info.language
        if on_status:
            on_status(f"Primary language: {lang_name(primary_lang)} ({info.language_probability:.0%})")
            on_status("Transcribing with multi-language detection...")

        segments_gen, info = model.transcribe(audio_path, **transcribe_opts)
    else:
        if on_status:
            on_status("Transcribing audio...")

        # First pass: detect language
        _, detect_info = model.transcribe(audio_path, beam_size=1, vad_filter=True)
        primary_lang = detect_info.language
        if on_status:
            on_status(f"Detected: {lang_name(primary_lang)} ({detect_info.language_probability:.0%})")

        # Second pass: transcribe with forced language for better accuracy
        segments_gen, info = model.transcribe(
            audio_path, language=primary_lang, **transcribe_opts,
        )

    segments = []
    detected_languages = set()
    total_text = ""

    # Get audio duration for progress estimation
    try:
        import wave
        with wave.open(audio_path, 'r') as wf:
            audio_duration = wf.getnframes() / wf.getframerate()
    except Exception:
        audio_duration = 0

    for seg in segments_gen:
        seg_lang = seg.language if hasattr(seg, 'language') and seg.language else primary_lang
        detected_languages.add(seg_lang)
        seg_dict = {
            'start': seg.start, 'end': seg.end,
            'text': seg.text.strip(), 'language': seg_lang,
        }
        segments.append(seg_dict)
        total_text += seg.text + " "

        if on_segment:
            on_segment(seg_dict)
        if on_progress and audio_duration > 0:
            pct = min(100, int(seg.end / audio_duration * 100))
            on_progress(pct)

    elapsed = time.time() - start_time
    actual_duration = segments[-1]['end'] if segments else 0
    speed_ratio = actual_duration / elapsed if elapsed > 0 else 0
    word_count = len(total_text.split())

    if len(detected_languages) > 1:
        detected_lang = ", ".join(lang_name(l) for l in sorted(detected_languages))
    else:
        detected_lang = lang_name(primary_lang)

    if on_status:
        on_status(f"Done! {elapsed:.1f}s for {format_timestamp(actual_duration)} ({speed_ratio:.1f}x realtime)")
        on_status(f"Segments: {len(segments)} | Words: {word_count:,} | Language: {detected_lang}")

    return segments, detected_lang


def merge_into_paragraphs(segments, max_gap=2.0, max_duration=30.0):
    if not segments:
        return []
    paragraphs, texts = [], []
    start = segments[0]['start']
    end = segments[0]['end']
    for seg in segments:
        gap = seg['start'] - end
        if gap > max_gap or (seg['start'] - start) > max_duration:
            if texts:
                paragraphs.append({'start': start, 'end': end, 'text': ' '.join(texts)})
            texts = [seg['text']]
            start = seg['start']
            end = seg['end']
        else:
            texts.append(seg['text'])
            end = seg['end']
    if texts:
        paragraphs.append({'start': start, 'end': end, 'text': ' '.join(texts)})
    return paragraphs


# ── Export Functions ──

def save_clean_txt(paragraphs, title, language, output_dir, filename_base):
    filepath = Path(output_dir) / f"{filename_base}_clean.txt"
    full_text = '\n\n'.join(p['text'] for p in paragraphs)
    word_count = len(full_text.split())
    duration = paragraphs[-1]['end'] if paragraphs else 0
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\nAI-GENERATED TRANSCRIPT (Whisper) - CLEAN TEXT FOR AI ANALYSIS\n" + "=" * 70 + "\n")
        f.write(f"Title        : {title}\nLanguage     : {language}\n")
        f.write(f"Word Count   : {word_count:,}\nDuration     : {format_timestamp(duration)}\n")
        f.write(f"Generated by : OpenAI Whisper (faster-whisper)\n")
        f.write(f"Export Date  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\nFULL TRANSCRIPT BELOW\n" + "=" * 70 + "\n\n")
        f.write(full_text)
        f.write("\n\n" + "=" * 70 + "\n[END OF TRANSCRIPT]\n")
    return str(filepath)


def save_timestamped_txt(paragraphs, title, language, output_dir, filename_base):
    filepath = Path(output_dir) / f"{filename_base}_timestamped.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"TRANSCRIPT: {title}\nLanguage: {language} | Generated by Whisper AI\n" + "=" * 70 + "\n\n")
        for p in paragraphs:
            f.write(f"[{format_timestamp(p['start'])}]\n{p['text']}\n\n")
        f.write("=" * 70 + "\n[END]\n")
    return str(filepath)


def save_md(paragraphs, title, language, output_dir, filename_base):
    filepath = Path(output_dir) / f"{filename_base}.md"
    full_text = ' '.join(p['text'] for p in paragraphs)
    word_count = len(full_text.split())
    duration = paragraphs[-1]['end'] if paragraphs else 0
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Transcript: {title}\n\n")
        f.write(f"- **Language:** {language}\n- **Words:** {word_count:,}\n")
        f.write(f"- **Duration:** {format_timestamp(duration)}\n")
        f.write(f"- **Generated by:** OpenAI Whisper AI\n\n---\n\n## Full Transcript\n\n")
        for p in paragraphs:
            f.write(f"**[{format_timestamp(p['start'])}]** {p['text']}\n\n")
        f.write("---\n*[End of Transcript]*\n")
    return str(filepath)


def save_srt(segments, output_dir, filename_base):
    filepath = Path(output_dir) / f"{filename_base}.srt"
    with open(filepath, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            f.write(f"{i}\n{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n{seg['text']}\n\n")
    return str(filepath)
