"""
Editor Workspace View component for editing document text content.
"""
from typing import Callable, Optional
import flet as ft
from src.ui_flet.theme import STYLE, resolve_color, make_border
from src.ui_flet.components.search_replace_bar import SearchReplaceBar


class EditorView:
    def __init__(
        self,
        search_replace_bar: SearchReplaceBar,
        on_editor_changed: Callable[[ft.ControlEvent], None],
        on_toggle_search: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_undo: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_redo: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_clear: Optional[Callable[[ft.ControlEvent], None]] = None,
    ):
        self.search_replace_bar = search_replace_bar
        self.on_editor_changed = on_editor_changed
        self.on_toggle_search = on_toggle_search
        self.on_undo = on_undo
        self.on_redo = on_redo
        self.on_clear = on_clear

        self.btn_undo = ft.IconButton(
            ft.Icons.UNDO,
            tooltip="Undo (Ctrl+Z)",
            on_click=self.on_undo,
        )
        self.btn_redo = ft.IconButton(
            ft.Icons.REDO,
            tooltip="Redo (Ctrl+Y)",
            on_click=self.on_redo,
        )
        self.btn_clear_editor = ft.IconButton(
            ft.Icons.DELETE_SWEEP,
            tooltip="Clear Editor",
            on_click=self.on_clear,
        )

        self.title_text = ft.Text("Editor Buffer", weight=ft.FontWeight.W_600)

        self.toolbar = ft.Row(
            controls=[
                self.title_text,
                ft.Container(expand=True),
                self.btn_undo,
                self.btn_redo,
                self.btn_clear_editor,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.selection_start: Optional[int] = 0
        self.selection_end: Optional[int] = 0

        self.editor = ft.TextField(
            multiline=True,
            expand=True,
            min_lines=23,
            max_lines=None,
            border_radius=8,
            text_style=ft.TextStyle(font_family=STYLE["font_family_mono"]),
            text_size=13,
            on_change=self.on_editor_changed,
            on_selection_change=self._on_selection_change,
            hint_text="Document text content will appear here...",
        )



        self.container = ft.Container(
            content=ft.Column(
                controls=[
                    self.toolbar,
                    self.search_replace_bar.results_container,
                    self.editor,
                ],
                expand=True,
            ),
            expand=True,
            padding=10,
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

    def _on_selection_change(self, e: ft.TextSelectionChangeEvent):
        """Track current selection/cursor range from Flet TextField events."""
        sel = e.selection
        if sel:
            self.selection_start = min(sel.base_offset, sel.extent_offset)
            self.selection_end = max(sel.base_offset, sel.extent_offset)

    def select_range(self, start: int, end: int, focus: bool = False):
        """Highlights text range and sets cursor in editor. Converts LF char index to raw TextField UTF-16 code unit index."""
        raw_val = self.editor.value or ""
        lf_val = raw_val.replace("\r\n", "\n")
        text_len = len(lf_val)
        start = max(0, min(start, text_len))
        end = max(start, min(end, text_len))

        def lf_to_utf16(lf_offset: int) -> int:
            raw_idx = len(raw_val)
            lf_count = 0
            for i, char in enumerate(raw_val):
                if lf_count == lf_offset:
                    raw_idx = i
                    break
                if char != "\r":
                    lf_count += 1
            return len(raw_val[:raw_idx].encode("utf-16-le")) // 2

        utf16_start = lf_to_utf16(start)
        utf16_end = lf_to_utf16(end)

        self.editor.selection = ft.TextSelection(base_offset=utf16_start, extent_offset=utf16_end)
        self.selection_start, self.selection_end = start, end
        try:
            if self.editor.page:
                if focus:
                    import asyncio
                    res = self.editor.focus()
                    if asyncio.iscoroutine(res):
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(res)
                        except RuntimeError:
                            pass
                self.editor.update()
        except Exception:
            pass





    def get_text(self) -> str:
        return self.editor.value or ""

    def set_min_lines(self, lines: int):
        """Dynamically update min_lines based on active UI panels."""
        self.editor.min_lines = lines
        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass

    def set_loading(self, filename: str = ""):
        name_str = f"'{filename}'" if filename else "document"
        self.editor.value = f"⏳ Loading {name_str}, please wait..."
        self.editor.read_only = True
        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass

    def set_text(self, text: str):
        self.editor.value = (text or "").replace("\r\n", "\n")
        self.editor.read_only = False
        self.selection_start = 0
        self.selection_end = 0
        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass


    def apply_formatting(self, prefix: str, suffix: str):
        """Applies prefix and suffix formatting around current selected text or at cursor index."""
        val = self.editor.value or ""
        start, end = self.selection_start, self.selection_end

        if 0 <= start < end <= len(val):
            selected = val[start:end]
            if prefix in ("> ", "- ", "1. ") and "\n" in selected:
                lines = selected.split("\n")
                if prefix == "1. ":
                    formatted_selected = "\n".join([f"{i+1}. {l}" for i, l in enumerate(lines)])
                else:
                    formatted_selected = "\n".join([f"{prefix}{l}" for l in lines])
                new_val = val[:start] + formatted_selected + val[end:]
                new_start = start
                new_end = start + len(formatted_selected)
            else:
                new_val = val[:start] + prefix + selected + suffix + val[end:]
                new_start = start + len(prefix)
                new_end = new_start + len(selected)
        else:
            pos = start if 0 <= start <= len(val) else len(val)
            new_val = val[:pos] + prefix + suffix + val[pos:]
            new_start = new_end = pos + len(prefix)

        self.editor.value = new_val
        self.editor.selection = ft.TextSelection(base_offset=new_start, extent_offset=new_end)
        self.selection_start, self.selection_end = new_start, new_end
        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass
        if self.on_editor_changed:
            self.on_editor_changed(None)

    def apply_heading(self, level: int):
        """Applies Markdown Heading (H1-H6) prefix to line(s) containing selection/cursor."""
        import re
        val = self.editor.value or ""
        lines = val.splitlines() or [""]
        start, end = self.selection_start, max(self.selection_start, self.selection_end)

        offset, start_line, end_line = 0, 0, 0
        for idx, line in enumerate(lines):
            line_end = offset + len(line)
            if offset <= start <= line_end:
                start_line = idx
            if offset <= end <= line_end:
                end_line = idx
                break
            offset = line_end + 1

        for idx in range(start_line, end_line + 1):
            stripped = re.sub(r"^#{1,6}\s*", "", lines[idx])
            lines[idx] = f"{'#' * level} {stripped}" if level > 0 else stripped

        self.editor.value = "\n".join(lines)
        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass
        if self.on_editor_changed:
            self.on_editor_changed(None)




    def apply_palette(self, palette: dict, is_dark: bool):
        """Apply palette colors to the editor view."""
        bg_dark = resolve_color(palette, "bg_pure_dark", is_dark)
        bg_comp = resolve_color(palette, "bg_component", is_dark)
        border = resolve_color(palette, "border_color", is_dark)
        accent = resolve_color(palette, "text_accent_primary", is_dark)

        # Editor container background + border
        self.container.bgcolor = bg_dark
        self.container.border = make_border(1, border)

        # Editor text area styling (dễ nhận diện với đường viền rõ ràng)
        self.editor.bgcolor = bg_comp
        self.editor.border_color = border
        self.editor.focused_border_color = accent
        self.editor.cursor_color = accent

        # Title text accent color
        self.title_text.color = accent

        try:
            if self.container.page:
                self.container.update()
        except Exception:
            pass
