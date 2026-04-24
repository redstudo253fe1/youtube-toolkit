"""AI caption generator tab — Local Whisper + Groq Cloud."""
import os
import time
import threading
from pathlib import Path

import customtkinter as ctk

from . import theme
from .widgets import URLEntry, OutputFormatSelector, ActionButton
from ..core.utils import extract_video_id, is_youtube_url, format_timestamp, sanitize_filename
from ..core.gpu import detect_device
from ..core.groq_engine import load_api_key, save_api_key

_WHISPER_AVAILABLE = True
try:
    from ..core.whisper_engine import (
        download_youtube_audio, transcribe_audio, merge_into_paragraphs,
        save_clean_txt, save_timestamped_txt, save_md, save_srt,
    )
except ImportError:
    _WHISPER_AVAILABLE = False


class WhisperTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._running = False
        self._seg_count = 0
        self._word_count = 0
        self._start_time = 0
        self._build_ui()

    def _build_ui(self):
        # ── Top strip: title + device ──────────────────────────
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(8, 4))

        ctk.CTkLabel(top, text="AI Caption Generator",
                     font=("Segoe UI", 16, "bold"),
                     text_color=theme.TEXT_PRIMARY).pack(side="left")

        _, _, desc = detect_device()
        color = theme.BG_SUCCESS if "GPU" in desc and "too old" not in desc else theme.BG_WARNING
        ctk.CTkLabel(top, text=f"  {desc}", font=theme.FONT_SMALL,
                     text_color=color).pack(side="left", padx=6)

        # ── Mode toggle: Cloud (Groq) / Local (Whisper) ────────
        mode_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=10)
        mode_frame.pack(fill="x", padx=16, pady=(0, 6))
        mf = ctk.CTkFrame(mode_frame, fg_color="transparent")
        mf.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(mf, text="Mode:", font=theme.FONT_SMALL,
                     text_color=theme.TEXT_SECONDARY).pack(side="left")

        self.mode_var = ctk.StringVar(value="cloud")
        ctk.CTkRadioButton(mf, text="Cloud (Groq) — instant, best accuracy",
                           variable=self.mode_var, value="cloud",
                           font=theme.FONT_SMALL, fg_color="#10B981",
                           text_color=theme.TEXT_PRIMARY,
                           command=self._on_mode_change).pack(side="left", padx=(8, 16))
        ctk.CTkRadioButton(mf, text="Local (Whisper) — offline, slower",
                           variable=self.mode_var, value="local",
                           font=theme.FONT_SMALL, fg_color=theme.BG_BUTTON,
                           text_color=theme.TEXT_PRIMARY,
                           command=self._on_mode_change).pack(side="left")

        # ── Groq API key row ───────────────────────────────────
        self._api_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=10)
        self._api_frame.pack(fill="x", padx=16, pady=(0, 6))
        af = ctk.CTkFrame(self._api_frame, fg_color="transparent")
        af.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(af, text="Groq API Key:", font=theme.FONT_SMALL,
                     text_color=theme.TEXT_SECONDARY).pack(side="left")
        self.api_entry = ctk.CTkEntry(af, width=320, height=30, font=theme.FONT_SMALL,
                                      fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                                      placeholder_text="gsk_... (free at console.groq.com)")
        self.api_entry.pack(side="left", padx=(6, 8), fill="x", expand=True)

        # Load saved key
        saved_key = load_api_key()
        if saved_key:
            self.api_entry.insert(0, saved_key)

        ctk.CTkButton(af, text="Save Key", font=theme.FONT_SMALL, width=80, height=28,
                      fg_color="#10B981", hover_color="#059669", corner_radius=6,
                      command=self._save_key).pack(side="left")

        ctk.CTkLabel(af, text="  FREE: 2hrs audio/hour, 8hrs/day",
                     font=("Segoe UI", 9), text_color=theme.TEXT_DIM).pack(side="left", padx=6)

        # ── URL + Browse row ───────────────────────────────────
        input_row = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=10)
        input_row.pack(fill="x", padx=16, pady=(0, 6))
        ir = ctk.CTkFrame(input_row, fg_color="transparent")
        ir.pack(fill="x", padx=12, pady=8)

        ctk.CTkLabel(ir, text="URL:", font=theme.FONT_SMALL,
                     text_color=theme.TEXT_SECONDARY, width=32).pack(side="left")
        self.url_entry = URLEntry(ir)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(4, 8))

        ctk.CTkLabel(ir, text="OR", font=theme.FONT_SMALL,
                     text_color=theme.TEXT_DIM).pack(side="left", padx=4)

        self._file_label = ctk.CTkLabel(ir, text="no file selected",
                                        font=theme.FONT_SMALL, text_color=theme.TEXT_DIM,
                                        width=140, anchor="w")
        self._file_label.pack(side="left", padx=(4, 4))

        ctk.CTkButton(ir, text="Browse File", font=theme.FONT_SMALL, width=100, height=36,
                      fg_color=theme.BG_ACCENT, hover_color=theme.BG_BUTTON,
                      corner_radius=8, command=self._browse_file).pack(side="left")

        self._local_file = None

        # ── Settings row ───────────────────────────────────────
        settings = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=10)
        settings.pack(fill="x", padx=16, pady=(0, 6))
        sr = ctk.CTkFrame(settings, fg_color="transparent")
        sr.pack(fill="x", padx=12, pady=8)

        # Cloud model selector
        ctk.CTkLabel(sr, text="Model:", font=theme.FONT_SMALL,
                     text_color=theme.TEXT_SECONDARY).pack(side="left")

        self.cloud_model_menu = ctk.CTkOptionMenu(
            sr,
            values=["whisper-large-v3  (best accuracy, 99+ languages)",
                    "whisper-large-v3-turbo  (faster, good accuracy)"],
            font=theme.FONT_SMALL, fg_color=theme.BG_INPUT,
            button_color="#10B981", text_color=theme.TEXT_PRIMARY,
            dropdown_fg_color=theme.BG_CARD, width=340,
        )
        self.cloud_model_menu.set("whisper-large-v3  (best accuracy, 99+ languages)")
        self.cloud_model_menu.pack(side="left", padx=(6, 12))

        # Local model selector (hidden by default)
        self.local_model_menu = ctk.CTkOptionMenu(
            sr,
            values=["tiny  (fastest, basic)",
                    "base  (fast, OK)",
                    "small  (recommended)",
                    "medium  (great accuracy)",
                    "large-v3  (best accuracy)"],
            font=theme.FONT_SMALL, fg_color=theme.BG_INPUT,
            button_color=theme.BG_ACCENT, text_color=theme.TEXT_PRIMARY,
            dropdown_fg_color=theme.BG_CARD, width=230,
        )
        self.local_model_menu.set("small  (recommended)")

        self.multi_var = ctk.BooleanVar(value=True)
        self.multi_check = ctk.CTkCheckBox(sr, text="Multi-language",
                        variable=self.multi_var, font=theme.FONT_SMALL,
                        fg_color=theme.BG_BUTTON, hover_color=theme.BG_BUTTON_HOVER,
                        text_color=theme.TEXT_PRIMARY)
        self.multi_check.pack(side="left", padx=(0, 12))

        self.formats = OutputFormatSelector(sr, formats=["Clean TXT", "Timestamped", "MD", "SRT"])
        self.formats.pack(side="left")

        # ── Action button ──────────────────────────────────────
        self.start_btn = ActionButton(self, text="Generate Captions", command=self._start)
        self.start_btn.pack(fill="x", padx=16, pady=(0, 6))

        # ── Progress + stats row ───────────────────────────────
        ps_row = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=10)
        ps_row.pack(fill="x", padx=16, pady=(0, 6))
        ps_inner = ctk.CTkFrame(ps_row, fg_color="transparent")
        ps_inner.pack(fill="x", padx=12, pady=8)

        prog_col = ctk.CTkFrame(ps_inner, fg_color="transparent")
        prog_col.pack(side="left", fill="x", expand=True, padx=(0, 16))

        self._status_lbl = ctk.CTkLabel(prog_col, text="Ready",
                                        font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY,
                                        anchor="w")
        self._status_lbl.pack(fill="x")
        self._prog_bar = ctk.CTkProgressBar(prog_col, fg_color=theme.PROGRESS_BG,
                                            progress_color=theme.PROGRESS_FG,
                                            height=8, corner_radius=4)
        self._prog_bar.pack(fill="x", pady=(2, 0))
        self._prog_bar.set(0)

        stats_col = ctk.CTkFrame(ps_inner, fg_color="transparent")
        stats_col.pack(side="right")

        def stat(parent, label):
            f = ctk.CTkFrame(parent, fg_color=theme.BG_INPUT, corner_radius=6)
            f.pack(side="left", padx=3)
            ctk.CTkLabel(f, text=label, font=("Segoe UI", 8),
                         text_color=theme.TEXT_DIM).pack(padx=8, pady=(3, 0))
            val = ctk.CTkLabel(f, text="—", font=("Segoe UI", 12, "bold"),
                               text_color=theme.TEXT_PRIMARY)
            val.pack(padx=8, pady=(0, 3))
            return val

        self._s_segs  = stat(stats_col, "SEGMENTS")
        self._s_words = stat(stats_col, "WORDS")
        self._s_dur   = stat(stats_col, "AUDIO")
        self._s_speed = stat(stats_col, "SPEED")

        # ── Live log ───────────────────────────────────────────
        log_card = ctk.CTkFrame(self, fg_color=theme.LOG_BG, corner_radius=10)
        log_card.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        log_hdr = ctk.CTkFrame(log_card, fg_color=theme.BG_CARD, corner_radius=6, height=28)
        log_hdr.pack(fill="x", padx=4, pady=(4, 0))
        log_hdr.pack_propagate(False)
        ctk.CTkLabel(log_hdr, text="  Live Transcript", font=("Segoe UI", 10, "bold"),
                     text_color=theme.TEXT_SECONDARY, anchor="w").pack(side="left", fill="x", expand=True)
        ctk.CTkButton(log_hdr, text="Clear", font=("Segoe UI", 9), width=46, height=20,
                      fg_color=theme.BG_INPUT, hover_color=theme.BG_ACCENT,
                      text_color=theme.TEXT_SECONDARY, corner_radius=4,
                      command=self._clear_log).pack(side="right", padx=4)

        self._log = ctk.CTkTextbox(log_card, font=("Segoe UI", 11),
                                   fg_color=theme.LOG_BG, text_color=theme.LOG_FG,
                                   corner_radius=6, wrap="word", state="disabled")
        self._log.pack(fill="both", expand=True, padx=4, pady=4)

        # Initial mode setup
        self._on_mode_change()

    # ── Mode switching ────────────────────────────────────────

    def _on_mode_change(self):
        is_cloud = self.mode_var.get() == "cloud"
        if is_cloud:
            self._api_frame.pack(fill="x", padx=16, pady=(0, 6), after=self._api_frame.master.winfo_children()[1])
            self.cloud_model_menu.pack(side="left", padx=(6, 12))
            self.local_model_menu.pack_forget()
            self.start_btn.configure(text="Generate Captions (Cloud)")
        else:
            self._api_frame.pack_forget()
            self.local_model_menu.pack(side="left", padx=(6, 12))
            self.cloud_model_menu.pack_forget()
            self.start_btn.configure(text="Generate Captions (Local)")

    # ── API key ───────────────────────────────────────────────

    def _save_key(self):
        key = self.api_entry.get().strip()
        if key.startswith('gsk_'):
            save_api_key(key)
            self._log_write("API key saved!")
        else:
            self._log_write("Invalid key. Get free key at console.groq.com/keys")

    # ── File browse ───────────────────────────────────────────

    def _browse_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Video/Audio File",
            filetypes=[("Media files", "*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.flac *.m4a *.ogg"),
                       ("All files", "*.*")],
        )
        if path:
            self._local_file = path
            name = Path(path).name
            self._file_label.configure(text=name[:30] + "..." if len(name) > 30 else name,
                                       text_color=theme.TEXT_PRIMARY)

    # ── Helpers ───────────────────────────────────────────────

    def _log_write(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")

    def _set_status(self, text):
        self._status_lbl.configure(text=text)

    def _set_progress(self, v):
        self._prog_bar.set(max(0, min(1, v)))

    def _update_stats(self, segs, words, dur, speed):
        self._s_segs.configure(text=str(segs))
        self._s_words.configure(text=f"{words:,}")
        self._s_dur.configure(text=format_timestamp(dur))
        color = theme.BG_SUCCESS if speed >= 1.0 else theme.BG_WARNING
        self._s_speed.configure(text=f"{speed:.1f}x", text_color=color)

    def _reset_stats(self):
        for w in (self._s_segs, self._s_words, self._s_dur, self._s_speed):
            w.configure(text="—", text_color=theme.TEXT_PRIMARY)

    # ── Start ─────────────────────────────────────────────────

    def _start(self):
        if self._running:
            return

        url = self.url_entry.get()
        local_file = self._local_file

        if not url and not local_file:
            self._log_write("Enter a YouTube URL or select a local file.")
            return

        is_cloud = self.mode_var.get() == "cloud"

        if is_cloud:
            api_key = self.api_entry.get().strip()
            if not api_key or not api_key.startswith('gsk_'):
                self._log_write("Enter a valid Groq API key (starts with gsk_)")
                self._log_write("Get FREE key at: console.groq.com/keys")
                return
            self._start_cloud(url, local_file, api_key)
        else:
            self._start_local(url, local_file)

    # ── Cloud (Groq) mode ─────────────────────────────────────

    def _start_cloud(self, url, local_file, api_key):
        from ..core.groq_engine import (
            download_youtube_audio_for_groq, transcribe_with_groq,
        )

        self._running = True
        self.start_btn.configure(state="disabled", text="Processing (Cloud)...")
        self._clear_log()
        self._reset_stats()
        self._set_progress(0)

        model_raw = self.cloud_model_menu.get().split("(")[0].strip().split()[0]
        multi_lang = self.multi_var.get()
        is_yt = bool(url) and is_youtube_url(url)

        self._seg_count = 0
        self._word_count = 0
        self._start_time = time.time()

        def run():
            try:
                audio_path = None
                title = "Unknown"

                # ── Download / load audio ──
                if is_yt:
                    video_id = extract_video_id(url)
                    yt_url = f"https://www.youtube.com/watch?v={video_id}"

                    def dl_status(msg):
                        self.after(0, lambda m=msg: self._log_write(f"  {m}"))
                        self.after(0, lambda m=msg: self._set_status(m))

                    audio_path, title, duration = download_youtube_audio_for_groq(
                        yt_url, on_status=dl_status)
                    self.after(0, lambda: self._set_progress(0.1))

                elif local_file:
                    if not os.path.exists(local_file):
                        self.after(0, lambda: self._log_write(f"ERROR: File not found: {local_file}"))
                        return
                    audio_path = local_file
                    title = Path(local_file).stem
                    self.after(0, lambda: self._log_write(f"  File: {local_file}"))
                else:
                    return

                safe = sanitize_filename(title)
                output_dir = Path(f"./output_{safe}")
                filename_base = f"whisper_{safe}"
                output_dir.mkdir(exist_ok=True)

                lang_hint = None if multi_lang else 'en'

                self.after(0, lambda: self._log_write(f"  Title : {title}"))
                self.after(0, lambda: self._log_write(f"  Model : {model_raw} (Groq Cloud)"))
                self.after(0, lambda: self._log_write(f"  Multi-lang: {multi_lang}"))
                self.after(0, lambda: self._log_write("─" * 55))

                def on_status(msg):
                    self.after(0, lambda m=msg: self._log_write(f"  {m}"))
                    self.after(0, lambda m=msg: self._set_status(m))

                def on_segment(seg):
                    self._seg_count += 1
                    self._word_count += len(seg['text'].split())
                    elapsed = time.time() - self._start_time
                    speed = seg['end'] / elapsed if elapsed > 0 else 0
                    ts = format_timestamp(seg['start'])
                    sc, wc, dur, sp = self._seg_count, self._word_count, seg['end'], speed
                    self.after(0, lambda t=ts, tx=seg['text'][:100]: self._log_write(f"[{t}]  {tx}"))
                    self.after(0, lambda: self._update_stats(sc, wc, dur, sp))

                self.after(0, lambda: self._set_progress(0.15))

                segments, detected_lang, stats = transcribe_with_groq(
                    audio_path, api_key, model=model_raw, language=lang_hint,
                    on_status=on_status, on_segment=on_segment,
                )

                if not segments:
                    self.after(0, lambda: self._log_write("ERROR: No speech detected."))
                    return

                # Merge into paragraphs for export
                paragraphs = []
                texts, p_start, p_end = [], segments[0]['start'], segments[0]['end']
                for seg in segments:
                    gap = seg['start'] - p_end
                    if gap > 2.0 or (seg['start'] - p_start) > 30.0:
                        if texts:
                            paragraphs.append({'start': p_start, 'end': p_end, 'text': ' '.join(texts)})
                        texts, p_start, p_end = [seg['text']], seg['start'], seg['end']
                    else:
                        texts.append(seg['text'])
                        p_end = seg['end']
                if texts:
                    paragraphs.append({'start': p_start, 'end': p_end, 'text': ' '.join(texts)})

                self.after(0, lambda: self._set_progress(0.95))
                self.after(0, lambda: self._log_write("─" * 55))

                # Save files
                selected = self.formats.get_selected()
                saved = []

                from ..core.whisper_engine import save_clean_txt, save_timestamped_txt, save_md, save_srt

                if "Clean TXT" in selected:
                    saved.append(save_clean_txt(paragraphs, title, detected_lang, output_dir, filename_base))
                if "Timestamped" in selected:
                    saved.append(save_timestamped_txt(paragraphs, title, detected_lang, output_dir, filename_base))
                if "MD" in selected:
                    saved.append(save_md(paragraphs, title, detected_lang, output_dir, filename_base))
                if "SRT" in selected:
                    saved.append(save_srt(segments, output_dir, filename_base))

                # Cleanup YT audio
                if is_yt and audio_path:
                    try:
                        os.remove(audio_path)
                    except Exception:
                        pass

                self.after(0, lambda: self._set_progress(1))
                self.after(0, lambda: self._set_status("Done!"))
                self.after(0, lambda: self._log_write(f"\n  Saved {len(saved)} file(s):"))
                self.after(0, lambda: self._log_write(f"  Folder: {output_dir.resolve()}"))
                for s in saved:
                    self.after(0, lambda p=s: self._log_write(f"    {Path(p).name}"))

                # Show speed stats
                self.after(0, lambda: self._log_write(f"\n  Speed: {stats['speed']:.1f}x realtime | Time: {stats['elapsed']:.1f}s"))

            except Exception as e:
                self.after(0, lambda: self._log_write(f"\n  ERROR: {e}"))
                self.after(0, lambda: self._set_status("Error"))
            finally:
                self.after(0, self._done)

        threading.Thread(target=run, daemon=True).start()

    # ── Local (Whisper) mode ──────────────────────────────────

    def _start_local(self, url, local_file):
        if not _WHISPER_AVAILABLE:
            self._log_write("Whisper not available in Light version.")
            self._log_write("Use Cloud (Groq) mode instead — it's free and faster!")
            return

        self._running = True
        self.start_btn.configure(state="disabled", text="Processing (Local)...")
        self._clear_log()
        self._reset_stats()
        self._set_progress(0)
        self._set_status("Starting...")

        model_size = self.local_model_menu.get().split("(")[0].strip().split()[0]
        multi_lang = self.multi_var.get()
        is_yt = bool(url) and is_youtube_url(url)

        self._seg_count = 0
        self._word_count = 0
        self._start_time = time.time()

        def run():
            try:
                audio_path = None
                title = "Unknown"

                if is_yt:
                    video_id = extract_video_id(url)

                    def dl_status(msg):
                        self.after(0, lambda m=msg: self._log_write(f"  {m}"))
                        self.after(0, lambda m=msg: self._set_status(m))

                    import tempfile
                    temp_dir = Path(tempfile.mkdtemp(prefix="yt_"))
                    audio_path, title = download_youtube_audio(
                        f"https://www.youtube.com/watch?v={video_id}",
                        temp_dir, on_status=dl_status,
                    )
                    if not audio_path:
                        self.after(0, lambda: self._log_write("ERROR: Failed to download audio."))
                        return
                    self.after(0, lambda: self._set_progress(0.1))

                elif local_file:
                    if not os.path.exists(local_file):
                        self.after(0, lambda: self._log_write(f"ERROR: File not found: {local_file}"))
                        return
                    audio_path = local_file
                    title = Path(local_file).stem
                    self.after(0, lambda: self._log_write(f"  File: {local_file}"))
                else:
                    return

                safe = sanitize_filename(title)
                output_dir = Path(f"./output_{safe}")
                filename_base = f"whisper_{safe}"
                output_dir.mkdir(exist_ok=True)

                self.after(0, lambda: self._log_write(f"  Title : {title}"))
                self.after(0, lambda: self._log_write(f"  Model : {model_size} (Local) | Multi-lang: {multi_lang}"))
                self.after(0, lambda: self._log_write("─" * 55))

                def on_status(msg):
                    self.after(0, lambda m=msg: self._log_write(f"  {m}"))
                    self.after(0, lambda m=msg: self._set_status(m))

                def on_segment(seg):
                    self._seg_count += 1
                    self._word_count += len(seg['text'].split())
                    elapsed = time.time() - self._start_time
                    speed = seg['end'] / elapsed if elapsed > 0 else 0
                    ts = format_timestamp(seg['start'])
                    sc, wc, dur, sp = self._seg_count, self._word_count, seg['end'], speed
                    self.after(0, lambda t=ts, tx=seg['text'][:100]: self._log_write(f"[{t}]  {tx}"))
                    self.after(0, lambda: self._update_stats(sc, wc, dur, sp))

                def on_progress(pct):
                    self.after(0, lambda p=pct: self._set_progress(0.1 + 0.82 * p / 100))

                segments, detected_lang = transcribe_audio(
                    audio_path, model_size=model_size, multi_lang=multi_lang,
                    on_status=on_status, on_segment=on_segment, on_progress=on_progress,
                )

                if not segments:
                    self.after(0, lambda: self._log_write("ERROR: No speech detected."))
                    return

                paragraphs = merge_into_paragraphs(segments)
                self.after(0, lambda: self._set_progress(0.95))
                self.after(0, lambda: self._log_write("─" * 55))

                selected = self.formats.get_selected()
                saved = []
                if "Clean TXT" in selected:
                    saved.append(save_clean_txt(paragraphs, title, detected_lang, output_dir, filename_base))
                if "Timestamped" in selected:
                    saved.append(save_timestamped_txt(paragraphs, title, detected_lang, output_dir, filename_base))
                if "MD" in selected:
                    saved.append(save_md(paragraphs, title, detected_lang, output_dir, filename_base))
                if "SRT" in selected:
                    saved.append(save_srt(segments, output_dir, filename_base))

                if is_yt:
                    try:
                        os.remove(audio_path)
                    except Exception:
                        pass

                self.after(0, lambda: self._set_progress(1))
                self.after(0, lambda: self._set_status("Done!"))
                self.after(0, lambda: self._log_write(f"\n  Saved {len(saved)} file(s):"))
                self.after(0, lambda: self._log_write(f"  Folder: {output_dir.resolve()}"))
                for s in saved:
                    self.after(0, lambda p=s: self._log_write(f"    {Path(p).name}"))

            except Exception as e:
                self.after(0, lambda: self._log_write(f"\n  ERROR: {e}"))
                self.after(0, lambda: self._set_status("Error"))
            finally:
                self.after(0, self._done)

        threading.Thread(target=run, daemon=True).start()

    def _done(self):
        self._running = False
        is_cloud = self.mode_var.get() == "cloud"
        self.start_btn.configure(state="normal",
                                 text="Generate Captions (Cloud)" if is_cloud else "Generate Captions (Local)")
