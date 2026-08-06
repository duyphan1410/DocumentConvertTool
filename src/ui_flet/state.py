"""
Centralized AppState Management for DocumentConvertTool Flet UI.
"""
from dataclasses import dataclass, field
import flet as ft


@dataclass
class AppState:
    in_path: str = ""
    out_path: str = ""
    last_converted_path: str = ""
    current_mode: str = "MD -> Excel"
    current_palette: str = "Deep Ocean"
    current_theme_mode: str = "System"
    full_content: str = ""
    is_dirty: bool = False
    is_processing: bool = False
    status_text: str = "Ready"
    status_color: str | None = None

    # Undo/Redo stack state
    undo_stack: list[str] = field(default_factory=list)
    redo_stack: list[str] = field(default_factory=list)
    is_undo_redo_op: bool = False

    # Search panel state
    search_matches: list[tuple[int, int]] = field(default_factory=list)
    current_match_idx: int = -1

    # User Settings (persisted to %APPDATA%\DocConvert\settings.json)
    autosave_enabled: bool = True
    autosave_interval_sec: int = 30
    default_mode: str = "MD -> Excel"
    editor_font_size: int = 13
    show_line_numbers: bool = False
    word_wrap: bool = True
    language: str = "en"
