"""YouTube Toolkit — Streamlit Web App."""
import queue
import sys
import threading
import time
from datetime import datetime

import streamlit as st

# ── Page config ───────────────────────────────────────────────
st.set_page_config(
    page_title="YouTube Toolkit",
    page_icon="▶️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
  /* Background */
  .stApp, [data-testid="stAppViewContainer"] { background-color: #0f0f1a !important; }
  [data-testid="stHeader"] { background-color: #0f0f1a !important; }

  /* Inputs */
  input, textarea { background-color: #0f3460 !important; color: #fff !important; }

  /* Buttons */
  .stButton > button {
    background-color: #e94560 !important; color: #fff !important;
    border: none !important; border-radius: 8px !important;
    font-weight: bold !important; width: 100% !important;
    font-size: 1rem !important; padding: 0.65rem 0 !important;
  }
  .stButton > button:hover { background-color: #ff6b6b !important; }

  /* Download buttons */
  .stDownloadButton > button {
    background-color: #0f3460 !important; color: #fff !important;
    border: 1px solid #e94560 !important; border-radius: 8px !important;
    font-weight: 600 !important;
  }
  .stDownloadButton > button:hover { background-color: #533483 !important; }

  /* Radio / checkbox labels */
  .stRadio label, .stCheckbox label { color: #e2e8f0 !important; }

  /* Selectbox / multiselect */
  [data-baseweb="select"] > div { background-color: #0f3460 !important; color: #fff !important; }

  /* Code block (for the AI link) */
  .stCode, code { background-color: #0f3460 !important; color: #00b894 !important; font-size: 0.95rem !important; }

  /* Success / info / error */
  .stSuccess { background-color: #003d2e !important; }
  .stInfo    { background-color: #0f3460 !important; }

  /* Divider */
  hr { border-color: #1e3a5f !important; }

  /* AI link box */
  .ai-box {
    background: #0a2540; border: 2px solid #00b894;
    border-radius: 10px; padding: 1.1rem 1.2rem; margin-top: 0.8rem;
  }
  .ai-box-title { color: #00b894; font-weight: 700; font-size: 1rem; margin-bottom: 0.4rem; }
  .ai-box-url   { color: #fff; font-family: monospace; font-size: 0.9rem; word-break: break-all; }
  .ai-box-hint  { color: #b2bec3; font-size: 0.82rem; margin-top: 0.5rem; }
</style>
""", unsafe_allow_html=True)


# ── Helper: AI link box ───────────────────────────────────────
def show_ai_link(url: str):
    st.markdown(f"""
    <div class="ai-box">
      <div class="ai-box-title">🤖 AI-Readable Link — paste this in ChatGPT / Perplexity / Claude</div>
      <div class="ai-box-url">{url}</div>
      <div class="ai-box-hint">💡 Open ChatGPT or Perplexity → paste the link → ask: "Summarize this"</div>
    </div>
    """, unsafe_allow_html=True)
    st.code(url, language=None)


# ── Helper: live log polling ──────────────────────────────────
def poll_log(log_q: queue.Queue, placeholder, logs: list, thread: threading.Thread):
    """Drain log queue into placeholder while thread is alive."""
    while thread.is_alive() or not log_q.empty():
        changed = False
        while not log_q.empty():
            logs.append(log_q.get_nowait())
            changed = True
        if changed:
            placeholder.code("\n".join(logs[-30:]), language=None)
        time.sleep(0.25)


# ── Header ────────────────────────────────────────────────────
st.markdown(
    "<h1 style='text-align:center;color:#e94560;margin-bottom:0'>▶ YouTube Toolkit</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center;color:#b2bec3;margin-top:0'>Comments · Captions · AI Transcription — 100% Free</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── URL input ─────────────────────────────────────────────────
with st.form("url_form"):
    url = st.text_input(
        "YouTube URL",
        placeholder="Paste YouTube URL or Video ID here...",
        label_visibility="collapsed",
    )
    st.form_submit_button("▶ Load Video", use_container_width=True)

if not url:
    st.markdown(
        "<p style='text-align:center;color:#636e72;margin-top:2rem'>"
        "Paste any YouTube URL above to get started</p>",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Validate URL ──────────────────────────────────────────────
from youtube_toolkit.core.utils import extract_video_id, is_youtube_url, format_timestamp, sanitize_filename

video_id = extract_video_id(url)
if not video_id or len(video_id) < 5:
    st.error("Invalid YouTube URL. Please paste a valid YouTube link.")
    st.stop()

st.markdown(
    f"<p style='color:#b2bec3;font-size:0.85rem;margin-bottom:0.5rem'>"
    f"Video ID: <code>{video_id}</code></p>",
    unsafe_allow_html=True,
)

# ── Action selector ───────────────────────────────────────────
action = st.radio(
    "What do you want to do?",
    ["💬 Download Comments", "📝 Download Captions", "🤖 AI Transcription (Groq)"],
    horizontal=True,
    label_visibility="collapsed",
)
st.divider()

VIDEO_URL = f"https://www.youtube.com/watch?v={video_id}"


# ══════════════════════════════════════════════════════════════
#  TAB 1 — COMMENTS
# ══════════════════════════════════════════════════════════════
if action == "💬 Download Comments":
    st.subheader("💬 Download Comments")
    st.caption("All comments + replies — free, no API key needed")

    col1, col2 = st.columns(2)
    with col1:
        sort_mode = st.selectbox("Sort By", ["Recent", "Popular"])
    with col2:
        max_comments = st.number_input("Max Comments (0 = All)", min_value=0, value=0, step=100)

    formats = st.multiselect(
        "Export Formats",
        ["TXT", "MD", "JSON"],
        default=["MD"],
    )

    if st.button("⬇️ Download Comments"):
        from youtube_toolkit.core.comments import (
            SORT_BY_POPULAR, SORT_BY_RECENT,
            build_structured_comments, download_comments,
            save_comments_json, save_comments_md, save_comments_txt,
        )
        from youtube_toolkit.web.share import upload_content

        sort = SORT_BY_POPULAR if sort_mode == "Popular" else SORT_BY_RECENT
        max_c = int(max_comments)

        log_q: queue.Queue = queue.Queue()
        result_q: queue.Queue = queue.Queue()

        def _run_comments():
            try:
                def on_progress(stats):
                    log_q.put(
                        f"Top: {stats.get('top', 0):,}  |  "
                        f"Replies: {stats.get('replies', 0):,}  |  "
                        f"Total: {stats.get('total', 0):,}"
                    )
                raw, title, _ = download_comments(
                    VIDEO_URL, sort_by=sort, max_comments=max_c, on_progress=on_progress,
                )
                comments = build_structured_comments(raw)
                result_q.put(("ok", comments, title))
            except Exception as exc:
                result_q.put(("error", str(exc), ""))

        t = threading.Thread(target=_run_comments, daemon=True)

        with st.status("Downloading comments…", expanded=True) as status:
            st.write(f"Video: `{VIDEO_URL}`")
            st.write(f"Sort: **{sort_mode}** | Max: **{'All' if max_c == 0 else max_c}**")
            log_placeholder = st.empty()
            logs: list = []
            t.start()
            poll_log(log_q, log_placeholder, logs, t)

            kind, data, title = result_q.get()

            if kind == "error":
                status.update(label=f"❌ Error: {data}", state="error")
                st.stop()

            comments: list = data
            top   = sum(1 for c in comments if not c["is_reply"])
            reps  = len(comments) - top
            status.update(
                label=f"✅ {len(comments):,} comments downloaded  ({top:,} top · {reps:,} replies)",
                state="complete",
            )

        st.success(f"**{len(comments):,}** comments  |  {top:,} top-level  |  {reps:,} replies")

        # ── Build markdown in memory ──────────────────────────
        md_lines = [
            f"# YouTube Comments: {title}",
            f"",
            f"- **Video:** {VIDEO_URL}",
            f"- **Total:** {len(comments):,} | Top: {top:,} | Replies: {reps:,}",
            f"- **Sorted:** {sort_mode}",
            f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
        ]
        for i, c in enumerate(comments, 1):
            if c["is_reply"]:
                md_lines += [
                    f"#### ↳ Reply #{i} by {c['author']}",
                    f"*{c['time']} · Likes: {c['likes']}*",
                    f"> {c['text']}",
                    "",
                ]
            else:
                md_lines += [
                    f"### Comment #{i}",
                    f"**{c['author']}** · {c['time']} · 👍 {c['likes']}",
                    f"> {c['text']}",
                    "",
                ]
        md_content = "\n".join(md_lines)

        # ── Upload for AI sharing ─────────────────────────────
        with st.spinner("Generating AI-readable link…"):
            ai_url = upload_content(md_content, f"comments_{sanitize_filename(title)}.md")

        if ai_url:
            show_ai_link(ai_url)
        else:
            st.warning("Could not generate AI link (paste service unreachable). Use download below.")

        # ── Download buttons ──────────────────────────────────
        st.subheader("Download Files")
        safe = sanitize_filename(title)

        if "MD" in formats:
            st.download_button(
                "📥 Download Markdown (.md)", md_content,
                file_name=f"comments_{safe}.md", mime="text/markdown",
            )
        if "TXT" in formats:
            txt_lines = [
                f"YOUTUBE COMMENTS — {title}",
                f"Video: {VIDEO_URL}",
                f"Total: {len(comments):,}  |  Date: {datetime.now().strftime('%Y-%m-%d')}",
                "=" * 60, "",
            ]
            for i, c in enumerate(comments, 1):
                pfx = "  REPLY" if c["is_reply"] else "COMMENT"
                txt_lines += [
                    f"{pfx} #{i} | {c['author']} | {c['time']} | Likes: {c['likes']}",
                    f"    {c['text']}", "",
                ]
            st.download_button(
                "📥 Download Text (.txt)", "\n".join(txt_lines),
                file_name=f"comments_{safe}.txt",
            )
        if "JSON" in formats:
            import json
            json_data = json.dumps(
                {"video_id": video_id, "title": title,
                 "total": len(comments), "date": datetime.now().isoformat(),
                 "comments": comments},
                ensure_ascii=False, indent=2,
            )
            st.download_button(
                "📥 Download JSON (.json)", json_data,
                file_name=f"comments_{safe}.json", mime="application/json",
            )


# ══════════════════════════════════════════════════════════════
#  TAB 2 — CAPTIONS
# ══════════════════════════════════════════════════════════════
elif action == "📝 Download Captions":
    st.subheader("📝 Download Captions")
    st.caption("Existing YouTube captions — manual & auto-generated")

    if st.button("🔍 Check Available Languages"):
        from youtube_toolkit.core.captions import list_available_languages
        with st.spinner("Checking languages…"):
            manual, auto = list_available_languages(video_id)
        langs, labels = [], []
        for lang in manual:
            langs.append(lang)
            labels.append(f"{lang['name']} ({lang['code']}) [manual]")
        for lang in auto:
            langs.append(lang)
            labels.append(f"{lang['name']} ({lang['code']}) [auto]")
        if labels:
            st.session_state["cap_langs"]  = langs
            st.session_state["cap_labels"] = labels
            st.success(f"Found **{len(labels)}** caption track(s)")
        else:
            st.error("No captions found for this video.")

    if "cap_labels" not in st.session_state:
        st.stop()

    selected_label = st.selectbox("Language", st.session_state["cap_labels"])
    formats = st.multiselect(
        "Export Formats",
        ["Clean TXT", "Timestamped TXT", "MD", "SRT"],
        default=["MD"],
    )

    if st.button("⬇️ Download Captions"):
        from youtube_toolkit.core.captions import (
            download_transcript, merge_segments_into_paragraphs,
        )
        from youtube_toolkit.core.utils import format_srt_time, get_video_title
        from youtube_toolkit.web.share import upload_content

        idx  = st.session_state["cap_labels"].index(selected_label)
        lang = st.session_state["cap_langs"][idx]

        with st.status("Downloading captions…", expanded=True) as status:
            st.write(f"Language: **{selected_label}**")

            title = get_video_title(video_id)
            st.write(f"Title: **{title}**")

            segments = download_transcript(video_id, lang["code"])
            if not segments:
                status.update(label="❌ Failed to download transcript", state="error")
                st.stop()

            paragraphs = merge_segments_into_paragraphs(segments)
            full_text  = " ".join(p["text"] for p in paragraphs)
            word_count = len(full_text.split())
            duration   = paragraphs[-1]["end"] if paragraphs else 0
            st.write(
                f"Paragraphs: **{len(paragraphs)}** | "
                f"Words: **{word_count:,}** | "
                f"Duration: **{format_timestamp(duration)}**"
            )

            # Build markdown
            md_lines = [
                f"# Transcript: {title}",
                "",
                f"- **Video:** {VIDEO_URL}",
                f"- **Language:** {selected_label}",
                f"- **Words:** {word_count:,}",
                f"- **Duration:** {format_timestamp(duration)}",
                f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "---",
                "",
            ]
            for p in paragraphs:
                md_lines.append(f"**[{format_timestamp(p['start'])}]** {p['text']}")
                md_lines.append("")
            md_content = "\n".join(md_lines)

            status.update(label="Uploading for AI sharing…", state="running")
            ai_url = upload_content(md_content, f"transcript_{sanitize_filename(title)}.md")
            status.update(
                label=f"✅ {word_count:,} words downloaded", state="complete",
            )

        st.success(f"**{len(paragraphs)}** paragraphs · **{word_count:,}** words · {format_timestamp(duration)}")

        if ai_url:
            show_ai_link(ai_url)
        else:
            st.warning("Could not generate AI link. Use download below.")

        safe = sanitize_filename(title)

        if "MD" in formats:
            st.download_button(
                "📥 Download Markdown (.md)", md_content,
                file_name=f"transcript_{safe}.md", mime="text/markdown",
            )
        if "Clean TXT" in formats:
            clean = "\n\n".join(p["text"] for p in paragraphs)
            st.download_button(
                "📥 Download Clean TXT", clean,
                file_name=f"transcript_{safe}_clean.txt",
            )
        if "Timestamped TXT" in formats:
            ts_lines = [f"[{format_timestamp(p['start'])}]\n{p['text']}\n" for p in paragraphs]
            st.download_button(
                "📥 Download Timestamped TXT", "\n".join(ts_lines),
                file_name=f"transcript_{safe}_timestamped.txt",
            )
        if "SRT" in formats:
            srt_lines = []
            for i, seg in enumerate(segments, 1):
                s = seg["start"]
                e = s + seg.get("duration", 0)
                srt_lines.append(
                    f"{i}\n{format_srt_time(s)} --> {format_srt_time(e)}\n{seg['text']}\n"
                )
            st.download_button(
                "📥 Download SRT (.srt)", "\n".join(srt_lines),
                file_name=f"transcript_{safe}.srt",
            )


# ══════════════════════════════════════════════════════════════
#  TAB 3 — AI TRANSCRIPTION (GROQ)
# ══════════════════════════════════════════════════════════════
elif action == "🤖 AI Transcription (Groq)":
    st.subheader("🤖 AI Transcription — Groq Cloud")
    st.caption("Free · Fast · 99+ languages · No GPU needed · 2 hrs audio/hour free")

    # ── API key ───────────────────────────────────────────────
    from youtube_toolkit.core.groq_engine import load_api_key, save_api_key
    if "groq_key" not in st.session_state:
        st.session_state["groq_key"] = load_api_key()
    api_key = st.text_input(
        "Groq API Key",
        value=st.session_state["groq_key"],
        type="password",
        placeholder="gsk_... (free at console.groq.com/keys)",
    )
    if api_key and api_key != st.session_state["groq_key"]:
        st.session_state["groq_key"] = api_key
        save_api_key(api_key)
    if not api_key:
        st.info("👆 Get a **free** Groq API key at [console.groq.com/keys](https://console.groq.com/keys)")

    # ── Settings ──────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        model_choice = st.selectbox("Model", [
            "whisper-large-v3  (best accuracy, 99+ langs)",
            "whisper-large-v3-turbo  (faster, great accuracy)",
        ])
        model_id = model_choice.split()[0]
    with col2:
        multi_lang = st.checkbox("Multi-language detection", value=True)

    formats = st.multiselect(
        "Export Formats",
        ["Clean TXT", "Timestamped TXT", "MD", "SRT"],
        default=["MD"],
    )

    if st.button("🎙️ Generate AI Transcript"):
        if not api_key or not api_key.strip().startswith("gsk_"):
            st.error("Enter a valid Groq API key (starts with `gsk_`)")
            st.stop()

        from youtube_toolkit.core.groq_engine import (
            download_youtube_audio_for_groq, transcribe_with_groq,
        )
        from youtube_toolkit.core.utils import format_srt_time
        from youtube_toolkit.web.share import upload_content
        import os

        log_q: queue.Queue = queue.Queue()
        result_q: queue.Queue = queue.Queue()

        def _run_groq():
            try:
                def on_status(msg):
                    log_q.put(f"  {msg}")

                def on_segment(seg):
                    ts = format_timestamp(seg["start"])
                    log_q.put(f"[{ts}]  {seg['text'][:90]}")

                audio_path, title, duration = download_youtube_audio_for_groq(
                    VIDEO_URL, on_status=on_status,
                )
                log_q.put(f"  Audio: {format_timestamp(duration)}")

                lang_hint = None if multi_lang else "en"
                segments, detected_lang, stats = transcribe_with_groq(
                    audio_path, api_key.strip(),
                    model=model_id, language=lang_hint,
                    on_status=on_status, on_segment=on_segment,
                )
                try:
                    os.remove(audio_path)
                except Exception:
                    pass
                result_q.put(("ok", segments, title, detected_lang, stats))
            except Exception as exc:
                result_q.put(("error", str(exc), "", "", {}))

        t = threading.Thread(target=_run_groq, daemon=True)

        with st.status("Transcribing with Groq…", expanded=True) as status:
            st.write(f"Model: **{model_id}** | Multi-lang: **{multi_lang}**")
            log_placeholder = st.empty()
            logs: list = []
            t.start()
            poll_log(log_q, log_placeholder, logs, t)

            kind, *rest = result_q.get()

            if kind == "error":
                status.update(label=f"❌ Error: {rest[0]}", state="error")
                st.stop()

            segments, title, detected_lang, stats = rest
            word_count = sum(len(s["text"].split()) for s in segments)
            speed      = stats.get("speed", 0)
            elapsed    = stats.get("elapsed", 0)
            status.update(
                label=(
                    f"✅ {word_count:,} words  |  {len(segments)} segments  |  "
                    f"{speed:.1f}x realtime  |  {elapsed:.0f}s"
                ),
                state="complete",
            )

        st.success(
            f"**{word_count:,}** words · **{len(segments)}** segments · "
            f"Language: **{detected_lang}** · Speed: **{speed:.1f}x**"
        )

        # ── Merge into paragraphs ─────────────────────────────
        paragraphs: list = []
        texts, p_start, p_end = [], segments[0]["start"], segments[0]["end"]
        for seg in segments:
            gap = seg["start"] - p_end
            if gap > 2.0 or (seg["start"] - p_start) > 30.0:
                if texts:
                    paragraphs.append({"start": p_start, "end": p_end, "text": " ".join(texts)})
                texts, p_start, p_end = [seg["text"]], seg["start"], seg["end"]
            else:
                texts.append(seg["text"])
                p_end = seg["end"]
        if texts:
            paragraphs.append({"start": p_start, "end": p_end, "text": " ".join(texts)})

        duration = paragraphs[-1]["end"] if paragraphs else 0

        # ── Build markdown ────────────────────────────────────
        md_lines = [
            f"# AI Transcript: {title}",
            "",
            f"- **Video:** {VIDEO_URL}",
            f"- **Language:** {detected_lang}",
            f"- **Words:** {word_count:,}",
            f"- **Duration:** {format_timestamp(duration)}",
            f"- **Model:** {model_id} (Groq Cloud)",
            f"- **Speed:** {speed:.1f}x realtime",
            f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
        ]
        for p in paragraphs:
            md_lines.append(f"**[{format_timestamp(p['start'])}]** {p['text']}")
            md_lines.append("")
        md_content = "\n".join(md_lines)

        # ── Upload for AI sharing ─────────────────────────────
        with st.spinner("Generating AI-readable link…"):
            ai_url = upload_content(md_content, f"transcript_{sanitize_filename(title)}.md")

        if ai_url:
            show_ai_link(ai_url)
        else:
            st.warning("Could not generate AI link. Use download below.")

        # ── Download buttons ──────────────────────────────────
        safe = sanitize_filename(title)

        if "MD" in formats:
            st.download_button(
                "📥 Download Markdown (.md)", md_content,
                file_name=f"transcript_{safe}.md", mime="text/markdown",
            )
        if "Clean TXT" in formats:
            clean = "\n\n".join(p["text"] for p in paragraphs)
            st.download_button(
                "📥 Download Clean TXT", clean,
                file_name=f"transcript_{safe}_clean.txt",
            )
        if "Timestamped TXT" in formats:
            ts_lines = [f"[{format_timestamp(p['start'])}]\n{p['text']}\n" for p in paragraphs]
            st.download_button(
                "📥 Download Timestamped TXT", "\n".join(ts_lines),
                file_name=f"transcript_{safe}_timestamped.txt",
            )
        if "SRT" in formats:
            srt_lines = []
            for i, seg in enumerate(segments, 1):
                srt_lines.append(
                    f"{i}\n"
                    f"{format_srt_time(seg['start'])} --> {format_srt_time(seg['end'])}\n"
                    f"{seg['text']}\n"
                )
            st.download_button(
                "📥 Download SRT (.srt)", "\n".join(srt_lines),
                file_name=f"transcript_{safe}.srt",
            )


# ── Footer ────────────────────────────────────────────────────
st.divider()
st.markdown(
    "<p style='text-align:center;color:#636e72;font-size:0.78rem'>"
    "YouTube Toolkit — Free & Open Source</p>",
    unsafe_allow_html=True,
)
