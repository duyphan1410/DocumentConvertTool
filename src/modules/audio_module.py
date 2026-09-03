"""
Audio/Video Document Module for Document Converter Tool.
Integrates local media files (.mp3, .wav, .m4a, .mp4, .mkv, etc.) with
the Whisper AI speech-to-text pipeline via the ModuleRegistry plugin pattern.
"""
import os
from typing import List

from src.core.base_module import BaseDocumentModule
from src.core.registry import ModuleRegistry
from src.core.errors import DocumentError, ErrorCode


class AudioModule(BaseDocumentModule):
    @property
    def name(self) -> str:
        return "Audio"

    @property
    def file_extensions(self) -> List[str]:
        return [
            ".mp3", ".wav", ".m4a", ".aac", ".flac",
            ".mp4", ".mkv", ".avi", ".mov", ".webm",
        ]

    @property
    def required_dependencies(self) -> List[str]:
        return ["faster-whisper", "av"]

    def load_to_markdown(self, file_path: str) -> str:
        from src.services.whisper_service import transcribe_file, get_best_installed_model

        model_id = get_best_installed_model()
        if not model_id:
            raise DocumentError(
                code=ErrorCode.DEPENDENCY_MISSING,
                title="Chưa cài đặt mô hình Whisper AI",
                message="Ứng dụng cần ít nhất một mô hình Whisper AI (offline) để nhận diện giọng nói từ tệp âm thanh/video.",
                suggestion="Mở AI Model Hub trên thanh Ribbon hoặc màn hình Chào mừng để tải nhanh Whisper Base (~145MB) hoặc Whisper Tiny (~75MB).",
            )

        success, content, err = transcribe_file(file_path, model_id=model_id)
        if not success or not content:
            raise DocumentError(
                code=ErrorCode.CONVERSION_FAILED,
                title="Nhận diện giọng nói thất bại",
                message=f"Không thể phiên âm tệp {os.path.basename(file_path)}: {err or 'Không phát hiện giọng nói'}.",
                suggestion="Kiểm tra lại tệp nguồn để đảm bảo có âm thanh rõ ràng và không bị hỏng.",
            )

        return content

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        raise NotImplementedError("Xuất ngược Markdown sang định dạng âm thanh/video không được hỗ trợ.")


# Auto-register plugin
ModuleRegistry.register(AudioModule())
