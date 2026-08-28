"""
Safe File Operations Helper for DocConvert Workspace.
Provides Recycle Bin deletion via Win32 SHFileOperationW, Windows Explorer reveal,
and Windows reserved device name & forbidden character sanitization.
"""
from __future__ import annotations

import os
import sys
import subprocess
from typing import Tuple, Optional

# Windows Reserved Device Names (case-insensitive)
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}

# Windows Invalid Filename Characters
FORBIDDEN_CHARS = set(r'\/:*?"<>|')


def sanitize_filename(name: str) -> Tuple[bool, str]:
    """
    Validates a file or directory name against Windows naming constraints.
    Returns (is_valid, error_message).
    """
    if not name or not name.strip():
        return False, "Filename cannot be empty."

    # Check leading/trailing whitespace or trailing dot in raw name
    if name.endswith(" ") or name.startswith(" ") or name.endswith("."):
        return False, "Filename cannot start/end with whitespace or a trailing dot."

    trimmed = name.strip()

    # Check length
    if len(trimmed) > 255:
        return False, "Filename is too long (maximum 255 characters)."

    # Check forbidden characters
    invalid_found = [c for c in trimmed if c in FORBIDDEN_CHARS]
    if invalid_found:
        return False, f"Filename cannot contain characters: {' '.join(set(invalid_found))}"

    # Check reserved device names (e.g., CON, con.txt, CON.txt.bak, aux.md)
    # Windows treats any name whose root before the first dot matches a device name as reserved
    primary_stem = trimmed.split(".")[0].strip().upper()
    full_upper = trimmed.upper()
    if primary_stem in RESERVED_NAMES or full_upper in RESERVED_NAMES:
        return False, f"'{trimmed}' is a reserved Windows system device name."

    return True, ""


def safe_delete_to_recycle_bin(path: str) -> bool:
    """
    Moves a file or directory to the OS Recycle Bin / Trash.
    Guarantees zero data loss on accidental delete.
    
    Raises:
        FileNotFoundError: If target path does not exist.
        OSError: If deletion fails or is aborted.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Target path does not exist: {path}")

    abs_path = os.path.abspath(path)

    # 1. Native Windows Win32 SHFileOperationW with FOF_ALLOWUNDO
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", wintypes.WORD),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", wintypes.LPVOID),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        FO_DELETE = 0x0003
        FOF_ALLOWUNDO = 0x0040
        FOF_NOCONFIRMATION = 0x0010
        FOF_SILENT = 0x0004

        # Create real Unicode buffer with double-null termination
        buf = ctypes.create_unicode_buffer(f"{abs_path}\0")

        file_op = SHFILEOPSTRUCTW()
        file_op.hwnd = None
        file_op.wFunc = FO_DELETE
        file_op.pFrom = ctypes.cast(buf, wintypes.LPCWSTR)
        file_op.pTo = None
        file_op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT
        file_op.fAnyOperationsAborted = False
        file_op.hNameMappings = None
        file_op.lpszProgressTitle = None

        shell32 = ctypes.windll.shell32
        shell32.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
        shell32.SHFileOperationW.restype = ctypes.c_int

        res = shell32.SHFileOperationW(ctypes.byref(file_op))

        if res != 0 or file_op.fAnyOperationsAborted:
            raise OSError(f"Win32 SHFileOperationW delete failed (code: {res}, aborted: {file_op.fAnyOperationsAborted})")

        return True

    # 2. Non-Windows fallback (send2trash if installed)
    try:
        import send2trash
        send2trash.send2trash(abs_path)
        return True
    except ImportError:
        raise OSError("Safe deletion is not supported on this platform without the 'send2trash' package.")


def reveal_in_windows_explorer(path: str) -> bool:
    """
    Opens Windows File Explorer and selects/highlights the specified file or folder.
    Guarantees injection-safe execution using subprocess list arguments.
    """
    if not os.path.exists(path):
        return False

    norm_path = os.path.normpath(os.path.abspath(path))

    if sys.platform == "win32":
        try:
            # Single argument f"/select,{norm_path}"
            subprocess.Popen(["explorer.exe", f"/select,{norm_path}"], shell=False)
            return True
        except Exception as ex:
            print(f"[file_ops] Failed to reveal in Explorer: {ex}")
            return False
    elif sys.platform == "darwin":
        try:
            subprocess.Popen(["open", "-R", norm_path], shell=False)
            return True
        except Exception:
            return False
    else:
        try:
            # Linux xdg-open directory
            target_dir = norm_path if os.path.isdir(norm_path) else os.path.dirname(norm_path)
            subprocess.Popen(["xdg-open", target_dir], shell=False)
            return True
        except Exception:
            return False
