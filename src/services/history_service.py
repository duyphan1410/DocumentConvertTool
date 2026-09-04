"""
History Service for DocumentConvertTool.
Manages recent files and folders history, persistence to %APPDATA%/DocConvert/recent_history.json,
LRU eviction, pinning, search filtering, and disk existence validation.
"""
import os
import json
import time
import threading
from typing import List, Dict, Any, Optional

_appdata = os.getenv("APPDATA", os.path.expanduser("~"))
HISTORY_FILE_PATH = os.path.join(_appdata, "DocConvert", "recent_history.json")

MAX_RECENT_FILES = 20
MAX_RECENT_FOLDERS = 10


class HistoryService:
    _instance: Optional["HistoryService"] = None
    _lock = threading.Lock()

    def __init__(self, storage_path: str = HISTORY_FILE_PATH):
        self.storage_path = storage_path
        self._lock = threading.Lock()
        self._files: List[Dict[str, Any]] = []
        self._folders: List[Dict[str, Any]] = []
        self._load()

    @classmethod
    def get_instance(cls, storage_path: str = HISTORY_FILE_PATH) -> "HistoryService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = HistoryService(storage_path)
        return cls._instance

    def _load(self) -> None:
        """Loads history from disk with graceful fallback on corruption."""
        if not os.path.isfile(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._files = data.get("files", [])
            self._folders = data.get("folders", [])
        except Exception as exc:
            print(f"[HistoryService] Failed to load history: {exc}")
            self._files = []
            self._folders = []

    def _save(self) -> None:
        """Persists history to disk safely."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = {
                "version": 1,
                "files": self._files,
                "folders": self._folders,
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            print(f"[HistoryService] Failed to save history: {exc}")

    def add_file(self, file_path: str, mode: str = "") -> None:
        """Adds or promotes a file path in the recent files list."""
        if not file_path:
            return
        norm_path = os.path.normpath(file_path)
        with self._lock:
            # Check if already exists
            existing_idx = next(
                (i for i, item in enumerate(self._files) if os.path.normpath(item.get("path", "")) == norm_path),
                -1,
            )
            is_pinned = False
            if existing_idx >= 0:
                item = self._files.pop(existing_idx)
                is_pinned = item.get("pinned", False)
                mode = mode or item.get("mode", "")

            name = os.path.basename(norm_path) or norm_path
            new_entry = {
                "path": norm_path,
                "name": name,
                "type": "file",
                "mode": mode,
                "last_opened": time.time(),
                "pinned": is_pinned,
            }

            if is_pinned:
                # Insert at top among pinned items
                self._files.insert(0, new_entry)
            else:
                # Find index after all pinned items
                first_unpinned_idx = next(
                    (i for i, item in enumerate(self._files) if not item.get("pinned", False)),
                    len(self._files),
                )
                self._files.insert(first_unpinned_idx, new_entry)

            # Enforce max limit
            if len(self._files) > MAX_RECENT_FILES:
                self._files = self._files[:MAX_RECENT_FILES]

            self._save()

    def add_folder(self, folder_path: str) -> None:
        """Adds or promotes a folder path in the recent folders list."""
        if not folder_path:
            return
        norm_path = os.path.normpath(folder_path)
        with self._lock:
            existing_idx = next(
                (i for i, item in enumerate(self._folders) if os.path.normpath(item.get("path", "")) == norm_path),
                -1,
            )
            is_pinned = False
            if existing_idx >= 0:
                item = self._folders.pop(existing_idx)
                is_pinned = item.get("pinned", False)

            name = os.path.basename(norm_path) or norm_path
            new_entry = {
                "path": norm_path,
                "name": name,
                "type": "folder",
                "last_opened": time.time(),
                "pinned": is_pinned,
            }

            if is_pinned:
                self._folders.insert(0, new_entry)
            else:
                first_unpinned_idx = next(
                    (i for i, item in enumerate(self._folders) if not item.get("pinned", False)),
                    len(self._folders),
                )
                self._folders.insert(first_unpinned_idx, new_entry)

            if len(self._folders) > MAX_RECENT_FOLDERS:
                self._folders = self._folders[:MAX_RECENT_FOLDERS]

            self._save()

    def remove_item(self, path: str, item_type: str = "file") -> None:
        """Removes a single file or folder from history."""
        norm_path = os.path.normpath(path)
        with self._lock:
            if item_type in ("file", "all"):
                self._files = [f for f in self._files if os.path.normpath(f.get("path", "")) != norm_path]
            if item_type in ("folder", "all"):
                self._folders = [f for f in self._folders if os.path.normpath(f.get("path", "")) != norm_path]
            self._save()

    def toggle_pin(self, path: str, item_type: str = "file") -> bool:
        """Toggles pinned status of an item and re-sorts list. Returns new pinned state."""
        norm_path = os.path.normpath(path)
        with self._lock:
            target_list = self._files if item_type == "file" else self._folders
            for item in target_list:
                if os.path.normpath(item.get("path", "")) == norm_path:
                    new_pinned = not item.get("pinned", False)
                    item["pinned"] = new_pinned
                    # Re-sort list: pinned first (by last_opened desc), then unpinned (by last_opened desc)
                    target_list.sort(key=lambda x: (not x.get("pinned", False), -x.get("last_opened", 0)))
                    self._save()
                    return new_pinned
        return False

    def clear_all(self, item_type: str = "all") -> None:
        """Clears recent files, folders, or both."""
        with self._lock:
            if item_type in ("file", "all"):
                self._files = []
            if item_type in ("folder", "all"):
                self._folders = []
            self._save()

    def get_items(self, filter_type: str = "all", query: str = "") -> List[Dict[str, Any]]:
        """
        Retrieves items matching filter_type ('all', 'files', 'folders') and query search string.
        Dynamically annotates each item with 'exists' (bool).
        """
        with self._lock:
            items: List[Dict[str, Any]] = []
            if filter_type in ("all", "files"):
                items.extend(list(self._files))
            if filter_type in ("all", "folders"):
                items.extend(list(self._folders))

            # If combined 'all', sort by pinned first, then last_opened desc
            if filter_type == "all":
                items.sort(key=lambda x: (not x.get("pinned", False), -x.get("last_opened", 0)))

            if query:
                q_lower = query.strip().lower()
                items = [
                    item for item in items
                    if q_lower in item.get("name", "").lower() or q_lower in item.get("path", "").lower()
                ]

            # Annotate existence without mutating state directly
            result = []
            for it in items:
                item_copy = dict(it)
                p = item_copy.get("path", "")
                item_copy["exists"] = os.path.exists(p) if p else False
                result.append(item_copy)

            return result
