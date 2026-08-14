import re
import os
import sys
import zipfile
from typing import Optional, List, Tuple

from src.core.errors import DocumentError, ErrorCode
from src.i18n import t


def resolve_windows_shortcut(path: str) -> str:
    """
    Resolves Windows .lnk shortcut target path if applicable.
    Returns the resolved real file path or original path.
    """
    if sys.platform == "win32" and path.lower().endswith(".lnk"):
        try:
            import subprocess
            cmd = f"$sh = New-Object -ComObject WScript.Shell; $sh.CreateShortcut('{path}').TargetPath"
            res = subprocess.check_output(["powershell", "-NoProfile", "-Command", cmd], text=True, timeout=2).strip()
            if res and os.path.exists(res):
                return os.path.normpath(res)
        except Exception:
            pass
    return path


def validate_md_tables(content: str) -> list[str]:
    """
    Validates Markdown tables in the content.
    Returns a list of warning strings. If empty, the tables are valid.
    """
    warnings = []
    lines = content.split("\n")
    i = 0
    table_index = 0
    
    while i < len(lines):
        line = lines[i].strip()
        if "|" in line and not re.match(r"^[\|\s\-:]+$", line):
            table_index += 1
            table_name = t("validator.table_name_default", index=table_index)
            for j in range(i-1, max(i-5, -1), -1):
                prev = lines[j].strip()
                if prev.startswith("#"):
                    table_name = re.sub(r"^#+\s*", "", prev)[:31]
                    break
            
            table_start_line = i + 1
            table_lines = []
            while i < len(lines) and "|" in lines[i]:
                table_lines.append(lines[i].strip())
                i += 1
                
            if len(table_lines) < 2:
                warnings.append(
                    t("validator.table_incomplete_warn", name=table_name, line=table_start_line)
                )
                continue
                
            separator_line = table_lines[1]
            if not re.match(r"^[\|\s\-:]+$", separator_line):
                warnings.append(
                    t("validator.table_separator_warn", name=table_name, line=table_start_line)
                )
                
            data_lines = [l for l in table_lines if not re.match(r"^[\|\s\-:]+$", l)]
            if len(data_lines) < 2:
                continue
                
            rows = [[c.strip() for c in l.split("|") if c.strip()] for l in data_lines]
            header_col_count = len(rows[0])
            
            for row_idx, r in enumerate(rows):
                if len(r) != header_col_count:
                    try:
                        line_num = table_start_line + table_lines.index(data_lines[row_idx])
                    except ValueError:
                        line_num = table_start_line
                    warnings.append(
                        t("validator.table_col_mismatch_warn", name=table_name, line=line_num, count=len(r), expected=header_col_count)
                    )
        else:
            i += 1
            
    return warnings


def validate_file_pipeline(path: str) -> str:
    """
    Executes multi-step Validation Pipeline in exact order:
    1. Existence Check (Check existence FIRST before extension)
    2. File Type / Shortcut (.lnk) / Directory Check
    3. Extension Check
    4. Permission & Lock Check
    5. File Size Check (0 bytes or excessive size)
    6. Integrity Check (OOXML, PDF, UTF-8 text)

    Returns:
        The validated (and resolved shortcut) absolute file path string.

    Raises:
        DocumentError if validation fails at any stage.
    """
    if not path or not path.strip():
        raise DocumentError(
            code=ErrorCode.FILE_NOT_FOUND,
            title=t("validator.empty_path_title"),
            message=t("validator.empty_path_msg"),
            suggestion=t("validator.empty_path_sug"),
        )

    clean_path = os.path.normpath(path.strip())

    # 1. STEP 1: Existence Check (Checks path existence FIRST before extension)
    if not os.path.exists(clean_path):
        raise DocumentError(
            code=ErrorCode.FILE_NOT_FOUND,
            title=t("validator.not_found_title"),
            message=t("validator.not_found_msg", path=clean_path),
            suggestion=t("validator.not_found_sug"),
        )

    # 2. STEP 2: File Type / Directory / Windows .lnk Shortcut Check
    if os.path.isdir(clean_path):
        raise DocumentError(
            code=ErrorCode.IS_DIRECTORY,
            title=t("validator.is_dir_title"),
            message=t("validator.is_dir_msg", filename=os.path.basename(clean_path)),
            suggestion=t("validator.is_dir_sug"),
        )

    if clean_path.lower().endswith(".lnk"):
        resolved = resolve_windows_shortcut(clean_path)
        if not os.path.exists(resolved) or os.path.isdir(resolved):
            raise DocumentError(
                code=ErrorCode.FILE_NOT_FOUND,
                title=t("validator.bad_lnk_title"),
                message=t("validator.bad_lnk_msg", filename=os.path.basename(clean_path)),
                suggestion=t("validator.bad_lnk_sug"),
            )
        clean_path = resolved

    # 3. STEP 3: Extension Check
    from src.core.registry import ModuleRegistry
    import src.modules  # noqa: F401

    ext = os.path.splitext(clean_path)[1].lower()
    valid_exts = [".md"] + [e for m in ModuleRegistry.get_all_modules() for e in m.file_extensions]

    if ext not in valid_exts:
        valid_str = ", ".join(valid_exts)
        raise DocumentError(
            code=ErrorCode.UNSUPPORTED_EXTENSION,
            title=t("validator.unsupported_ext_title"),
            message=t("validator.unsupported_ext_msg", ext=ext),
            suggestion=t("validator.unsupported_ext_sug", valid_exts=valid_str),
        )

    # 4. STEP 4: Permission & Lock Check
    first_bytes = b""
    try:
        with open(clean_path, "rb") as f:
            first_bytes = f.read(8)
    except PermissionError as pe:
        raise DocumentError(
            code=ErrorCode.FILE_LOCKED,
            title=t("validator.file_locked_title"),
            message=t("validator.file_locked_msg", filename=os.path.basename(clean_path)),
            suggestion=t("validator.file_locked_sug"),
            detail=str(pe),
        )
    except Exception as exc:
        raise DocumentError(
            code=ErrorCode.FILE_LOCKED,
            title=t("validator.access_error_title"),
            message=t("validator.access_error_msg", filename=os.path.basename(clean_path), error=str(exc)),
            suggestion=t("validator.access_error_sug"),
            detail=str(exc),
        )

    # 5. STEP 5: File Size Check
    file_size = os.path.getsize(clean_path)
    if file_size == 0:
        raise DocumentError(
            code=ErrorCode.FILE_EMPTY,
            title=t("validator.file_empty_title"),
            message=t("validator.file_empty_msg", filename=os.path.basename(clean_path)),
            suggestion=t("validator.file_empty_sug"),
        )

    if file_size > 2 * 1024 * 1024 * 1024:
        raise DocumentError(
            code=ErrorCode.FILE_TOO_LARGE,
            title=t("validator.file_too_large_title"),
            message=t("validator.file_too_large_msg", filename=os.path.basename(clean_path)),
            suggestion=t("validator.file_too_large_sug"),
        )

    # 6. STEP 6: Format Integrity Check
    if ext == ".md":
        try:
            with open(clean_path, "r", encoding="utf-8") as f:
                chunk = f.read(4096)
                if "\x00" in chunk:
                    raise DocumentError(
                        code=ErrorCode.CORRUPTED_STRUCTURE,
                        title=t("validator.fake_md_title"),
                        message=t("validator.fake_md_msg", filename=os.path.basename(clean_path)),
                        suggestion=t("validator.fake_md_sug"),
                    )
        except UnicodeDecodeError:
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title=t("validator.encoding_title"),
                message=t("validator.encoding_msg", filename=os.path.basename(clean_path)),
                suggestion=t("validator.encoding_sug"),
            )

    elif ext in (".docx", ".xlsx", ".pptx"):
        if first_bytes == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            raise DocumentError(
                code=ErrorCode.PASSWORD_PROTECTED,
                title=t("validator.encrypted_office_title"),
                message=t("validator.encrypted_office_msg", filename=os.path.basename(clean_path)),
                suggestion=t("validator.encrypted_office_sug"),
            )
        elif not first_bytes.startswith(b"PK\x03\x04"):
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title=t("validator.corrupted_office_title"),
                message=t("validator.corrupted_office_msg", filename=os.path.basename(clean_path)),
                suggestion=t("validator.corrupted_office_sug"),
            )

        try:
            with zipfile.ZipFile(clean_path) as zf:
                if zf.testzip() is not None:
                    raise DocumentError(
                        code=ErrorCode.CORRUPTED_STRUCTURE,
                        title=t("validator.corrupted_zip_structure_title"),
                        message=t("validator.corrupted_zip_structure_msg", filename=os.path.basename(clean_path)),
                        suggestion=t("validator.corrupted_zip_structure_sug"),
                    )
                namelist = zf.namelist()
                if ext == ".docx" and "word/document.xml" not in namelist:
                    raise DocumentError(
                        code=ErrorCode.CORRUPTED_STRUCTURE,
                        title=t("validator.missing_word_xml_title"),
                        message=t("validator.missing_word_xml_msg"),
                        suggestion=t("validator.missing_word_xml_sug"),
                    )
                if ext == ".xlsx" and not any(n.startswith("xl/") for n in namelist):
                    raise DocumentError(
                        code=ErrorCode.CORRUPTED_STRUCTURE,
                        title=t("validator.missing_excel_xml_title"),
                        message=t("validator.missing_excel_xml_msg"),
                        suggestion=t("validator.missing_excel_xml_sug"),
                    )
                if ext == ".pptx" and not any(n.startswith("ppt/") for n in namelist):
                    raise DocumentError(
                        code=ErrorCode.CORRUPTED_STRUCTURE,
                        title=t("validator.missing_ppt_xml_title"),
                        message=t("validator.missing_ppt_xml_msg"),
                        suggestion=t("validator.missing_ppt_xml_sug"),
                    )
        except zipfile.BadZipFile:
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title=t("validator.corrupted_zip_title"),
                message=t("validator.corrupted_zip_msg", filename=os.path.basename(clean_path)),
                suggestion=t("validator.corrupted_zip_sug"),
            )

    elif ext == ".xls":
        if first_bytes != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title=t("validator.bad_xls_title"),
                message=t("validator.bad_xls_msg", filename=os.path.basename(clean_path)),
                suggestion=t("validator.bad_xls_sug"),
            )

    elif ext == ".pdf":
        if not first_bytes.startswith(b"%PDF"):
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title=t("validator.bad_pdf_title"),
                message=t("validator.bad_pdf_msg", filename=os.path.basename(clean_path)),
                suggestion=t("validator.bad_pdf_sug"),
            )

    elif ext == ".json":
        import json
        try:
            with open(clean_path, "r", encoding="utf-8-sig") as f:
                json.load(f)
        except Exception as exc:
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title=t("validator.corrupted_json_title"),
                message=t("validator.corrupted_json_msg", filename=os.path.basename(clean_path)),
                suggestion=t("validator.corrupted_json_sug"),
                detail=str(exc),
            )

    elif ext in (".yaml", ".yml"):
        try:
            import yaml
            with open(clean_path, "r", encoding="utf-8-sig") as f:
                yaml.safe_load(f)
        except ImportError:
            pass  # If pyyaml is missing, BaseDocumentModule.check_dependencies will handle warning
        except Exception as exc:
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title=t("validator.corrupted_yaml_title"),
                message=t("validator.corrupted_yaml_msg", filename=os.path.basename(clean_path)),
                suggestion=t("validator.corrupted_yaml_sug"),
                detail=str(exc),
            )

    return clean_path


def validate_file_integrity(path: str) -> Optional[Tuple[str, str]]:
    """
    Backward-compatibility wrapper around validate_file_pipeline.
    Returns (error_short, error_detail) tuple if invalid, or None if valid.
    """
    try:
        validate_file_pipeline(path)
        return None
    except DocumentError as err:
        return (err.title, err.message + (" " + err.suggestion if err.suggestion else ""))
    except Exception as exc:
        return (t("validator.integrity_check_error"), str(exc))
