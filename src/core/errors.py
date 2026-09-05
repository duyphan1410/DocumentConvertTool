import uuid
import datetime
from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    UNSUPPORTED_EXTENSION = "UNSUPPORTED_EXTENSION"
    IS_DIRECTORY = "IS_DIRECTORY"
    FILE_LOCKED = "FILE_LOCKED"
    FILE_EMPTY = "FILE_EMPTY"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    CORRUPTED_STRUCTURE = "CORRUPTED_STRUCTURE"
    PASSWORD_PROTECTED = "PASSWORD_PROTECTED"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
    CONVERSION_FAILED = "CONVERSION_FAILED"
    READ_ONLY_SAVE_ERROR = "READ_ONLY_SAVE_ERROR"
    MODEL_DOWNLOAD_FAILED = "MODEL_DOWNLOAD_FAILED"
    MODEL_VERIFICATION_FAILED = "MODEL_VERIFICATION_FAILED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class DocumentError(Exception):
    """
    Standardized domain exception for DocumentConverterTool.
    Provides structured error codes, human-friendly titles/messages,
    desktop-oriented actionable suggestions, optional pip commands,
    and unique Error IDs for logging.
    """
    def __init__(
        self,
        code: ErrorCode,
        title: str,
        message: str,
        suggestion: str = "",
        install_command: Optional[str] = None,
        detail: str = "",
        error_id: Optional[str] = None,
    ):
        super().__init__(message)
        self.code = code
        self.title = title
        self.message = message
        self.suggestion = suggestion
        self.install_command = install_command
        self.detail = detail
        self.timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.error_id = error_id or f"ERR-{datetime.datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    def to_log_string(self) -> str:
        """Formats error payload into a structured string for logging and copying."""
        lines = [
            f"Error ID: {self.error_id}",
            f"Time: {self.timestamp}",
            f"Code: {self.code.value}",
            f"Title: {self.title}",
            f"Message: {self.message}",
        ]
        if self.suggestion:
            lines.append(f"Suggestion: {self.suggestion}")
        if self.install_command:
            lines.append(f"Install Command: {self.install_command}")
        if self.detail:
            lines.append(f"Technical Detail:\n{self.detail}")
        return "\n".join(lines)
