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
    ("Supported Documents (*.md;*.docx;*.xlsx;*.xls;*.csv;*.pdf;*.html;*.htm;*.pptx;*.json;*.yaml;*.yml)", "*.md;*.docx;*.xlsx;*.xls;*.csv;*.pdf;*.html;*.htm;*.pptx;*.json;*.yaml;*.yml"),
    ("Markdown (*.md)", "*.md"),
    ("PowerPoint (*.pptx)", "*.pptx"),
    ("Excel (*.xlsx, *.xls)", "*.xlsx;*.xls"),
    ("Word (*.docx)", "*.docx"),
    ("CSV (*.csv)", "*.csv"),
    ("PDF (*.pdf)", "*.pdf"),
    ("HTML Document (*.html, *.htm)", "*.html;*.htm"),
    ("JSON (*.json)", "*.json"),
    ("YAML (*.yaml, *.yml)", "*.yaml;*.yml"),
    ("All Files (*.*)", "*.*"),
]

OUTPUT_FILETYPES = [
    ("Word (*.docx)", "*.docx"),
    ("PowerPoint (*.pptx)", "*.pptx"),
    ("Excel (*.xlsx)", "*.xlsx"),
    ("Markdown (*.md)", "*.md"),
    ("CSV (*.csv)", "*.csv"),
    ("PDF (*.pdf)", "*.pdf"),
    ("HTML Document (*.html)", "*.html"),
    ("JSON (*.json)", "*.json"),
    ("YAML (*.yaml, *.yml)", "*.yaml;*.yml"),
    ("All Files (*.*)", "*.*"),
]


def ensure_tcl_tk():
    """Configures Tcl/Tk library paths if running in a virtual environment on Windows."""
    try:
        from src.utils.env import setup_environment
        setup_environment()
    except Exception:
        pass


def pick_input_file_sync() -> str | None:
    """Synchronous worker that opens transient Windows Open File Dialog."""
    ensure_tcl_tk()
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


ARCHIVE_FILETYPES = [
    ("Supported Archives (*.zip;*.rar;*.7z;*.tar.gz;*.tgz;*.tar)", "*.zip;*.rar;*.7z;*.tar.gz;*.tgz;*.tbz2;*.tar;*.bz2"),
    ("ZIP Archive (*.zip)", "*.zip"),
    ("RAR Archive (*.rar)", "*.rar"),
    ("7-Zip Archive (*.7z)", "*.7z"),
    ("Tarball (*.tar.gz;*.tgz;*.tar)", "*.tar.gz;*.tgz;*.tar;*.tbz2;*.bz2"),
    ("All Files (*.*)", "*.*"),
]



def pick_archive_file_sync() -> str | None:
    """Synchronous worker that opens transient Windows Open File Dialog filtered for compressed archives."""
    ensure_tcl_tk()
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
            title="Select Compressed Archive File",
            filetypes=ARCHIVE_FILETYPES,
        )
        if selected_path:
            return os.path.normpath(selected_path)
    except Exception as e:
        print(f"[DEBUG] Native archive filedialog error: {e}")
    finally:
        if root:
            try:
                root.destroy()
            except Exception:
                pass
    return None


def pick_output_file_sync(default_ext: str = ".docx", initial_file: str = "output.docx", initial_dir: str | None = None) -> str | None:
    """Synchronous worker that opens transient Windows Save File Dialog."""
    ensure_tcl_tk()
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

        # Prioritize the matching default_ext filter to be the first selected in Windows dialog
        sorted_filetypes = list(OUTPUT_FILETYPES)
        if default_ext:
            ext_pat = f"*{default_ext.lower()}"
            matched = [ft for ft in OUTPUT_FILETYPES if ext_pat in ft[1].lower()]
            unmatched = [ft for ft in OUTPUT_FILETYPES if ft not in matched]
            sorted_filetypes = matched + unmatched

        save_path = filedialog.asksaveasfilename(
            title="Select Output Destination",
            defaultextension=default_ext,
            initialfile=initial_file,
            initialdir=initial_dir,
            filetypes=sorted_filetypes,
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
                allowed_extensions=["md", "docx", "xlsx", "xls", "csv", "pdf", "html", "htm", "pptx", "json", "yaml", "yml"],
            )
            if files:
                return files[0].path
            return None
    return await asyncio.to_thread(pick_input_file_sync)


async def pick_output_file_async(default_ext: str = ".docx", initial_file: str = "output.docx", initial_dir: str | None = None, page: ft.Page | None = None, picker: ft.FilePicker | None = None) -> str | None:
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
    return await asyncio.to_thread(pick_output_file_sync, default_ext, initial_file, initial_dir)


IMAGE_FILETYPES = [
    ("Image Files (*.png;*.jpg;*.jpeg;*.gif;*.webp;*.bmp;*.svg)", "*.png;*.jpg;*.jpeg;*.gif;*.webp;*.bmp;*.svg"),
    ("PNG Image (*.png)", "*.png"),
    ("JPEG Image (*.jpg;*.jpeg)", "*.jpg;*.jpeg"),
    ("WebP Image (*.webp)", "*.webp"),
    ("All Files (*.*)", "*.*"),
]


def pick_image_file_sync() -> str | None:
    """Synchronous worker that opens transient Windows Image File Dialog."""
    ensure_tcl_tk()
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


MEDIA_FILETYPES = [
    (
        "Audio & Video Files (*.mp3;*.wav;*.m4a;*.flac;*.aac;*.mp4;*.mkv;*.mov;*.webm;*.avi)",
        "*.mp3;*.wav;*.m4a;*.flac;*.aac;*.mp4;*.mkv;*.mov;*.webm;*.avi;*.ogg",
    ),
    ("All Files (*.*)", "*.*"),
]


def pick_media_file_sync() -> str | None:
    """Synchronous worker that opens transient Windows File Dialog for media files."""
    ensure_tcl_tk()
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
            title="Select Audio / Video File",
            filetypes=MEDIA_FILETYPES,
        )
        if selected_path:
            return os.path.normpath(selected_path)
    except Exception as e:
        print(f"[DEBUG] Native media filedialog error: {e}")
    finally:
        if root:
            try:
                root.destroy()
            except Exception:
                pass
    return None


async def pick_media_file_async() -> str | None:
    """Async wrapper running native media file picker dialog."""
    return await asyncio.to_thread(pick_media_file_sync)


def confirm_overwrite_sync(file_path: str) -> bool:
    """Prompts a native Windows messagebox asking user if they want to overwrite an existing file."""
    ensure_tcl_tk()
    try:
        import tkinter as tk
        from tkinter import messagebox
        enable_high_dpi_awareness()
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        file_name = os.path.basename(file_path)
        res = messagebox.askyesno(
            "Confirm File Overwrite",
            f"The target file '{file_name}' already exists at destination:\n\n{file_path}\n\nDo you want to overwrite it?",
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


def pick_directory_sync() -> str | None:
    """Synchronous worker that opens transient Windows Directory Picker Dialog."""
    ensure_tcl_tk()
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
        selected_dir = filedialog.askdirectory(
            title="Select Project / Workspace Directory"
        )
        if selected_dir:
            return os.path.normpath(selected_dir)
    except Exception as e:
        print(f"[DEBUG] Native directory filedialog error: {e}")
    finally:
        if root:
            try:
                root.destroy()
            except Exception:
                pass
    return None


async def pick_directory_async(page: ft.Page | None = None, picker: ft.FilePicker | None = None) -> str | None:
    """
    Async wrapper running directory picker dialog.
    Uses native Tkinter on Desktop; falls back to Flet FilePicker on Web/Mobile if provided.
    """
    if page and (page.web or page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)):
        if picker:
            path = await picker.get_directory_path(
                dialog_title="Select Project / Workspace Directory"
            )
            return path
    return await asyncio.to_thread(pick_directory_sync)




