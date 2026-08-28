"""
Centralized AppState and DocumentTabState Management for DocumentConvertTool Flet UI.
Implements Property Delegation Pattern for transparent multi-tab state management.
"""
from dataclasses import dataclass, field
import os
import time
import uuid


def _generate_tab_id() -> str:
    return f"tab_{uuid.uuid4().hex[:8]}"


@dataclass
class DocumentTabState:
    tab_id: str = field(default_factory=_generate_tab_id)
    in_path: str = ""
    out_path: str = ""
    last_converted_path: str = ""
    current_mode: str = "MD -> Excel"
    full_content: str = ""
    is_dirty: bool = False
    is_orphaned: bool = False  # True when source file on disk was deleted but tab is kept in RAM
    is_loading: bool = False   # True when tab content/preview is undergoing heavy async rendering
    title: str = "Untitled"
    undo_stack: list[str] = field(default_factory=list)
    redo_stack: list[str] = field(default_factory=list)
    is_undo_redo_op: bool = False
    search_matches: list[tuple[int, int]] = field(default_factory=list)
    current_match_idx: int = -1
    media_session_id: str = ""
    cursor_position: int = 0
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.media_session_id:
            self.media_session_id = f"session_{self.tab_id}"
        if not self.title or self.title == "Untitled":
            if self.in_path:
                self.title = os.path.basename(self.in_path)


@dataclass
class AppState:
    # ── Multi-Tab Management ───────────────────────────────────────────
    tabs: list[DocumentTabState] = field(default_factory=list)
    active_tab_id: str | None = None

    # Global UI State
    current_palette: str = "Deep Ocean"
    current_theme_mode: str = "System"
    is_processing: bool = False
    status_text: str = "Ready"
    status_color: str | None = None

    # User Settings (persisted to %APPDATA%\\DocConvert\\settings.json)
    autosave_enabled: bool = True
    autosave_interval_sec: int = 30
    default_mode: str = "MD -> Excel"
    editor_font_size: int = 13
    show_line_numbers: bool = False
    word_wrap: bool = True
    language: str = "en"
    show_preview: bool = True
    show_path_bar: bool = True
    show_status_bar: bool = True
    show_sidebar: bool = True
    sidebar_width: int = 240
    sidebar_position: str = "left"
    editor_ratio: float = 0.5
    workspace_folder: str = ""
    active_activity_tab: str = "explorer"

    # Window State & Geometry
    window_width: int | None = None
    window_height: int | None = None
    window_top: int | None = None
    window_left: int | None = None
    window_maximized: bool = True

    # ── Tab Lifecycle Methods ──────────────────────────────────────────

    @property
    def active_tab(self) -> DocumentTabState | None:
        """Returns the currently active DocumentTabState, or None if no tabs exist."""
        if not self.tabs:
            return None
        if self.active_tab_id:
            for tab in self.tabs:
                if tab.tab_id == self.active_tab_id:
                    return tab
        # Fallback to first tab if active_tab_id is unset or not found
        self.active_tab_id = self.tabs[0].tab_id
        return self.tabs[0]

    def create_tab(
        self,
        in_path: str = "",
        out_path: str = "",
        title: str = "",
        content: str = "",
        mode: str | None = None,
        activate: bool = True,
    ) -> DocumentTabState:
        """Creates a new DocumentTabState and optionally activates it."""
        tab_mode = mode or self.default_mode or "MD -> Excel"
        tab_title = title or (os.path.basename(in_path) if in_path else "Untitled")
        tab = DocumentTabState(
            in_path=in_path,
            out_path=out_path,
            title=tab_title,
            full_content=content,
            current_mode=tab_mode,
        )
        self.tabs.append(tab)
        if activate or self.active_tab_id is None:
            self.active_tab_id = tab.tab_id
        return tab

    def close_tab(self, tab_id: str) -> bool:
        """Removes the tab with tab_id. Updates active_tab_id if needed."""
        idx = self.get_tab_index(tab_id)
        if idx == -1:
            return False

        self.tabs.pop(idx)
        if not self.tabs:
            self.active_tab_id = None
        elif self.active_tab_id == tab_id:
            # Switch to neighboring tab
            new_idx = min(idx, len(self.tabs) - 1)
            self.active_tab_id = self.tabs[new_idx].tab_id
        return True

    def activate_tab(self, tab_id: str) -> DocumentTabState | None:
        """Sets active_tab_id to tab_id and returns the tab if found."""
        tab = self.find_tab_by_id(tab_id)
        if tab:
            self.active_tab_id = tab.tab_id
        return tab

    def find_tab_by_id(self, tab_id: str) -> DocumentTabState | None:
        for tab in self.tabs:
            if tab.tab_id == tab_id:
                return tab
        return None

    def find_tab_by_path(self, path: str) -> DocumentTabState | None:
        """
        Finds open tab by file path.
        CRITICAL GUARD: Early returns None if path is empty/blank to prevent false matches on Untitled tabs.
        """
        if not path or not path.strip():
            return None
        target_norm = os.path.normcase(os.path.normpath(path))
        for tab in self.tabs:
            if tab.in_path and os.path.normcase(os.path.normpath(tab.in_path)) == target_norm:
                return tab
        return None

    def get_tab_index(self, tab_id: str) -> int:
        for idx, tab in enumerate(self.tabs):
            if tab.tab_id == tab_id:
                return idx
        return -1

    def reorder_tabs(self, source_id: str, target_id: str) -> None:
        """Moves source_id tab to target_id tab position."""
        if source_id == target_id:
            return
        src_idx = self.get_tab_index(source_id)
        tgt_idx = self.get_tab_index(target_id)
        if src_idx != -1 and tgt_idx != -1:
            tab = self.tabs.pop(src_idx)
            self.tabs.insert(tgt_idx, tab)

    def _ensure_active_tab(self) -> DocumentTabState:
        """Returns the active tab, creating an initial default tab if tabs is empty."""
        tab = self.active_tab
        if tab is None:
            tab = self.create_tab()
        return tab

    # ── Transparent Property Delegation (Backward Compatibility) ───────

    @property
    def in_path(self) -> str:
        tab = self.active_tab
        return tab.in_path if tab else ""

    @in_path.setter
    def in_path(self, val: str):
        tab = self._ensure_active_tab()
        tab.in_path = val
        if val and (not tab.title or tab.title == "Untitled"):
            tab.title = os.path.basename(val)

    @property
    def out_path(self) -> str:
        tab = self.active_tab
        return tab.out_path if tab else ""

    @out_path.setter
    def out_path(self, val: str):
        tab = self._ensure_active_tab()
        tab.out_path = val

    @property
    def last_converted_path(self) -> str:
        tab = self.active_tab
        return tab.last_converted_path if tab else ""

    @last_converted_path.setter
    def last_converted_path(self, val: str):
        tab = self._ensure_active_tab()
        tab.last_converted_path = val

    @property
    def current_mode(self) -> str:
        tab = self.active_tab
        return tab.current_mode if tab else (self.default_mode or "MD -> Excel")

    @current_mode.setter
    def current_mode(self, val: str):
        tab = self._ensure_active_tab()
        tab.current_mode = val

    @property
    def full_content(self) -> str:
        tab = self.active_tab
        return tab.full_content if tab else ""

    @full_content.setter
    def full_content(self, val: str):
        tab = self._ensure_active_tab()
        tab.full_content = val

    @property
    def is_dirty(self) -> bool:
        tab = self.active_tab
        return tab.is_dirty if tab else False

    @is_dirty.setter
    def is_dirty(self, val: bool):
        tab = self._ensure_active_tab()
        tab.is_dirty = val

    @property
    def is_orphaned(self) -> bool:
        tab = self.active_tab
        return tab.is_orphaned if tab else False

    @is_orphaned.setter
    def is_orphaned(self, val: bool):
        tab = self._ensure_active_tab()
        tab.is_orphaned = val

    @property
    def undo_stack(self) -> list[str]:
        tab = self.active_tab
        return tab.undo_stack if tab else []

    @undo_stack.setter
    def undo_stack(self, val: list[str]):
        tab = self._ensure_active_tab()
        tab.undo_stack = val

    @property
    def redo_stack(self) -> list[str]:
        tab = self.active_tab
        return tab.redo_stack if tab else []

    @redo_stack.setter
    def redo_stack(self, val: list[str]):
        tab = self._ensure_active_tab()
        tab.redo_stack = val

    @property
    def is_undo_redo_op(self) -> bool:
        tab = self.active_tab
        return tab.is_undo_redo_op if tab else False

    @is_undo_redo_op.setter
    def is_undo_redo_op(self, val: bool):
        tab = self._ensure_active_tab()
        tab.is_undo_redo_op = val

    @property
    def search_matches(self) -> list[tuple[int, int]]:
        tab = self.active_tab
        return tab.search_matches if tab else []

    @search_matches.setter
    def search_matches(self, val: list[tuple[int, int]]):
        tab = self._ensure_active_tab()
        tab.search_matches = val

    @property
    def current_match_idx(self) -> int:
        tab = self.active_tab
        return tab.current_match_idx if tab else -1

    @current_match_idx.setter
    def current_match_idx(self, val: int):
        tab = self._ensure_active_tab()
        tab.current_match_idx = val
