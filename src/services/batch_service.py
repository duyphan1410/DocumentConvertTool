"""
Batch and Archive Document Conversion Service.
Provides multi-threaded document conversion with error isolation,
archive decompression (.zip, .rar, .7z, .tar.gz), and structured packaging.
"""

import os
import shutil
import time
import zipfile
import tarfile
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Set

from src.services.file_loader import load_document
from src.services.conversion_service import convert_content
from src.core.registry import ModuleRegistry
from src.core.errors import DocumentError
from src.i18n import t

IGNORED_SCAN_DIRS: Set[str] = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
    "$recycle.bin",
    "system volume information",
}

SUPPORTED_ARCHIVES: Set[str] = {
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".tgz",
    ".tar.gz",
    ".bz2",
    ".tar.bz2",
}


@dataclass
class BatchItemResult:
    source_file: str
    output_file: str
    status: str  # "success" | "failed" | "skipped"
    error_message: str = ""
    duration: float = 0.0


@dataclass
class BatchResult:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    duration: float = 0.0
    output_path: str = ""
    items: List[BatchItemResult] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)


class BatchConversionService:
    """
    Executes batch conversions on directories or extracted archives in a background thread pool.
    """

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self._cancel_event = threading.Event()
        self._is_running = False

    def cancel(self):
        """Signals running conversion tasks to abort promptly."""
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def is_running(self) -> bool:
        return self._is_running

    def extract_archive(self, archive_path: str, extract_to: str) -> bool:
        """
        Safely extracts supported archives (.zip, .tar.gz, .rar, .7z) into a target directory.
        """
        clean_path = os.path.normpath(archive_path)
        low_name = clean_path.lower()

        if low_name.endswith(".zip"):
            with zipfile.ZipFile(clean_path, "r") as zf:
                zf.extractall(extract_to)
            return True

        if low_name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2")):
            mode = "r:gz" if low_name.endswith((".tar.gz", ".tgz")) else ("r:bz2" if low_name.endswith((".tar.bz2", ".tbz2")) else "r:")
            with tarfile.open(clean_path, mode) as tf:
                tf.extractall(extract_to)
            return True

        # For .rar and .7z, attempt shutil.unpack_archive, py7zr, or patool if available
        try:
            shutil.unpack_archive(clean_path, extract_to)
            return True
        except Exception:
            pass

        if low_name.endswith(".7z"):
            try:
                import py7zr  # type: ignore
                with py7zr.SevenZipFile(clean_path, mode='r') as z:
                    z.extractall(path=extract_to)
                return True
            except ImportError:
                pass

        if low_name.endswith(".rar"):
            try:
                import rarfile  # type: ignore
                with rarfile.RarFile(clean_path) as rf:
                    rf.extractall(extract_to)
                return True
            except ImportError:
                pass

        raise DocumentError(
            code="UNSUPPORTED_ARCHIVE",
            title=t("dialog.error_title_default"),
            message=f"Không thể giải nén định dạng: {os.path.basename(clean_path)}",
            suggestion="Vui lòng giải nén tệp bằng phần mềm chuyên dụng và chọn thư mục giải nén.",
        )

    def scan_files_for_target(self, root_dir: str, target_ext: str) -> List[str]:
        """
        Recursively scans root_dir for document files eligible for conversion to target_ext.
        """
        valid_files = []
        target_clean = target_ext.lower().strip()
        if not target_clean.startswith("."):
            target_clean = f".{target_clean}"

        # Collect extensions that can be converted
        import src.modules  # noqa: F401
        all_modules = ModuleRegistry.get_all_modules()
        readable_exts = {".md"}
        for mod in all_modules:
            for ext in mod.file_extensions:
                readable_exts.add(ext.lower())

        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d.lower() not in IGNORED_SCAN_DIRS and not d.startswith(".")]
            for f in sorted(files):
                if f.startswith(".") and f not in (".env",):
                    continue
                ext = os.path.splitext(f)[1].lower()
                if ext in readable_exts:
                    # If target is same as source extension, we can skip or copy
                    valid_files.append(os.path.join(root, f))

        return valid_files

    def convert_single_file(
        self,
        src_path: str,
        out_path: str,
        target_ext: str,
    ) -> BatchItemResult:
        """
        Converts a single document with full Error Isolation.
        """
        t0 = time.perf_counter()
        src_ext = os.path.splitext(src_path)[1].lower()
        target_clean = target_ext.lower()
        if not target_clean.startswith("."):
            target_clean = f".{target_clean}"

        # Same format: direct copy
        if src_ext == target_clean:
            try:
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                shutil.copy2(src_path, out_path)
                return BatchItemResult(
                    source_file=src_path,
                    output_file=out_path,
                    status="success",
                    duration=round(time.perf_counter() - t0, 3),
                )
            except Exception as ex:
                return BatchItemResult(
                    source_file=src_path,
                    output_file=out_path,
                    status="failed",
                    error_message=str(ex),
                    duration=round(time.perf_counter() - t0, 3),
                )

        # Multi-stage conversion: Load -> Intermediate -> Convert
        try:
            # 1. Load source document into intermediate text/markdown
            load_res = load_document(src_path)
            if not load_res.success:
                err_msg = load_res.error_detail or load_res.error_short or "Không thể đọc nội dung tệp"
                return BatchItemResult(
                    source_file=src_path,
                    output_file=out_path,
                    status="failed",
                    error_message=err_msg,
                    duration=round(time.perf_counter() - t0, 3),
                )

            raw_text = load_res.content

            # 2. Determine target conversion mode

            # If target is .md, writing raw_text directly is sufficient
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            if target_clean == ".md":
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(raw_text)
            else:
                ext_to_module = {
                    ".md": "MD",
                    ".docx": "Word",
                    ".xlsx": "Excel",
                    ".csv": "CSV",
                    ".pdf": "PDF",
                    ".html": "HTML",
                    ".htm": "HTML",
                    ".json": "JSON",
                    ".yaml": "YAML",
                    ".yml": "YAML",
                    ".pptx": "PowerPoint",
                }
                dest_name = ext_to_module.get(target_clean, "MD")
                mode_name = f"MD -> {dest_name}"
                convert_content(mode_name, raw_text, out_path)

            return BatchItemResult(
                source_file=src_path,
                output_file=out_path,
                status="success",
                duration=round(time.perf_counter() - t0, 3),
            )
        except Exception as ex:
            return BatchItemResult(
                source_file=src_path,
                output_file=out_path,
                status="failed",
                error_message=str(ex),
                duration=round(time.perf_counter() - t0, 3),
            )


    def run_batch(
        self,
        source_path: str,
        target_ext: str,
        output_destination: str,
        output_type: str = "folder",  # "folder" | "zip"
        preserve_structure: bool = True,
        on_progress: Optional[Callable[[int, int, str, BatchItemResult], None]] = None,
    ) -> BatchResult:
        """
        Synchronous batch runner (designed to be executed in a dedicated worker thread).
        """
        self._cancel_event.clear()
        self._is_running = True
        overall_t0 = time.perf_counter()

        result = BatchResult()
        temp_dir: Optional[str] = None
        working_source_dir = source_path

        try:
            # 1. Check if source is an archive (.zip, .rar, .7z, .tar.gz)
            if os.path.isfile(source_path):
                temp_dir = tempfile.mkdtemp(prefix="docconvert_batch_")
                extract_sub = os.path.join(temp_dir, "extracted")
                os.makedirs(extract_sub, exist_ok=True)
                self.extract_archive(source_path, extract_sub)
                working_source_dir = extract_sub

            # 2. Scan files to convert
            files_to_convert = self.scan_files_for_target(working_source_dir, target_ext)
            result.total = len(files_to_convert)

            if result.total == 0:
                result.duration = round(time.perf_counter() - overall_t0, 2)
                return result

            # 3. Determine output base directory
            target_clean = target_ext.lower().strip()
            if not target_clean.startswith("."):
                target_clean = f".{target_clean}"

            if output_type == "zip":
                if not temp_dir:
                    temp_dir = tempfile.mkdtemp(prefix="docconvert_batch_")
                working_output_dir = os.path.join(temp_dir, "converted_output")
                os.makedirs(working_output_dir, exist_ok=True)
            else:
                working_output_dir = output_destination
                os.makedirs(working_output_dir, exist_ok=True)

            # 4. Multi-threaded processing
            completed_count = 0

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {}
                for src_file in files_to_convert:
                    if self._cancel_event.is_set():
                        break

                    if preserve_structure:
                        rel_path = os.path.relpath(src_file, working_source_dir)
                    else:
                        rel_path = os.path.basename(src_file)

                    base_rel, _ = os.path.splitext(rel_path)
                    dest_file = os.path.join(working_output_dir, f"{base_rel}{target_clean}")

                    future = executor.submit(self.convert_single_file, src_file, dest_file, target_clean)
                    futures[future] = src_file

                for future in as_completed(futures):
                    if self._cancel_event.is_set():
                        break

                    src_f = futures[future]
                    try:
                        item_res = future.result()
                    except Exception as ex:
                        item_res = BatchItemResult(
                            source_file=src_f,
                            output_file="",
                            status="failed",
                            error_message=str(ex),
                        )

                    completed_count += 1
                    result.items.append(item_res)

                    if item_res.status == "success":
                        result.succeeded += 1
                    elif item_res.status == "failed":
                        result.failed += 1
                        result.errors.append({
                            "file": os.path.basename(item_res.source_file),
                            "error": item_res.error_message,
                        })
                    else:
                        result.skipped += 1

                    if on_progress:
                        on_progress(
                            completed_count,
                            result.total,
                            os.path.basename(item_res.source_file),
                            item_res,
                        )

            # 5. Packaging into zip if requested
            if output_type == "zip" and not self._cancel_event.is_set():
                out_zip = output_destination
                if not out_zip.lower().endswith(".zip"):
                    out_zip = f"{out_zip}.zip"

                os.makedirs(os.path.dirname(os.path.abspath(out_zip)), exist_ok=True)
                with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(working_output_dir):
                        for f in files:
                            full_p = os.path.join(root, f)
                            rel_p = os.path.relpath(full_p, working_output_dir)
                            zf.write(full_p, rel_p)
                result.output_path = out_zip
            else:
                result.output_path = working_output_dir

        finally:
            self._is_running = False
            result.duration = round(time.perf_counter() - overall_t0, 2)
            # Cleanup temp directories
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass

        return result
