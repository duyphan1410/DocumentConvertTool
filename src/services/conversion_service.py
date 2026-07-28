from concurrent.futures import ThreadPoolExecutor
import os
from typing import List, Callable, Any
from src.core.converters import save_markdown_from_text, parse_md_tables
from src.core.validator import validate_md_tables
from src.core.registry import ModuleRegistry
import src.modules  # noqa: F401

# Shared pool for non-blocking conversion tasks
_conversion_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="doc_converter_worker")


def has_md_tables(content: str) -> bool:
    return bool(parse_md_tables(content))


def get_md_table_warnings(content: str) -> List[str]:
    return validate_md_tables(content)


def is_output_locked(out_path: str) -> bool:
    if not os.path.exists(out_path):
        return False
    try:
        with open(out_path, "r+b"):
            return False
    except PermissionError:
        return True
    except Exception:
        return False


def convert_content(mode: str, content: str, out_path: str) -> str:
    if "->" not in mode:
        raise ValueError(f"Invalid mode format: {mode}")
        
    src_fmt, dest_fmt = [part.strip() for part in mode.split("->")]
    
    if dest_fmt == "MD":
        return save_markdown_from_text(content, out_path)
        
    module = ModuleRegistry.get_module_by_name(dest_fmt)
    if not module:
        raise ValueError(f"No module found to convert Markdown to {dest_fmt}!")
        
    return module.save_from_markdown(content, out_path)


def submit_async_task(fn: Callable[..., Any], *args, **kwargs):
    """Submits a background task to the shared ThreadPoolExecutor."""
    return _conversion_executor.submit(fn, *args, **kwargs)

