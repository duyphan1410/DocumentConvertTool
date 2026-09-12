"""
Security Guard and Path Traversal Prevention for DocConvert Local MCP Server.
Ensures zero-leakage, ID-only surface validation, strict UUID v4, and workspace boundary containment.
"""
from __future__ import annotations
import os
import json
import uuid
from typing import Optional, Tuple, Any

# Supported target formats for MD -> Target programmatic conversion
SUPPORTED_CONVERT_FORMATS = frozenset([
    "docx", "pdf", "html", "json", "yaml", "csv", "txt"
])

# Internal cache state for settings.json to avoid stale workspace and minimize redundant file I/O
_cached_settings_mtime: Optional[float] = None
_cached_settings_workspace: Optional[str] = None


def get_active_workspace_dir() -> Optional[str]:
    """
    Resolves active workspace directory from environment variable or AppData settings.json.
    Caches based on file mtime to stay fresh when workspace is switched in GUI app.
    """
    global _cached_settings_mtime, _cached_settings_workspace

    # 1. Highest priority: explicit environment variable
    env_ws = os.getenv("DOCCONVERT_WORKSPACE")
    if env_ws and os.path.isdir(env_ws):
        return os.path.normpath(os.path.abspath(env_ws))

    # 2. Read from settings.json with mtime freshness check
    appdata = os.getenv("APPDATA", os.path.expanduser("~"))
    settings_path = os.path.join(appdata, "DocConvert", "settings.json")

    if os.path.exists(settings_path):
        try:
            current_mtime = os.path.getmtime(settings_path)
            if _cached_settings_mtime is not None and current_mtime == _cached_settings_mtime:
                return _cached_settings_workspace

            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cand = data.get("workspace_folder") or data.get("last_workspace")
                if cand and os.path.isdir(cand):
                    _cached_settings_mtime = current_mtime
                    _cached_settings_workspace = os.path.normpath(os.path.abspath(cand))
                    return _cached_settings_workspace
                else:
                    _cached_settings_mtime = current_mtime
                    _cached_settings_workspace = None
                    return None
        except Exception:
            _cached_settings_mtime = None
            _cached_settings_workspace = None
            return None

    _cached_settings_mtime = None
    _cached_settings_workspace = None
    return None


def is_path_in_workspace(file_path: str, workspace_dir: Optional[str]) -> bool:
    """
    Verifies if file_path is strictly contained within workspace_dir.
    Handles Windows cross-drive cases safely (returns False on ValueError).
    """
    if not workspace_dir:
        return True

    norm_file = os.path.normpath(os.path.abspath(file_path))
    norm_ws = os.path.normpath(os.path.abspath(workspace_dir))

    try:
        common = os.path.commonpath([norm_file, norm_ws])
        return common == norm_ws
    except ValueError:
        # Raised on Windows when paths are on different drive letters (e.g. C: vs D:)
        return False


def is_valid_uuid(val: Any) -> bool:
    """
    Validates strictly for standard UUID version 4.
    Rejects Nil UUID, UUID v1/v3/v5, and non-UUID formats.
    """
    if not val or not isinstance(val, str):
        return False
    try:
        u = uuid.UUID(str(val).strip())
        return u.version == 4
    except (ValueError, AttributeError):
        return False


def resolve_safe_doc_path(
    doc_id: str,
    index: Any
) -> Tuple[bool, Optional[str], Optional[dict]]:
    """
    Prevents path traversal by enforcing UUID v4, SQLite index existence,
    disk existence, AND active workspace boundary containment.
    
    Returns:
        (is_valid_and_exists, absolute_file_path, document_record_dict)
    """
    if not is_valid_uuid(doc_id):
        return False, None, None

    doc = index.get_document_by_id(doc_id)
    if not doc:
        return False, None, None

    stored_path = doc.get("path")
    if not stored_path or not isinstance(stored_path, str):
        return False, None, doc

    # Normalize path and check file existence on physical disk
    norm_path = os.path.normpath(os.path.abspath(stored_path))
    if not os.path.exists(norm_path) or not os.path.isfile(norm_path):
        return False, None, doc

    # Enforce active workspace boundary containment if configured
    ws = get_active_workspace_dir()
    if ws and not is_path_in_workspace(norm_path, ws):
        return False, None, doc

    return True, norm_path, doc


def sanitize_target_format(target_format: str) -> str:
    """
    Validates and normalizes target export format.
    Raises ValueError if format is unsupported.
    """
    if not target_format or not isinstance(target_format, str):
        raise ValueError("Target format must be a non-empty string.")
    
    clean_fmt = target_format.strip().lower().lstrip(".")
    if clean_fmt not in SUPPORTED_CONVERT_FORMATS:
        valid_list = ", ".join(sorted(SUPPORTED_CONVERT_FORMATS))
        raise ValueError(f"Unsupported target format: '{target_format}'. Supported formats: {valid_list}")
    
    return clean_fmt
