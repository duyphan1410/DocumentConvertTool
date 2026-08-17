import os
import sys
import traceback
import zipfile
from typing import Optional

from src.core.errors import DocumentError, ErrorCode
from src.i18n import t


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
                title=t("error.file_not_found_title"),
                message=t("error.file_not_found_msg", path=context_path or str(exc)),
                suggestion=t("error.file_not_found_sug"),
                detail=tb_str,
            )

        # 2. Is A Directory
        if isinstance(exc, IsADirectoryError):
            return DocumentError(
                code=ErrorCode.IS_DIRECTORY,
                title=t("error.is_directory_title"),
                message=t("error.is_directory_msg", filename=file_name),
                suggestion=t("error.is_directory_sug"),
                detail=tb_str,
            )

        # 3. Permission & Lock Errors (Context-stage aware)
        if isinstance(exc, PermissionError):
            if stage == "write":
                return DocumentError(
                    code=ErrorCode.READ_ONLY_SAVE_ERROR,
                    title=t("error.save_permission_title"),
                    message=t("error.save_permission_msg", filename=file_name),
                    suggestion=t("error.save_permission_sug"),
                    detail=tb_str,
                )
            else:
                return DocumentError(
                    code=ErrorCode.FILE_LOCKED,
                    title=t("error.file_locked_title"),
                    message=t("error.file_locked_msg", filename=file_name),
                    suggestion=t("error.file_locked_sug"),
                    detail=tb_str,
                )

        # 4. Missing Dependencies (ImportError / ModuleNotFoundError)
        if isinstance(exc, (ImportError, ModuleNotFoundError)):
            pkg_name = getattr(exc, "name", None) or str(exc)
            if is_frozen:
                suggestion = t("error.missing_dep_sug_frozen", pkg=pkg_name)
                install_cmd = None
            else:
                install_cmd = f"pip install {pkg_name}"
                suggestion = t("error.missing_dep_sug_dev", cmd=install_cmd)

            return DocumentError(
                code=ErrorCode.MISSING_DEPENDENCY,
                title=t("error.missing_dep_title"),
                message=t("error.missing_dep_msg", pkg=pkg_name),
                suggestion=suggestion,
                install_command=install_cmd,
                detail=tb_str,
            )

        # 5. Corrupted ZIP Structure (docx/xlsx)
        if isinstance(exc, zipfile.BadZipFile):
            return DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title=t("error.corrupted_zip_title"),
                message=t("error.corrupted_zip_msg", filename=file_name),
                suggestion=t("error.corrupted_zip_sug"),
                detail=tb_str,
            )

        # 6. Text Decoding Error
        if isinstance(exc, UnicodeDecodeError):
            return DocumentError(
                code=ErrorCode.CORRUPTED_STRUCTURE,
                title=t("error.encoding_title"),
                message=t("error.encoding_msg", filename=file_name),
                suggestion=t("error.encoding_sug"),
                detail=tb_str,
            )

        # 7. Value Error / Conversion Error
        if isinstance(exc, ValueError):
            return DocumentError(
                code=ErrorCode.CONVERSION_FAILED,
                title=t("error.conversion_val_title"),
                message=str(exc),
                suggestion=t("error.conversion_val_sug"),
                detail=tb_str,
            )

        # 8. Catch-all General Unknown Error
        return DocumentError(
            code=ErrorCode.UNKNOWN_ERROR,
            title=t("error.unknown_title"),
            message=t("error.unknown_msg", filename=file_name, stage=stage, error=str(exc)),
            suggestion=t("error.unknown_sug"),
            detail=tb_str,
        )
