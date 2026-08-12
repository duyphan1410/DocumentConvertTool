"""
File I/O Controller for Flet UI.
Decouples document loading, image insertion, output path picking, and draft autosaving.
Integrated with Production-Grade Error Handling and Draft Protection.
"""
import json
import os
import time
import asyncio
import flet as ft

from src.i18n import t
from src.core.errors import DocumentError
from src.core.error_mapper import ErrorMapper
from src.core.validator import validate_file_pipeline
from src.services.file_loader import load_document
from src.ui_flet.constants import (
    DRAFT_PATH,
    DRAFT_META_PATH,
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
from src.ui_flet.state import AppState


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

    async def open_file_by_path(self, file_path: str):
        """
        Loads document from file_path into the editor workspace.
        Handles errors gracefully using production MessageDialog.
        """
        if "on_show_editor" in self.app_controls and self.app_controls["on_show_editor"]:
            self.app_controls["on_show_editor"]()
        try:
            self.ribbon_bar.select_tab("edit", force=True)
        except Exception:
            pass

        filename = os.path.basename(file_path)
        self.editor_view.set_loading(filename)
        self.preview.set_content(f"*Loading {filename}...*")
        self.preview.doc_info_text.value = "Loading..."
        self.footer_bar.set_status_key("status.file_loading", color=ft.Colors.AMBER_400, filename=filename)
        self.footer_bar.set_processing(True)
        self.page.update()

        t0 = time.time()
        res = await asyncio.to_thread(load_document, file_path)
        t_extract = time.time() - t0

        if not res.success:
            self.footer_bar.set_status_key("status.load_failed", color=ft.Colors.RED_400, error=res.error_short or "Lỗi tải tệp", is_error=True)
            self.footer_bar.set_processing(False)
            self.page.update()

            if res.error:
                show_message_dialog(self.page, res.error)
            else:
                doc_err = ErrorMapper.map_exception(
                    Exception(res.error_detail or "Không thể nạp nội dung tài liệu"),
                    context_path=file_path,
                    stage="read",
                )
                show_message_dialog(self.page, doc_err)
            return

        content = res.content
        actual_path = res.path or file_path
        self.state.in_path = actual_path
        self.file_path_bar.set_in_path(actual_path)

        ext = os.path.splitext(actual_path)[1].lower()
        preferred_mode = getattr(self.state, "default_mode", "")
        self.ribbon_bar.update_mode_options(ext, preferred_mode=preferred_mode)
        self.state.current_mode = self.ribbon_bar.mode_dropdown.value

        out_ext = MODES[self.state.current_mode]["out_ext"]
        base, _ = os.path.splitext(actual_path)
        self.state.out_path = f"{base}{out_ext}"
        self.file_path_bar.set_out_path(self.state.out_path)

        self.state.full_content = content
        self.state.undo_stack.clear()
        self.state.redo_stack.clear()

        if len(content) > EDITOR_DISPLAY_LIMIT:
            self.editor_view.set_text(content[:EDITOR_DISPLAY_LIMIT])
        else:
            self.editor_view.set_text(content)

        self.state.undo_stack.append(self.editor_view.get_text())
        self.state.is_dirty = False

        words = len(content.split())
        chars = len(content)
        self.preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")

        base_dir = os.path.dirname(self.state.in_path) if self.state.in_path else None
        self.preview.update_preview(content, base_dir=base_dir)

        t_total = time.time() - t0
        print(f"[BENCHMARK] Total load time: {t_total:.2f}s | Module extraction: {t_extract:.2f}s")

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
                filename=os.path.basename(actual_path),
                duration=f"{t_total:.2f}",
            )

        self.footer_bar.set_processing(False)
        self.perform_autosave()
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

    def has_draft_on_disk(self) -> bool:
        """Returns True if auto draft file exists on disk and is non-empty."""
        return os.path.exists(DRAFT_PATH) and os.path.getsize(DRAFT_PATH) > 0

    async def async_load_draft_if_exists(self) -> bool:
        """
        Asynchronously restores auto-saved draft content & metadata.
        Shows hardware-accelerated LoadingView animation and handles edge-cases (missing files/dirs).
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
        res = await asyncio.to_thread(self._sync_load_draft_data)
        if not res:
            return False

        draft_content, meta = res

        # 1. Restore Source File & Verify Existence
        in_path = meta.get("in_path", "")
        out_path = meta.get("out_path", "")
        saved_mode = meta.get("mode", "")
        timestamp = meta.get("timestamp", time.strftime("%H:%M:%S"))

        missing_in_file = False
        missing_filename = ""
        if in_path:
            if os.path.exists(in_path):
                self.state.in_path = in_path
                self.file_path_bar.set_in_path(in_path)
            else:
                missing_in_file = True
                missing_filename = os.path.basename(in_path)
                self.state.in_path = ""
                self.file_path_bar.set_in_path("")

        # 2. Restore & Filter Conversion Mode by File Extension (matching OpenFile logic)
        ext = os.path.splitext(self.state.in_path)[1].lower() if self.state.in_path else ""
        def_mode = getattr(self.state, "default_mode", "")

        if def_mode and def_mode in MODES and (not ext or MODES[def_mode]["in_ext"] == ext):
            preferred_mode = def_mode
        elif saved_mode and saved_mode in MODES and (not ext or MODES[saved_mode]["in_ext"] == ext):
            preferred_mode = saved_mode
        else:
            preferred_mode = def_mode or saved_mode

        self.ribbon_bar.update_mode_options(ext, preferred_mode=preferred_mode)
        self.state.current_mode = self.ribbon_bar.mode_dropdown.value
        if self.state.current_mode in MODES:
            mode_cfg = MODES[self.state.current_mode]
            self.file_path_bar.set_in_label(mode_cfg["in_label"])
            self.file_path_bar.set_out_label(mode_cfg["out_label"])

        # 3. Restore Output Path with Resilient Fallback
        if out_path and os.path.exists(os.path.dirname(out_path)):
            self.state.out_path = out_path
        elif self.state.in_path:
            out_ext = MODES.get(self.state.current_mode, MODES["MD -> Word"])["out_ext"]
            base, _ = os.path.splitext(self.state.in_path)
            self.state.out_path = f"{base}{out_ext}"
        else:
            out_ext = MODES.get(self.state.current_mode, MODES["MD -> Word"])["out_ext"]
            def_dir = get_default_output_dir()
            self.state.out_path = os.path.join(def_dir, f"output{out_ext}")

        self.file_path_bar.set_out_path(self.state.out_path)

        # 4. Populate Editor View Text
        self.state.full_content = draft_content
        if len(draft_content) > EDITOR_DISPLAY_LIMIT:
            self.editor_view.set_text(draft_content[:EDITOR_DISPLAY_LIMIT])
        else:
            self.editor_view.set_text(draft_content)

        self.state.undo_stack.append(self.editor_view.get_text())
        self.state.is_dirty = False

        words = len(draft_content.split())
        chars = len(draft_content)
        self.preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")

        # 5. Ensure minimum smooth loading animation display time while LoadingView is active
        min_display_time = 0.40
        elapsed_so_far = time.time() - t0
        if elapsed_so_far < min_display_time:
            await asyncio.sleep(min_display_time - elapsed_so_far)

        # 6. Seamless Workspace Transition to Editor View FIRST (LoadingView finishes cleanly with zero freezing!)
        if workspace_view and hasattr(workspace_view, "show_editor"):
            workspace_view.show_editor(ribbon_bar=self.ribbon_bar)
        elif "on_show_editor" in self.app_controls and self.app_controls["on_show_editor"]:
            self.app_controls["on_show_editor"]()

        # 7. Asynchronously Process & Update Markdown Preview AFTER workspace switch
        base_dir = os.path.dirname(self.state.in_path) if self.state.in_path else None

        if hasattr(self.preview, "show_loading"):
            self.preview.show_loading()

        processed_md = await process_markdown_media_async(draft_content, base_dir=base_dir)

        # Assign processed markdown content and restore doc info stats
        self.preview._last_raw_text = draft_content
        self.preview._cached_processed_text = processed_md
        self.preview.markdown.value = processed_md
        self.preview.doc_info_text.value = t("editor.doc_info", words=f"{words:,}", chars=f"{chars:,}")
        try:
            if self.preview.page:
                self.preview.update()
        except Exception:
            pass

        t_total = time.time() - t0
        dur_str = f"{t_total:.2f}"
        print(f"[LOG][DRAFT][{timestamp}] Draft restored ({len(draft_content)} chars) in {dur_str}s")

        # 7. Set Detailed Footer Status with Duration Benchmark
        if missing_in_file:
            self.footer_bar.set_status_key(
                "status.draft_restored_missing",
                color=ft.Colors.ORANGE_400,
                filename=missing_filename,
                duration=dur_str,
            )
        elif self.state.in_path:
            filename = os.path.basename(self.state.in_path)
            self.footer_bar.set_status_key(
                "status.draft_restored_file",
                color=ft.Colors.GREEN_400,
                filename=filename,
                duration=dur_str,
            )
        else:
            self.footer_bar.set_status_key(
                "status.draft_restored_untitled",
                color=ft.Colors.GREEN_400,
                timestamp=timestamp,
                duration=dur_str,
            )

        try:
            self.page.update()
        except Exception:
            pass
        return True

    def _sync_load_draft_data(self):
        try:
            with open(DRAFT_PATH, "r", encoding="utf-8") as f:
                draft = f.read()
            if not draft.strip():
                return None
            meta = {}
            if os.path.exists(DRAFT_META_PATH):
                try:
                    with open(DRAFT_META_PATH, "r", encoding="utf-8") as mf:
                        meta = json.load(mf)
                except Exception:
                    pass
            return draft, meta
        except Exception as e:
            print(f"[LOG][DRAFT][ERROR] Failed to load draft: {e}")
            return None

    def load_draft_if_exists(self) -> bool:
        """Synchronous wrapper for legacy invocations."""
        if not self.has_draft_on_disk():
            return False
        return asyncio.run(self.async_load_draft_if_exists())

    def perform_autosave(self):
        """
        Auto-saves current non-empty editor content and metadata (in_path, out_path, mode).
        NEVER deletes or clears draft files when text is empty.
        """
        if not getattr(self.state, "autosave_enabled", True):
            return
        try:
            text = self.editor_view.get_text() if self.editor_view else ""
            if not text or not text.strip():
                # Safety Guard: Do not modify or clear draft file when editor text is empty
                return

            os.makedirs(os.path.dirname(DRAFT_PATH), exist_ok=True)
            with open(DRAFT_PATH, "w", encoding="utf-8") as f:
                f.write(text)

            timestamp = time.strftime("%H:%M:%S")

            meta_data = {
                "in_path": self.state.in_path or "",
                "out_path": self.state.out_path or "",
                "mode": self.state.current_mode or "",
                "timestamp": timestamp,
                "is_untitled": not bool(self.state.in_path),
            }
            os.makedirs(os.path.dirname(DRAFT_META_PATH), exist_ok=True)
            with open(DRAFT_META_PATH, "w", encoding="utf-8") as meta_f:
                json.dump(meta_data, meta_f, indent=2, ensure_ascii=False)

            print(f"[LOG][AUTO-SAVE][{timestamp}] Draft auto-saved ({len(text)} chars) -> {DRAFT_PATH}")

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
            print(f"[LOG][AUTO-SAVE][ERROR] Autosave error: {e}")

    def clear_draft_file(self):
        """
        Single Responsibility: Explicitly removes the draft_autosave.md and metadata files from disk.
        Only invoked when user explicitly executes 'Clear Content' action.
        """
        for path in [DRAFT_PATH, DRAFT_META_PATH]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"[LOG][AUTO-SAVE][{timestamp}] Removed draft file: {path}")
                except Exception as e:
                    print(f"[LOG][AUTO-SAVE][ERROR] Failed to remove draft file {path}: {e}")
