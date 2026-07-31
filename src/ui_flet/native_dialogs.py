import os
import sys
import asyncio
import flet as ft

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
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("[DEBUG] tkinter not available on this platform")
        return None

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
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("[DEBUG] tkinter not available on this platform")
        return None

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
            filetypes=OUTPUT_FILETYPES,
            confirmoverwrite=True,
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


async def pick_input_file_async(page: ft.Page | None = None, picker: ft.FilePicker | None = None) -> str | None:
    """
    Async wrapper running input dialog.
    Uses native Tkinter on Desktop; falls back to Flet FilePicker on Web/Mobile if provided.
    """
    if page and (page.web or page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)):
        if picker:
            files = await picker.pick_files(
                dialog_title="Select Input Document",
                allow_multiple=False,
                allowed_extensions=["md", "docx", "xlsx", "xls", "csv", "pdf", "html", "htm"],
            )
            if files:
                return files[0].path
            return None
    return await asyncio.to_thread(pick_input_file_sync)


async def pick_output_file_async(default_ext: str = ".docx", initial_file: str = "output.docx", page: ft.Page | None = None, picker: ft.FilePicker | None = None) -> str | None:
    """
    Async wrapper running output dialog.
    Uses native Tkinter on Desktop; falls back to Flet FilePicker on Web/Mobile if provided.
    """
    if page and (page.web or page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)):
        if picker:
            path = await picker.save_file(
                dialog_title="Select Output Destination",
                file_name=initial_file,
                allowed_extensions=[default_ext.lstrip(".")],
            )
            return path
    return await asyncio.to_thread(pick_output_file_sync, default_ext, initial_file)


IMAGE_FILETYPES = [
    ("Image Files (*.png;*.jpg;*.jpeg;*.gif;*.webp;*.bmp;*.svg)", "*.png;*.jpg;*.jpeg;*.gif;*.webp;*.bmp;*.svg"),
    ("PNG Image (*.png)", "*.png"),
    ("JPEG Image (*.jpg;*.jpeg)", "*.jpg;*.jpeg"),
    ("WebP Image (*.webp)", "*.webp"),
    ("All Files (*.*)", "*.*"),
]


def pick_image_file_sync() -> str | None:
    """Synchronous worker that opens transient Windows Open Image File Dialog."""
    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print("[DEBUG] tkinter not available on this platform")
        return None

    enable_high_dpi_awareness()
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected_path = filedialog.askopenfilename(
            title="Select Image File to Insert",
            filetypes=IMAGE_FILETYPES
        )
        if selected_path:
            return os.path.normpath(selected_path)
    except Exception as e:
        print(f"[DEBUG] Native image filedialog error: {e}")
    finally:
        if root:
            try:
                root.destroy()
            except Exception:
                pass
    return None


async def pick_image_file_async(page: ft.Page | None = None, picker: ft.FilePicker | None = None) -> str | None:
    """Async wrapper running image picker dialog."""
    if page and (page.web or page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)):
        if picker:
            files = await picker.pick_files(
                dialog_title="Select Image File to Insert",
                allow_multiple=False,
                allowed_extensions=["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"],
            )
            if files:
                return files[0].path
            return None
    return await asyncio.to_thread(pick_image_file_sync)


def confirm_overwrite_sync(file_path: str) -> bool:
    """Prompts a native Windows messagebox asking user if they want to overwrite an existing file."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        enable_high_dpi_awareness()
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        res = messagebox.askyesno(
            "Confirm Overwrite",
            f"The file '{os.path.basename(file_path)}' already exists.\n\nDo you want to overwrite it?",
            parent=root
        )
        root.destroy()
        return res
    except Exception as e:
        print(f"[DEBUG] confirm_overwrite_sync error: {e}")
        return True


async def confirm_overwrite_async(file_path: str) -> bool:
    """Async wrapper for confirm_overwrite_sync."""
    return await asyncio.to_thread(confirm_overwrite_sync, file_path)



