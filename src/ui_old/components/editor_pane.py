import customtkinter as ctk


class EditorPane(ctk.CTkFrame):
    """
    Component encapsulating the Markdown Editor text box, 
    editor toolbar controls, character counter, and syntax guide tooltips.
    """
    def __init__(self, master, palette=None, style=None, **kwargs):
        super().__init__(master, **kwargs)
        self.palette = palette
        self.style = style

        self.editor_box = None
        self.char_count_lbl = None
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header toolbar frame
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
        toolbar.columnconfigure(1, weight=1)

        lbl_title = ctk.CTkLabel(
            toolbar,
            text="📝 Markdown Editor",
            font=ctk.CTkFont(family=self.style["font_family_title"] if self.style else "Segoe UI", size=13, weight="bold")
        )
        lbl_title.grid(row=0, column=0, sticky="w")

        self.char_count_lbl = ctk.CTkLabel(
            toolbar,
            text="0 chars",
            font=ctk.CTkFont(family=self.style["font_family_body"] if self.style else "Segoe UI", size=11),
            text_color=self.style["text_muted"] if self.style else "#8f93a7"
        )
        self.char_count_lbl.grid(row=0, column=2, sticky="e")

        # Text Editor Widget
        self.editor_box = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family=self.style["font_family_mono"] if self.style else "Consolas", size=12),
            wrap="word",
            border_width=1,
            corner_radius=6
        )
        self.editor_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))

    def update_char_count(self, text: str):
        count = len(text)
        self.char_count_lbl.configure(text=f"{count:,} chars")

    def set_content(self, text: str):
        self.editor_box.delete("1.0", "end")
        self.editor_box.insert("1.0", text)
        self.update_char_count(text)

    def get_content(self) -> str:
        return self.editor_box.get("1.0", "end-1c")
