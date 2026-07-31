import os
from dataclasses import dataclass
from typing import List, Optional

from src.core.registry import ModuleRegistry
import src.modules  # noqa: F401

@dataclass
class LoadResult:
    success: bool
    content: str = ""
    mode: str = ""
    error_short: Optional[str] = None
    error_detail: Optional[str] = None
    missing_dependencies: Optional[List[str]] = None


def get_missing_dependencies_for_path(path: str) -> List[str]:
    ext = os.path.splitext(path)[1].lower()
    module = ModuleRegistry.get_module_by_extension(ext)
    if module:
        return module.check_dependencies()
    return []


def load_document(path: str) -> LoadResult:
    from src.core.validator import validate_file_integrity
    integrity_error = validate_file_integrity(path)
    if integrity_error:
        short, detail = integrity_error
        return LoadResult(False, error_short=short, error_detail=detail)

    from src.services.media_asset_manager import MediaAssetManager
    asset_mgr = MediaAssetManager()
    asset_mgr.open_session(path)

    ext = os.path.splitext(path)[1].lower()
    module = ModuleRegistry.get_module_by_extension(ext)
    if not module:
        if ext == ".md":
            try:
                with open(path, encoding="utf-8") as f:
                    raw_content = f.read()
                content = asset_mgr.import_local_images(raw_content, os.path.dirname(path))
                return LoadResult(True, content=content, mode="MD -> Excel")
            except Exception as exc:
                return LoadResult(False, error_short="Load error", error_detail=str(exc))
        return LoadResult(False, error_short="Unsupported extension", error_detail=f"File extension {ext} is not supported.")

    missing = module.check_dependencies()
    if missing:
        missing_msg = " and ".join(missing)
        return LoadResult(
            False,
            error_short=f"{missing_msg} missing",
            error_detail="",
            missing_dependencies=missing,
        )

    try:
        content = module.load_to_markdown(path)
        mode = f"{module.name} -> MD"
    except Exception as exc:
        return LoadResult(False, error_short="Load error", error_detail=str(exc))

    return LoadResult(True, content=content, mode=mode)
