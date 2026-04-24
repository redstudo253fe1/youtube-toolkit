"""Captions/subtitle downloader tab."""
import threading
from pathlib import Path

import customtkinter as ctk

from . import theme
from .widgets import URLEntry, OutputFormatSelector, ProgressSection, LogConsole, ActionButton
from ..core.utils import extract_video_id, get_video_title, sanitize_filename
from ..core.captions import (
    list_available_languages, download_transcript, merge_segments_into_paragraphs,
    save_clean_txt, save_timestamped_txt, save_md, save_srt, save_json_transcript,
)


class CaptionsTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._build_ui()
        self._running = False
        self._langs = []

    def _build_ui(self):
        ctk.CTkLabel(self, text="YouTube Caption Downloader",
                      font=theme.FONT_TITLE, text_color=theme.TEXT_PRIMARY).pack(pady=(10, 2))
        ctk.CTkLabel(self, text="Download existing captions/subtitles - Manual & Auto-generated",
                      font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY).pack(pady=(0, 10))

        # URL + check button
        url_row = ctk.CTkFrame(self, fg_color="transparent")
        url_row.pack(fill="x", padx=20, pady=5)
        self.url_entry = URLEntry(url_row)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.check_btn = ctk.CTkButton(
            url_row, text="Check Languages", font=theme.FONT_SMALL, width=130, height=40,
            fg_color=theme.BG_ACCENT, hover_color=theme.BG_BUTTON, corner_radius=8,
            command=self._check_langs,
        )
        self.check_btn.pack(side="right")

        # Language selector
        lang_frame = ctk.CTkFrame(self, fg_color="transparent")
        lang_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkLabel(lang_frame, text="Language:", font=theme.FONT_SMALL,
                      text_color=theme.TEXT_SECONDARY).pack(side="left")
        self.lang_menu = ctk.CTkOptionMenu(
            lang_frame, values=["(check languages first)"], font=theme.FONT_SMALL,
            fg_color=theme.BG_INPUT, button_color=theme.BG_ACCENT,
            text_color=theme.TEXT_PRIMARY, width=300,
        )
        self.lang_menu.pack(side="left", padx=8)

        # Format selector
        self.formats = OutputFormatSelector(self, formats=["Clean TXT", "Timestamped", "MD", "SRT", "JSON"])
        self.formats.pack(fill="x", padx=20, pady=5)

        # Start button
        self.start_btn = ActionButton(self, text="Download Captions", command=self._start)
        self.start_btn.set_text("Download Captions")
        self.start_btn.pack(padx=20, pady=8, fill="x")

        # Progress
        self.progress = ProgressSection(self)
        self.progress.pack(fill="x", padx=20, pady=2)

        # Log
        self.log = LogConsole(self, height=200, title="Captions Log")
        self.log.pack(fill="both", expand=True, padx=20, pady=(5, 10))

    def _check_langs(self):
        url = self.url_entry.get()
        if not url:
            self.log.log("Please enter a YouTube URL first.")
            return
        self.log.clear()
        self.log.log("Checking available captions...")
        self.check_btn.configure(state="disabled")

        def run():
            video_id = extract_video_id(url)
            manual, auto = list_available_languages(video_id)
            all_langs = []
            labels = []
            for l in manual:
                all_langs.append(l)
                labels.append(f"{l['name']} ({l['code']}) [manual]")
            for l in auto:
                all_langs.append(l)
                labels.append(f"{l['name']} ({l['code']}) [auto]")

            self._langs = all_langs

            def update():
                if labels:
                    self.lang_menu.configure(values=labels)
                    self.lang_menu.set(labels[0])
                    self.log.log(f"Found {len(labels)} caption track(s):")
                    for lb in labels:
                        self.log.log(f"  {lb}")
                else:
                    self.lang_menu.configure(values=["No captions available"])
                    self.lang_menu.set("No captions available")
                    self.log.log("No captions found for this video.")
                self.check_btn.configure(state="normal")

            self.after(0, update)

        threading.Thread(target=run, daemon=True).start()

    def _start(self):
        if self._running or not self._langs:
            if not self._langs:
                self.log.log("Please check languages first.")
            return

        url = self.url_entry.get()
        if not url:
            self.log.log("Please enter a YouTube URL.")
            return

        self._running = True
        self.start_btn.configure(state="disabled", text="Downloading...")
        self.log.clear()
        self.progress.reset()

        # Find selected language
        selected_idx = 0
        current_val = self.lang_menu.get()
        for i, l in enumerate(self._langs):
            label = f"{l['name']} ({l['code']}) [{'auto' if l['auto'] else 'manual'}]"
            if label == current_val:
                selected_idx = i
                break
        lang = self._langs[selected_idx]
        lang_code = lang['code']
        lang_type = "auto-generated" if lang['auto'] else "manual"
        lang_info = f"{lang['name']} ({lang_code}) [{lang_type}]"

        video_id = extract_video_id(url)

        def run():
            try:
                title = get_video_title(video_id)
                safe_title = sanitize_filename(title)
                self.after(0, lambda: self.log.log(f"Title: {title}"))
                self.after(0, lambda: self.log.log(f"Language: {lang_info}"))
                self.after(0, lambda: self.progress.set_status("Downloading transcript..."))
                self.after(0, lambda: self.progress.set_progress(0.3))

                segments = download_transcript(video_id, lang_code)
                if not segments:
                    self.after(0, lambda: self.log.log("ERROR: Failed to download transcript."))
                    return

                paragraphs = merge_segments_into_paragraphs(segments)
                full_text = ' '.join(p['text'] for p in paragraphs)
                word_count = len(full_text.split())

                self.after(0, lambda: self.log.log(f"Segments: {len(segments)} | Words: {word_count:,}"))
                self.after(0, lambda: self.progress.set_progress(0.6))

                # Folder and files named by video title
                output_dir = Path(f"./output_{safe_title}")
                output_dir.mkdir(exist_ok=True)
                selected = self.formats.get_selected()
                saved = []

                if "Clean TXT" in selected:
                    saved.append(save_clean_txt(paragraphs, video_id, title, lang_info, output_dir))
                if "Timestamped" in selected:
                    saved.append(save_timestamped_txt(paragraphs, video_id, title, lang_info, output_dir))
                if "MD" in selected:
                    saved.append(save_md(paragraphs, video_id, title, lang_info, output_dir))
                if "SRT" in selected:
                    saved.append(save_srt(segments, video_id, output_dir, title=title))
                if "JSON" in selected:
                    saved.append(save_json_transcript(paragraphs, segments, video_id, title, lang_info, output_dir))

                self.after(0, lambda: self.progress.set_progress(1))
                self.after(0, lambda: self.log.log(f"\nSaved {len(saved)} files to: {output_dir.resolve()}"))
                for s in saved:
                    self.after(0, lambda p=s: self.log.log(f"  {Path(p).name}"))
                self.after(0, lambda: self.progress.set_status("Done!"))

            except Exception as e:
                self.after(0, lambda: self.log.log(f"\nERROR: {e}"))
                self.after(0, lambda: self.progress.set_status("Error"))
            finally:
                self.after(0, self._done)

        threading.Thread(target=run, daemon=True).start()

    def _done(self):
        self._running = False
        self.start_btn.configure(state="normal", text="Download Captions")
