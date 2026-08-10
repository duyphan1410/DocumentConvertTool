import os
from dataclasses import dataclass
from typing import List, Optional

from src.core.errors import DocumentError, ErrorCode
from src.core.error_mapper import ErrorMapper
from src.core.validator import validate_file_pipeline
from src.core.registry import ModuleRegistry
import src.modules  # noqa: F401


@dataclass
class LoadResult:
    success: bool
    content: str = ""
    mode: str = ""
    path: str = ""
    error: Optional[DocumentError] = None
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
    """
    Loads document file through the Validation Pipeline and Module Importers.
    Guarantees structured DocumentError on failure.
    """
    # 1. Validation Pipeline Step (Exist -> Ext -> Type -> Perm -> Size -> Integrity)
    try:
        clean_path = validate_file_pipeline(path)
    except DocumentError as doc_err:
        return LoadResult(
            success=False,
            path=path,
            error=doc_err,
            error_short=doc_err.title,
            error_detail=doc_err.message,
        )
    except Exception as exc:
        doc_err = ErrorMapper.map_exception(exc, context_path=path, stage="read")
        return LoadResult(
            success=False,
            path=path,
            error=doc_err,
            error_short=doc_err.title,
            error_detail=doc_err.message,
        )

    # 2. Asset Manager Session
    from src.services.media_asset_manager import MediaAssetManager
    asset_mgr = MediaAssetManager()
    asset_mgr.open_session(clean_path)

    ext = os.path.splitext(clean_path)[1].lower()
    module = ModuleRegistry.get_module_by_extension(ext)

    if not module:
        if ext == ".md":
            try:
                with open(clean_path, encoding="utf-8") as f:
                    raw_content = f.read()
                content = asset_mgr.import_local_images(raw_content, os.path.dirname(clean_path))
                return LoadResult(success=True, content=content, mode="MD -> Excel", path=clean_path)
            except Exception as exc:
                doc_err = ErrorMapper.map_exception(exc, context_path=clean_path, stage="read")
                return LoadResult(success=False, path=clean_path, error=doc_err, error_short=doc_err.title, error_detail=doc_err.message)

        doc_err = DocumentError(
            code=ErrorCode.UNSUPPORTED_EXTENSION,
            title="Định dạng không hỗ trợ",
            message=f"Tệp đuôi '{ext}' không được hỗ trợ.",
            suggestion="Chọn một tệp thuộc các định dạng .docx, .pdf, .xlsx, .csv, .md, .html.",
        )
        return LoadResult(success=False, path=clean_path, error=doc_err, error_short=doc_err.title, error_detail=doc_err.message)

    # 3. Missing Dependencies Check
    missing = module.check_dependencies()
    if missing:
        missing_pkgs = ", ".join(missing)
        doc_err = ErrorMapper.map_exception(
            ModuleNotFoundError(missing_pkgs),
            context_path=clean_path,
            stage="read",
        )
        return LoadResult(
            success=False,
            path=clean_path,
            error=doc_err,
            error_short=doc_err.title,
            error_detail=doc_err.message,
            missing_dependencies=missing,
        )

    # 4. Importer Execution
    try:
        content = module.load_to_markdown(clean_path)
        mode = f"{module.name} -> MD"
        return LoadResult(success=True, content=content, mode=mode, path=clean_path)
    except Exception as exc:
        doc_err = ErrorMapper.map_exception(exc, context_path=clean_path, stage="read")
        return LoadResult(
            success=False,
            path=clean_path,
            error=doc_err,
            error_short=doc_err.title,
            error_detail=doc_err.message,
        )
