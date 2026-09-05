"""
Editor Workspace View component for editing document text content.
"""
from typing import Callable, Optional
import flet as ft
from src.i18n import t
from src.ui_flet.theme import STYLE, resolve_color, make_border
from src.ui_flet.components.search_replace_bar import SearchReplaceBar
from src.ui_flet.components.floating_image_toolbar import FloatingImageToolbar
from src.ui_flet.helpers.image_token_helper import (
    ImageTokenInfo,
    find_all_image_tokens,
    find_image_token_at_offset,
    generate_image_token,
)


class EditorView:
    def __init__(
        self,
        search_replace_bar: SearchReplaceBar,
        on_editor_changed: Callable[[ft.ControlEvent], None],
        on_toggle_search: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_undo: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_redo: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_clear: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_open_file: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_save_md: Optional[Callable[[ft.ControlEvent], None]] = None,
        on_image_context_changed: Optional[Callable[[Optional[ImageTokenInfo]], None]] = None,
    ):
        self.search_replace_bar = search_replace_bar
        self.on_editor_changed = on_editor_changed
        self.on_toggle_search = on_toggle_search
        self.on_undo = on_undo
        self.on_redo = on_redo
        self.on_clear = on_clear
        self.on_open_file = on_open_file
        self.on_save_md = on_save_md
        self.on_image_context_changed = on_image_context_changed
        self.active_image_token: Optional[ImageTokenInfo] = None
        self.pinned_image_token: Optional[ImageTokenInfo] = None
        self._dismissed_token_raw: Optional[str] = None
        self._suppress_image_detection: bool = False

        self._on_toolbar_preset: Optional[Callable[[str], None]] = None
        self._on_toolbar_align: Optional[Callable[[str], None]] = None
        self._on_toolbar_custom: Optional[Callable[[], None]] = None
        self._on_toolbar_replace: Optional[Callable[[], None]] = None
        self._on_toolbar_reset: Optional[Callable[[], None]] = None

        self.btn_open_file = ft.IconButton(
            ft.Icons.FOLDER_OPEN_ROUNDED,
            tooltip=t("editor.tooltip_open"),
            icon_size=16,
            on_click=self.on_open_file,
        )
        self.btn_save_md = ft.IconButton(
            ft.Icons.FILE_DOWNLOAD_OUTLINED,
            tooltip=t("editor.tooltip_save_md"),
            icon_size=16,
            on_click=self.on_save_md,
        )
        self.btn_undo = ft.IconButton(
            ft.Icons.UNDO,
            tooltip=t("editor.tooltip_undo"),
            icon_size=16,
            on_click=self.on_undo,
        )
        self.btn_redo = ft.IconButton(
            ft.Icons.REDO,
            tooltip=t("editor.tooltip_redo"),
            icon_size=16,
            on_click=self.on_redo,
        )
        self.btn_clear_editor = ft.IconButton(
            ft.Icons.DELETE_SWEEP,
            tooltip=t("editor.tooltip_clear"),
            icon_size=16,
            on_click=self.on_clear,
        )

        self.title_text = ft.Text(t("editor.title"), size=12, weight=ft.FontWeight.W_600)

        # Contextual Floating Mini-Toolbar placed seamlessly inside editor header
        self.floating_image_toolbar = FloatingImageToolbar(
            on_open_context_menu=lambda x, y: self._handle_toolbar_open_menu(x, y),
            on_preset_click=lambda p: self._handle_toolbar_preset(p),
            on_align_click=lambda a: self._handle_toolbar_align(a),
            on_custom_click=lambda: self._handle_toolbar_custom(),
            on_replace_click=lambda: self._handle_toolbar_replace(),
            on_reset_click=lambda: self._handle_toolbar_reset(),
            on_dismiss_click=lambda: self._handle_toolbar_dismiss(),
        )

        self.toolbar_left = ft.Row(
            controls=[
                self.title_text,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        self.toolbar = ft.Row(
            controls=[
                self.toolbar_left,
                ft.Container(expand=True),
                self.btn_open_file,
                self.btn_undo,
                self.btn_redo,
                self.btn_clear_editor,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            spacing=2,
        )

        self.selection_start: Optional[int] = 0
        self.selection_end: Optional[int] = 0

        self.editor = ft.TextField(
            multiline=True,
            expand=True,
            min_lines=28,
            max_lines=None,
            border_radius=6,
            text_style=ft.TextStyle(font_family=STYLE["font_family_mono"]),
            text_size=13,
            on_change=self.on_editor_changed,
            on_selection_change=self._on_selection_change,
            hint_text=t("editor.hint"),
        )

        self.editor_row = ft.Row(
            controls=[self.editor],
            expand=True,
            scroll=None,
        )

        self.editor_column = ft.Column(
            controls=[
                self.toolbar,
                self.search_replace_bar.results_container,
                self.editor_row,
            ],
            expand=True,
            spacing=2,
        )

        self.editor_drag_target = ft.DragTarget(
            group="doc_explorer",
            content=self.editor_column,
            on_accept=self._handle_drag_accept,
            on_will_accept=self._handle_drag_will_accept,
            on_leave=self._handle_drag_leave,
        )

        self.container = ft.Container(
            content=self.editor_drag_target,
            expand=True,
            padding=ft.Padding(left=8, top=4, right=8, bottom=6),
            border_radius=8,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
        )

    def set_image_action_handlers(
        self,
        on_preset: Optional[Callable[[str], None]] = None,
        on_align: Optional[Callable[[str], None]] = None,
        on_custom: Optional[Callable[[], None]] = None,
        on_replace: Optional[Callable[[], None]] = None,
        on_reset: Optional[Callable[[], None]] = None,
        on_open_menu: Optional[Callable[[float, float], None]] = None,
    ):
        """Sets callbacks for floating image toolbar actions."""
        self._on_toolbar_preset = on_preset
        self._on_toolbar_align = on_align
        self._on_toolbar_custom = on_custom
        self._on_toolbar_replace = on_replace
        self._on_toolbar_reset = on_reset
        self._on_toolbar_open_menu = on_open_menu

    def _handle_toolbar_open_menu(self, x: float, y: float):
        if self._on_toolbar_open_menu:
            self._on_toolbar_open_menu(x, y)

    def _handle_toolbar_preset(self, preset: str):
        tok = self.pinned_image_token or self.active_image_token
        if tok and self._on_toolbar_preset:
            self._on_toolbar_preset(preset)

    def _handle_toolbar_align(self, align: str):
        tok = self.pinned_image_token or self.active_image_token
        if tok and self._on_toolbar_align:
            self._on_toolbar_align(align)

    def _handle_toolbar_custom(self):
        if self._on_toolbar_custom:
            self._on_toolbar_custom()

    def _handle_toolbar_replace(self):
        if self._on_toolbar_replace:
            self._on_toolbar_replace()

    def _handle_toolbar_reset(self):
        tok = self.pinned_image_token or self.active_image_token
        if tok and self._on_toolbar_reset:
            self._on_toolbar_reset()

    def _handle_toolbar_dismiss(self):
        tok = self.pinned_image_token or self.active_image_token
        if tok:
            self._dismissed_token_raw = tok.raw_token
        self.pinned_image_token = None
        self.active_image_token = None
        self.title_text.visible = True
        self.floating_image_toolbar.set_image_context(None)
        try:
            if hasattr(self, "toolbar_left") and self.toolbar_left.page:
                self.toolbar_left.update()
        except Exception:
            pass
        if self.on_image_context_changed:
            try:
                self.on_image_context_changed(None)
            except Exception:
                pass
        self.focus_editor()

    def _handle_drag_will_accept(self, e):
        try:
            self.editor.border_color = ft.Colors.PRIMARY
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass

    def _handle_drag_leave(self, e):
        try:
            self.editor.border_color = None
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass

    def _handle_drag_accept(self, e):
        try:
            self.editor.border_color = None
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass

        file_path = None
        src_ctrl_id = getattr(e, "src_id", None)
        page = (
            getattr(self.container, "page", None)
            or getattr(self.editor, "page", None)
            or getattr(getattr(e, "control", None), "page", None)
            or getattr(self, "page", None)
        )
        if src_ctrl_id and page:
            try:
                src_ctrl = page.get_control(src_ctrl_id)
                if src_ctrl and hasattr(src_ctrl, "data") and src_ctrl.data:
                    file_path = str(src_ctrl.data)
            except Exception as ex:
                print(f"[DEBUG] Error getting draggable control data: {ex}")

        if not file_path:
            raw_data = getattr(e, "data", None)
            if raw_data and not (isinstance(raw_data, str) and raw_data.startswith("_")):
                file_path = raw_data

        if not file_path or not isinstance(file_path, str):
            return

        import os
        name = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()
        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp", ".ico"}

        clean_path = name
        try:
            active_p = self._get_active_file_path() if (hasattr(self, "_get_active_file_path") and self._get_active_file_path) else None
            ws_p = self._get_workspace_path() if (hasattr(self, "_get_workspace_path") and self._get_workspace_path) else None

            if active_p:
                clean_path = os.path.relpath(file_path, os.path.dirname(active_p))
            elif ws_p:
                clean_path = os.path.relpath(file_path, ws_p)
        except Exception:
            clean_path = file_path

        clean_path = clean_path.replace("\\", "/")

        if ext in image_exts:
            token = f"![{name}]({clean_path})"
            self.insert_image_token(token)
        else:
            token = f"[{name}]({clean_path})"
            self.insert_text_at_cursor(token)

    def set_path_providers(self, get_active_file_path: Optional[Callable[[], str]] = None, get_workspace_path: Optional[Callable[[], str]] = None):
        """Sets callbacks to dynamically resolve relative paths on drag and drop."""
        self._get_active_file_path = get_active_file_path
        self._get_workspace_path = get_workspace_path

    def update_dynamic_width(self):
        """Calculates dynamic width based on the longest line when word wrap is disabled."""
        if getattr(self, "word_wrap_enabled", True):
            self.editor.width = None
            self.editor.expand = True
            if hasattr(self, "editor_row"):
                self.editor_row.scroll = None
        else:
            val = self.editor.value or ""
            lines = val.splitlines()
            max_len = max([len(line) for line in lines], default=0)
            char_w = (self.editor.text_size or 13) * 0.60
            calc_w = int(max_len * char_w) + 40

            if calc_w > 650:
                self.editor.width = calc_w
                self.editor.expand = False
                if hasattr(self, "editor_row"):
                    self.editor_row.scroll = ft.ScrollMode.AUTO
            else:
                self.editor.width = None
                self.editor.expand = True
                if hasattr(self, "editor_row"):
                    self.editor_row.scroll = None

    def set_word_wrap(self, enabled: bool):
        """Toggles horizontal word wrap for the editor text field dynamically."""
        self.word_wrap_enabled = enabled
        self.update_dynamic_width()
        try:
            if self.container.page:
                self.container.update()
        except Exception:
            pass

    def _on_selection_change(self, e: ft.TextSelectionChangeEvent):
        """Track current selection/cursor range from Flet TextField events and detect image context."""
        sel = e.selection
        if sel:
            self.selection_start = min(sel.base_offset, sel.extent_offset)
            self.selection_end = max(sel.base_offset, sel.extent_offset)
            self.check_image_context()

    def check_image_context(self):
        """Checks if current cursor or selection range is inside/on an image token and updates toolbar."""
        if getattr(self, "_suppress_image_detection", False):
            return

        raw_val = self.editor.value or ""
        start = self.selection_start if self.selection_start is not None else 0
        end = self.selection_end if self.selection_end is not None else start
        token = find_image_token_at_offset(raw_val, start, end)

        if token:
            self.pinned_image_token = token
            self.active_image_token = token
            if self.on_image_context_changed:
                try:
                    self.on_image_context_changed(token)
                except Exception as ex:
                    print(f"[DEBUG] on_image_context_changed error: {ex}")
        else:
            self._dismissed_token_raw = None
            if self.active_image_token is not None:
                self.active_image_token = None
                if self.on_image_context_changed:
                    try:
                        self.on_image_context_changed(None)
                    except Exception as ex:
                        print(f"[DEBUG] on_image_context_changed error: {ex}")

    def replace_image_token(self, image_info: ImageTokenInfo, new_token: str):
        """Replaces an image token accurately, preserves cursor offset, and triggers change events."""
        if not image_info or not new_token or getattr(self.editor, "read_only", False):
            return
        raw_val = self.editor.value or ""
        start, end = image_info.start, image_info.end

        # Verify exact slice or fallback search to prevent offset drift
        if not (0 <= start <= end <= len(raw_val) and raw_val[start:end] == image_info.raw_token):
            idx = raw_val.find(image_info.raw_token)
            if idx != -1:
                start = idx
                end = idx + len(image_info.raw_token)
            else:
                return

        new_val = raw_val[:start] + new_token + raw_val[end:]
        new_cursor = start + len(new_token)
        self.editor.value = new_val
        self.editor.selection = ft.TextSelection(base_offset=new_cursor, extent_offset=new_cursor)
        self.selection_start, self.selection_end = new_cursor, new_cursor

        # Refresh token coordinates
        new_token_info = find_image_token_at_offset(new_val, start, start + len(new_token))
        self.pinned_image_token = new_token_info
        self.active_image_token = new_token_info
        if self.floating_image_toolbar and new_token_info:
            self.floating_image_toolbar.set_image_context(new_token_info)

        try:
            if self.editor.page:
                self.editor.update()
            if self.floating_image_toolbar.page:
                self.floating_image_toolbar.update()
        except Exception:
            pass

        if self.on_editor_changed:
            self.on_editor_changed(None)

    def focus_and_select_image_at_offset(self, offset: int):
        """Focuses the editor and sets cursor/selection to the image token at offset."""
        raw_val = self.editor.value or ""
        token = find_image_token_at_offset(raw_val, offset, offset)
        if token:
            self.selection_start = token.start
            self.selection_end = token.end
            self.editor.selection = ft.TextSelection(base_offset=token.start, extent_offset=token.end)
            self._dismissed_token_raw = None
            self.check_image_context()
            self.focus_editor()
            try:
                if self.editor.page:
                    self.editor.update()
            except Exception:
                pass

    def apply_image_size(
        self,
        image_info: ImageTokenInfo,
        width: str = "",
        height: str = "",
        align: str = "",
        alt: Optional[str] = None,
        src: Optional[str] = None,
    ):
        """Generates and applies formatted token for the given active image."""
        target_src = src if src is not None else image_info.src
        target_alt = alt if alt is not None else image_info.alt
        new_token = generate_image_token(
            src=target_src,
            alt=target_alt,
            width=width,
            height=height,
            align=align,
        )
        self.replace_image_token(image_info, new_token)

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

    def insert_text_at_cursor(self, text: str):
        """Inserts text at the current cursor selection range and updates editor state."""
        if not text or getattr(self.editor, "read_only", False):
            return
        raw_val = self.editor.value or ""
        start = self.selection_start if self.selection_start is not None else len(raw_val)
        end = self.selection_end if self.selection_end is not None else start
        start = max(0, min(start, len(raw_val)))
        end = max(start, min(end, len(raw_val)))

        new_val = raw_val[:start] + text + raw_val[end:]
        new_pos = start + len(text)
        self.editor.value = new_val
        self.editor.selection = ft.TextSelection(base_offset=new_pos, extent_offset=new_pos)
        self.selection_start, self.selection_end = new_pos, new_pos

        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass

        if self.on_editor_changed:
            self.on_editor_changed(None)

    def get_text(self) -> str:
        return self.editor.value or ""

    def set_loading(self, filename: str = ""):
        name_str = f"'{filename}'" if filename else t("editor.loading_default")
        self.editor.value = t("editor.loading", name=name_str)
        self.editor.read_only = True
        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass

    def set_text(self, text: str):
        self._suppress_image_detection = True
        self.editor.value = (text or "").replace("\r\n", "\n")
        self.editor.read_only = False
        self.selection_start = 0
        self.selection_end = 0
        self.pinned_image_token = None
        self.active_image_token = None
        self._dismissed_token_raw = None
        if hasattr(self, "floating_image_toolbar"):
            self.floating_image_toolbar.set_image_context(None)
        if not getattr(self, "word_wrap_enabled", True):
            self.update_dynamic_width()
        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass
        self._suppress_image_detection = False

    def set_text_with_selection(self, text: str, start: int, end: int, focus: bool = True):
        """Updates editor text then defers selection to next event loop tick to avoid Flutter cursor-reset on value change."""
        import asyncio

        clean_text = (text or "").replace("\r\n", "\n")
        self.editor.value = clean_text
        self.editor.read_only = False
        self.selection_start = start
        self.selection_end = end

        if not getattr(self, "word_wrap_enabled", True):
            self.update_dynamic_width()

        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass

        delay = 0.05 + min(0.1, len(clean_text) / 500_000)

        async def _apply_selection():
            await asyncio.sleep(delay)
            raw_val = self.editor.value or ""
            lf_val = raw_val.replace("\r\n", "\n")
            text_len = len(lf_val)
            s = max(0, min(start, text_len))
            e = max(s, min(end, text_len))

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

            utf16_start = lf_to_utf16(s)
            utf16_end = lf_to_utf16(e)

            self.editor.selection = ft.TextSelection(base_offset=utf16_start, extent_offset=utf16_end)
            self.selection_start, self.selection_end = s, e
            try:
                if self.editor.page:
                    if focus:
                        res = self.editor.focus()
                        if asyncio.iscoroutine(res):
                            await res
                    self.editor.update()
            except Exception:
                pass

        try:
            if self.editor.page:
                self.editor.page.run_task(_apply_selection)
        except Exception:
            pass

    def focus_editor(self):
        """Focus the editor text field."""
        try:
            if self.editor.page:
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

    def set_font_size(self, size: int):
        """Dynamically update font size of editor text field."""
        self.editor.text_size = size
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

    def insert_image_token(self, token: str):
        """Inserts an image Markdown token into the editor, selects it cleanly, and activates image context immediately."""
        val = self.editor.value or ""
        start = self.selection_start if self.selection_start is not None else len(val)
        end = self.selection_end if self.selection_end is not None else start

        start = max(0, min(start, len(val)))
        end = max(start, min(end, len(val)))

        # Safety Check: Prevent inserting into the middle of an existing image token
        tokens = find_all_image_tokens(val)
        for t in tokens:
            if (t.start < start < t.end) or (t.start < end < t.end):
                if not (start == t.start and end == t.end):
                    mid = (t.start + t.end) // 2
                    if start < mid:
                        start = t.start
                        end = t.start
                    else:
                        start = t.end
                        end = t.end
                break

        prefix_nl = "\n" if start > 0 and val[start - 1] != "\n" else ""
        suffix_nl = "\n" if end < len(val) and val[end] != "\n" else ""
        block_token = f"{prefix_nl}{token}{suffix_nl}"

        new_val = val[:start] + block_token + val[end:]
        token_start = start + len(prefix_nl)
        token_end = token_start + len(token)

        self.editor.value = new_val
        self.selection_start, self.selection_end = token_start, token_end
        self.editor.selection = ft.TextSelection(base_offset=token_start, extent_offset=token_end)

        self.check_image_context()

        try:
            if self.editor.page:
                self.editor.update()
        except Exception:
            pass
        if self.on_editor_changed:
            self.on_editor_changed(None)

    def insert_sample_table(self):
        """Inserts a structured Markdown table template into the editor buffer."""
        sample = (
            "\n\n| STT | Tên sản phẩm | Số lượng | Đơn giá | Thành tiền |\n"
            "| :---: | :--- | :---: | :---: | :---: |\n"
            "| 1 | Laptop Dell XPS 15 | 2 | $1,500 | $3,000 |\n"
            "| 2 | Bàn phím cơ Không dây | 5 | $80 | $400 |\n"
            "| 3 | Màn hình 4K LG 27 inch | 3 | $450 | $1,350 |\n\n"
        )
        val = self.editor.value or ""
        start = self.selection_start if self.selection_start is not None else len(val)
        start = max(0, min(start, len(val)))
        new_val = val[:start] + sample + val[start:]
        self.editor.value = new_val
        self.selection_start = start + len(sample)
        self.selection_end = self.selection_start
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
        """Apply palette colors to the editor view and floating image toolbar."""
        bg_dark = resolve_color(palette, "bg_pure_dark", is_dark)
        bg_comp = resolve_color(palette, "bg_component", is_dark)
        border = resolve_color(palette, "border_color", is_dark)
        accent = resolve_color(palette, "text_accent_primary", is_dark)

        # Editor container background + border
        self.container.bgcolor = bg_dark
        self.container.border = make_border(1, border)

        # Editor text area styling
        self.editor.bgcolor = bg_comp
        self.editor.border_color = border
        self.editor.focused_border_color = accent
        self.editor.cursor_color = accent

        # Title text accent color
        self.title_text.color = accent

        if hasattr(self, "floating_image_toolbar"):
            self.floating_image_toolbar.apply_palette(palette, is_dark)

        try:
            if self.container.page:
                self.container.update()
        except Exception:
            pass

    def update_locale(self):
        """Refresh all text to current locale."""
        self.title_text.value = t("editor.title")
        self.btn_open_file.tooltip = t("editor.tooltip_open")
        self.btn_save_md.tooltip = t("editor.tooltip_save_md")
        self.btn_undo.tooltip = t("editor.tooltip_undo")
        self.btn_redo.tooltip = t("editor.tooltip_redo")
        self.btn_clear_editor.tooltip = t("editor.tooltip_clear")
        self.editor.hint_text = t("editor.hint")

        for ctrl in [self.title_text, self.btn_open_file, self.btn_save_md, self.btn_undo, self.btn_redo, self.btn_clear_editor, self.editor, self.toolbar]:
            try:
                if hasattr(ctrl, "page") and ctrl.page:
                    ctrl.update()
            except Exception:
                pass

        try:
            if self.container.page:
                self.container.update()
        except Exception:
            pass
