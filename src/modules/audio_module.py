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
from src.i18n import t


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
                code=ErrorCode.MISSING_DEPENDENCY,
                title=t("audio.missing_whisper_title"),
                message=t("audio.missing_whisper_msg"),
                suggestion=t("audio.missing_whisper_sug"),
            )

        success, content, err = transcribe_file(file_path, model_id=model_id)
        if not success or not content:
            raise DocumentError(
                code=ErrorCode.CONVERSION_FAILED,
                title=t("audio.transcription_failed_title"),
                message=t("audio.transcription_failed_msg", filename=os.path.basename(file_path), error=err or t("audio.no_speech_detected")),
                suggestion=t("audio.transcription_failed_sug"),
            )

        return content

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        raise NotImplementedError("Xuất ngược Markdown sang định dạng âm thanh/video không được hỗ trợ.")


# Auto-register plugin
ModuleRegistry.register(AudioModule())
