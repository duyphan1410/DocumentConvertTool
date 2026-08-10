# Technical Report: Windows OS Window Focus & Z-Order Behavior in Flet Applications

**Project**: Document Converter Tool  
**Date**: 31/07/2026  
**Target Environment**: Windows 10/11, Python 3.12, Flet Framework (v0.25+ / v0.80+)

---

## 1. Executive Summary

During the development and refactoring of the Flet desktop UI for Document Converter Tool, a subtle OS-level window focus interaction was observed when users click **Open File** or **Open Folder** after document conversion:
1. Newly opened target applications (e.g. Microsoft Excel, Word) or File Explorer windows sometimes did not jump to the absolute top (**Foreground Z-Index #1**), remaining behind the Flet application window.
2. Attempts to surrender focus via Flet's `self.page.window.focused = False` caused the Flet window to drop down to **Z-Index #3** in the Windows Alt+Tab stack (behind other running background apps), breaking normal `Alt + Tab` return navigation.
3. Rapid repeated clicks on **Open Folder** using `subprocess.Popen("explorer /select,...")` spawned duplicate File Explorer windows.
4. Overwriting output files currently opened and locked by Excel/Word triggered Windows `PermissionError` (`WinError 32`), requiring clear general English status reporting.

This document analyzes the root causes of these behaviors, documents the OS mechanics, and establishes standard architectural guidelines.

### 1.1 Application Roles & Terminology Mapping

To prevent ambiguity between window handles, this report defines the following explicit application roles:

| Acronym / Role | Application Name | Process / Binary Name | Role & Action |
|---|---|---|---|
| **DCT (Primary App)** | **DocumentConvertTool** | `python.exe` / Flet Desktop GUI Window | Main desktop GUI converter window holding active focus when user clicks **Open File** or **Open Folder**. |
| **Target File Viewer** | **Microsoft Excel**, **Microsoft Word**, **Google Chrome**, **VS Code** | `excel.exe`, `winword.exe`, `chrome.exe`, `code.exe` | Target viewer application launched/reactivated after converting files (`.xlsx`, `.docx`, `.html`, `.md`). |
| **Target Folder Viewer** | **Windows File Explorer** | `explorer.exe` | Native OS directory browser window opened when user clicks **Open Folder**. |

---

## 2. Technical Root Cause Analysis

### 2.1 Windows Foreground Lock Prevention

Since Windows 98 / 2000, Microsoft Windows enforces **Foreground Lock Prevention** (`SPI_SETFOREGROUNDLOCKTIMEOUT`). 
- When Process A (Flet App) is the active foreground window, Windows restricts background or external processes from forcibly stealing focus unless explicitly granted permission by Process A via `AllowSetForegroundWindow(process_id)` or native `ShellExecute`.
- In Flet, the Flutter Runner continuously maintains window focus events. When an external file is launched:
  - If the target application (e.g. `excel.exe`) is **NOT currently running**, Windows creates a new process and grants it foreground status (Z-Index #1).
  - If the target application is **ALREADY RUNNING** in the background, Windows `ShellExecute` passes the file path via DDE / COM IPC to the existing process. Windows Foreground Lock blocks the existing process from stealing focus over Flet, leaving the target app at Z-Index #2 behind Flet.

### 2.2 Z-Order Stack Degradation with `page.window.focused = False`

When `self.page.window.focused = False` was invoked:
- Flutter Runner surrenders focus by deactivating the Flet window.
- Windows responds by passing focus back to the *previously active window* (e.g. VS Code or Web Browser), pushing Flet down to **Z-Index #3**.
- When the target application opens at Z-Index #1, pressing `Alt + Tab` from the target app returns to the app at Z-Index #2 (VS Code / Browser) rather than Flet.

### 2.3 Single-Instance vs. Multi-Instance Window Spawning

| Launch Method | Windows OS Behavior | Duplicate Window Risk |
|---|---|---|
| `subprocess.Popen('explorer /select,"path"')` | Spawns a brand new `explorer.exe` process for every invocation. | ⚠️ **High**: Creates multiple duplicate Explorer windows when clicked repeatedly. |
| `os.startfile(folder_path)` | Calls native `ShellExecuteW(..., "open", ...)`. Windows Shell activates existing Explorer window for that folder. | ✅ **Zero**: Reuses existing Explorer window. |
| `os.startfile(file_path)` | Calls native `ShellExecuteW`. Target app (Excel/Word/VS Code) reuses existing tab/instance. | ✅ **Zero**: Reuses existing app instance. |

---

## 3. Implemented Architecture & Solutions

### 3.1 Clean ShellExecute Integration (`os.startfile`)

To eliminate duplicate Explorer windows and maintain natural OS Z-Order hierarchy:
```python
# Open File: Reuse existing application tab/window
if sys.platform == "win32":
    os.startfile(file_path)

# Open Folder: Reuse existing File Explorer window
if sys.platform == "win32":
    os.startfile(folder_path)
```

### 3.2 Flet 0.80+ Clipboard API Standardization

Fixed `AttributeError` caused by Flet 0.80+ deprecations (`page.set_clipboard` removed, `page.clipboard` getter-only property) by using native OS clipboard standard stream:
```python
# Cross-platform fallback using native OS streams
if sys.platform == "win32":
    subprocess.run("clip", input=err_text, text=True, encoding="utf-8", shell=True)
elif sys.platform == "darwin":
    subprocess.run("pbcopy", input=err_text, text=True, encoding="utf-8")
else:
    subprocess.run(["xclip", "-selection", "clipboard"], input=err_text, text=True, encoding="utf-8")
```

### 3.3 Unified General English File Lock Reporting

When attempting to convert or overwrite an output file locked by another application:
```python
if isinstance(ex, PermissionError) or "Permission denied" in raw_err or "WinError 32" in raw_err:
    file_name = os.path.basename(out_path)
    display_err = f"Cannot overwrite! File '{file_name}' is currently open in another program. Please close the file and try again."
```
Status message displayed to user:
`Cannot overwrite! File 'TestCase1.xlsx' is currently open in another program. Please close the file and try again.`

---

## 4. Analysis of Attempted Methods, Code Snippets & Technical Drawbacks (Open File & Open Folder)

During the optimization of the **Open File** and **Open Folder** post-conversion action handlers in DocumentConvertTool (DCT), several window control approaches and launch methods were evaluated. The section below documents why each approach failed OS windowing constraints and was rejected.

### 4.1 Summary Comparison Table (Open File & Open Folder Mechanics)

| Launch / Focus Approach | Target Action | Root Technical Cause of Failure | Impact / User Experience Drawback | Final Architectural Solution |
|---|---|---|---|---|
| **`self.page.window.focused = False`** | Open File & Open Folder | Surrenders focus without designating target handle; Windows drops DCT to Z-Index #3. | Destroys `Alt + Tab` window stack; returning from Excel switches to VS Code instead of DCT. | Omit forced unfocus; rely on native `os.startfile` ShellExecute. |
| **`subprocess.Popen("explorer /select,...")`** | Open Folder | Spawns a brand-new `explorer.exe` process per click without OS window reuse. | Rapid clicks produce 5–10 duplicate File Explorer windows cluttering taskbar. | Use `os.startfile(folder_path)` to reuse existing File Explorer instance. |
| **`subprocess.Popen("cmd /c start...")`** | Open File | Invokes Windows Command Prompt process wrapper to launch target file. | Flashes a temporary black `cmd.exe` terminal window on screen before opening app. | Use native `os.startfile(file_path)` without command shell invocation. |
| **Unassisted `SetForegroundWindow(hwnd)`** | Open File | Bare cross-process focus stealing blocked by OS Foreground Lock (`SPI_SETFOREGROUNDLOCKTIMEOUT`). | API call fails silently or causes target taskbar icon to flash amber without raising window. | Wrap with 3-Layer Fallback Architecture: (1) Class-name `EnumWindows` matching, (2) `SPI_SETFOREGROUNDLOCKTIMEOUT` bypass, (3) `SetWindowPos` TOPMOST Z-order toggle fallback, (4) `FlashWindowEx` fallback. |
| **Unhandled `PermissionError` (WinError 32)** | Overwrite Active File | Target file is locked exclusively by active viewer (Excel/Word). | Conversion worker thread crashes with raw Python traceback instead of friendly guidance. | Catch `PermissionError` / `WinError 32` explicitly and display general English status message. |

---

### 4.2 Detailed Technical Breakdown of Failed Code Snippets & Production Solution

#### 1. Forced Window Unfocus (`page.window.focused = False`)
```python
# FAILED CODE (in Open File / Open Folder click handler):
os.startfile(out_path)
self.page.window.focused = False  # Attempted to push target app to front
```
- **Technical Drawback**: Microsoft Windows manages the window Z-Order stack based on active thread focus hierarchy. Calling `focused = False` forces Flutter Runner to deactivate DCT's window handle without transferring explicit foreground privilege to the target viewer (Excel/Word/Chrome). Windows defaults to raising the window directly underneath DCT (Z-Index #2, e.g. VS Code or browser), pushing DCT down to **Z-Index #3**. Consequently, pressing `Alt + Tab` inside Excel switches focus to VS Code rather than back to DCT.

#### 2. Explorer Selection Subprocess (`subprocess.Popen`)
```python
# FAILED CODE (in Open Folder click handler):
subprocess.Popen(["explorer", "/select,", os.path.normpath(out_path)])
```
- **Technical Drawback**: Executing `subprocess.Popen` with the `/select,` argument triggers a direct binary launch of `explorer.exe`. Unlike shell integration routines, `Popen` does not query the OS Shell Desktop Manager to check for open directory windows. Each click spawns a completely new process and desktop window. Clicking "Open Folder" multiple times leaves 5–10 redundant Explorer windows open.

#### 3. Command Prompt Shell Launch (`subprocess.Popen("cmd /c start")`)
```python
# FAILED CODE (in Open File click handler):
subprocess.Popen(f'cmd /c start "" "{out_path}"', shell=True)
```
- **Technical Drawback**: Launching files via `cmd.exe` introduces an unnecessary process layer (`python.exe` -> `cmd.exe` -> target app). On Windows 10 and 11 desktop environments, a black Command Prompt console window briefly flashes on screen for 100–300ms before `cmd.exe` delegates the file execution to the default application, causing visual flicker.

#### 4. Bare Win32 Focus Stealing vs 3-Layer Win32 Fallback Standard
```python
# FAILED CODE (Unassisted SetForegroundWindow):
hwnd = win32gui.FindWindow(None, "Microsoft Excel - TestCase.xlsx")
if hwnd:
    win32gui.SetForegroundWindow(hwnd)  # Fails silently due to OS Foreground Lock!
```
- **Technical Drawback of Bare Call**: Calling `SetForegroundWindow` without clearing OS foreground lock timeout policy fails silently, leaving the target app at Z-Index #2 with an amber flashing taskbar button.
- **Production Standard (3-Layer Win32 Fallback in `src/utils/env.py`)**:
  1. **Layer 1 (Discovery)**: Background thread retry loop (2.0s timeout, 100ms interval) scanning visible window handles strictly matching class name (`OpusApp`, `XLMAIN`, `PPTFrameClass`, `CabinetWClass`, `ExploreWClass`). Window title is logged for debug tracing only.
  2. **Layer 2 (SPI Lock Bypass)**: Temporarily sets `SPI_SETFOREGROUNDLOCKTIMEOUT` to 0, calls `AllowSetForegroundWindow(-1)` as an auxiliary hint, invokes `SetForegroundWindow(hwnd)`, and immediately restores original timeout in a `finally` block.
  3. **Layer 3 (Topmost Z-Order Toggle)**: If OS policy blocks active focus grant, performs `SetWindowPos` to `HWND_TOPMOST` then `HWND_NOTOPMOST` (`SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW`), visually raising the target window to Z-Index #1.
  4. **Layer 4 (Taskbar Flash Fallback)**: If active focus is still withheld, triggers `FlashWindowEx` to notify the user.

#### 5. Unhandled Active File Overwrite Lock (`PermissionError`)
```python
# FAILED CODE (in conversion worker execution):
with open(out_path, "w", encoding="utf-8") as f:
    f.write(converted_content)  # Crashes if file is open in Excel/Word!
```
- **Technical Drawback**: When a user converts a document to `.xlsx` or `.docx` and leaves it open in Microsoft Excel or Microsoft Word, Windows places an exclusive file lock (`LOCK_EX`) on the target path. Attempting to write to `out_path` raises `PermissionError: [WinError 32] The process cannot access the file because it is being used by another process`. Without explicit lock exception handling, conversion worker threads crash and leave the UI stuck in "Converting..." status.

---

## 5. Summary & Recommendations for Open File / Open Folder Architecture

1. **Use 3-Layer Fallback Architecture in `open_file_or_folder_foreground()`**: Leverage native `os.startfile` combined with background HWND discovery (class-name matching + 2.0s polling loop), `SPI_SETFOREGROUNDLOCKTIMEOUT` bypass, and `SetWindowPos` TOPMOST Z-order fallback. *(Note: Non-Office target formats like `.pdf` or `.html` rely on standard `os.startfile` delegation, while Win32 class-name HWND elevation specifically targets MS Office applications (`.doc(x)`, `.xls(x)`, `.ppt(x)`) and Windows File Explorer).*
2. **Use Single-Instance `os.startfile(folder_path)` for Open Folder**: Passing directory path to `os.startfile(folder_dir)` activates existing File Explorer windows without spawning duplicate Explorer processes.
3. **Avoid Forced Focus Surrender (`page.window.focused = False`)**: Maintain natural OS Z-Order focus handling. Forcing unfocus corrupts the `Alt + Tab` navigation stack for desktop users.
4. **Enforce Graceful File Lock Error Handling**: Always wrap conversion writes in explicit `PermissionError` / `WinError 32` try-except blocks and notify the user with clear English guidance: `Cannot overwrite! File '...' is currently open in another program. Please close the file and try again.`



