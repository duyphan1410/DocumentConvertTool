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
    to foreground focus (Z-Index #1) using a 4-layer fallback architecture:
    1. System Input Simulation: ALT key event tap (keybd_event VK_MENU) to instantly unlock Windows ForegroundLockTimeout.
    2. HWND Discovery: Strict window title matching combined with target class priority.
    3. Primary Elevation: Explicit AllowSetForegroundWindow(target_pid) + AttachThreadInput + SetForegroundWindow.
    4. Notification Fallback: FlashWindowEx taskbar flash if OS restricts background focus transfer.
    """
    target_path = os.path.normpath(os.path.abspath(target_path))
    if not os.path.exists(target_path):
        raise FileNotFoundError(f"Target path does not exist: {target_path}")

    if sys.platform != "win32":
        import subprocess
        if sys.platform == "darwin":
            cmd = ["open", "-R", target_path] if is_folder else ["open", target_path]
        else:
            folder = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
            cmd = ["xdg-open", folder] if is_folder else ["xdg-open", target_path]
        subprocess.Popen(cmd)
        return

    # --- WINDOWS WIN32 FOREGROUND ENFORCEMENT ---
    import ctypes
    import ctypes.wintypes
    import threading
    import time

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # Win32 Constants & Structs
    SPI_GETFOREGROUNDLOCKTIMEOUT = 0x2000
    SPI_SETFOREGROUNDLOCKTIMEOUT = 0x2001
    SW_SHOW = 5
    SW_RESTORE = 9
    SW_MAXIMIZE = 3
    SW_SHOWMAXIMIZED = 3

    HWND_TOP = ctypes.wintypes.HWND(0)
    HWND_TOPMOST = ctypes.wintypes.HWND(-1)
    HWND_NOTOPMOST = ctypes.wintypes.HWND(-2)
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_SHOWWINDOW = 0x0040

    FLASHW_ALL = 0x0003
    FLASHW_TIMERNOFG = 0x000C
    VK_MENU = 0x12
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.wintypes.UINT),
            ("hwnd", ctypes.wintypes.HWND),
            ("dwFlags", ctypes.wintypes.DWORD),
            ("uCount", ctypes.wintypes.UINT),
            ("dwTimeout", ctypes.wintypes.DWORD),
        ]

    user32.SetWindowPos.argtypes = [
        ctypes.wintypes.HWND, ctypes.wintypes.HWND,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        ctypes.wintypes.UINT
    ]
    user32.SetWindowPos.restype = ctypes.wintypes.BOOL

    user32.IsIconic.argtypes = [ctypes.wintypes.HWND]
    user32.IsIconic.restype = ctypes.wintypes.BOOL

    user32.GetWindowThreadProcessId.argtypes = [ctypes.wintypes.HWND, ctypes.POINTER(ctypes.wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD

    user32.AttachThreadInput.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.DWORD, ctypes.wintypes.BOOL]
    user32.AttachThreadInput.restype = ctypes.wintypes.BOOL

    user32.BringWindowToTop.argtypes = [ctypes.wintypes.HWND]
    user32.BringWindowToTop.restype = ctypes.wintypes.BOOL

    user32.keybd_event.argtypes = [ctypes.c_byte, ctypes.c_byte, ctypes.wintypes.DWORD, ctypes.c_size_t]
    user32.keybd_event.restype = None

    # Pre-launch privilege grant while current Python thread holds foreground
    try:
        user32.AllowSetForegroundWindow(-1)
    except Exception:
        pass

    # Launch file or folder using native ShellExecute (os.startfile reuses existing processes)
    if is_folder:
        folder_dir = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
        os.startfile(folder_dir)
    else:
        os.startfile(target_path)

    folder_name = ""
    file_name = os.path.basename(target_path).lower()
    file_stem = os.path.splitext(file_name)[0].lower()
    ext = os.path.splitext(file_name)[1].lower()

    if is_folder:
        folder_dir = target_path if os.path.isdir(target_path) else os.path.dirname(target_path)
        folder_name = os.path.basename(folder_dir).lower()

    system_shell_classes = {
        "progman", "workerw", "shell_traywnd", "searchhost",
        "startmenuexperiencehost", "windows.immersivecontextmenu"
    }

    expected_classes = set()
    if is_folder:
        expected_classes = {"cabinetwclass", "explorer"}
    elif ext in (".xlsx", ".xls", ".csv"):
        expected_classes = {"xlmain"}
    elif ext in (".docx", ".doc"):
        expected_classes = {"opusapp"}
    elif ext in (".pptx", ".ppt"):
        expected_classes = {"pptframeclass"}
    elif ext in (".pdf", ".html"):
        expected_classes = {"chrome_widgetwin_1", "mozilla_window_class", "pdf_realm"}

    def poll_and_force_foreground():
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)

        for attempt in range(25):
            time.sleep(0.1)
            found_hwnds = []

            def enum_windows_callback(hwnd, lparam):
                if user32.IsWindowVisible(hwnd):
                    class_buff = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, class_buff, 256)
                    cls_name = class_buff.value.lower()

                    if cls_name in system_shell_classes:
                        return True

                    length = user32.GetWindowTextLengthW(hwnd)
                    if length <= 0:
                        return True

                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()

                    if "antigravity" in title:
                        return True

                    is_iconic = bool(user32.IsIconic(hwnd))

                    score = 0
                    if is_folder:
                        if folder_name and folder_name in title:
                            score = 100 if not is_iconic else 80
                    else:
                        # Check exact file_name (including extension, e.g. "resume.docx")
                        if file_name and file_name in title:
                            score = 200 if not is_iconic else 180
                        elif file_stem and len(file_stem) > 2 and file_stem in title:
                            # Reject title if it contains a DIFFERENT document extension (e.g. ignore .html when opening .docx)
                            other_exts = {".pdf", ".html", ".htm", ".docx", ".doc", ".xlsx", ".pptx"} - {ext}
                            if any(o_ext in title for o_ext in other_exts):
                                score = 0
                            else:
                                score = 90 if not is_iconic else 70

                    if score > 0:
                        if cls_name in expected_classes:
                            score += 20
                        found_hwnds.append((score, hwnd, cls_name, title))
                return True

            cb = WNDENUMPROC(enum_windows_callback)
            user32.EnumWindows(cb, 0)

            if found_hwnds:
                found_hwnds.sort(key=lambda item: item[0], reverse=True)
                _, hwnd, cls_name, win_title = found_hwnds[0]

                length = user32.GetWindowTextLengthW(hwnd)
                title = ""
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value

                print(f"[DEBUG] Match target HWND {hwnd} (class: '{cls_name}', title: '{title}')")

                try:
                    # 1. Unlock Windows OS ForegroundLockTimeout via simulated ALT key tap
                    try:
                        user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | 0, 0)
                        user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
                    except Exception:
                        pass

                    # 2. Grant explicit foreground privilege to target process PID
                    target_pid = ctypes.wintypes.DWORD()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target_pid))
                    if target_pid.value:
                        try:
                            user32.AllowSetForegroundWindow(target_pid.value)
                        except Exception:
                            pass

                    # 3. Restore window state if minimized
                    if user32.IsIconic(hwnd):
                        user32.ShowWindow(hwnd, SW_RESTORE)
                    else:
                        user32.ShowWindow(hwnd, SW_SHOW)

                    # 4. SPI Lock Timeout Bypass + AttachThreadInput + SetForegroundWindow
                    old_timeout = ctypes.wintypes.DWORD()
                    user32.SystemParametersInfoW(SPI_GETFOREGROUNDLOCKTIMEOUT, 0, ctypes.byref(old_timeout), 0)

                    set_fg_success = False
                    attached = False
                    fg_thread_id = 0
                    target_thread_id = 0

                    try:
                        user32.SystemParametersInfoW(SPI_SETFOREGROUNDLOCKTIMEOUT, 0, ctypes.c_void_p(0), 0)
                        user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

                        curr_fg_hwnd = user32.GetForegroundWindow()
                        if curr_fg_hwnd and curr_fg_hwnd != hwnd:
                            fg_thread_id = user32.GetWindowThreadProcessId(curr_fg_hwnd, None)
                            target_thread_id = user32.GetWindowThreadProcessId(hwnd, None)
                            if fg_thread_id and target_thread_id and fg_thread_id != target_thread_id:
                                attached = bool(user32.AttachThreadInput(fg_thread_id, target_thread_id, True))

                        try:
                            user32.BringWindowToTop(hwnd)
                        except Exception:
                            pass

                        set_fg_success = bool(user32.SetForegroundWindow(hwnd))
                    finally:
                        if attached and fg_thread_id and target_thread_id:
                            try:
                                user32.AttachThreadInput(fg_thread_id, target_thread_id, False)
                            except Exception:
                                pass

                        user32.SystemParametersInfoW(
                            SPI_SETFOREGROUNDLOCKTIMEOUT, 0, ctypes.c_void_p(old_timeout.value), 0
                        )

                    # If initial SetForegroundWindow didn't activate, tap ALT again & retry
                    if user32.GetForegroundWindow() != hwnd:
                        try:
                            user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | 0, 0)
                            user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
                            set_fg_success = bool(user32.SetForegroundWindow(hwnd))
                        except Exception:
                            pass

                    is_fg = (user32.GetForegroundWindow() == hwnd)
                    print(f"[DEBUG] Layer 2 SetForegroundWindow: {set_fg_success}, IsForeground: {is_fg}")

                    # --- DELAYED RE-ASSERTION SAFETY NET (350ms) ---
                    # Catches asynchronous Excel/Explorer workbook loading focus-steals (t=300-400ms)
                    def reassert_foreground():
                        try:
                            if user32.IsWindow(hwnd) and user32.GetForegroundWindow() != hwnd:
                                print(f"[DEBUG] Delayed re-assertion (350ms): Target HWND {hwnd} lost focus, re-activating...")
                                user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | 0, 0)
                                user32.keybd_event(VK_MENU, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
                                user32.SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
                                user32.BringWindowToTop(hwnd)
                                user32.SetForegroundWindow(hwnd)
                        except Exception as ex:
                            print(f"[DEBUG] Exception in delayed re-assertion for HWND {hwnd}: {ex}")

                    threading.Timer(0.35, reassert_foreground).start()

                    if not is_fg:
                        print(f"[DEBUG] Target HWND {hwnd} placed in top Z-order, triggering Layer 4 FlashWindowEx fallback")
                        finfo = FLASHWINFO()
                        finfo.cbSize = ctypes.sizeof(FLASHWINFO)
                        finfo.hwnd = hwnd
                        finfo.dwFlags = FLASHW_ALL | FLASHW_TIMERNOFG
                        finfo.uCount = 3
                        finfo.dwTimeout = 0
                        user32.FlashWindowEx(ctypes.byref(finfo))

                except Exception as ex:
                    print(f"[DEBUG] Exception forcing foreground for HWND {hwnd}: {ex}")
                break
        else:
            print(f"[DEBUG] Timeout: no matching window found for '{target_path}'")

    threading.Thread(target=poll_and_force_foreground, daemon=True).start()
