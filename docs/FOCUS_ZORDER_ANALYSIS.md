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

## 4. Summary & Recommendations

1. **Use Native `os.startfile` for Desktop Integrations**: Always prefer `os.startfile` on Windows to leverage OS window reuse mechanisms without spawning duplicate processes.
2. **Avoid Forced Focus Surrender (`page.window.focused = False`)**: Forcing unfocus causes Z-Order stack degradation in Windows Alt+Tab navigation.
3. **Graceful File Lock Error Handling**: Always catch `PermissionError` / `WinError 32` explicitly and display general, user-friendly English error guidance.
