"""Main application window with tabbed interface."""
import customtkinter as ctk

from . import theme
from .tab_comments import CommentsTab
from .tab_captions import CaptionsTab
from .tab_whisper import WhisperTab


class YouTubeToolkitApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Toolkit - Comments, Captions & AI Generator")
        self.geometry("900x720")
        self.minsize(750, 600)

        # Dark theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color=theme.BG_DARK)

        self._build_ui()
        self._setup_dnd()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=theme.BG_CARD, height=60, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header, text="YouTube Toolkit",
            font=("Segoe UI", 22, "bold"), text_color=theme.BG_BUTTON,
        ).pack(side="left", padx=20, pady=10)
        ctk.CTkLabel(
            header, text="Comments  |  Captions  |  AI Generator",
            font=theme.FONT_SMALL, text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=10, pady=10)

        # Tabview
        self.tabview = ctk.CTkTabview(
            self, fg_color=theme.BG_CARD, segmented_button_fg_color=theme.TAB_UNSELECTED,
            segmented_button_selected_color=theme.TAB_SELECTED,
            segmented_button_unselected_color=theme.TAB_UNSELECTED,
            segmented_button_selected_hover_color=theme.BG_BUTTON_HOVER,
            text_color=theme.TEXT_PRIMARY, corner_radius=12,
        )
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # Add tabs
        tab1 = self.tabview.add("Comments")
        tab2 = self.tabview.add("Captions")
        tab3 = self.tabview.add("AI Generator")

        self.comments_tab = CommentsTab(tab1)
        self.comments_tab.pack(fill="both", expand=True)

        self.captions_tab = CaptionsTab(tab2)
        self.captions_tab.pack(fill="both", expand=True)

        self.whisper_tab = WhisperTab(tab3)
        self.whisper_tab.pack(fill="both", expand=True)

    def _setup_dnd(self):
        """Setup drag-and-drop for the Whisper tab."""
        try:
            import windnd
            def on_drop(files):
                if files:
                    path = files[0].decode('utf-8') if isinstance(files[0], bytes) else files[0]
                    # Switch to Whisper tab and set the file
                    self.tabview.set("AI Generator")
                    self.whisper_tab.drop_zone.set_file(path)
            windnd.hook_dropfiles(self, func=on_drop)
        except ImportError:
            pass  # windnd not available, browse button still works


def run():
    app = YouTubeToolkitApp()
    app.mainloop()
