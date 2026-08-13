"""
Search & Replace Controller for Flet UI.
Decouples search query matching, snippet rendering, range selection, and text replacements.
"""
import re
import flet as ft
from src.i18n import t
from src.ui_flet.state import AppState
from src.ui_flet.components.search_replace_bar import SearchReplaceBar
from src.ui_flet.views.editor_view import EditorView


class SearchController:
    def __init__(
        self,
        page: ft.Page,
        state: AppState,
        search_bar: SearchReplaceBar,
        editor_view: EditorView,
        ribbon_bar=None,
    ):
        self.page = page
        self.state = state
        self.search_bar = search_bar
        self.editor_view = editor_view
        self.ribbon_bar = ribbon_bar

    def toggle_search(self, visible=None):
        """Toggle or set search panel visibility for keyboard shortcuts (Ctrl+F / Ctrl+H).
        Pass visible=None to toggle, True to open, False to close.
        """
        if self.ribbon_bar:
            self.ribbon_bar.toggle_search(visible)
            # ribbon_bar.toggle_search manages focus internally; derive open state from ribbon flag
            opening = self.ribbon_bar._search_visible
        else:
            if visible is None:
                visible = not (self.search_bar and self.search_bar.find_container.visible)
            self.toggle_search_panel(visible)
            opening = visible

        if opening and self.search_bar:
            try:
                self.search_bar.focus_search_input()
            except Exception:
                pass

    def toggle_search_panel(self, e=None):
        if isinstance(e, bool):
            if not e:
                self.state.search_matches.clear()
                self.state.current_match_idx = -1
                self.search_bar.set_match_label(t("search.match_zero"))
                self.search_bar.results_container.visible = False
                self.search_bar.update_results([])
                self.editor_view.editor.selection = None
                try:
                    self.editor_view.editor.update()
                except Exception:
                    pass
            else:
                self.on_search_changed(None)
            return

        if self.ribbon_bar:
            self.ribbon_bar.toggle_search()

    def highlight_current_match(self, focus: bool = False):
        if not self.state.search_matches or self.state.current_match_idx < 0:
            return
        if self.state.current_match_idx >= len(self.state.search_matches):
            self.state.current_match_idx = 0

        start, end = self.state.search_matches[self.state.current_match_idx]
        self.editor_view.select_range(start, end, focus=focus)

    def on_search_match_clicked(self, start: int, end: int):
        if self.state.search_matches:
            for idx, (s, e) in enumerate(self.state.search_matches):
                if s == start and e == end:
                    self.state.current_match_idx = idx
                    break
        self.search_bar.set_match_label(
            t("search.match_position", current=self.state.current_match_idx + 1, total=len(self.state.search_matches))
        )
        self.on_search_changed(None, keep_active_idx=True)
        self.editor_view.select_range(start, end, focus=True)

    def on_search_changed(self, e=None, keep_active_idx: bool = False):
        query = self.search_bar.search_input.value
        content = self.editor_view.get_text()
        content_lf = content.replace("\r\n", "\n")

        if not keep_active_idx:
            self.state.search_matches.clear()
            self.state.current_match_idx = -1

        if query:
            try:
                flags = 0 if self.search_bar.chk_case.value else re.IGNORECASE
                pattern = query if self.search_bar.chk_regex.value else re.escape(query)
                matches = []
                for match in re.finditer(pattern, content_lf, flags):
                    matches.append(match.span())
                self.state.search_matches = matches
            except Exception:
                pass

        count = len(self.state.search_matches)
        matches_data = []

        if count > 0:
            if self.state.current_match_idx < 0 or self.state.current_match_idx >= count:
                self.state.current_match_idx = 0
            self.search_bar.set_match_label(
                t("search.match_position", current=self.state.current_match_idx + 1, total=count)
            )

            lines = content_lf.split("\n")
            line_starts = []
            curr = 0
            for l in lines:
                line_starts.append(curr)
                curr += len(l) + 1

            for start, end in self.state.search_matches:
                line_num = 1
                snippet = ""
                for idx, l_start in enumerate(line_starts):
                    l_end = l_start + len(lines[idx])
                    if l_start <= start <= l_end or (
                        idx == len(lines) - 1 and start >= l_start
                    ):
                        line_num = idx + 1
                        snippet = lines[idx]
                        break
                matches_data.append(
                    {
                        "start": start,
                        "end": end,
                        "line": line_num,
                        "snippet": f"L{line_num}: {snippet.strip()[:60]}",
                    }
                )

            self.highlight_current_match(focus=False)
        else:
            self.search_bar.set_match_label(t("search.match_zero"))

        self.search_bar.update_results(matches_data, self.state.current_match_idx)

    def find_next(self, e=None):
        if self.state.search_matches:
            self.state.current_match_idx = (
                self.state.current_match_idx + 1
            ) % len(self.state.search_matches)
            self.search_bar.set_match_label(
                t("search.match_position", current=self.state.current_match_idx + 1, total=len(self.state.search_matches))
            )
            start, end = self.state.search_matches[self.state.current_match_idx]
            self.on_search_changed(None, keep_active_idx=True)
            self.editor_view.select_range(start, end, focus=True)
            self.search_bar.focus_search_input()

    def find_prev(self, e=None):
        if self.state.search_matches:
            self.state.current_match_idx = (
                self.state.current_match_idx - 1
            ) % len(self.state.search_matches)
            self.search_bar.set_match_label(
                t("search.match_position", current=self.state.current_match_idx + 1, total=len(self.state.search_matches))
            )
            start, end = self.state.search_matches[self.state.current_match_idx]
            self.on_search_changed(None, keep_active_idx=True)
            self.editor_view.select_range(start, end, focus=True)
            self.search_bar.focus_search_input()

    def replace_current(self, e=None, on_editor_changed_cb=None):
        if not self.state.search_matches or self.state.current_match_idx < 0:
            return
        find_val = self.search_bar.search_input.value
        repl_val = self.search_bar.replace_input.value or ""
        content = self.editor_view.get_text()
        start, end = self.state.search_matches[self.state.current_match_idx]

        new_content = content[:start] + repl_val + content[end:]
        self.editor_view.set_text(new_content)
        if on_editor_changed_cb:
            on_editor_changed_cb(None)
        self.on_search_changed(None)

    def replace_all(self, e=None, on_editor_changed_cb=None, error_cb=None):
        query = self.search_bar.search_input.value
        repl_val = self.search_bar.replace_input.value or ""
        content = self.editor_view.get_text()
        if not query:
            return
        try:
            flags = 0 if self.search_bar.chk_case.value else re.IGNORECASE
            pattern = query if self.search_bar.chk_regex.value else re.escape(query)
            new_content = re.sub(pattern, repl_val, content, flags=flags)
            self.editor_view.set_text(new_content)
            if on_editor_changed_cb:
                on_editor_changed_cb(None)
            self.on_search_changed(None)
        except Exception as ex:
            if error_cb:
                error_cb(f"Replace All failed: {ex}")
