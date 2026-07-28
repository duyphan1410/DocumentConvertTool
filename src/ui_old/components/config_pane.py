import customtkinter as ctk


class ConfigPane(ctk.CTkFrame):
    """
    Component encapsulating conversion modes, file path controls,
    theme palette selectors, and system configuration buttons.
    """
    def __init__(self, master, palette=None, style=None, **kwargs):
        super().__init__(master, **kwargs)
        self.palette = palette
        self.style = style

        self.mode_option = None
        self.palette_option = None
        self.btn_convert = None
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)

        # Header title
        lbl_title = ctk.CTkLabel(
            self,
            text="⚙️ Conversion Settings",
            font=ctk.CTkFont(family=self.style["font_family_title"] if self.style else "Segoe UI", size=13, weight="bold")
        )
        lbl_title.pack(anchor="w", padx=12, pady=(10, 6))

        # Mode Selection Sub-frame
        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.pack(fill="x", padx=12, pady=4)

        lbl_mode = ctk.CTkLabel(
            mode_frame,
            text="Mode:",
            font=ctk.CTkFont(family=self.style["font_family_body"] if self.style else "Segoe UI", size=11, weight="bold")
        )
        lbl_mode.pack(side="left", padx=(0, 8))

        self.mode_option = ctk.CTkOptionMenu(
            mode_frame,
            values=[
                "MD -> Excel", "MD -> Word", "MD -> CSV", "MD -> PDF", "MD -> HTML",
                "Excel -> MD", "Word -> MD", "CSV -> MD", "PDF -> MD", "HTML -> MD"
            ],
            dynamic_resizing=False
        )
        self.mode_option.pack(side="left", fill="x", expand=True)
