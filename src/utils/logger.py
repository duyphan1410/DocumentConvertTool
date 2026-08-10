import os
import sys
import glob
import datetime
import traceback
from typing import Union

from src.core.errors import DocumentError


def get_log_dir() -> str:
    """Returns the persistent logs directory path inside AppData or fallback local directory."""
    if sys.platform == "win32":
        app_data = os.getenv("APPDATA")
        if app_data:
            log_dir = os.path.join(app_data, "DocConvert", "logs")
        else:
            log_dir = os.path.abspath("logs")
    else:
        log_dir = os.path.abspath("logs")

    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def cleanup_old_logs(max_days: int = 30):
    """Purges log files older than max_days to keep disk footprint minimal."""
    try:
        log_dir = get_log_dir()
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=max_days)
        log_files = glob.glob(os.path.join(log_dir, "*.log"))
        
        for file_path in log_files:
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
                if mtime < cutoff_date:
                    os.remove(file_path)
                    print(f"[LOGGER] Purged old log file: {os.path.basename(file_path)}")
            except Exception as e:
                print(f"[LOGGER] Failed to delete old log {file_path}: {e}")
    except Exception as exc:
        print(f"[LOGGER] Error during log retention cleanup: {exc}")


def log_error(err: Union[DocumentError, Exception], context_info: str = "") -> str:
    """
    Appends an error entry to today's log file.
    
    Returns:
        The formatted log string.
    """
    cleanup_old_logs()
    log_dir = get_log_dir()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(log_dir, f"{today_str}.log")

    if isinstance(err, DocumentError):
        entry_text = err.to_log_string()
    else:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tb_str = "".join(traceback.format_exception(type(err), err, err.__traceback__))
        entry_text = f"Time: {now_str}\nException: {type(err).__name__}: {err}\nDetail:\n{tb_str}"

    if context_info:
        entry_text = f"Context: {context_info}\n" + entry_text

    full_entry = f"========================================\n{entry_text}\n========================================\n\n"

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(full_entry)
    except Exception as e:
        print(f"[LOGGER] Unable to write to log file {log_path}: {e}")

    return entry_text


def log_info(msg: str):
    """Appends an info entry to today's log file."""
    log_dir = get_log_dir()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(log_dir, f"{today_str}.log")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = f"[{now_str}] [INFO] {msg}\n"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass
