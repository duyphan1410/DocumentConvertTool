"""
File I/O Controller for Flet UI.
Decouples document loading, image insertion, output path picking, and draft autosaving.
"""
import os
import time
import asyncio
import flet as ft

from src.services.file_loader import load_document
from src.ui_flet.constants import DRAFT_PATH, EDITOR_DISPLAY_LIMIT, MODES
from src.ui_flet.native_dialogs import (
    pick_input_file_async,
    pick_output_file_async,
    pick_image_file_async,
)
from src.ui_flet.state import AppState


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
            # Mount Editor Workspace onto page tree immediately before updating controls
            if "on_show_editor" in self.app_controls and self.app_controls["on_show_editor"]:
                self.app_controls["on_show_editor"]()
            try:
                self.ribbon_bar._select_tab("edit")
            except Exception:
                pass

            filename = os.path.basename(file_path)
            self.editor_view.set_loading(filename)
            self.preview.set_content(f"*Loading {filename}...*")
            self.preview.doc_info_text.value = "Loading..."
            self.footer_bar.set_status(f"Loading file: {filename}...", ft.Colors.AMBER_400)
            self.footer_bar.set_processing(True)
            self.page.update()

            t0 = time.time()
            res = await asyncio.to_thread(load_document, file_path)
            t_extract = time.time() - t0

            if not res.success:
                err_msg = res.error_short or "Failed to load document"
                self.footer_bar.set_status(f"Load failed: {err_msg}", ft.Colors.RED_400)
                self.footer_bar.set_processing(False)
                self.page.update()
                return

            content = res.content
            self.state.in_path = file_path
            self.file_path_bar.set_in_path(file_path)

            ext = os.path.splitext(file_path)[1].lower()
            self.ribbon_bar.update_mode_options(ext)
            self.state.current_mode = self.ribbon_bar.mode_dropdown.value

            out_ext = MODES[self.state.current_mode]["out_ext"]
            base, _ = os.path.splitext(file_path)
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
            self.preview.doc_info_text.value = f"{words:,} words | {chars:,} chars"

            base_dir = os.path.dirname(self.state.in_path) if self.state.in_path else None
            self.preview.update_preview(content, base_dir=base_dir)

            t_total = time.time() - t0
            print(
                f"[BENCHMARK] Total load time: {t_total:.2f}s | Module extraction: {t_extract:.2f}s"
            )

            if len(content) > EDITOR_DISPLAY_LIMIT:
                self.footer_bar.set_status(
                    f"File truncated (>{EDITOR_DISPLAY_LIMIT} chars) ({t_total:.2f}s)",
                    ft.Colors.ORANGE_400,
                )
            else:
                self.footer_bar.set_status(
                    f"Loaded: {os.path.basename(file_path)} ({t_total:.2f}s)",
                    ft.Colors.GREEN_400,
                )

            # Ensure active Ribbon tab switches to "Edit" on successful load
            try:
                self.ribbon_bar.select_tab("edit", force=True)
            except Exception as ex:
                print(f"[DEBUG] select_tab Edit error: {ex}")

            self.footer_bar.set_processing(False)
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
            token = f"![{alt_text}](file:///{normalized_path})"
            self.editor_view.apply_formatting(token, "")

    def load_draft_if_exists(self) -> bool:
        if os.path.exists(DRAFT_PATH):
            try:
                with open(DRAFT_PATH, "r", encoding="utf-8") as f:
                    draft = f.read()
                if draft.strip():
                    self.state.full_content = draft
                    self.editor_view.set_text(draft)
                    self.state.undo_stack.append(draft)
                    base_dir = (
                        os.path.dirname(self.state.in_path)
                        if self.state.in_path
                        else None
                    )
                    self.preview.update_preview(draft, base_dir=base_dir)
                    timestamp = time.strftime("%H:%M:%S")
                    print(f"[LOG][DRAFT][{timestamp}] Loaded existing draft ({len(draft)} chars) from {DRAFT_PATH}")
                    self.footer_bar.set_status(
                        f"Loaded autosaved draft ({timestamp})", ft.Colors.GREEN_400
                    )
                    return True
            except Exception as e:
                print(f"[LOG][DRAFT][ERROR] Failed to load draft: {e}")
        return False

    def perform_autosave(self):
        if not getattr(self.state, "autosave_enabled", True):
            return
        try:
            os.makedirs(os.path.dirname(DRAFT_PATH), exist_ok=True)
            text = self.editor_view.get_text()
            with open(DRAFT_PATH, "w", encoding="utf-8") as f:
                f.write(text)

            timestamp = time.strftime("%H:%M:%S")
            print(f"[LOG][AUTO-SAVE][{timestamp}] Draft auto-saved ({len(text)} chars) -> {DRAFT_PATH}")

            if hasattr(self, "footer_bar") and self.footer_bar:
                self.footer_bar.set_status(
                    f"Auto-saved draft ({timestamp})", ft.Colors.GREEN_400
                )
                try:
                    if self.page:
                        self.page.update()
                except Exception:
                    pass
        except Exception as e:
            print(f"[LOG][AUTO-SAVE][ERROR] Autosave error: {e}")
