"""
Backlink & Knowledge Graph View Component for Flet UI (PKB Phase 1).
Displays Linked References and Unlinked Mentions with snippet previews,
relative path disambiguation, and 1-click [+ Link] actions.
Follows Flet 0.86.4 standards and Material Design 3 guidelines.
"""
from __future__ import annotations
import os
import re
import threading
from collections import OrderedDict
from typing import Optional, Callable
import flet as ft
from src.i18n import t
from src.services.metadata_index import MetadataIndex
from src.ui_flet.theme import make_border, get_style_color, resolve_color

MAX_BACKLINK_CACHE_ENTRIES = 100


def _sanitize_snippet(text: str) -> str:
    """
    Cleans raw markdown formatting, pipe tables, headers, and link URLs
    from snippet text to ensure clean, natural multi-line preview text.
    """
    if not text:
        return ""
    # 1. Strip markdown image and standard links [title](url) -> title
    s = re.sub(r'!*\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # 2. Strip wikilinks [[doc|alias]] -> alias or doc
    s = re.sub(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]', lambda m: m.group(2) if m.group(2) else m.group(1), s)
    # 3. Strip table pipes and markdown headers/blockquotes
    s = re.sub(r'\|+', ' ', s)
    s = re.sub(r'^[#>\s\-*+]+', '', s)
    # 4. Strip bold / italic / code markers
    s = re.sub(r'(\*\*|__|\*|_|`+)', '', s)
    # 5. Clean up duplicate quotes / whitespace
    s = re.sub(r'["\']{2,}', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


class BacklinkView(ft.Container):
    """
    Dedicated Sidebar View displaying bidirectional backlinks and unlinked mentions
    for the currently active document.
    """

    def __init__(
        self,
        on_open_file: Optional[Callable[[str], None]] = None,
        on_convert_mention: Optional[Callable[[str, str], None]] = None,
        on_status_message: Optional[Callable[[str, Optional[str]], None]] = None,
        get_workspace_path: Optional[Callable[[], str]] = None,
        width: int = 240,
        visible: bool = True,
        **kwargs,
    ):
        self.on_open_file = on_open_file
        self.on_convert_mention = on_convert_mention
        self.on_status_message = on_status_message
        self._get_workspace_path = get_workspace_path

        self._active_doc_path: Optional[str] = None
        self._active_doc_title: Optional[str] = None
        self._active_doc_id: Optional[str] = None

        self._linked_refs_data: list[dict] = []
        self._unlinked_mentions_data: list[dict] = []
        self._doc_cache: OrderedDict[str, dict] = OrderedDict()
        self._is_loading: bool = False
        self._filter_query: str = ""
        self._is_dark: bool = False
        self._palette: dict = {}

        # 1. Header controls
        self.header_title = ft.Text(
            t("backlinks.title"),
            size=11,
            weight=ft.FontWeight.W_700,
            color=ft.Colors.PRIMARY,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )

        self.btn_refresh = ft.IconButton(
            icon=ft.Icons.REFRESH_ROUNDED,
            icon_size=15,
            tooltip=t("backlinks.refresh"),
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=4),
                padding=ft.Padding(0, 0, 0, 0),
            ),
            on_click=self._handle_refresh_clicked,
        )

        self.header_row = ft.Row(
            controls=[
                ft.Icon(ft.Icons.HUB_OUTLINED, size=15, color=ft.Colors.PRIMARY),
                self.header_title,
                self.btn_refresh,
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        # 2. Search/Filter text field
        self.filter_input = ft.TextField(
            hint_text=t("backlinks.filter_hint"),
            text_size=11,
            dense=True,
            height=30,
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            border_radius=6,
            content_padding=ft.Padding(left=6, top=0, right=6, bottom=0),
            border_color=ft.Colors.OUTLINE_VARIANT,
            on_change=self._handle_filter_changed,
        )

        # 3. Active Document Header Banner
        self.active_doc_title_text = ft.Text(
            t("backlinks.no_active_doc"),
            size=11,
            weight=ft.FontWeight.W_600,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.active_doc_text = self.active_doc_title_text  # Backward compatibility
        self.active_doc_sub_text = ft.Text(
            t("backlinks.active_note"),
            size=8,
            weight=ft.FontWeight.BOLD,
            color=ft.Colors.OUTLINE,
        )

        self.active_doc_banner = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ARTICLE_ROUNDED, size=15, color=ft.Colors.PRIMARY),
                    ft.Column(
                        controls=[
                            self.active_doc_title_text,
                            self.active_doc_sub_text,
                        ],
                        spacing=0,
                        expand=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding(left=8, top=5, right=8, bottom=5),
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border_radius=6,
            border=make_border(1, ft.Colors.OUTLINE_VARIANT),
        )

        # 4. Scrollable Container for sections
        self.sections_column = ft.Column(
            controls=[],
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        self.content_column = ft.Column(
            controls=[
                self.header_row,
                self.active_doc_banner,
                self.filter_input,
                ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT),
                self.sections_column,
            ],
            spacing=6,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        super().__init__(
            content=self.content_column,
            width=width,
            visible=visible,
            padding=ft.Padding(left=8, top=6, right=8, bottom=6),
            bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            **kwargs,
        )

    def update_responsive_width(self, new_width: float):
        """Updates width and resizes layout safely."""
        self.width = new_width
        try:
            if self.page:
                self.update()
        except Exception:
            pass

    def invalidate_cache(self, file_path: Optional[str] = None):
        """Invalidates in-memory backlinks & mentions cache for a specific file or all files."""
        if file_path:
            norm = os.path.normpath(os.path.abspath(file_path))
            self._doc_cache.pop(norm, None)
        else:
            self._doc_cache.clear()

    def set_active_document(self, file_path: Optional[str], title: Optional[str] = None, lazy: bool = False):
        """Sets the active document to inspect and loads its backlinks and unlinked mentions."""
        if not file_path:
            self._active_doc_path = None
            self._active_doc_title = None
            self._active_doc_id = None
            self._is_loading = False
            self.active_doc_title_text.value = t("backlinks.no_active_doc")
            self.active_doc_sub_text.value = ""
            self._linked_refs_data.clear()
            self._unlinked_mentions_data.clear()
            self._rebuild_sections()
            return

        norm_path = os.path.normpath(os.path.abspath(file_path))
        if not title:
            base = os.path.basename(file_path)
            doc_title = os.path.splitext(base)[0]
        else:
            doc_title = title

        self._active_doc_path = norm_path
        self._active_doc_title = doc_title

        self.active_doc_title_text.value = self._active_doc_title
        self.active_doc_sub_text.value = t("backlinks.active_note")

        # 1. Check RAM Cache for instant (0ms) display without showing loading spinner
        cached = self._doc_cache.get(norm_path)
        if cached is not None:
            self._doc_cache.move_to_end(norm_path)
            self._linked_refs_data = list(cached.get("linked", []))
            self._unlinked_mentions_data = list(cached.get("unlinked", []))
            self._active_doc_id = cached.get("doc_id")
            self._is_loading = False
            self._rebuild_sections()
        else:
            # First time visiting this document: clear old data and show loading spinner
            self._linked_refs_data.clear()
            self._unlinked_mentions_data.clear()
            self._is_loading = True
            self._rebuild_sections()

        if lazy or not getattr(self, "visible", False):
            self._needs_refresh = True
            return

        self._needs_refresh = False
        self.refresh_data(is_background_sync=bool(cached))

    def refresh_data(self, force: bool = False, is_background_sync: bool = False):
        """Fetches fresh backlinks and unlinked mentions from SQLite MetadataIndex asynchronously."""
        if not self._active_doc_path or not self._active_doc_title:
            self._is_loading = False
            self._rebuild_sections()
            return

        self._refresh_token = getattr(self, "_refresh_token", 0) + 1
        current_token = self._refresh_token
        active_path = self._active_doc_path
        active_title = self._active_doc_title
        ws_folder = self._get_workspace_path() if self._get_workspace_path else None

        if force:
            self._doc_cache.pop(active_path, None)

        # Show loading indicator only if there is no cached data currently rendered
        if not is_background_sync and active_path not in self._doc_cache:
            self._is_loading = True
            self._rebuild_sections()
        else:
            self._is_loading = False

        def _bg_worker():
            try:
                index = MetadataIndex.get_instance()
                # 1. Lookup active document id
                doc_rec = index.get_document_by_path(active_path)
                if not doc_rec:
                    content = ""
                    if os.path.exists(active_path):
                        with open(active_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                    h = index.calculate_hash(content)
                    doc_id = index.upsert_document(active_path, active_title, h)
                else:
                    doc_id = doc_rec["id"]

                # 2. Get Linked References
                linked_refs = index.get_linked_references(doc_id, workspace_folder=ws_folder)

                # 3. Get Unlinked Mentions
                unlinked_mentions = index.get_unlinked_mentions(doc_id, active_title, workspace_folder=ws_folder)

                # Save to RAM cache with LRU bounding
                self._doc_cache[active_path] = {
                    "doc_id": doc_id,
                    "linked": linked_refs,
                    "unlinked": unlinked_mentions,
                }
                self._doc_cache.move_to_end(active_path)
                while len(self._doc_cache) > MAX_BACKLINK_CACHE_ENTRIES:
                    self._doc_cache.popitem(last=False)

                def _apply_success():
                    if getattr(self, "_refresh_token", 0) == current_token and self._active_doc_path == active_path:
                        self._active_doc_id = doc_id
                        self._linked_refs_data = linked_refs
                        self._unlinked_mentions_data = unlinked_mentions
                        self._is_loading = False
                        self._rebuild_sections()

                if hasattr(self, "page") and self.page and hasattr(self.page, "loop") and self.page.loop:
                    self.page.loop.call_soon_threadsafe(_apply_success)
                else:
                    _apply_success()

            except Exception as ex:
                print(f"[BacklinkView] refresh_data error: {ex}")
                def _apply_error():
                    if getattr(self, "_refresh_token", 0) == current_token:
                        self._is_loading = False
                        self._rebuild_sections()
                    if self.on_status_message:
                        self.on_status_message(f"Backlink query error: {ex}", ft.Colors.RED_400)

                if hasattr(self, "page") and self.page and hasattr(self.page, "loop") and self.page.loop:
                    self.page.loop.call_soon_threadsafe(_apply_error)
                else:
                    _apply_error()

        threading.Thread(target=_bg_worker, daemon=True).start()

    def _handle_filter_changed(self, e):
        self._filter_query = (self.filter_input.value or "").lower().strip()
        self._rebuild_sections()

    def _handle_refresh_clicked(self, e):
        self.refresh_data(force=True)
        if self.on_status_message:
            self.on_status_message(t("backlinks.refresh"), ft.Colors.BLUE_400)

    def _rebuild_sections(self):
        """Reconstructs the UI list for Linked References and Unlinked Mentions."""
        controls: list[ft.Control] = []

        if not self._active_doc_path:
            self.active_doc_banner.visible = False
            self.filter_input.visible = False
            controls.append(
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.HUB_OUTLINED, size=26, color=ft.Colors.PRIMARY),
                                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.PRIMARY),
                                border_radius=22,
                                padding=10,
                            ),
                            ft.Text(
                                t("backlinks.no_active_doc"),
                                size=11,
                                weight=ft.FontWeight.W_700,
                                color=ft.Colors.ON_SURFACE,
                            ),
                            ft.Text(
                                t("backlinks.no_active_doc_sub"),
                                size=9,
                                color=ft.Colors.OUTLINE,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        spacing=6,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(10, 24, 10, 24),
                    alignment=ft.alignment.Alignment(0.0, 0.0),
                )
            )
            self.sections_column.controls = controls
            self._safe_update()
            return

        self.active_doc_banner.visible = True
        self.filter_input.visible = True

        q = self._filter_query

        # Filter items
        filtered_linked = [
            item for item in self._linked_refs_data
            if not q or q in item.get("source_title", "").lower() or q in item.get("snippet", "").lower()
        ]

        filtered_unlinked = [
            item for item in self._unlinked_mentions_data
            if not q or q in item.get("source_title", "").lower() or q in item.get("snippet", "").lower()
        ]

        # ── Section 1: Linked References ───────────────────────────────────────
        count_linked = len(filtered_linked)
        pill_linked = ft.Container(
            content=ft.ProgressRing(width=8, height=8, stroke_width=1.5, color=ft.Colors.PRIMARY)
            if self._is_loading
            else ft.Text(str(count_linked), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
            bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.PRIMARY),
            border_radius=8,
            padding=ft.Padding(6, 1, 6, 1),
        )

        controls.append(
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.LINK_ROUNDED, size=13, color=ft.Colors.PRIMARY),
                    ft.Text(t("backlinks.linked_refs"), size=11, weight=ft.FontWeight.W_700, color=ft.Colors.PRIMARY, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    pill_linked,
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

        if self._is_loading:
            controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.ProgressRing(width=12, height=12, stroke_width=1.8, color=ft.Colors.PRIMARY),
                            ft.Text(t("backlinks.loading_linked"), size=10, italic=True, color=ft.Colors.OUTLINE),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(6, 4, 6, 6),
                )
            )
        elif not filtered_linked:
            controls.append(
                ft.Container(
                    content=ft.Text(t("backlinks.empty_linked"), size=10, italic=True, color=ft.Colors.OUTLINE),
                    padding=ft.Padding(6, 2, 6, 6),
                )
            )
        else:
            for item in filtered_linked:
                controls.append(self._build_linked_ref_card(item))

        controls.append(ft.Divider(height=1, thickness=1, color=ft.Colors.OUTLINE_VARIANT))

        # ── Section 2: Unlinked Mentions ───────────────────────────────────────
        count_unlinked = len(filtered_unlinked)
        pill_unlinked = ft.Container(
            content=ft.ProgressRing(width=8, height=8, stroke_width=1.5, color=ft.Colors.AMBER_400)
            if self._is_loading
            else ft.Text(str(count_unlinked), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.AMBER_400),
            bgcolor=ft.Colors.with_opacity(0.16, ft.Colors.AMBER_400),
            border_radius=8,
            padding=ft.Padding(6, 1, 6, 1),
        )

        controls.append(
            ft.Row(
                controls=[
                    ft.Icon(ft.Icons.TAG_ROUNDED, size=13, color=ft.Colors.AMBER_400),
                    ft.Text(t("backlinks.unlinked_mentions"), size=11, weight=ft.FontWeight.W_700, color=ft.Colors.AMBER_400, expand=True, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
                    pill_unlinked,
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

        if self._is_loading:
            controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.ProgressRing(width=12, height=12, stroke_width=1.8, color=ft.Colors.AMBER_400),
                            ft.Text(t("backlinks.loading_unlinked"), size=10, italic=True, color=ft.Colors.OUTLINE),
                        ],
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding(6, 4, 6, 6),
                )
            )
        elif not filtered_unlinked:
            controls.append(
                ft.Container(
                    content=ft.Text(t("backlinks.empty_unlinked"), size=10, italic=True, color=ft.Colors.OUTLINE),
                    padding=ft.Padding(6, 2, 6, 6),
                )
            )
        else:
            for item in filtered_unlinked:
                controls.append(self._build_unlinked_mention_card(item))

        self.sections_column.controls = controls
        self._safe_update()

    def _build_linked_ref_card(self, item: dict) -> ft.Container:
        source_path = item.get("source_path", "")
        source_title = item.get("source_title", "Document")
        rel_path = item.get("relative_path", os.path.basename(source_path))
        raw_snippet = item.get("snippet", "").strip()
        clean_snippet = _sanitize_snippet(raw_snippet)

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ARTICLE_OUTLINED, size=13, color=ft.Colors.PRIMARY),
                            ft.Text(
                                source_title,
                                size=11,
                                weight=ft.FontWeight.W_600,
                                expand=True,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        rel_path,
                        size=9,
                        color=ft.Colors.OUTLINE,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(
                        content=ft.Text(
                            clean_snippet if clean_snippet else "...",
                            size=10,
                            italic=True,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        padding=ft.Padding(left=6, top=3, right=4, bottom=3),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                        border_radius=4,
                        border=ft.Border(left=ft.BorderSide(2, ft.Colors.PRIMARY)),
                    ),
                ],
                spacing=3,
            ),
            padding=ft.Padding(8, 6, 8, 6),
            border_radius=6,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border=make_border(1, ft.Colors.OUTLINE_VARIANT),
            on_click=lambda e, p=source_path: self._on_item_clicked(p),
            tooltip=f"{source_path}\n(Click to open)",
            ink=True,
        )

    def _build_unlinked_mention_card(self, item: dict) -> ft.Container:
        source_path = item.get("source_path", "")
        source_title = item.get("source_title", "Document")
        rel_path = item.get("relative_path", os.path.basename(source_path))
        matched_text = item.get("matched_text", "")
        raw_snippet = item.get("snippet", "").strip()
        clean_snippet = _sanitize_snippet(raw_snippet)

        start_pos = item.get("start_pos")
        end_pos = item.get("end_pos")

        btn_link = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ADD_LINK_ROUNDED, size=11, color=ft.Colors.WHITE),
                    ft.Text(t("backlinks.btn_link"), size=9, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ],
                spacing=2,
                tight=True,
            ),
            bgcolor=ft.Colors.PRIMARY,
            border_radius=4,
            padding=ft.Padding(5, 2, 6, 2),
            on_click=lambda e, sp=source_path, mt=matched_text, sp_pos=start_pos, ep_pos=end_pos: self._handle_link_mention_clicked(sp, mt, start_pos=sp_pos, end_pos=ep_pos),
            tooltip=t("backlinks.btn_link_tooltip"),
            ink=True,
        )

        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.ARTICLE_OUTLINED, size=13, color=ft.Colors.AMBER_400),
                            ft.Text(
                                source_title,
                                size=11,
                                weight=ft.FontWeight.W_600,
                                expand=True,
                                no_wrap=True,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            btn_link,
                        ],
                        spacing=4,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        rel_path,
                        size=9,
                        color=ft.Colors.OUTLINE,
                        no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Container(
                        content=ft.Text(
                            clean_snippet if clean_snippet else "...",
                            size=10,
                            italic=True,
                            max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        padding=ft.Padding(left=6, top=3, right=4, bottom=3),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_LOW,
                        border_radius=4,
                        border=ft.Border(left=ft.BorderSide(2, ft.Colors.AMBER_400)),
                    ),
                ],
                spacing=3,
            ),
            padding=ft.Padding(8, 6, 8, 6),
            border_radius=6,
            bgcolor=ft.Colors.SURFACE_CONTAINER,
            border=make_border(1, ft.Colors.OUTLINE_VARIANT),
            on_click=lambda e, p=source_path: self._on_item_clicked(p),
            tooltip=f"{source_path}\n(Click to open and preview)",
            ink=True,
        )

    def _on_item_clicked(self, file_path: str):
        if file_path and os.path.exists(file_path) and self.on_open_file:
            self.on_open_file(file_path)

    def _handle_link_mention_clicked(
        self,
        source_path: str,
        matched_text: str,
        start_pos: Optional[int] = None,
        end_pos: Optional[int] = None,
    ):
        """Wraps matched text with [[...]] in source file and triggers refresh."""
        if not source_path or not os.path.exists(source_path) or not matched_text:
            return

        try:
            with open(source_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            new_content = None
            if start_pos is not None and end_pos is not None and 0 <= start_pos < end_pos <= len(content):
                target_slice = content[start_pos:end_pos]
                if target_slice.lower() == matched_text.lower():
                    actual_end = end_pos
                    # If followed immediately by .md or .markdown, consume extension to prevent [[Name]].md
                    if content[actual_end:actual_end+3].lower() == ".md":
                        actual_end += 3
                    elif content[actual_end:actual_end+9].lower() == ".markdown":
                        actual_end += 9

                    # Check if enclosed in inline backticks on the same line
                    line_start = content.rfind("\n", 0, start_pos)
                    line_start = 0 if line_start == -1 else line_start + 1
                    line_end = content.find("\n", actual_end)
                    line_end = len(content) if line_end == -1 else line_end

                    line = content[line_start:line_end]
                    rel_start = start_pos - line_start
                    rel_end = actual_end - line_start

                    enclosing_bt = None
                    for m in re.finditer(r'`([^`\r\n]+)`', line):
                        if m.start(1) <= rel_start and rel_end <= m.end(1):
                            enclosing_bt = (line_start + m.start(), line_start + m.end(), line_start + m.start(1), line_start + m.end(1))
                            break

                    if enclosing_bt:
                        full_s, full_e, in_s, in_e = enclosing_bt
                        prefix = content[in_s:start_pos]
                        suffix = content[actual_end:in_e]
                        new_content = content[:full_s] + prefix + f"[[{matched_text}]]" + suffix + content[full_e:]
                    else:
                        new_content = content[:start_pos] + f"[[{matched_text}]]" + content[actual_end:]

            if new_content is None:
                # Fallback: robust regex with extension boundary consumption
                pattern = re.compile(rf'(?<!\[\[)`?({re.escape(matched_text)})(?:\.md|\.markdown)?`?(?!\]\])', re.IGNORECASE)
                new_content = pattern.sub(rf'[[\1]]', content, count=1)

            if new_content != content:
                with open(source_path, "w", encoding="utf-8") as f:
                    f.write(new_content)

                # Re-sync modified source file
                index = MetadataIndex.get_instance()
                h = index.calculate_hash(new_content)
                title = os.path.splitext(os.path.basename(source_path))[0]
                doc_id = index.upsert_document(source_path, title, h)
                from src.services.link_parser import extract_tags, extract_wikilinks
                index.set_document_tags(doc_id, extract_tags(new_content))
                index.set_document_wikilinks(doc_id, extract_wikilinks(new_content), source_path=source_path)

                if self.on_status_message:
                    self.on_status_message(f"Linked [[{matched_text}]] in {os.path.basename(source_path)}", ft.Colors.GREEN_400)

                # Invalidate cache and refresh current view
                self.invalidate_cache()
                self.refresh_data(force=True)

                if self.on_convert_mention:
                    self.on_convert_mention(source_path, matched_text)

        except Exception as ex:
            print(f"[BacklinkView] _handle_link_mention_clicked error: {ex}")
            if self.on_status_message:
                self.on_status_message(f"Error converting mention: {ex}", ft.Colors.RED_400)

    def update_responsive_width(self, width: int):
        self.width = width
        self._safe_update()

    def update_locale(self):
        """Refreshes all localized strings when app language changes."""
        self.header_title.value = t("backlinks.title")
        self.btn_refresh.tooltip = t("backlinks.refresh")
        self.filter_input.hint_text = t("backlinks.filter_hint")
        if not self._active_doc_path:
            self.active_doc_title_text.value = t("backlinks.no_active_doc")
            self.active_doc_sub_text.value = ""
        else:
            self.active_doc_sub_text.value = t("backlinks.active_note")
        self._rebuild_sections()

    def apply_palette(self, palette: dict, is_dark: bool):
        self._is_dark = is_dark
        self._palette = palette
        self._safe_update()

    def _safe_update(self):
        try:
            if hasattr(self.sections_column, "page") and self.sections_column.page:
                self.sections_column.update()
        except Exception:
            pass
        try:
            if hasattr(self.active_doc_banner, "page") and self.active_doc_banner.page:
                self.active_doc_banner.update()
        except Exception:
            pass
        try:
            if hasattr(self, "page") and self.page:
                self.update()
        except Exception:
            try:
                if hasattr(self, "page") and self.page:
                    self.page.update()
            except Exception:
                pass
