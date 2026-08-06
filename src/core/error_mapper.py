import os
import sys
import traceback
import zipfile
from typing import Optional

from src.core.errors import DocumentError, ErrorCode


class ErrorMapper:
    """
    Centralized transformation layer that converts low-level Python exceptions
    into structured, desktop-friendly DocumentError domain exceptions.
    """

    @staticmethod
    def map_exception(
        exc: Exception,
        context_path: Optional[str] = None,
        stage: str = "read",
    ) -> DocumentError:
        """
        Maps an arbitrary exception to a DocumentError.
        
        Args:
            exc: The caught exception.
            context_path: Optional file path involved in the operation.
            stage: Operation stage ("read", "write", "convert").
        """
        if isinstance(exc, DocumentError):
            return exc

        file_name = os.path.basename(context_path) if context_path else "Tệp"
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        is_frozen = getattr(sys, "frozen", False)

        # 1. File Not Found
        if isinstance(exc, FileNotFoundError):
            return DocumentError(
                code=ErrorCode.FILE_NOT_FOUND,
                title="Tệp không tồn tại",
                message=f"Không tìm thấy tệp tài liệu tại đường dẫn: '{context_path or str(exc)}'.",
                suggestion="Vui lòng kiểm tra lại đường dẫn tệp hoặc di chuyển tệp về đúng vị trí.",
                detail=tb_str,
            )

        # 2. Is A Directory
        if isinstance(exc, IsADirectoryError):
            return DocumentError(
                code=ErrorCode.IS_DIRECTORY,
                title="Thư mục không được hỗ trợ",
                message=f"Đường dẫn '{file_name}' là một thư mục, không phải tệp tài liệu đơn lẻ.",
                suggestion="Vui lòng chọn hoặc kéo thả từng tệp tài liệu cụ thể (.docx, .pdf, .xlsx, .md...).",
                detail=tb_str,
            )

        # 3. Permission & Lock Errors (Context-stage aware)
        if isinstance(exc, PermissionError):
            if stage == "write":
                return DocumentError(
                    code=ErrorCode.READ_ONLY_SAVE_ERROR,
                    title="Không thể lưu tệp đầu ra",
                    message=f"Ứng dụng bị từ chối quyền ghi khi lưu tệp '{file_name}'.",
                    suggestion="Vui lòng kiểm tra xem tệp đầu ra có đang mở trong Microsoft Excel/Word không, hoặc kiểm tra quyền ghi của thư mục đích.",
                    detail=tb_str,
                )
            else:
                return DocumentError(
                    code=ErrorCode.FILE_LOCKED,
                    title="Tệp đang bị khóa hoặc bị ứng dụng khác mở",
                    message=f"Tài liệu '{file_name}' đang được sử dụng bởi một ứng dụng khác.",
                    suggestion="Tài liệu này hiện đang được mở trong Microsoft Word, Excel hoặc trình đọc khác. Vui lòng đóng ứng dụng đó và thử lại.",
                    detail=tb_str,
                )

        # 4. Missing Dependencies (ImportError / ModuleNotFoundError)
        if isinstance(exc, (ImportError, ModuleNotFoundError)):
            pkg_name = getattr(exc, "name", None) or str(exc)
            if is_frozen:
                suggestion = f"Tệp cài đặt hiện tại thiếu thành phần '{pkg_name}'. Vui lòng liên hệ nhà phát triển hoặc tải bản phát hành đầy đủ."
                install_cmd = None
            else:
                install_cmd = f"pip install {pkg_name}"
                suggestion = f"Vui lòng chạy lệnh '{install_cmd}' trong Terminal và khởi động lại ứng dụng."

            return DocumentError(
                code=ErrorCode.MISSING_DEPENDENCY,
                title="Thiếu thư viện phụ thuộc",
                message=f"Cần có thư viện mở rộng '{pkg_name}' để thực hiện thao tác này.",
                suggestion=suggestion,
                install_command=install_cmd,
                detail=tb_str,
            )

        # 5. Corrupted ZIP Structure (docx/xlsx)
        if isinstance(exc, zipfile.BadZipFile):
            return DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title="Cấu trúc tệp bị hỏng",
                message=f"Tệp '{file_name}' bị hỏng cấu trúc lưu trữ ZIP hoặc không phải tệp Word/Excel hợp lệ.",
                suggestion="Hãy mở tệp bằng Microsoft Office và bấm Save As để tự động khôi phục cấu trúc tệp.",
                detail=tb_str,
            )

        # 6. Text Decoding Error
        if isinstance(exc, UnicodeDecodeError):
            return DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title="Lỗi mã hóa ký tự",
                message=f"Tệp '{file_name}' chứa dữ liệu nhị phân không khớp với định dạng mã hóa UTF-8.",
                suggestion="Vui lòng kiểm tra lại định dạng tệp hoặc đảm bảo tệp được lưu với mã hóa UTF-8.",
                detail=tb_str,
            )

        # 7. Value Error / Conversion Error
        if isinstance(exc, ValueError):
            return DocumentError(
                code=ErrorCode.CONVERSION_FAILED,
                title="Lỗi tham số hoặc dữ liệu chuyển đổi",
                message=str(exc),
                suggestion="Vui lòng kiểm tra lại tùy chọn chuyển đổi và nội dung dữ liệu đầu vào.",
                detail=tb_str,
            )

        # 8. Catch-all General Unknown Error
        return DocumentError(
            code=ErrorCode.UNKNOWN_ERROR,
            title="Đã xảy ra lỗi không xác định",
            message=f"Đã xảy ra sự cố không mong muốn trong quá trình {stage} tệp '{file_name}': {str(exc)}",
            suggestion="Hãy thử lại thao tác hoặc sao chép log lỗi bên dưới để gửi báo cáo sự cố.",
            detail=tb_str,
        )
