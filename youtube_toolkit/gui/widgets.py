"""Shared GUI widgets for YouTube Toolkit."""
import tkinter as tk
import customtkinter as ctk
from . import theme


class LogConsole(ctk.CTkFrame):
    """Scrollable log output area with header, clear button, and monospace font."""

    def __init__(self, master, height=250, title="Output Log", **kwargs):
        super().__init__(master, fg_color=theme.LOG_BG, corner_radius=8, **kwargs)

        # Header bar with title and clear button
        header = ctk.CTkFrame(self, fg_color=theme.BG_CARD, height=30, corner_radius=6)
        header.pack(fill="x", padx=4, pady=(4, 0))
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text=f"  {title}", font=("Segoe UI", 10, "bold"),
            text_color=theme.TEXT_SECONDARY, anchor="w",
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            header, text="Clear", font=("Segoe UI", 9), width=50, height=22,
            fg_color=theme.BG_INPUT, hover_color=theme.BG_ACCENT,
            text_color=theme.TEXT_SECONDARY, corner_radius=4,
            command=self.clear,
        ).pack(side="right", padx=4)

        # Text area
        self.textbox = ctk.CTkTextbox(
            self, font=theme.FONT_MONO, fg_color=theme.LOG_BG,
            text_color=theme.LOG_FG, height=height, corner_radius=6,
            wrap="word", state="disabled",
        )
        self.textbox.pack(fill="both", expand=True, padx=4, pady=4)

    def log(self, text, tag=None):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", text + "\n")
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def clear(self):
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")


class ProgressSection(ctk.CTkFrame):
    """Progress bar with status label."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.status_label = ctk.CTkLabel(
            self, text="Ready", font=theme.FONT_SMALL,
            text_color=theme.TEXT_SECONDARY, anchor="w",
        )
        self.status_label.pack(fill="x", padx=4, pady=(0, 2))
        self.progress = ctk.CTkProgressBar(
            self, fg_color=theme.PROGRESS_BG, progress_color=theme.PROGRESS_FG,
            height=8, corner_radius=4,
        )
        self.progress.pack(fill="x", padx=4)
        self.progress.set(0)

    def set_status(self, text):
        self.status_label.configure(text=text)

    def set_progress(self, value):
        self.progress.set(max(0, min(1, value)))

    def reset(self):
        self.set_status("Ready")
        self.set_progress(0)


class URLEntry(ctk.CTkFrame):
    """URL input field with paste button."""

    def __init__(self, master, placeholder="Enter YouTube URL or Video ID...", **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.entry = ctk.CTkEntry(
            self, placeholder_text=placeholder, font=theme.FONT_BODY,
            fg_color=theme.BG_INPUT, text_color=theme.TEXT_PRIMARY,
            border_color=theme.BORDER, height=40, corner_radius=8,
        )
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.paste_btn = ctk.CTkButton(
            self, text="Paste", font=theme.FONT_SMALL, width=60, height=40,
            fg_color=theme.BG_ACCENT, hover_color=theme.BG_BUTTON,
            command=self._paste, corner_radius=8,
        )
        self.paste_btn.pack(side="right")

    def _paste(self):
        try:
            text = self.winfo_toplevel().clipboard_get()
            self.entry.delete(0, "end")
            self.entry.insert(0, text.strip())
        except Exception:
            pass

    def get(self):
        return self.entry.get().strip()

    def set(self, text):
        self.entry.delete(0, "end")
        self.entry.insert(0, text)


class OutputFormatSelector(ctk.CTkFrame):
    """Checkboxes for selecting export formats."""

    def __init__(self, master, formats=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        if formats is None:
            formats = ["TXT", "MD", "PDF", "JSON"]
        self.vars = {}
        ctk.CTkLabel(self, text="Export Formats:", font=theme.FONT_SMALL,
                      text_color=theme.TEXT_SECONDARY).pack(side="left", padx=(0, 8))
        for fmt in formats:
            var = ctk.BooleanVar(value=True)
            self.vars[fmt] = var
            cb = ctk.CTkCheckBox(
                self, text=fmt, variable=var, font=theme.FONT_SMALL,
                fg_color=theme.BG_BUTTON, hover_color=theme.BG_BUTTON_HOVER,
                border_color=theme.BORDER, text_color=theme.TEXT_PRIMARY,
            )
            cb.pack(side="left", padx=6)

    def get_selected(self):
        return [k for k, v in self.vars.items() if v.get()]


class DropZone(ctk.CTkFrame):
    """Drag-and-drop zone for local files."""

    def __init__(self, master, on_drop=None, **kwargs):
        super().__init__(
            master, fg_color=theme.DROP_ZONE_BG, border_color=theme.DROP_ZONE_BORDER,
            border_width=2, corner_radius=12, height=100, **kwargs,
        )
        self.on_drop = on_drop
        self.label = ctk.CTkLabel(
            self, text="Drag & Drop a video/audio file here\nor click Browse",
            font=theme.FONT_BODY, text_color=theme.TEXT_SECONDARY,
        )
        self.label.pack(expand=True, pady=15)
        self.browse_btn = ctk.CTkButton(
            self, text="Browse File", font=theme.FONT_SMALL, width=100,
            fg_color=theme.BG_ACCENT, hover_color=theme.BG_BUTTON,
            command=self._browse, corner_radius=8,
        )
        self.browse_btn.pack(pady=(0, 10))
        self.file_path = None

    def _browse(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Video/Audio File",
            filetypes=[
                ("Media files", "*.mp4 *.mkv *.avi *.mov *.webm *.mp3 *.wav *.flac *.m4a *.ogg"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.set_file(path)

    def set_file(self, path):
        self.file_path = path
        name = path.split("/")[-1].split("\\")[-1]
        self.label.configure(text=f"Selected: {name}")
        if self.on_drop:
            self.on_drop(path)

    def get_file(self):
        return self.file_path

    def setup_dnd(self):
        """Setup windnd drag-and-drop if available."""
        try:
            import windnd
            windnd.hook_dropfiles(self.winfo_toplevel(), func=self._handle_drop)
            return True
        except ImportError:
            return False

    def _handle_drop(self, files):
        if files:
            path = files[0].decode('utf-8') if isinstance(files[0], bytes) else files[0]
            self.set_file(path)


class ActionButton(ctk.CTkButton):
    """Styled action button."""

    def __init__(self, master, text="Start", **kwargs):
        self._orig_text = text
        defaults = dict(
            font=theme.FONT_BUTTON, fg_color=theme.BG_BUTTON,
            hover_color=theme.BG_BUTTON_HOVER, height=45, corner_radius=10,
        )
        defaults.update(kwargs)
        super().__init__(master, text=text, **defaults)

    def set_running(self, running=True):
        if running:
            self.configure(state="disabled", text="Processing...")
        else:
            self.configure(state="normal", text=self._orig_text)

    def set_text(self, text):
        self._orig_text = text
        self.configure(text=text)
