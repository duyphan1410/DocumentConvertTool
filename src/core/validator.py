import re
import os
import sys
import zipfile
from typing import Optional, List, Tuple

from src.core.errors import DocumentError, ErrorCode


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
            table_name = f"Table #{table_index}"
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
                    f"'{table_name}' starting at line {table_start_line}: "
                    "The table is incomplete. A valid table must have at least a header row and a separator line (e.g., '| Header |' followed by '|---|')."
                )
                continue
                
            separator_line = table_lines[1]
            if not re.match(r"^[\|\s\-:]+$", separator_line):
                warnings.append(
                    f"'{table_name}' starting at line {table_start_line}: "
                    "Missing or incorrect separator line below the header. Please ensure the second line looks like '|---|---|'."
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
                        f"'{table_name}' at line {line_num}: "
                        f"This row has {len(r)} columns but the header has {header_col_count}. Please check if you are missing a '|' separator."
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
            title="Đường dẫn rỗng",
            message="Chưa cung cấp đường dẫn tệp tài liệu.",
            suggestion="Vui lòng chọn hoặc kéo thả tệp tài liệu vào ứng dụng.",
        )

    clean_path = os.path.normpath(path.strip())

    # 1. STEP 1: Existence Check (Checks path existence FIRST before extension)
    if not os.path.exists(clean_path):
        raise DocumentError(
            code=ErrorCode.FILE_NOT_FOUND,
            title="Tệp không tồn tại",
            message=f"Tệp tài liệu không tồn tại tại đường dẫn: '{clean_path}'.",
            suggestion="Vui lòng kiểm tra lại đường dẫn tệp hoặc di chuyển tệp về đúng vị trí.",
        )

    # 2. STEP 2: File Type / Directory / Windows .lnk Shortcut Check
    if os.path.isdir(clean_path):
        raise DocumentError(
            code=ErrorCode.IS_DIRECTORY,
            title="Thư mục không được hỗ trợ",
            message=f"Đường dẫn '{os.path.basename(clean_path)}' là một thư mục, không phải tệp tài liệu.",
            suggestion="Vui lòng chọn hoặc kéo thả tệp tài liệu đơn lẻ (.docx, .pdf, .xlsx, .md...).",
        )

    if clean_path.lower().endswith(".lnk"):
        resolved = resolve_windows_shortcut(clean_path)
        if not os.path.exists(resolved) or os.path.isdir(resolved):
            raise DocumentError(
                code=ErrorCode.FILE_NOT_FOUND,
                title="Phím tắt (.lnk) không hợp lệ",
                message=f"Phím tắt '{os.path.basename(clean_path)}' trỏ tới một tệp không tồn tại hoặc là một thư mục.",
                suggestion="Vui lòng kiểm tra lại đích đến của phím tắt.",
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
            title="Định dạng tệp không được hỗ trợ",
            message=f"Định dạng '{ext}' không được hệ thống hỗ trợ.",
            suggestion=f"Vui lòng chọn một tệp thuộc các định dạng sau: {valid_str}.",
        )

    # 4. STEP 4: Permission & Lock Check
    first_bytes = b""
    try:
        with open(clean_path, "rb") as f:
            first_bytes = f.read(8)
    except PermissionError as pe:
        raise DocumentError(
            code=ErrorCode.FILE_LOCKED,
            title="Tệp đang bị khóa",
            message=f"Tệp '{os.path.basename(clean_path)}' đang mở trong ứng dụng khác hoặc bị hạn chế quyền truy cập.",
            suggestion="Vui lòng đóng Microsoft Word, Excel hoặc trình đọc khác và thử lại.",
            detail=str(pe),
        )
    except Exception as exc:
        raise DocumentError(
            code=ErrorCode.FILE_LOCKED,
            title="Lỗi truy cập tệp",
            message=f"Không thể đọc tệp '{os.path.basename(clean_path)}': {exc}",
            suggestion="Vui lòng kiểm tra lại quyền truy cập của hệ điều hành.",
            detail=str(exc),
        )

    # 5. STEP 5: File Size Check
    file_size = os.path.getsize(clean_path)
    if file_size == 0:
        raise DocumentError(
            code=ErrorCode.FILE_EMPTY,
            title="Tệp rỗng (0 bytes)",
            message=f"Tệp '{os.path.basename(clean_path)}' có dung lượng 0 bytes và không chứa dữ liệu.",
            suggestion="Vui lòng chọn một tệp tài liệu có nội dung.",
        )

    if file_size > 2 * 1024 * 1024 * 1024:
        raise DocumentError(
            code=ErrorCode.FILE_TOO_LARGE,
            title="Tệp quá lớn (>2GB)",
            message=f"Tệp '{os.path.basename(clean_path)}' vượt quá giới hạn 2GB xử lý của trình chuyển đổi.",
            suggestion="Vui lòng nén hoặc chia nhỏ tài liệu trước khi nạp vào ứng dụng.",
        )

    # 6. STEP 6: Format Integrity Check
    if ext == ".md":
        try:
            with open(clean_path, "r", encoding="utf-8") as f:
                chunk = f.read(4096)
                if "\x00" in chunk:
                    raise DocumentError(
                        code=ErrorCode.CORRUPTED_STRUCTURE,
                        title="Đuôi tệp giả mạo",
                        message=f"Tệp '{os.path.basename(clean_path)}' có đuôi .md nhưng chứa nội dung nhị phân.",
                        suggestion="Vui lòng kiểm tra lại định dạng thật của tệp.",
                    )
        except UnicodeDecodeError:
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title="Mã hóa tệp không đúng",
                message=f"Tệp '{os.path.basename(clean_path)}' không đúng định dạng mã hóa văn bản UTF-8.",
                suggestion="Vui lòng lưu lại tệp với mã hóa UTF-8.",
            )

    elif ext in (".docx", ".xlsx"):
        if first_bytes == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            raise DocumentError(
                code=ErrorCode.PASSWORD_PROTECTED,
                title="Tệp bị mã hóa hoặc đặt mật khẩu",
                message=f"Tệp '{os.path.basename(clean_path)}' bị đặt mật khẩu hoặc lưu ở định dạng cũ .doc/.xls đổi tên.",
                suggestion="Vui lòng bỏ mật khẩu tệp trong Microsoft Office và đảm bảo chọn định dạng .docx/.xlsx hiện đại.",
            )
        elif not first_bytes.startswith(b"PK\x03\x04"):
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title="Tệp giả mạo hoặc hỏng",
                message=f"Tệp '{os.path.basename(clean_path)}' không có cấu trúc nén ZIP chuẩn của Microsoft Office.",
                suggestion="Hãy mở tệp trong Microsoft Office và Save As lại.",
            )

        try:
            with zipfile.ZipFile(clean_path) as zf:
                if zf.testzip() is not None:
                    raise DocumentError(
                        code=ErrorCode.CORRUPTED_STRUCTURE,
                        title="Cấu trúc tệp bị hỏng",
                        message=f"Tệp '{os.path.basename(clean_path)}' bị lỗi cấu trúc ZIP bên trong.",
                        suggestion="Mở tệp bằng MS Office để ứng dụng tự sửa lỗi.",
                    )
                namelist = zf.namelist()
                if ext == ".docx" and "word/document.xml" not in namelist:
                    raise DocumentError(
                        code=ErrorCode.CORRUPTED_STRUCTURE,
                        title="Thiếu cấu trúc Word OOXML",
                        message="Tệp là kho ZIP nhưng thiếu thành phần word/document.xml.",
                        suggestion="Hãy kiểm tra lại tệp Word đầu vào.",
                    )
                if ext == ".xlsx" and not any(n.startswith("xl/") for n in namelist):
                    raise DocumentError(
                        code=ErrorCode.CORRUPTED_STRUCTURE,
                        title="Thiếu cấu trúc Excel OOXML",
                        message="Tệp là kho ZIP nhưng thiếu thành phần xl/ workbook.",
                        suggestion="Hãy kiểm tra lại tệp Excel đầu vào.",
                    )
        except zipfile.BadZipFile:
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title="Kho lưu trữ ZIP bị hỏng",
                message=f"Tệp '{os.path.basename(clean_path)}' bị hỏng hoặc không phải tệp ZIP hợp lệ.",
                suggestion="Vui lòng kiểm tra lại tệp nguồn.",
            )

    elif ext == ".xls":
        if first_bytes != b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title="Lỗi định dạng Excel cũ (.xls)",
                message=f"Tệp '{os.path.basename(clean_path)}' không đúng mộc nhị phân của Excel legacy.",
                suggestion="Mở tệp bằng Excel và lưu sang định dạng hiện đại .xlsx.",
            )

    elif ext == ".pdf":
        if not first_bytes.startswith(b"%PDF"):
            raise DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title="Lỗi định dạng PDF",
                message=f"Tệp '{os.path.basename(clean_path)}' không chứa tiêu đề PDF hợp lệ (%PDF-).",
                suggestion="Vui lòng kiểm tra lại tệp PDF.",
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
        return ("Lỗi kiểm tra tệp", str(exc))
