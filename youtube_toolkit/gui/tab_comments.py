"""Comments downloader tab."""
import threading
from pathlib import Path

import customtkinter as ctk

from . import theme
from .widgets import URLEntry, OutputFormatSelector, ProgressSection, LogConsole, ActionButton
from ..core.utils import extract_video_id, sanitize_filename
from ..core.comments import (
    download_comments, build_structured_comments,
    save_comments_txt, save_comments_md, save_comments_pdf, save_comments_json,
    SORT_BY_RECENT, SORT_BY_POPULAR,
)


class CommentsTab(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._build_ui()
        self._running = False

    def _build_ui(self):
        # Title
        ctk.CTkLabel(self, text="YouTube Comment Downloader",
                      font=theme.FONT_TITLE, text_color=theme.TEXT_PRIMARY).pack(pady=(10, 2))
        ctk.CTkLabel(self, text="Download ALL comments with full details - FREE, no API key",
                      font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY).pack(pady=(0, 10))

        # URL input
        self.url_entry = URLEntry(self)
        self.url_entry.pack(fill="x", padx=20, pady=5)

        # Options row
        opts = ctk.CTkFrame(self, fg_color="transparent")
        opts.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(opts, text="Sort:", font=theme.FONT_SMALL,
                      text_color=theme.TEXT_SECONDARY).pack(side="left")
        self.sort_var = ctk.StringVar(value="recent")
        ctk.CTkRadioButton(opts, text="Recent", variable=self.sort_var, value="recent",
                            font=theme.FONT_SMALL, fg_color=theme.BG_BUTTON,
                            text_color=theme.TEXT_PRIMARY).pack(side="left", padx=8)
        ctk.CTkRadioButton(opts, text="Popular", variable=self.sort_var, value="popular",
                            font=theme.FONT_SMALL, fg_color=theme.BG_BUTTON,
                            text_color=theme.TEXT_PRIMARY).pack(side="left", padx=8)

        ctk.CTkLabel(opts, text="  Max:", font=theme.FONT_SMALL,
                      text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(16, 0))
        self.max_entry = ctk.CTkEntry(opts, width=80, height=30, font=theme.FONT_SMALL,
                                       fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
                                       placeholder_text="0=All")
        self.max_entry.pack(side="left", padx=4)

        # Format selector
        self.formats = OutputFormatSelector(self, formats=["TXT", "MD", "PDF", "JSON"])
        self.formats.pack(fill="x", padx=20, pady=5)

        # Start button
        self.start_btn = ActionButton(self, text="Download Comments", command=self._start)
        self.start_btn.set_text("Download Comments")
        self.start_btn.pack(padx=20, pady=8, fill="x")

        # Progress
        self.progress = ProgressSection(self)
        self.progress.pack(fill="x", padx=20, pady=2)

        # Log
        self.log = LogConsole(self, height=200, title="Comments Log")
        self.log.pack(fill="both", expand=True, padx=20, pady=(5, 10))

    def _start(self):
        if self._running:
            return
        url = self.url_entry.get()
        if not url:
            self.log.log("Please enter a YouTube URL or video ID.")
            return

        self._running = True
        self.start_btn.configure(state="disabled", text="Downloading...")
        self.log.clear()
        self.progress.reset()

        sort = SORT_BY_POPULAR if self.sort_var.get() == "popular" else SORT_BY_RECENT
        max_c = 0
        try:
            max_c = int(self.max_entry.get())
        except (ValueError, TypeError):
            max_c = 0

        video_id = extract_video_id(url)
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        self.log.log(f"Video ID: {video_id}")
        self.log.log(f"Sort: {'Popular' if sort == SORT_BY_POPULAR else 'Recent'}")
        self.log.log(f"Max comments: {'Unlimited' if max_c == 0 else max_c}")
        self.log.log("Downloading comments (powered by yt-dlp)...")

        def run():
            try:
                def on_progress(stats):
                    msg = f"Top: {stats.get('top',0)} | Replies: {stats.get('replies',0)}"
                    total = stats.get('total', 0)
                    self.after(0, lambda m=msg: self.progress.set_status(m))
                    if max_c > 0:
                        self.after(0, lambda: self.progress.set_progress(min(1, total / max_c)))

                raw, title, total_count = download_comments(
                    video_url, sort_by=sort, max_comments=max_c,
                    on_progress=on_progress,
                )

                self.after(0, lambda: self.log.log(f"Title: {title}"))

                comments = build_structured_comments(raw)

                top = sum(1 for c in comments if not c['is_reply'])
                reps = sum(1 for c in comments if c['is_reply'])
                self.after(0, lambda: self.log.log(f"\nTotal: {len(comments)} (Top-level: {top}, Replies: {reps})"))
                self.after(0, lambda: self.progress.set_progress(1))

                # Export — folder and files named by video title
                safe_title = sanitize_filename(title)
                output_dir = Path(f"./output_{safe_title}")
                output_dir.mkdir(exist_ok=True)
                selected = self.formats.get_selected()
                saved = []

                if "TXT" in selected:
                    saved.append(save_comments_txt(comments, video_id, output_dir, title=title))
                if "MD" in selected:
                    saved.append(save_comments_md(comments, video_id, output_dir, title=title))
                if "PDF" in selected:
                    saved.append(save_comments_pdf(comments, video_id, output_dir, title=title))
                if "JSON" in selected:
                    saved.append(save_comments_json(comments, video_id, output_dir, title=title))

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
        self.start_btn.configure(state="normal", text="Download Comments")
