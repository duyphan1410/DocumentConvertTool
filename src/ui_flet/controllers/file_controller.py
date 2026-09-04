"""
File I/O Controller for Flet UI.
Decouples document loading, image insertion, output path picking, and draft autosaving.
Integrated with Production-Grade Error Handling and Draft Protection.
"""
import json
import os
import time
import asyncio
from typing import Optional, List, Callable, Dict, Any
import flet as ft

from src.i18n import t
from src.core.errors import DocumentError
from src.core.error_mapper import ErrorMapper
from src.core.validator import validate_file_pipeline
from src.services.file_loader import load_document
from src.services.media_asset_manager import MediaAssetManager
from src.ui_flet.constants import (
    DRAFT_PATH,
    DRAFT_META_PATH,
    DRAFTS_DIR,
    TAB_SESSION_PATH,
    EDITOR_DISPLAY_LIMIT,
    MODES,
    get_default_output_dir,
)
from src.ui_flet.components.message_dialog import show_message_dialog, DialogType
from src.ui_flet.native_dialogs import (
    pick_input_file_async,
    pick_output_file_async,
    pick_image_file_async,
)
from src.ui_flet.state import AppState, DocumentTabState


from src.ui_flet.views.preview_view import process_markdown_media, process_markdown_media_async


class FileController:
    def __init__(self, page: ft.Page, state: AppState, app_controls: dict):
        self.page = page
        self.state = state
        self.app_controls = app_controls
        self.file_path_bar = app_controls["file_path_bar"]
        self.editor_view = app_controls["editor_view"]
        self.preview = app_controls["preview"]
        self.footer_bar = app_controls["footer_bar"]
        self.ribbon_bar = app_controls["ribbon_bar"]
        self.file_picker_in = app_controls["file_picker_in"]
        self.file_picker_out = app_controls["file_picker_out"]

    def trigger_browse_input(self, e=None):
        asyncio.create_task(self.async_browse_input())

    async def async_browse_input(self):
        file_path = await pick_input_file_async(
            page=self.page, picker=self.file_picker_in
        )
        if file_path:
            await self.open_file_by_path(file_path)

    async def open_file_by_path(self, file_path: str, force_reload: bool = False):
        """
        Loads document from file_path into the editor workspace.
        Handles multi-tab deduplication, creates new tabs or switches to existing ones.
        """
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (
            ".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg",
            ".mp4", ".mkv", ".avi", ".mov", ".webm",
        ):
            self.trigger_media_transcribe(default_file_path=file_path)
            return

        # 1. Multi-Tab Deduplication Guard: If file is already open, switch to that tab
        existing_tab = self.state.find_tab_by_path(file_path)
        if existing_tab and not force_reload:
            if existing_tab.is_loading:
                # If tab is already loading, switch to it so user sees progress if they are on another tab
                if self.state.active_tab_id != existing_tab.tab_id:
                    layout_controller = self.app_controls.get("layout_controller")
                    if layout_controller and hasattr(layout_controller, "handle_doc_tab_selected"):
                        layout_controller.handle_doc_tab_selected(existing_tab.tab_id)
                return
            # If the file is already open but currently has no content (e.g. previous load extracted nothing)
            # or if the mode in Ribbon indicates a different PDF conversion engine, reload instead of doing nothing
            curr_mode = self.ribbon_bar.mode_dropdown.value if (self.ribbon_bar and self.ribbon_bar.mode_dropdown) else ""
            if not existing_tab.full_content.strip() or (curr_mode in ("PDF -> MD", "PDF Scan -> MD") and existing_tab.current_mode != curr_mode):
                force_reload = True
            else:
                layout_controller = self.app_controls.get("layout_controller")
                if layout_controller and hasattr(layout_controller, "handle_doc_tab_selected"):
                    layout_controller.handle_doc_tab_selected(existing_tab.tab_id)
                    return

        if "on_show_editor" in self.app_controls and self.app_controls["on_show_editor"]:
            self.app_controls["on_show_editor"]()
        try:
            self.ribbon_bar.select_tab("edit", force=True)
        except Exception:
            pass

        filename = os.path.basename(file_path)
        tab_bar = self.app_controls.get("workspace_tab_bar")

        # ── BƯỚC 1: CAPTURE previous_active_id VÀ XÁC ĐỊNH TARGET TAB ──
        prev_active_id = self.state.active_tab_id
        curr_active_tab = self.state.active_tab

        can_reuse_blank = (
            len(self.state.tabs) == 1
            and curr_active_tab is not None
            and not curr_active_tab.in_path
            and not curr_active_tab.full_content.strip()
            and not curr_active_tab.is_dirty
            and not curr_active_tab.is_orphaned
        )
        can_reuse_existing = (
            curr_active_tab is not None
            and curr_active_tab.in_path == file_path
        )

        if can_reuse_blank or can_reuse_existing:
            target_tab = curr_active_tab
            target_tab.in_path = file_path
            target_tab.title = filename
            target_tab.is_loading = True
            is_new_placeholder = False
        elif existing_tab:
            target_tab = existing_tab
            target_tab.in_path = file_path
            target_tab.title = filename
            target_tab.is_loading = True
            is_new_placeholder = False
        else:
            target_tab = self.state.create_tab(
                in_path=file_path,
                title=filename,
                activate=True,
            )
            target_tab.is_loading = True
            is_new_placeholder = True

        self.state.active_tab_id = target_tab.tab_id

        if tab_bar and hasattr(tab_bar, "render_tabs"):
            tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

        # Cập nhật chế độ Ribbon ngay lập tức theo extension file
        if self.ribbon_bar and hasattr(self.ribbon_bar, "update_mode_options"):
            tab_mode = getattr(target_tab, "current_mode", "")
            def_mode = getattr(self.state, "default_mode", "")
            pref_mode = tab_mode if (tab_mode and tab_mode in MODES and MODES[tab_mode]["in_ext"] == ext) else def_mode
            self.ribbon_bar.update_mode_options(ext, preferred_mode=pref_mode)

        if self.state.active_tab_id == target_tab.tab_id:
            self.editor_view.set_loading(filename)
            self.preview.set_content(f"*Loading {filename}...*", session_id=target_tab.media_session_id)
            self.preview.doc_info_text.value = "Loading..."
            self.footer_bar.set_status_key("status.file_loading", color=ft.Colors.AMBER_400, filename=filename)
            self.footer_bar.set_processing(True)
            self.footer_bar.set_result_buttons_visible(False)

        self.page.update()

        # ── BƯỚC 2: ASYNC LOAD VỚI GUARD TOÀN DIỆN ──
        t0 = time.time()
        try:
            is_pdf = file_path.lower().endswith(".pdf")
            req_module = "PDF Scan" if (
                is_pdf and (
                    (self.ribbon_bar and self.ribbon_bar.mode_dropdown and self.ribbon_bar.mode_dropdown.value == "PDF Scan -> MD")
                    or (target_tab and target_tab.current_mode == "PDF Scan -> MD")
                    or (self.state and getattr(self.state, "current_mode", "") == "PDF Scan -> MD")
                )
            ) else None

            last_ui_update = [0.0]

            def on_load_progress(cur: int, total: int, msg: str, partial_text: Optional[str] = None):
                pct = int(cur / total * 100) if total > 0 else 0
                label = "OCR Scan" if req_module == "PDF Scan" else "Đang đọc"
                if self.footer_bar:
                    self.footer_bar.set_status(f"{label} ({pct}%): {msg}", color=ft.Colors.AMBER_400)

                # Progressive streaming with UI throttling to avoid choking the event loop during dragging/resizing
                now = time.time()
                is_final = (cur >= total)
                is_resizing = getattr(self.state, "is_ui_resizing", False)
                should_update_heavy_ui = is_final or (not is_resizing and (now - last_ui_update[0] >= 1.5))

                if partial_text:
                    target_tab.full_content = partial_text
                    if self.state.active_tab_id == target_tab.tab_id and should_update_heavy_ui:
                        last_ui_update[0] = now
                        if self.editor_view:
                            self.editor_view.set_text(partial_text)
                        if self.preview:
                            preview_text = partial_text
                            if cur < total:
                                preview_text += (
                                    f"\n\n---\n\n"
                                    f"> ⏳ *Đang nạp tiếp trang {cur + 1}/{total}... ({pct}%)*"
                                )
                            self.preview.set_content(
                                preview_text,
                                session_id=target_tab.media_session_id,
                            )

            res = await asyncio.to_thread(
                load_document,
                file_path,
                session_id=target_tab.media_session_id,
                module_name=req_module,
                progress_callback=on_load_progress,
            )

            if not res.success:
                doc_err = res.error or ErrorMapper.map_exception(
                    Exception(res.error_detail or "Không thể nạp nội dung tài liệu"),
                    context_path=file_path,
                    stage="read",
                )

                if self.state.active_tab_id == target_tab.tab_id:
                    show_message_dialog(self.page, doc_err)
                    self.footer_bar.set_status_key("status.load_failed", color=ft.Colors.RED_400, is_error=True)
                else:
                    self.footer_bar.set_status(f"Load failed: {filename}", color=ft.Colors.RED_400)

                if is_new_placeholder:
                    still_on_target = (self.state.active_tab_id == target_tab.tab_id)
                    self.state.close_tab(target_tab.tab_id)
                    self.clear_tab_draft(target_tab.tab_id, media_session_id=target_tab.media_session_id)

                    if still_on_target:
                        fallback_id = prev_active_id if (prev_active_id and self.state.find_tab_by_id(prev_active_id)) else self.state.active_tab_id
                        fallback_tab = self.state.find_tab_by_id(fallback_id) if fallback_id else None
                        if fallback_tab:
                            self.state.active_tab_id = fallback_id
                            if self.editor_view:
                                self.editor_view.set_text(fallback_tab.full_content)
                            layout_controller = self.app_controls.get("layout_controller")
                            if layout_controller and hasattr(layout_controller, "handle_doc_tab_selected"):
                                layout_controller.handle_doc_tab_selected(fallback_id)
                        else:
                            if self.editor_view:
                                self.editor_view.set_text("")
                            if self.preview:
                                self.preview.set_content("")
                                self.preview.doc_info_text.value = t("preview.no_doc")
                            if self.file_path_bar:
                                self.file_path_bar.set_in_path("")
                                self.file_path_bar.set_out_path("")
                else:
                    target_tab.in_path = ""
                    target_tab.title = "Untitled"
                    target_tab.full_content = ""
                    if self.state.active_tab_id == target_tab.tab_id:
                        self.editor_view.set_text("")
                        self.preview.set_content("")
                        self.preview.doc_info_text.value = t("preview.no_doc")
                        self.file_path_bar.set_in_path("")
                        self.file_path_bar.set_out_path("")
                return

            content = res.content
            actual_path = res.path or file_path
            ext = os.path.splitext(actual_path)[1].lower()

            preferred_mode = res.mode if (res and res.mode in MODES) else getattr(self.state, "default_mode", "")
            self.ribbon_bar.update_mode_options(ext, preferred_mode=preferred_mode)
            mode = self.ribbon_bar.mode_dropdown.value
            out_ext = MODES.get(mode, {}).get("out_ext", ".md")
            base, _ = os.path.splitext(actual_path)
            out_path = f"{base}{out_ext}"

            # Cập nhật Data Model
            target_tab.in_path = actual_path
            target_tab.out_path = out_path
            target_tab.title = filename
            target_tab.current_mode = mode
            target_tab.full_content = content
            target_tab.saved_content = content
            target_tab.is_dirty = False
            target_tab.is_orphaned = False
            target_tab.undo_stack.clear()
            target_tab.redo_stack.clear()
            target_tab.undo_stack.append(
                content[:EDITOR_DISPLAY_LIMIT] if len(content) > EDITOR_DISPLAY_LIMIT else content
            )

            self.perform_autosave(target_tab.tab_id)
            self.save_tab_session()

            # Compute preview asynchronously first
            is_dark = getattr(self.preview, "_is_dark", False)
            palette_name = getattr(self.preview, "_palette_name", "Deep Ocean")
            base_dir = os.path.dirname(actual_path)
            processed_md = await process_markdown_media_async(
                content,
                base_dir=base_dir,
                is_dark=is_dark,
                palette_name=palette_name,
                session_id=target_tab.media_session_id,
            )
            target_tab.cached_preview_md = processed_md

            # Atomic UI Guard: Only mutate UI widgets if target_tab is STILL the active tab
            if self.state.active_tab_id == target_tab.tab_id:
                if len(content) > EDITOR_DISPLAY_LIMIT:
                    self.editor_view.set_text(content[:EDITOR_DISPLAY_LIMIT])
                else:
                    self.editor_view.set_text(content)

                self.file_path_bar.set_in_path(actual_path)
                self.file_path_bar.set_out_path(out_path)

                words = len(content.split())
                chars = len(content)
                self.preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")
                self.preview.set_processed_content(
                    processed_md, content, base_dir=base_dir, session_id=target_tab.media_session_id
                )

                t_total = time.time() - t0
                from src.__version__ import __version__
                self.page.title = f"{filename} — Document Converter v{__version__}"

                if len(content) > EDITOR_DISPLAY_LIMIT:
                    self.footer_bar.set_status_key(
                        "status.file_truncated",
                        color=ft.Colors.ORANGE_400,
                        limit=EDITOR_DISPLAY_LIMIT,
                        duration=f"{t_total:.2f}",
                    )
                else:
                    self.footer_bar.set_status_key(
                        "status.file_loaded",
                        color=ft.Colors.GREEN_400,
                        filename=filename,
                        duration=f"{t_total:.2f}",
                    )

                has_valid_converted = bool(
                    target_tab.last_converted_path
                    and os.path.exists(target_tab.last_converted_path)
                )
                self.footer_bar.set_result_buttons_visible(has_valid_converted)

                explorer_view = self.app_controls.get("explorer_view")
                if explorer_view and hasattr(explorer_view, "set_active_file"):
                    explorer_view.set_active_file(actual_path)

        finally:
            target_tab.is_loading = False
            if tab_bar and hasattr(tab_bar, "render_tabs"):
                tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)
            self.footer_bar.set_processing(False)
            if target_tab.full_content and target_tab.full_content.strip():
                self.perform_autosave(target_tab.tab_id)
                self.save_tab_session()
            self.page.update()

    def trigger_browse_output(self, e=None):
        asyncio.create_task(self.async_browse_output())

    async def async_browse_output(self):
        mode_cfg = MODES[self.state.current_mode]
        def_ext = mode_cfg["out_ext"]
        init_file = (
            os.path.basename(self.state.out_path)
            if self.state.out_path
            else f"output{def_ext}"
        )
        file_path = await pick_output_file_async(
            default_ext=def_ext,
            initial_file=init_file,
            page=self.page,
            picker=self.file_picker_out,
        )
        if file_path:
            self.state.out_path = file_path
            self.file_path_bar.set_out_path(file_path)

    def trigger_insert_image(self, e=None):
        asyncio.create_task(self.async_insert_image())

    async def async_insert_image(self):
        img_path = await pick_image_file_async(
            page=self.page, picker=self.file_picker_in
        )
        if img_path:
            img_name = os.path.basename(img_path)
            alt_text = os.path.splitext(img_name)[0]
            normalized_path = img_path.replace("\\", "/")
            token = f"![{alt_text}]({normalized_path})"
            self.editor_view.insert_image_token(token)

    def trigger_replace_image(self, e=None):
        asyncio.create_task(self.async_replace_image())

    async def async_replace_image(self):
        active_tok = getattr(self.editor_view, "pinned_image_token", None) or getattr(self.editor_view, "active_image_token", None)
        if not active_tok:
            return
        img_path = await pick_image_file_async(
            page=self.page, picker=self.file_picker_in
        )
        if img_path:
            clean_path = img_path.replace("\\", "/")
            base_dir = os.path.dirname(self.state.in_path) if self.state.in_path else None
            ws_path = getattr(self.state, "workspace_folder", None)
            if base_dir:
                try:
                    clean_path = os.path.relpath(img_path, base_dir).replace("\\", "/")
                except Exception:
                    clean_path = img_path.replace("\\", "/")
            elif ws_path:
                try:
                    clean_path = os.path.relpath(img_path, ws_path).replace("\\", "/")
                except Exception:
                    clean_path = img_path.replace("\\", "/")

            img_name = os.path.basename(img_path)
            alt_text = os.path.splitext(img_name)[0]
            self.editor_view.apply_image_size(
                active_tok,
                width=active_tok.width,
                height=active_tok.height,
                align=active_tok.align,
                alt=alt_text,
                src=clean_path,
            )
            try:
                if self.page:
                    self.page.update()
            except Exception:
                pass

    def trigger_youtube_import(self, e=None):
        from src.ui_flet.components.youtube_dialog import show_youtube_dialog

        current_pal = self.state.current_palette
        show_youtube_dialog(
            page=self.page,
            on_success=self.handle_youtube_transcript_loaded,
            current_palette=current_pal,
        )

    def trigger_media_transcribe(self, e=None, default_file_path: Optional[str] = None):
        """Opens the local Audio/Video Transcribe Dialog."""
        from src.ui_flet.components.transcribe_dialog import show_transcribe_dialog

        current_pal = self.state.current_palette
        show_transcribe_dialog(
            page=self.page,
            current_palette=current_pal,
            on_success=self.handle_media_transcript_loaded,
            default_file_path=default_file_path,
        )

    def _open_or_create_transcript_tab(self, virtual_name: str, content: str, source_label: str):
        """
        Non-intrusive Tab creation with disambiguation for extracted transcripts.
        If current active tab is clean/untitled, updates it directly.
        Otherwise creates a background tab without stealing focus.
        """
        import re
        import os
        from src.ui_flet.constants import MODES, get_default_output_dir, EDITOR_DISPLAY_LIMIT

        # 1. Disambiguate tab title
        existing_titles = [t.title for t in self.state.tabs] if self.state.tabs else []
        stem, ext = os.path.splitext(virtual_name)
        final_name = virtual_name
        counter = 1
        while final_name in existing_titles:
            final_name = f"{stem} ({counter}){ext}"
            counter += 1

        active_tab = self.state.get_active_tab()
        is_active_clean = (
            active_tab is None
            or (not active_tab.full_content or not active_tab.full_content.strip())
        )

        def_dir = get_default_output_dir()
        file_stem = os.path.splitext(final_name)[0]
        out_path = os.path.join(def_dir, f"{file_stem}.md")

        if is_active_clean:
            if active_tab is None:
                active_tab = self.state.create_tab(
                    title=final_name,
                    mode="MD -> Markdown",
                    in_path="",
                    out_path=out_path,
                    content=content,
                    activate=True,
                )
            else:
                # Update current active tab directly
                active_tab.title = final_name
                active_tab.full_content = content
                active_tab.in_path = ""
                active_tab.out_path = out_path
                active_tab.current_mode = "MD -> Markdown"
            active_tab.is_dirty = True

            if "on_show_editor" in self.app_controls and self.app_controls["on_show_editor"]:
                self.app_controls["on_show_editor"]()
            try:
                self.ribbon_bar.select_tab("edit", force=True)
            except Exception:
                pass

            self.file_path_bar.set_in_path(source_label)
            self.ribbon_bar.update_mode_options(".md", preferred_mode="MD -> Markdown")
            self.state.current_mode = self.ribbon_bar.mode_dropdown.value
            self.file_path_bar.set_out_path(out_path)

            self.state.full_content = content
            self.state.undo_stack.clear()
            self.state.redo_stack.clear()

            if len(content) > EDITOR_DISPLAY_LIMIT:
                self.editor_view.set_text(content[:EDITOR_DISPLAY_LIMIT])
            else:
                self.editor_view.set_text(content)

            self.state.undo_stack.append(self.editor_view.get_text())
            self.state.is_dirty = True

            words = len(content.split())
            chars = len(content)
            self.preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")
            self.preview.update_preview(content, base_dir=None)

            tab_bar = self.app_controls.get("workspace_tab_bar")
            if tab_bar and hasattr(tab_bar, "render_tabs"):
                tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

            self.footer_bar.set_status_key(
                "status.file_loaded",
                color=ft.Colors.GREEN_400,
                filename=final_name,
                duration="0.00",
            )
            self.perform_autosave(tab_id=active_tab.tab_id)
        else:
            # Create new background tab without stealing active typing focus
            new_tab = self.state.create_tab(
                title=final_name,
                mode="MD -> Markdown",
                in_path="",
                out_path=out_path,
                content=content,
                activate=False,
            )
            new_tab.is_dirty = True
            tab_bar = self.app_controls.get("workspace_tab_bar")
            if tab_bar and hasattr(tab_bar, "render_tabs"):
                tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

            self.footer_bar.set_status_key(
                "status.file_loaded",
                color=ft.Colors.GREEN_400,
                filename=final_name,
                duration="0.00",
            )
            self.perform_autosave(tab_id=new_tab.tab_id)

        try:
            self.page.update()
        except Exception:
            pass

    def handle_media_transcript_loaded(self, content: str, source_path: str, title: Optional[str] = None):
        """Injects extracted local media Markdown transcript into editor workspace."""
        base_name = os.path.basename(source_path)
        file_stem = os.path.splitext(base_name)[0]
        virtual_name = f"{file_stem}.md"
        self._open_or_create_transcript_tab(virtual_name, content, f"Media: {source_path}")

    def handle_youtube_transcript_loaded(self, content: str, source_url: str, title: Optional[str] = None):
        """Injects extracted video Markdown transcript into editor workspace (YouTube or Drive)."""
        from src.services.drive_service import is_drive_url, extract_drive_file_id
        from src.services.youtube_service import extract_video_id
        import re

        is_drive = is_drive_url(source_url)
        if is_drive:
            file_id = extract_drive_file_id(source_url) or "drive"
            source_label = f"Drive: {source_url}"
            fallback_stem = f"drive_{file_id}"
        else:
            vid_id = extract_video_id(source_url) or "video"
            source_label = f"YouTube: {source_url}"
            fallback_stem = f"youtube_{vid_id}"

        # Extract title from markdown header for meaningful default filename
        first_line = content.splitlines()[0] if content else ""
        if first_line.startswith("# "):
            title_candidate = first_line[2:].strip()
            safe_title = re.sub(r'[\\/*?"<>|]', "", title_candidate)
            safe_title = re.sub(r'\s+', "_", safe_title).strip("_")[:60]
        elif title:
            safe_title = re.sub(r'[\\/*?"<>|]', "", title)
            safe_title = re.sub(r'\s+', "_", safe_title).strip("_")[:60]
        else:
            safe_title = ""

        file_stem = safe_title if safe_title else fallback_stem
        virtual_name = f"{file_stem}.md"
        self._open_or_create_transcript_tab(virtual_name, content, source_label)

    def trigger_save_markdown(self, e=None):
        """Asynchronously triggers Save As dialog for Markdown content."""
        asyncio.create_task(self.async_save_markdown())

    def handle_save_shortcut(self, e=None):
        """
        Smart Save handler triggered by Ctrl+S:
        - If active tab is linked to an existing file on disk: Direct Fast Save (overwrites in_path, clears dirty dot).
        - If active tab is Untitled (in_path == ""): Prompts Save As dialog suggesting workspace_folder.
        """
        active_tab = self.state.active_tab
        if not active_tab:
            return

        content = self.editor_view.get_text() if self.editor_view else ""
        active_tab.full_content = content

        if active_tab.in_path and os.path.exists(os.path.dirname(active_tab.in_path)):
            # Direct Fast Save
            try:
                with open(active_tab.in_path, "w", encoding="utf-8") as f:
                    f.write(content)
                active_tab.saved_content = content
                active_tab.is_dirty = False
                active_tab.is_orphaned = False
                tab_bar = self.app_controls.get("workspace_tab_bar")
                if tab_bar and hasattr(tab_bar, "render_tabs"):
                    tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)
                self.save_tab_session()
                self.footer_bar.set_status(
                    f"Đã lưu -> {os.path.basename(active_tab.in_path)}",
                    color=ft.Colors.GREEN_400,
                )
                try:
                    self.page.update()
                except Exception:
                    pass
            except Exception as ex:
                self.footer_bar.set_status(f"Save error: {ex}", ft.Colors.RED_400)
                try:
                    self.page.update()
                except Exception:
                    pass
        else:
            # Untitled: Prompt Save File As Dialog
            asyncio.create_task(self.async_save_markdown())

    async def async_save_markdown(self):
        """Directly prompts to save the current editor Markdown content to a .md file."""
        content = self.editor_view.get_text() if self.editor_view else ""
        if not content or not content.strip():
            self.footer_bar.set_status(t("status.empty_editor"), ft.Colors.AMBER_400)
            self.page.update()
            return

        active_tab = self.state.active_tab
        init_file = "Untitled.md"
        if active_tab and active_tab.title and active_tab.title not in ("Untitled", t("tab.untitled")):
            base = os.path.splitext(active_tab.title)[0]
            init_file = f"{base}.md"
        elif self.state.in_path:
            base = os.path.splitext(os.path.basename(self.state.in_path))[0]
            init_file = f"{base}.md"
        else:
            # Smart default: Extract title from first heading in content (# Title)
            import re
            m = re.search(r"^#+\s+(.+)$", content, re.MULTILINE)
            if m:
                clean_t = re.sub(r'[\\/*?:"<>|]', "", m.group(1).strip())
                if clean_t:
                    init_file = f"{clean_t}.md"

        init_dir = getattr(self.state, "workspace_folder", "") or None


        file_path = await pick_output_file_async(
            default_ext=".md",
            initial_file=init_file,
            initial_dir=init_dir,
            page=self.page,
            picker=self.file_picker_out,
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

                if active_tab:
                    active_tab.in_path = file_path
                    active_tab.title = os.path.basename(file_path)
                    active_tab.saved_content = content
                    active_tab.is_dirty = False
                    active_tab.is_orphaned = False

                self.file_path_bar.set_in_path(file_path)
                self.file_path_bar.set_out_path(file_path)
                tab_bar = self.app_controls.get("workspace_tab_bar")
                if tab_bar and hasattr(tab_bar, "render_tabs"):
                    tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

                from src.__version__ import __version__
                self.page.title = f"{os.path.basename(file_path)} — Document Converter v{__version__}"

                self.save_tab_session()
                self.footer_bar.set_result_buttons_visible(True)
                self.footer_bar.set_status(
                    f"Đã lưu Markdown -> {os.path.basename(file_path)}",
                    color=ft.Colors.GREEN_400,
                )
                self.page.update()
                return True
            except Exception as ex:
                self.footer_bar.set_status(f"Save error: {ex}", ft.Colors.RED_400)
                self.page.update()
                return False
        return False

    def get_tab_draft_paths(self, tab_id: str) -> tuple[str, str]:
        """Returns (md_path, meta_path) for the given tab_id."""
        os.makedirs(DRAFTS_DIR, exist_ok=True)
        return (
            os.path.join(DRAFTS_DIR, f"{tab_id}.md"),
            os.path.join(DRAFTS_DIR, f"{tab_id}_meta.json"),
        )

    def save_tab_session(self):
        """Persists the full workspace tab session manifest to tab_session.json."""
        try:
            os.makedirs(os.path.dirname(TAB_SESSION_PATH), exist_ok=True)
            session_data = {
                "active_tab_id": self.state.active_tab_id,
                "tabs": [
                    {
                        "tab_id": tab.tab_id,
                        "in_path": tab.in_path,
                        "out_path": tab.out_path,
                        "title": tab.title,
                        "mode": tab.current_mode,
                        "is_dirty": tab.is_dirty,
                        "is_orphaned": tab.is_orphaned,
                        "media_session_id": tab.media_session_id,
                        "last_converted_path": getattr(tab, "last_converted_path", "") or "",
                    }
                    for tab in self.state.tabs
                ],
            }
            with open(TAB_SESSION_PATH, "w", encoding="utf-8") as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[LOG][TAB_SESSION][ERROR] Failed to save tab session: {e}")

    def has_draft_on_disk(self) -> bool:
        """Returns True if auto draft files or non-empty tab session exist on disk."""
        if os.path.exists(TAB_SESSION_PATH) and os.path.getsize(TAB_SESSION_PATH) > 0:
            try:
                with open(TAB_SESSION_PATH, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                if manifest.get("tabs") and len(manifest["tabs"]) > 0:
                    return True
                return False
            except Exception:
                pass
        if os.path.exists(DRAFTS_DIR):
            try:
                if any(f.endswith(".md") for f in os.listdir(DRAFTS_DIR)):
                    return True
            except Exception:
                pass
        return os.path.exists(DRAFT_PATH) and os.path.getsize(DRAFT_PATH) > 0

    async def async_load_draft_if_exists(self) -> bool:
        """
        Asynchronously restores multi-tab workspace sessions or legacy draft content.
        Shows hardware-accelerated LoadingView animation and handles edge-cases.
        """
        if not self.has_draft_on_disk():
            return False

        workspace_view = self.app_controls.get("workspace_view")
        if workspace_view and hasattr(workspace_view, "show_loading"):
            workspace_view.show_loading(t("status.draft_loading"))

        self.footer_bar.set_status_key("status.draft_loading", color=ft.Colors.AMBER_400)
        try:
            self.page.update()
        except Exception:
            pass

        t0 = time.time()
        res = await asyncio.to_thread(self._sync_load_all_draft_data)
        if not res or not res.get("tabs"):
            self.footer_bar.set_status(t("status.ready"), color=ft.Colors.ON_SURFACE_VARIANT)
            has_workspace = bool(
                getattr(self.state, "workspace_folder", "")
                and os.path.exists(self.state.workspace_folder)
            )
            if has_workspace:
                if workspace_view and hasattr(workspace_view, "show_editor"):
                    workspace_view.show_editor(ribbon_bar=self.ribbon_bar, auto_select_edit=False)
                folder_name = os.path.basename(self.state.workspace_folder) or self.state.workspace_folder
                from src.__version__ import __version__
                self.page.title = f"{folder_name} — Document Converter v{__version__}"
            else:
                if workspace_view and hasattr(workspace_view, "show_welcome"):
                    workspace_view.show_welcome(ribbon_bar=self.ribbon_bar)
            try:
                self.page.update()
            except Exception:
                pass
            return False


        restored_tabs = res["tabs"]
        active_id = res.get("active_tab_id")

        self.state.tabs = restored_tabs
        if active_id and any(t.tab_id == active_id for t in restored_tabs):
            self.state.active_tab_id = active_id
        else:
            self.state.active_tab_id = restored_tabs[0].tab_id

        active_tab = self.state.active_tab
        if not active_tab:
            return False

        MediaAssetManager().set_active_session(active_tab.media_session_id)

        # 1. Populate Editor View Text First (Prevent draft wiping during mode changes)
        content = active_tab.full_content
        if len(content) > EDITOR_DISPLAY_LIMIT:
            self.editor_view.set_text(content[:EDITOR_DISPLAY_LIMIT])
        else:
            self.editor_view.set_text(content)

        active_tab.undo_stack.append(self.editor_view.get_text())

        # 2. Restore Active Tab File Paths & Mode
        if active_tab.in_path and os.path.exists(active_tab.in_path):
            self.file_path_bar.set_in_path(active_tab.in_path)
        else:
            self.file_path_bar.set_in_path("")

        ext = os.path.splitext(active_tab.in_path)[1].lower() if active_tab.in_path else ""
        def_mode = getattr(self.state, "default_mode", "")
        self.ribbon_bar.update_mode_options(ext, preferred_mode=active_tab.current_mode or def_mode)
        active_tab.current_mode = self.ribbon_bar.mode_dropdown.value

        if active_tab.out_path:
            self.file_path_bar.set_out_path(active_tab.out_path)

        words = len(content.split())
        chars = len(content)
        self.preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")

        # 3. Seamless Workspace Transition to Editor View
        if workspace_view and hasattr(workspace_view, "show_editor"):
            workspace_view.show_editor(ribbon_bar=self.ribbon_bar)
        elif "on_show_editor" in self.app_controls and self.app_controls["on_show_editor"]:
            self.app_controls["on_show_editor"]()

        # 4. Render WorkspaceTabBar
        tab_bar = self.app_controls.get("workspace_tab_bar")
        if tab_bar and hasattr(tab_bar, "render_tabs"):
            tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

        # 5. Process Markdown Preview
        base_dir = os.path.dirname(active_tab.in_path) if active_tab.in_path else None
        is_dark = getattr(self.preview, "_is_dark", False)
        palette_name = getattr(self.preview, "_palette_name", "Deep Ocean")
        processed_md = await process_markdown_media_async(
            content, base_dir=base_dir, is_dark=is_dark, palette_name=palette_name, session_id=active_tab.media_session_id
        )

        active_tab.cached_preview_md = processed_md
        self.preview.set_processed_content(
            processed_md, content, base_dir=base_dir, session_id=active_tab.media_session_id
        )
        self.preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")

        t_total = time.time() - t0
        dur_str = f"{t_total:.2f}"
        tab_count = len(self.state.tabs)
        print(f"[LOG][DRAFT] Restored {tab_count} tabs in {dur_str}s")

        self.footer_bar.set_status(
            t("status.tab_restored_count", count=tab_count) if tab_count > 1
            else (
                t("status.draft_restored_file", filename=active_tab.title, duration=dur_str)
                if active_tab.in_path
                else t("status.draft_restored_untitled", timestamp=time.strftime("%H:%M:%S"), duration=dur_str)
            ),
            color=ft.Colors.GREEN_400,
        )

        from src.__version__ import __version__
        self.page.title = f"{active_tab.title} — Document Converter v{__version__}"

        try:
            self.page.update()
        except Exception:
            pass
        return True

    def _sync_load_all_draft_data(self):
        """Loads tabs from tab_session.json and drafts folder, or migrates legacy draft."""
        tabs: list[DocumentTabState] = []
        active_tab_id = None

        # Try multi-tab session format first
        if os.path.exists(TAB_SESSION_PATH):
            try:
                with open(TAB_SESSION_PATH, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                active_tab_id = manifest.get("active_tab_id")
                for item in manifest.get("tabs", []):
                    tid = item.get("tab_id")
                    if not tid:
                        continue
                    content = ""
                    md_path, _ = self.get_tab_draft_paths(tid)
                    if os.path.exists(md_path):
                        try:
                            with open(md_path, "r", encoding="utf-8") as mf:
                                raw_c = mf.read()
                                if not raw_c.startswith("<MagicMock") and not raw_c.startswith("⏳ Loading") and not raw_c.startswith("*Loading"):
                                    content = raw_c
                        except Exception:
                            pass

                    # Fallback 1: if draft was missing but target .md was already saved/converted
                    candidate_paths = [item.get("last_converted_path", ""), item.get("out_path", "")]
                    for cand_p in candidate_paths:
                        if not content and cand_p and os.path.exists(cand_p) and cand_p.lower().endswith(".md"):
                            try:
                                with open(cand_p, "r", encoding="utf-8") as cf:
                                    raw_c = cf.read()
                                    if raw_c.strip() and not raw_c.startswith("<MagicMock"):
                                        content = raw_c
                                        break
                            except Exception:
                                pass

                    if not content and item.get("in_path") and os.path.exists(item.get("in_path")):
                        try:
                            sid = item.get("media_session_id", f"session_{tid}")
                            req_mod = "PDF Scan" if item.get("mode") == "PDF Scan -> MD" else None
                            res = load_document(item["in_path"], session_id=sid, module_name=req_mod)
                            if res.success and not res.content.startswith("<MagicMock"):
                                content = res.content
                        except Exception:
                            pass

                    tab = DocumentTabState(
                        tab_id=tid,
                        in_path=item.get("in_path", ""),
                        out_path=item.get("out_path", ""),
                        title=item.get("title", "Untitled"),
                        current_mode=item.get("mode", "MD -> Excel"),
                        full_content=content,
                        is_dirty=item.get("is_dirty", False),
                        is_orphaned=item.get("is_orphaned", False),
                        media_session_id=item.get("media_session_id", f"session_{tid}"),
                        last_converted_path=item.get("last_converted_path", ""),
                    )
                    tabs.append(tab)
            except Exception as e:
                print(f"[LOG][DRAFT][ERROR] Failed reading tab_session.json: {e}")

        # Fallback to legacy single draft file ONLY on first-time migration when tab_session.json does not exist
        if not os.path.exists(TAB_SESSION_PATH) and not tabs and os.path.exists(DRAFT_PATH):
            try:
                with open(DRAFT_PATH, "r", encoding="utf-8") as f:
                    legacy_content = f.read()
                if legacy_content.strip() and not legacy_content.startswith("<MagicMock") and not legacy_content.startswith("⏳ Loading"):
                    meta = {}
                    if os.path.exists(DRAFT_META_PATH):
                        try:
                            with open(DRAFT_META_PATH, "r", encoding="utf-8") as mf:
                                meta = json.load(mf)
                        except Exception:
                            pass
                    in_p = meta.get("in_path", "")
                    out_p = meta.get("out_path", "")
                    mode_val = meta.get("mode", "MD -> Excel")
                    legacy_title = os.path.basename(in_p) if in_p else "Untitled"
                    tab = DocumentTabState(
                        in_path=in_p,
                        out_path=out_p,
                        title=legacy_title,
                        current_mode=mode_val,
                        full_content=legacy_content,
                        is_dirty=False,
                    )
                    tabs.append(tab)
                    active_tab_id = tab.tab_id
            except Exception as e:
                print(f"[LOG][DRAFT][ERROR] Failed reading legacy draft: {e}")

        return {"tabs": tabs, "active_tab_id": active_tab_id}

    def load_draft_if_exists(self) -> bool:
        """Synchronous wrapper for legacy invocations."""
        if not self.has_draft_on_disk():
            return False
        return asyncio.run(self.async_load_draft_if_exists())

    def perform_autosave(self, tab_id: str | None = None):
        """
        Auto-saves current active tab (or specific tab) content to its dedicated draft file in drafts/{tab_id}.md.
        Never deletes or clears draft files when text is empty.
        """
        if not getattr(self.state, "autosave_enabled", True):
            return

        target_tab = self.state.find_tab_by_id(tab_id) if tab_id else self.state.active_tab
        if not target_tab or target_tab.is_loading:
            return

        try:
            # If target tab is the currently active tab, sync latest text from editor
            if (
                target_tab.tab_id == self.state.active_tab_id
                and self.editor_view
                and not getattr(self.editor_view.editor, "read_only", False)
            ):
                text = self.editor_view.get_text()
                if isinstance(text, str) and not text.startswith("<MagicMock") and not text.startswith("⏳ Loading"):
                    target_tab.full_content = text

            content_to_save = target_tab.full_content
            if not isinstance(content_to_save, str) or content_to_save.startswith("<MagicMock"):
                return

            if not content_to_save or not content_to_save.strip():
                return

            md_path, meta_path = self.get_tab_draft_paths(target_tab.tab_id)
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(content_to_save)

            timestamp = time.strftime("%H:%M:%S")
            meta_data = {
                "tab_id": target_tab.tab_id,
                "in_path": target_tab.in_path or "",
                "out_path": target_tab.out_path or "",
                "title": target_tab.title,
                "mode": target_tab.current_mode or "",
                "timestamp": timestamp,
                "is_dirty": target_tab.is_dirty,
                "is_orphaned": target_tab.is_orphaned,
            }
            with open(meta_path, "w", encoding="utf-8") as meta_f:
                json.dump(meta_data, meta_f, indent=2, ensure_ascii=False)

            self.save_tab_session()

            # Also maintain legacy DRAFT_PATH for backward compatibility
            try:
                with open(DRAFT_PATH, "w", encoding="utf-8") as f:
                    f.write(content_to_save)
                with open(DRAFT_META_PATH, "w", encoding="utf-8") as meta_f:
                    json.dump(meta_data, meta_f, indent=2, ensure_ascii=False)
            except Exception:
                pass

            if hasattr(self, "footer_bar") and self.footer_bar:
                self.footer_bar.set_status_key(
                    "status.draft_autosaved", color=ft.Colors.GREEN_400, timestamp=timestamp
                )
                try:
                    if self.page:
                        self.page.update()
                except Exception:
                    pass
        except Exception as e:
            print(f"[LOG][AUTO-SAVE][ERROR] Autosave error for tab {target_tab.tab_id}: {e}")

    def clear_tab_draft(self, tab_id: str, media_session_id: str | None = None):
        """Removes the draft and metadata files for the specified tab_id and clears media cache."""
        md_path, meta_path = self.get_tab_draft_paths(tab_id)
        for path in [md_path, meta_path]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    print(f"[LOG][AUTO-SAVE] Removed tab draft: {path}")
                except Exception as e:
                    print(f"[LOG][AUTO-SAVE][ERROR] Failed to remove {path}: {e}")
        
        sid = media_session_id
        if not sid:
            tab = self.state.find_tab_by_id(tab_id)
            sid = tab.media_session_id if tab else f"session_{tab_id}"
        MediaAssetManager().clear_session(sid)
        self.save_tab_session()
        if len(self.state.tabs) == 0:
            for path in [DRAFT_PATH, DRAFT_META_PATH, TAB_SESSION_PATH]:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass


    def clear_draft_file(self):
        """Clears draft files for the currently active tab and legacy files."""
        if self.state.active_tab_id:
            tab = self.state.active_tab
            sid = tab.media_session_id if tab else None
            self.clear_tab_draft(self.state.active_tab_id, media_session_id=sid)
        for path in [DRAFT_PATH, DRAFT_META_PATH]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass

    def handle_file_renamed(self, old_path: str, new_path: str):
        """
        Synchronizes all matching tabs in state.tabs when a file or directory is renamed on disk.
        Updates tab titles, paths, FilePathBar, Page Title, and TabBar visual items.
        """
        if not old_path or not self.state.tabs:
            return

        old_norm = os.path.normcase(os.path.normpath(old_path))
        any_matched = False

        for tab in self.state.tabs:
            if not tab.in_path:
                continue
            tab_norm = os.path.normcase(os.path.normpath(tab.in_path))
            is_direct = (tab_norm == old_norm)
            is_parent = tab_norm.startswith(old_norm + os.sep)

            if not (is_direct or is_parent):
                continue

            any_matched = True

            if is_direct:
                tab.in_path = new_path
                tab.title = os.path.basename(new_path)
            elif is_parent:
                rel = os.path.relpath(tab.in_path, old_path)
                tab.in_path = os.path.join(new_path, rel)
                tab.title = os.path.basename(tab.in_path)

            # Only update FilePathBar & Window Title if THIS tab is currently active
            if tab.tab_id == self.state.active_tab_id:
                self.file_path_bar.set_in_path(tab.in_path)
                if tab.out_path:
                    out_dir = os.path.dirname(tab.out_path)
                    mode_cfg = MODES.get(tab.current_mode, {})
                    out_ext = mode_cfg.get("out_ext", os.path.splitext(tab.out_path)[1])
                    new_base = os.path.splitext(os.path.basename(tab.in_path))[0]
                    tab.out_path = os.path.join(out_dir, f"{new_base}{out_ext}")
                    self.file_path_bar.set_out_path(tab.out_path)

                from src.__version__ import __version__
                self.page.title = f"{tab.title} — Document Converter v{__version__}"

        if any_matched:
            tab_bar = self.app_controls.get("workspace_tab_bar")
            if tab_bar and hasattr(tab_bar, "render_tabs"):
                tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)
            self.perform_autosave()
            self.save_tab_session()
            try:
                self.page.update()
            except Exception:
                pass

    def handle_file_deleted(self, deleted_path: str):
        """
        Handles file/folder deletion on disk across all open tabs:
        - If tab has unsaved changes (is_dirty): marks as is_orphaned=True, in_path="", keeps title, preserves RAM data.
        - If tab has no unsaved changes (not is_dirty): closes the tab safely and removes draft.
        """
        if not deleted_path or not self.state.tabs:
            return

        deleted_norm = os.path.normcase(os.path.normpath(deleted_path))
        tabs_to_close: list[tuple[str, str]] = []  # (tab_id, media_session_id)
        state_changed = False

        for tab in list(self.state.tabs):
            if not tab.in_path:
                continue
            tab_norm = os.path.normcase(os.path.normpath(tab.in_path))
            is_direct = (tab_norm == deleted_norm)
            is_parent = tab_norm.startswith(deleted_norm + os.sep)

            if is_direct or is_parent:
                state_changed = True
                if tab.is_dirty:
                    # Preserve user content in RAM / drafts, flag as orphaned
                    tab.is_orphaned = True
                    tab.in_path = ""
                    if tab.tab_id == self.state.active_tab_id:
                        self.file_path_bar.set_in_path("")
                        self.footer_bar.set_status(
                            t("status.file_deleted_warning", filename=tab.title),
                            ft.Colors.AMBER_400,
                        )
                else:
                    # Clean tab with zero unsaved changes: close immediately
                    tabs_to_close.append((tab.tab_id, tab.media_session_id))

        for tid, sid in tabs_to_close:
            self.state.close_tab(tid)
            self.clear_tab_draft(tid, media_session_id=sid)

        if not state_changed:
            return

        tab_bar = self.app_controls.get("workspace_tab_bar")
        layout_controller = self.app_controls.get("layout_controller")

        if len(self.state.tabs) == 0:
            if tab_bar and hasattr(tab_bar, "render_tabs"):
                tab_bar.render_tabs([], None)
            if self.editor_view:
                self.editor_view.set_text("")
            if self.preview:
                self.preview.update_preview("")
            if self.file_path_bar:
                self.file_path_bar.set_in_path("")
                self.file_path_bar.set_out_path("")

            has_workspace = bool(getattr(self.state, "workspace_folder", "") and os.path.exists(self.state.workspace_folder))
            if not has_workspace:
                # 1. No workspace folder open: Return cleanly to WelcomeView
                workspace_view = self.app_controls.get("workspace_view")
                if workspace_view and hasattr(workspace_view, "show_welcome"):
                    workspace_view.show_welcome(ribbon_bar=self.ribbon_bar)
                from src.__version__ import __version__
                self.page.title = t("app.title", version=__version__)
            else:
                # 2. Workspace folder active: Keep Editor Workspace (Sidebar/Explorer visible), show empty editor
                folder_name = os.path.basename(self.state.workspace_folder) or self.state.workspace_folder
                from src.__version__ import __version__
                self.page.title = f"{folder_name} — Document Converter v{__version__}"
        else:
            if layout_controller and hasattr(layout_controller, "handle_doc_tab_selected"):
                layout_controller.handle_doc_tab_selected(self.state.active_tab_id)
            elif tab_bar and hasattr(tab_bar, "render_tabs"):
                tab_bar.render_tabs(self.state.tabs, self.state.active_tab_id)

        self.save_tab_session()
        try:
            self.page.update()
        except Exception:
            pass
