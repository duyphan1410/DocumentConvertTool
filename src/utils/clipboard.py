"""
Universal Unicode-Safe Clipboard Helper for Windows, macOS, and Linux.
Guarantees Vietnamese and multi-byte UTF-8/UTF-16 characters are copied without mojibake.
"""
import sys
import subprocess
from typing import Optional


def set_clipboard_text(text: str, page: Optional[object] = None) -> bool:
    """
    Sets text to the OS system clipboard with guaranteed UTF-16 / Unicode support.
    """
    if not text:
        return False

    # 1. Native Windows Win32 API with CF_UNICODETEXT (Zero mojibake, zero subprocess lag)
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.EmptyClipboard.argtypes = []
            user32.EmptyClipboard.restype = wintypes.BOOL
            user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
            user32.SetClipboardData.restype = wintypes.HANDLE
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype = wintypes.BOOL

            kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
            kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = wintypes.LPVOID
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL

            utf16_bytes = text.encode("utf-16le") + b"\x00\x00"
            h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(utf16_bytes))
            if h_mem:
                ptr = kernel32.GlobalLock(h_mem)
                if ptr:
                    ctypes.memmove(ptr, utf16_bytes, len(utf16_bytes))
                    kernel32.GlobalUnlock(h_mem)
                    if user32.OpenClipboard(None):
                        user32.EmptyClipboard()
                        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                        user32.CloseClipboard()
                        # Also sync Flet page clipboard if available
                        if page:
                            _safe_flet_page_clipboard(page, text)
                        return True
        except Exception as ex:
            print(f"[DEBUG] Win32 clipboard error: {ex}")

    # 2. macOS native pbcopy
    elif sys.platform == "darwin":
        try:
            subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True, timeout=1)
            if page:
                _safe_flet_page_clipboard(page, text)
            return True
        except Exception:
            pass

    # 3. Linux xclip / xsel
    elif sys.platform.startswith("linux"):
        try:
            subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode("utf-8"), check=True, timeout=1)
            if page:
                _safe_flet_page_clipboard(page, text)
            return True
        except Exception:
            try:
                subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode("utf-8"), check=True, timeout=1)
                if page:
                    _safe_flet_page_clipboard(page, text)
                return True
            except Exception:
                pass

    # 4. Fallback to Flet Page API
    if page:
        return _safe_flet_page_clipboard(page, text)

    return False


def _safe_flet_page_clipboard(page: object, text: str) -> bool:
    try:
        setattr(page, "clipboard", text)
        return True
    except Exception:
        try:
            if hasattr(page, "set_clipboard"):
                page.set_clipboard(text)
                return True
        except Exception:
            pass
    return False


def get_clipboard_text(page: Optional[object] = None) -> str:
    """
    Retrieves Unicode text directly from the OS system clipboard.
    Supports Windows Win32 API (CF_UNICODETEXT), macOS pbpaste, Linux xclip/xsel.
    """
    # 1. Native Windows Win32 API
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            CF_UNICODETEXT = 13
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            user32.OpenClipboard.argtypes = [wintypes.HWND]
            user32.OpenClipboard.restype = wintypes.BOOL
            user32.GetClipboardData.argtypes = [wintypes.UINT]
            user32.GetClipboardData.restype = wintypes.HANDLE
            user32.CloseClipboard.argtypes = []
            user32.CloseClipboard.restype = wintypes.BOOL

            kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalLock.restype = wintypes.LPVOID
            kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
            kernel32.GlobalUnlock.restype = wintypes.BOOL

            if user32.OpenClipboard(None):
                h_data = user32.GetClipboardData(CF_UNICODETEXT)
                if h_data:
                    ptr = kernel32.GlobalLock(h_data)
                    if ptr:
                        text = ctypes.c_wchar_p(ptr).value or ""
                        kernel32.GlobalUnlock(h_data)
                        user32.CloseClipboard()
                        return text
                user32.CloseClipboard()
        except Exception as ex:
            print(f"[DEBUG] Win32 get_clipboard error: {ex}")

    # 2. macOS pbpaste
    elif sys.platform == "darwin":
        try:
            res = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True, timeout=1)
            return res.stdout or ""
        except Exception:
            pass

    # 3. Linux xclip / xsel
    elif sys.platform.startswith("linux"):
        try:
            res = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, check=True, timeout=1)
            return res.stdout or ""
        except Exception:
            try:
                res = subprocess.run(["xsel", "--clipboard", "--output"], capture_output=True, text=True, check=True, timeout=1)
                return res.stdout or ""
            except Exception:
                pass

    # 4. Fallback to Flet page clipboard if available
    if page:
        try:
            if hasattr(page, "get_clipboard"):
                val = page.get_clipboard()
                if val:
                    return str(val)
        except Exception:
            pass

    return ""
