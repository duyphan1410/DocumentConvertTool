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
