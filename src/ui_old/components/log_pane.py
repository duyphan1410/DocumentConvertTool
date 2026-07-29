import customtkinter as ctk


class LogPane(ctk.CTkFrame):
    """
    Component encapsulating system event logging, progress feedback,
    and status badge indicators.
    """
    def __init__(self, master, palette=None, style=None, **kwargs):
        super().__init__(master, **kwargs)
        self.palette = palette
        self.style = style

        self.log_box = None
        self._build_ui()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # Header title
        lbl_title = ctk.CTkLabel(
            self,
            text="📋 System Activity Log",
            font=ctk.CTkFont(family=self.style["font_family_title"] if self.style else "Segoe UI", size=12, weight="bold")
        )
        lbl_title.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))

        # Log Text Box
        self.log_box = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family=self.style["font_family_mono"] if self.style else "Consolas", size=11),
            wrap="word",
            border_width=1,
            corner_radius=6
        )
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self.log_box.configure(state="disabled")

    def append_log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
