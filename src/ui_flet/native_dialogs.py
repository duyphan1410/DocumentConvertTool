import os
import sys
import asyncio
import tkinter as tk
from tkinter import filedialog

def enable_high_dpi_awareness():
    """Ensures Windows process DPI awareness Per-Monitor v2 to render sharp Win32 dialogs."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware v2
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

INPUT_FILETYPES = [
    ("Supported Documents (*.md;*.docx;*.xlsx;*.xls;*.csv;*.pdf;*.html;*.htm)", "*.md;*.docx;*.xlsx;*.xls;*.csv;*.pdf;*.html;*.htm"),
    ("Markdown (*.md)", "*.md"),
    ("Excel (*.xlsx, *.xls)", "*.xlsx;*.xls"),
    ("Word (*.docx)", "*.docx"),
    ("CSV (*.csv)", "*.csv"),
    ("PDF (*.pdf)", "*.pdf"),
    ("HTML Document (*.html, *.htm)", "*.html;*.htm"),
    ("All Files (*.*)", "*.*"),
]

OUTPUT_FILETYPES = [
    ("Word (*.docx)", "*.docx"),
    ("Excel (*.xlsx)", "*.xlsx"),
    ("Markdown (*.md)", "*.md"),
    ("CSV (*.csv)", "*.csv"),
    ("PDF (*.pdf)", "*.pdf"),
    ("HTML Document (*.html)", "*.html"),
    ("All Files (*.*)", "*.*"),
]


def pick_input_file_sync() -> str | None:
    """Synchronous worker that opens transient Windows Open File Dialog."""
    enable_high_dpi_awareness()
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected_path = filedialog.askopenfilename(
            title="Select Input Document",
            filetypes=INPUT_FILETYPES
        )
        if selected_path:
            return os.path.normpath(selected_path)
    except Exception as e:
        print(f"[DEBUG] Native input filedialog error: {e}")
    finally:
        if root:
            try:
                root.destroy()
            except Exception:
                pass
    return None


def pick_output_file_sync(default_ext: str = ".docx", initial_file: str = "output.docx") -> str | None:
    """Synchronous worker that opens transient Windows Save File Dialog."""
    enable_high_dpi_awareness()
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        save_path = filedialog.asksaveasfilename(
            title="Select Output Destination",
            defaultextension=default_ext,
            initialfile=initial_file,
            filetypes=OUTPUT_FILETYPES
        )
        if save_path:
            return os.path.normpath(save_path)
    except Exception as e:
        print(f"[DEBUG] Native output filedialog error: {e}")
    finally:
        if root:
            try:
                root.destroy()
            except Exception:
                pass
    return None


async def pick_input_file_async() -> str | None:
    """Async wrapper running transient input dialog in a background thread via asyncio.to_thread."""
    return await asyncio.to_thread(pick_input_file_sync)


async def pick_output_file_async(default_ext: str = ".docx", initial_file: str = "output.docx") -> str | None:
    """Async wrapper running transient output dialog in a background thread via asyncio.to_thread."""
    return await asyncio.to_thread(pick_output_file_sync, default_ext, initial_file)
