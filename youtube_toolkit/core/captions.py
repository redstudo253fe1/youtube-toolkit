"""YouTube caption/subtitle downloader engine with callback support."""
import json
from datetime import datetime
from pathlib import Path

from youtube_transcript_api import YouTubeTranscriptApi

from .utils import extract_video_id, get_video_title, format_timestamp, sanitize_filename


def list_available_languages(video_id):
    """List all available caption languages. Returns (manual, auto) lists."""
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        manual, auto = [], []
        for t in transcript_list:
            info = {'code': t.language_code, 'name': t.language, 'auto': t.is_generated}
            if t.is_generated:
                auto.append(info)
            else:
                manual.append(info)
        return manual, auto
    except Exception as e:
        return [], []


def download_transcript(video_id, lang=None):
    """Download transcript. Returns list of segment dicts or None."""
    try:
        api = YouTubeTranscriptApi()
        if lang:
            result = api.fetch(video_id, languages=[lang])
        else:
            try:
                result = api.fetch(video_id, languages=['en'])
            except Exception:
                try:
                    result = api.fetch(video_id, languages=['en-US', 'en-GB'])
                except Exception:
                    result = api.fetch(video_id)
        segments = []
        for snippet in result.snippets:
            segments.append({
                'text': snippet.text,
                'start': snippet.start,
                'duration': snippet.duration,
            })
        return segments
    except Exception:
        return None


def merge_segments_into_paragraphs(segments, max_gap=2.0, max_para_duration=30.0):
    """Merge small caption segments into natural paragraphs."""
    if not segments:
        return []
    paragraphs = []
    current_texts = []
    current_start = segments[0]['start']
    current_end = segments[0]['start'] + segments[0].get('duration', 0)

    for seg in segments:
        seg_start = seg['start']
        seg_end = seg_start + seg.get('duration', 0)
        gap = seg_start - current_end
        if gap > max_gap or (seg_start - current_start) > max_para_duration:
            if current_texts:
                paragraphs.append({'start': current_start, 'end': current_end, 'text': ' '.join(current_texts)})
            current_texts = [seg['text']]
            current_start = seg_start
            current_end = seg_end
        else:
            current_texts.append(seg['text'])
            current_end = seg_end
    if current_texts:
        paragraphs.append({'start': current_start, 'end': current_end, 'text': ' '.join(current_texts)})
    return paragraphs


# ── Export Functions ──

def save_clean_txt(paragraphs, video_id, title, lang_info, output_dir):
    safe = sanitize_filename(title) if title else video_id
    filepath = Path(output_dir) / f"transcript_{safe}_clean.txt"
    full_text = '\n\n'.join(p['text'] for p in paragraphs)
    word_count = len(full_text.split())
    duration_sec = paragraphs[-1]['end'] if paragraphs else 0
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("YOUTUBE VIDEO TRANSCRIPT - CLEAN TEXT FOR AI ANALYSIS\n")
        f.write("=" * 70 + "\n")
        f.write(f"Video Title  : {title}\nVideo ID     : {video_id}\n")
        f.write(f"Video URL    : https://www.youtube.com/watch?v={video_id}\n")
        f.write(f"Language     : {lang_info}\nWord Count   : {word_count:,}\n")
        f.write(f"Duration     : {format_timestamp(duration_sec)}\n")
        f.write(f"Export Date  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")
        f.write("INSTRUCTIONS FOR AI CHATBOT:\n")
        f.write("This is the complete transcript of a YouTube video.\n")
        f.write("You can ask the chatbot to: Summarize, list key points, extract topics,\n")
        f.write("answer questions, create notes, translate, or find specific quotes.\n")
        f.write("=" * 70 + "\nFULL TRANSCRIPT BELOW\n" + "=" * 70 + "\n\n")
        f.write(full_text)
        f.write("\n\n" + "=" * 70 + "\n[END OF TRANSCRIPT]\n")
    return str(filepath)


def save_timestamped_txt(paragraphs, video_id, title, lang_info, output_dir):
    safe = sanitize_filename(title) if title else video_id
    filepath = Path(output_dir) / f"transcript_{safe}_timestamped.txt"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\nYOUTUBE VIDEO TRANSCRIPT - WITH TIMESTAMPS\n" + "=" * 70 + "\n")
        f.write(f"Video Title  : {title}\nLanguage     : {lang_info}\n")
        f.write(f"Export Date  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n" + "=" * 70 + "\n\n")
        for p in paragraphs:
            f.write(f"[{format_timestamp(p['start'])}]\n{p['text']}\n\n")
        f.write("=" * 70 + "\n[END OF TRANSCRIPT]\n")
    return str(filepath)


def save_md(paragraphs, video_id, title, lang_info, output_dir):
    safe = sanitize_filename(title) if title else video_id
    filepath = Path(output_dir) / f"transcript_{safe}.md"
    full_text = ' '.join(p['text'] for p in paragraphs)
    word_count = len(full_text.split())
    duration_sec = paragraphs[-1]['end'] if paragraphs else 0
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"# Video Transcript: {title}\n\n")
        f.write(f"- **Video URL:** https://www.youtube.com/watch?v={video_id}\n")
        f.write(f"- **Language:** {lang_info}\n- **Word Count:** {word_count:,}\n")
        f.write(f"- **Duration:** {format_timestamp(duration_sec)}\n")
        f.write(f"- **Export Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n## Full Transcript\n\n")
        for p in paragraphs:
            f.write(f"**[{format_timestamp(p['start'])}]** {p['text']}\n\n")
        f.write("---\n\n*[End of Transcript]*\n")
    return str(filepath)


def save_srt(segments, video_id, output_dir, title=None):
    safe = sanitize_filename(title) if title else video_id
    filepath = Path(output_dir) / f"transcript_{safe}.srt"
    from .utils import format_srt_time
    with open(filepath, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = seg['start']
            end = start + seg.get('duration', 0)
            f.write(f"{i}\n{format_srt_time(start)} --> {format_srt_time(end)}\n{seg['text']}\n\n")
    return str(filepath)


def save_json_transcript(paragraphs, segments, video_id, title, lang_info, output_dir):
    safe = sanitize_filename(title) if title else video_id
    filepath = Path(output_dir) / f"transcript_{safe}.json"
    data = {
        "video_id": video_id, "video_url": f"https://www.youtube.com/watch?v={video_id}",
        "title": title, "language": lang_info,
        "export_date": datetime.now().isoformat(),
        "paragraphs": paragraphs, "raw_segments": segments,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(filepath)
