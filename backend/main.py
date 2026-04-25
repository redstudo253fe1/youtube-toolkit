"""ytbro — FastAPI backend for Hugging Face Spaces."""
import json
import os
import queue
import sys
import threading
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

sys.path.insert(0, str(Path(__file__).parent.parent))

app = FastAPI(title="ytbro API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def stream(task_fn, *args):
    q: queue.Queue = queue.Queue()

    def run():
        try:
            task_fn(q, *args)
        except Exception as exc:
            q.put({"type": "error", "message": str(exc)})
        finally:
            q.put(None)

    threading.Thread(target=run, daemon=True).start()

    def generate():
        while True:
            item = q.get()
            if item is None:
                yield sse({"type": "done"})
                break
            yield sse(item)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Health ────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "ytbro-api"}


# ── Video info ────────────────────────────────────────────────
@app.post("/api/video/info")
async def video_info(body: dict):
    from youtube_toolkit.core.utils import extract_video_id, get_video_title
    url = body.get("url", "")
    video_id = extract_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL"}
    try:
        title = get_video_title(video_id)
    except Exception:
        title = video_id
    return {
        "video_id": video_id,
        "title": title,
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }


# ── Comments ──────────────────────────────────────────────────
@app.post("/api/comments")
async def download_comments(body: dict):
    url = body.get("url", "")
    sort_mode = body.get("sort", "recent")
    max_comments = int(body.get("max_comments", 0))

    def task(q, url, sort_mode, max_comments):
        from youtube_toolkit.core.comments import (
            SORT_BY_POPULAR, SORT_BY_RECENT,
            build_structured_comments, download_comments as dl,
        )
        from youtube_toolkit.core.utils import sanitize_filename
        from youtube_toolkit.web.share import upload_content

        video_url = (url if ("youtube.com" in url or "youtu.be" in url)
                     else f"https://www.youtube.com/watch?v={url}")
        sort = SORT_BY_POPULAR if sort_mode == "popular" else SORT_BY_RECENT

        def on_progress(stats):
            q.put({"type": "progress",
                   "message": f"Downloaded {stats.get('total', 0):,} comments…",
                   "count": stats.get("total", 0)})

        q.put({"type": "progress", "message": "Starting comment download…"})
        raw, title, _ = dl(video_url, sort_by=sort, max_comments=max_comments,
                           on_progress=on_progress)
        comments = build_structured_comments(raw)
        top = sum(1 for c in comments if not c["is_reply"])
        reps = len(comments) - top

        q.put({"type": "progress", "message": "Building markdown…"})
        md = [
            f"# YouTube Comments: {title}", "",
            f"- **Video:** {video_url}",
            f"- **Total:** {len(comments):,} | Top: {top:,} | Replies: {reps:,}",
            f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "", "---", "",
        ]
        for i, c in enumerate(comments, 1):
            if c["is_reply"]:
                md += [f"#### ↳ Reply #{i} by {c['author']}",
                       f"*{c['time']} · Likes: {c['likes']}*",
                       f"> {c['text']}", ""]
            else:
                md += [f"### Comment #{i}",
                       f"**{c['author']}** · {c['time']} · 👍 {c['likes']}",
                       f"> {c['text']}", ""]
        md_content = "\n".join(md)

        q.put({"type": "progress", "message": "Generating AI link…"})
        ai_url = upload_content(md_content, f"comments_{sanitize_filename(title)}.md")

        q.put({
            "type": "result",
            "title": title,
            "content": md_content,
            "ai_url": ai_url or "",
            "stats": {"total": len(comments), "top": top, "replies": reps},
            "filename": f"comments_{sanitize_filename(title)}.md",
        })

    return stream(task, url, sort_mode, max_comments)


# ── Caption languages ─────────────────────────────────────────
@app.post("/api/captions/languages")
async def captions_languages(body: dict):
    from youtube_toolkit.core.captions import list_available_languages
    from youtube_toolkit.core.utils import extract_video_id
    url = body.get("url", "")
    video_id = extract_video_id(url) or url
    try:
        manual, auto = list_available_languages(video_id)
        return {"manual": manual, "auto": auto}
    except Exception as exc:
        return {"error": str(exc), "manual": [], "auto": []}


# ── Captions download ─────────────────────────────────────────
@app.post("/api/captions/download")
async def download_captions(body: dict):
    url = body.get("url", "")
    lang_code = body.get("lang_code", "en")
    lang_name = body.get("lang_name", lang_code)

    def task(q, url, lang_code, lang_name):
        from youtube_toolkit.core.captions import (
            download_transcript, merge_segments_into_paragraphs,
        )
        from youtube_toolkit.core.utils import (
            extract_video_id, format_timestamp, get_video_title, sanitize_filename,
        )
        from youtube_toolkit.web.share import upload_content

        video_id = extract_video_id(url) or url
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        q.put({"type": "progress", "message": "Fetching captions…"})
        title = get_video_title(video_id)
        segments = download_transcript(video_id, lang_code)
        if not segments:
            q.put({"type": "error", "message": "No captions found for this video."})
            return

        paragraphs = merge_segments_into_paragraphs(segments)
        full_text = " ".join(p["text"] for p in paragraphs)
        word_count = len(full_text.split())
        duration = paragraphs[-1]["end"] if paragraphs else 0

        q.put({"type": "progress",
               "message": f"Processing {word_count:,} words · {format_timestamp(duration)}…"})

        md = [
            f"# Transcript: {title}", "",
            f"- **Video:** {video_url}",
            f"- **Language:** {lang_name} ({lang_code})",
            f"- **Words:** {word_count:,}",
            f"- **Duration:** {format_timestamp(duration)}",
            f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "", "---", "",
        ]
        for p in paragraphs:
            md.append(f"**[{format_timestamp(p['start'])}]** {p['text']}")
            md.append("")
        md_content = "\n".join(md)

        q.put({"type": "progress", "message": "Generating AI link…"})
        ai_url = upload_content(md_content, f"transcript_{sanitize_filename(title)}.md")

        q.put({
            "type": "result",
            "title": title,
            "content": md_content,
            "ai_url": ai_url or "",
            "stats": {"words": word_count, "duration": format_timestamp(duration),
                      "paragraphs": len(paragraphs)},
            "filename": f"transcript_{sanitize_filename(title)}.md",
        })

    return stream(task, url, lang_code, lang_name)


# ── AI Transcription ──────────────────────────────────────────
@app.post("/api/transcribe")
async def transcribe(body: dict):
    url = body.get("url", "")
    api_key = body.get("api_key", "")
    model = body.get("model", "whisper-large-v3")
    language = body.get("language") or None

    def task(q, url, api_key, model, language):
        from youtube_toolkit.core.groq_engine import (
            download_youtube_audio_for_groq, transcribe_with_groq,
        )
        from youtube_toolkit.core.utils import format_timestamp, sanitize_filename
        from youtube_toolkit.web.share import upload_content

        video_url = (url if ("youtube.com" in url or "youtu.be" in url)
                     else f"https://www.youtube.com/watch?v={url}")

        def on_status(msg):
            q.put({"type": "progress", "message": msg})

        def on_segment(seg):
            q.put({"type": "progress",
                   "message": f"[{format_timestamp(seg['start'])}] {seg['text'][:80]}"})

        audio_path, title, duration = download_youtube_audio_for_groq(
            video_url, on_status=on_status)
        segments, detected_lang, stats = transcribe_with_groq(
            audio_path, api_key, model=model, language=language,
            on_status=on_status, on_segment=on_segment)

        try:
            os.remove(audio_path)
        except Exception:
            pass

        paragraphs, texts, p_start, p_end = [], [], segments[0]["start"], segments[0]["end"]
        for seg in segments:
            if seg["start"] - p_end > 2.0 or (seg["start"] - p_start) > 30.0:
                if texts:
                    paragraphs.append({"start": p_start, "end": p_end,
                                       "text": " ".join(texts)})
                texts, p_start, p_end = [seg["text"]], seg["start"], seg["end"]
            else:
                texts.append(seg["text"])
                p_end = seg["end"]
        if texts:
            paragraphs.append({"start": p_start, "end": p_end, "text": " ".join(texts)})

        word_count = sum(len(s["text"].split()) for s in segments)
        dur = paragraphs[-1]["end"] if paragraphs else 0

        md = [
            f"# AI Transcript: {title}", "",
            f"- **Video:** {video_url}",
            f"- **Language:** {detected_lang}",
            f"- **Words:** {word_count:,}",
            f"- **Model:** {model} (Groq Cloud)",
            f"- **Speed:** {stats.get('speed', 0):.1f}x realtime",
            f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "", "---", "",
        ]
        for p in paragraphs:
            md.append(f"**[{format_timestamp(p['start'])}]** {p['text']}")
            md.append("")
        md_content = "\n".join(md)

        q.put({"type": "progress", "message": "Generating AI link…"})
        ai_url = upload_content(md_content, f"transcript_{sanitize_filename(title)}.md")

        q.put({
            "type": "result",
            "title": title,
            "content": md_content,
            "ai_url": ai_url or "",
            "stats": {"words": word_count, "language": detected_lang,
                      "speed": stats.get("speed", 0)},
            "filename": f"transcript_{sanitize_filename(title)}.md",
        })

    return stream(task, url, api_key, model, language)
