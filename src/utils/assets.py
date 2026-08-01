"""
Asset path resolution utility for DocumentConvertTool.
Supports both local development environment and PyInstaller executable bundle paths.
"""
import os
import sys


def get_asset_path(relative_path: str) -> str:
    """
    Returns absolute path to resource asset.
    Handles PyInstaller sys._MEIPASS runtime directory.
    """
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, "assets", relative_path)


def resolve_icon_path(filename: str) -> str:
    """
    Finds absolute path of an icon or logo file.
    Searches in assets/, assets/icons/, and root directory.
    """
    # 1. Check in assets/
    p1 = get_asset_path(filename)
    if os.path.exists(p1):
        return p1
    # 2. Check in assets/icons/
    p2 = get_asset_path(os.path.join("icons", filename))
    if os.path.exists(p2):
        return p2
    # 3. Check in root directory
    p3 = os.path.abspath(filename)
    if os.path.exists(p3):
        return p3
    return ""


def load_image_bytes(file_path: str) -> bytes | str:
    """
    Loads image as raw bytes for Flet ft.Image(src=bytes).
    Per official Flet docs: src can accept raw bytes directly without data:image header bugs.
    """
    resolved = resolve_icon_path(file_path) if not os.path.isabs(file_path) else file_path
    target = resolved if resolved and os.path.exists(resolved) else file_path
    if os.path.exists(target):
        try:
            with open(target, "rb") as f:
                return f.read()
        except Exception:
            pass
    return file_path
