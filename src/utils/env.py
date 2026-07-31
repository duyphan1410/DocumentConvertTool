import sys
import os

def setup_environment():
    # 1. Prevent UnicodeEncodeError when printing UTF-8 characters to standard output in Windows console
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')  # type: ignore
        except AttributeError:
            pass
    if sys.stderr is not None:
        try:
            sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')  # type: ignore
        except AttributeError:
            pass

    # 2. Automatically configure Tcl/Tk environment paths for Windows Python interpreters
    tcl_base = os.path.join(sys.base_prefix, "tcl")
    if os.path.exists(tcl_base):
        for entry in os.listdir(tcl_base):
            full = os.path.join(tcl_base, entry)
            if entry.startswith("tcl") and os.path.isdir(full):
                os.environ["TCL_LIBRARY"] = full
            if entry.startswith("tk") and os.path.isdir(full):
                os.environ["TK_LIBRARY"] = full

    # 3. Enable Windows High-DPI awareness at startup (Per-Monitor v2)
    # Prevents blurry text on launch & eliminates dynamic DPI reload flickers when top-level windows open
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


def open_file_or_folder_foreground(target_path: str, is_folder: bool = False):
    """
    Opens a file or folder and guarantees bringing the target application window
    to absolute foreground focus (Z-Index #1) even if Chrome/VS Code or other apps
    are open fullscreen on Windows.
    """
    target_path = os.path.normpath(os.path.abspath(target_path))
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Target path does not exist: {target_path}")

    if sys.platform != "win32":
        import subprocess
        if sys.platform == "darwin":
            cmd = ["open", "-R", target_path] if is_folder else ["open", target_path]
        else:
            folder = target_path if is_folder else os.path.dirname(target_path)
            cmd = ["xdg-open", folder] if is_folder else ["xdg-open", target_path]
        subprocess.Popen(cmd)
        return

    # --- WINDOWS WIN32 FOREGROUND ENFORCEMENT ---
    import ctypes
    import ctypes.wintypes
    import subprocess
    import threading
    import time

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Set explicit ctypes argtypes & restypes
    user32.GetWindowThreadProcessId.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD

    user32.SetWindowPos.argtypes = [
        ctypes.wintypes.HWND, ctypes.wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.wintypes.UINT
    ]
    user32.SetWindowPos.restype = ctypes.wintypes.BOOL

    # 1. Temporarily disable OS Foreground Lock timeout
    try:
        SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
        SPIF_SENDWININICHANGE = 0x02
        user32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0, 0, SPIF_SENDWININICHANGE)
    except Exception:
        pass

    # 2. Grant foreground lock permission to custom/all processes
    try:
        user32.AllowSetForegroundWindow(-1)  # ASFW_CUSTOM = -1
    except Exception:
        pass

    # 3. Launch file / folder
    if is_folder:
        subprocess.Popen(f'explorer /select,"{target_path}"')
    else:
        os.startfile(target_path)

    # 4. Background thread to track down target HWND and force foreground Z-Index #1
    file_name = os.path.basename(target_path).lower()
    base_name = os.path.splitext(file_name)[0].lower()
    ext = os.path.splitext(file_name)[1].lower()

    target_classes = []
    if ext in (".doc", ".docx"):
        target_classes.append("opusapp")
    elif ext in (".xls", ".xlsx", ".csv"):
        target_classes.append("xlmain")
    elif ext in (".ppt", ".pptx"):
        target_classes.append("pptframeclass")
    if is_folder:
        target_classes.extend(["cabinetwclass", "explorewclass"])

    def poll_and_force_foreground():
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

        for attempt in range(20):  # Poll up to 1.0 second (20 * 50ms)
            time.sleep(0.05)
            found_hwnds = []

            def enum_windows_callback(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    title = ""
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value.lower()

                    class_buff = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_buff, 256)
                    cls_name = class_buff.value.lower()

                    # Strict match strategy:
                    # Only match if full file name is in title, OR if window class is specifically Word/Excel/PPT/Explorer
                    is_target_class = (cls_name in target_classes) if target_classes else False

                    if file_name and file_name in title:
                        found_hwnds.append(hwnd)
                    elif is_target_class:
                        # For Word/Excel/Explorer, verify title contains base_name if title is present
                        if not title or not base_name or base_name in title or (ext and ext in title):
                            found_hwnds.append(hwnd)
                return True

            cb = WNDENUMPROC(enum_windows_callback)
            user32.EnumWindows(cb, 0)

            if found_hwnds:
                # Take only the first matching window to avoid cycling through multiple windows
                hwnd = found_hwnds[0]
                try:
                    # Restore window if minimized
                    SW_RESTORE = 9
                    user32.ShowWindow(hwnd, SW_RESTORE)

                    # Win32 ALT key unlock trick
                    VK_MENU = 0x12
                    KEYEVENTF_KEYUP = 0x0002
                    user32.keybd_event(VK_MENU, 0, 0, 0)
                    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

                    # AttachThreadInput trick
                    fg_hwnd = user32.GetForegroundWindow()
                    fg_pid = ctypes.wintypes.DWORD()
                    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, ctypes.byref(fg_pid)) if fg_hwnd else 0
                    cur_thread = kernel32.GetCurrentThreadId()

                    if fg_thread and fg_thread != cur_thread:
                        user32.AttachThreadInput(cur_thread, fg_thread, True)

                    HWND_TOPMOST = ctypes.wintypes.HWND(-1)
                    HWND_NOTOPMOST = ctypes.wintypes.HWND(-2)
                    SWP_NOSIZE = 0x0001
                    SWP_NOMOVE = 0x0002
                    SWP_SHOWWINDOW = 0x0040

                    # Force top-most Z-order then return to normal stack
                    user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                    user32.SetForegroundWindow(hwnd)
                    user32.SwitchToThisWindow(hwnd, True)

                    if fg_thread and fg_thread != cur_thread:
                        user32.AttachThreadInput(cur_thread, fg_thread, False)
                    print(f"[DEBUG] Successfully forced foreground for HWND {hwnd} (file: '{file_name}')")
                except Exception as ex:
                    print(f"[DEBUG] Error forcing foreground for HWND {hwnd}: {ex}")
                break

    threading.Thread(target=poll_and_force_foreground, daemon=True).start()

