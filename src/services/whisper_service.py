"""
Core Whisper AI Speech-to-Text Engine & Media Processing Service.
Handles audio extraction, multi-format decoding (PyAV), 16kHz resampling,
DC offset removal, volume normalization, and offline CTranslate2 inference.
Adheres to the project Lazy Import and Import Order Safety standards.
"""
import io
import gc
import os
import re
import shutil
import tempfile
from typing import Callable, List, Optional, Tuple

from src.services.youtube_service import format_timestamp, _group_snippets_into_sentences


def get_optimal_device_and_compute_type() -> Tuple[str, str]:
    """
    Evaluates system hardware and selects the best inference device and compute type.
    Uses CUDA float16 if an NVIDIA GPU with usable CUDA is present, otherwise CPU int8.
    """
    try:
        from src.services.hardware_detector import get_hardware_info
        hw = get_hardware_info()
        if hw.cuda_usable and hw.vram_free_mb >= 1000:
            return "cuda", "float16"
    except Exception as e:
        print(f"[DEBUG] Hardware detection error in whisper_service: {e}")
    return "cpu", "int8"


def get_best_installed_model() -> Optional[str]:
    """
    Returns the best available installed model ID.
    Priority order: whisper-large-v3 > whisper-medium > whisper-small > whisper-base.
    Returns None if no model is installed.
    """
    from src.services.model_manager import is_model_installed

    priority = ["whisper-large-v3", "whisper-medium", "whisper-small", "whisper-base"]
    for model_id in priority:
        if is_model_installed(model_id):
            return model_id
    return None


def preprocess_audio(
    input_file: str,
    target_sr: int = 16000,
) -> Optional[object]:
    """
    Decodes, downmixes to mono, resamples to target_sr, removes DC offset,
    and normalizes audio peak volume to -0.9 dBFS.
    Converts any audio or video container (.mp4, .mkv, .avi, .mov, .webm,
    .mp3, .wav, .m4a, .flac, .aac, .ogg) to 16kHz float32 PCM array.

    Returns:
        np.ndarray of float32 samples in range [-1.0, 1.0], or None on error.
    """
    try:
        import av
        import numpy as np
    except ImportError as e:
        print(f"[DEBUG] Missing PyAV or NumPy for audio preprocessing: {e}")
        return None

    if not input_file or not os.path.isfile(input_file) or os.path.getsize(input_file) == 0:
        return None

    try:
        resampler = av.audio.resampler.AudioResampler(
            format="s16",
            layout="mono",
            rate=target_sr,
        )

        raw_buffer = io.BytesIO()
        dtype = None

        with av.open(input_file, mode="r", metadata_errors="ignore") as container:
            if not container.streams.audio:
                print(f"[DEBUG] No audio stream found in {input_file}")
                return None

            frames = container.decode(audio=0)
            for frame in frames:
                for r_frame in resampler.resample(frame):
                    arr = r_frame.to_ndarray()
                    dtype = arr.dtype
                    raw_buffer.write(arr)

            # Flush remaining frames from resampler
            for r_frame in resampler.resample(None):
                arr = r_frame.to_ndarray()
                dtype = arr.dtype
                raw_buffer.write(arr)

        del resampler
        gc.collect()

        if raw_buffer.tell() == 0 or dtype is None:
            return None

        audio = np.frombuffer(raw_buffer.getvalue(), dtype=dtype)
        # Convert s16 to f32 [-1.0, 1.0]
        audio = audio.astype(np.float32) / 32768.0

        # 1. DC Offset Removal (triệt tiêu lệch một chiều)
        audio = audio - np.mean(audio)

        # 2. Peak Volume Normalization (-0.9 dBFS ~ 0.90)
        max_peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        if max_peak > 1e-4:
            gain = min(0.90 / max_peak, 10.0)
            audio = np.clip(audio * gain, -1.0, 1.0)
            print(f"[SPEECH] Audio preprocessed: {len(audio)} samples ({len(audio)/target_sr:.1f}s), peak={max_peak:.3f}->{np.max(np.abs(audio)):.3f}, gain={gain:.2f}x")
        else:
            print(f"[SPEECH] Audio preprocessed: near-silent audio ({len(audio)} samples)")

        return audio
    except Exception as e:
        print(f"[DEBUG] preprocess_audio failed for {input_file}: {e}")
        return None


def transcribe_audio_whisper(
    audio_input: object,
    model_id: str,
    language: Optional[str] = None,
    status_callback: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[float, float], None]] = None,
    return_info: bool = False,
):
    """
    Transcribes an audio file or preprocessed numpy array using a locally installed
    faster-whisper model with Silero VAD filtering and anti-hallucination configurations.

    Args:
        audio_input: Path to audio/video file OR preprocessed 1D float32 numpy array.
        model_id: The installed model ID (e.g. 'whisper-base').
        language: Language code ('vi', 'en', 'auto', or None for auto-detect).
        status_callback: Optional callable(stage_name) for UI status updates.
        on_progress: Optional callable(current_sec, total_sec) for progress updates.
        return_info: If True, returns (results, detected_language, total_duration).

    Returns:
        List of (start_timestamp_seconds, text) tuples, OR (results, detected_lang, duration) if return_info=True.
    """
    # CRITICAL: Always import numpy before ctranslate2 to prevent symbol lookup segfaults
    try:
        import numpy as np  # noqa: F401
        import ctranslate2  # noqa: F401
        from faster_whisper import WhisperModel
    except ImportError as e:
        print(f"[DEBUG] faster_whisper/ctranslate2 not available: {e}")
        return ([], "", 0.0) if return_info else []

    from src.services.model_manager import get_model_path

    model_dir = get_model_path(model_id)
    if not os.path.isdir(model_dir):
        print(f"[DEBUG] Model directory not found: {model_dir}")
        return ([], "", 0.0) if return_info else []

    # 1. Preprocess audio if input is a file path
    audio_data = audio_input
    total_duration = 0.0
    if isinstance(audio_input, str):
        if status_callback:
            try:
                status_callback("preprocessing")
            except Exception:
                pass
        preprocessed = preprocess_audio(audio_input)
        if preprocessed is not None:
            audio_data = preprocessed
            total_duration = len(audio_data) / 16000.0
    elif hasattr(audio_data, "__len__"):
        total_duration = len(audio_data) / 16000.0

    # 2. Map language parameters
    lang_code: Optional[str] = None
    if language:
        low = language.strip().lower()
        if low.startswith("vi"):
            lang_code = "vi"
        elif low.startswith("en"):
            lang_code = "en"
        elif low not in ("auto", "none", ""):
            lang_code = low[:2]

    try:
        if status_callback:
            try:
                status_callback("transcribing")
            except Exception:
                pass

        # 3. Determine device and compute type
        device, compute_type = get_optimal_device_and_compute_type()
        cpu_threads = min(8, os.cpu_count() or 1)
        print(f"[SPEECH] Loading {model_id} on {device} ({compute_type}, threads={cpu_threads})...")

        try:
            model = WhisperModel(
                model_dir,
                device=device,
                compute_type=compute_type,
                cpu_threads=cpu_threads,
            )
        except Exception as dev_err:
            if device != "cpu":
                print(f"[WARN] GPU initialization failed ({dev_err}), falling back to CPU int8")
                model = WhisperModel(
                    model_dir,
                    device="cpu",
                    compute_type="int8",
                    cpu_threads=cpu_threads,
                )
            else:
                raise dev_err

        # 4. Anti-hallucination transcription parameters
        transcribe_kwargs = {
            "beam_size": 5,
            # Silero VAD filter: removes silence and non-speech background noise
            "vad_filter": True,
            "vad_parameters": dict(
                min_silence_duration_ms=500,
                speech_pad_ms=300,
                threshold=0.5,
            ),
            # Prevents looping hallucinations on silent or repetitive audio
            "condition_on_previous_text": False,
            "compression_ratio_threshold": 2.4,
            "no_speech_threshold": 0.6,
        }

        if lang_code:
            transcribe_kwargs["language"] = lang_code
            if lang_code == "vi":
                transcribe_kwargs["initial_prompt"] = (
                    "Đây là văn bản tiếng Việt có dấu, viết hoa đầu câu và chấm câu đầy đủ."
                )
            elif lang_code == "en":
                transcribe_kwargs["initial_prompt"] = (
                    "This is a standard English transcript with proper capitalization and punctuation."
                )

        segments, info = model.transcribe(audio_data, **transcribe_kwargs)

        results: List[Tuple[float, str]] = []
        last_text = ""

        for seg in segments:
            text = seg.text.strip()
            # Deduplicate repeated identical lines
            if text and text != last_text:
                results.append((seg.start, text))
                last_text = text
            if on_progress and total_duration > 0:
                try:
                    on_progress(min(seg.end, total_duration), total_duration)
                except Exception:
                    pass

        detected_lang = getattr(info, "language", lang_code or "vi")
        if total_duration <= 0 and hasattr(info, "duration"):
            total_duration = float(info.duration)

        del model
        gc.collect()
        print(f"[SPEECH] Transcription complete: {len(results)} segments (lang={detected_lang}, duration={total_duration:.1f}s).")

        if return_info:
            return results, detected_lang
        return results

    except Exception as e:
        print(f"[DEBUG] transcribe_audio_whisper failed: {e}")
        return ([], "") if return_info else []


def transcribe_file(
    file_path: str,
    model_id: Optional[str] = None,
    language: Optional[str] = None,
    include_timestamps: bool = True,
    on_progress: Optional[Callable[[float, float], None]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    High-level API: Transcribes any local audio or video file and produces
    structured Markdown documentation with metadata and timestamped paragraphs.

    Args:
        file_path: Absolute path to the audio/video file.
        model_id: Model ID to use, or None to auto-select best installed.
        language: Language code ('vi', 'en', 'auto', or None).
        include_timestamps: Whether to format [mm:ss] timestamp anchors.
        on_progress: Callable(current_sec, total_sec) for progress bars.
        status_callback: Callable(stage_name) for text status changes.

    Returns:
        (success: bool, markdown_content: str, error_code: Optional[str])
    """
    if not file_path or not os.path.exists(file_path):
        return False, "", "ERR_FILE_NOT_FOUND"

    # Select best installed model if not specified
    target_model_id = model_id or get_best_installed_model()
    if not target_model_id:
        return False, "", "ERR_NO_LOCAL_MODEL"

    try:
        chunks, detected_lang = transcribe_audio_whisper(
            file_path,
            model_id=target_model_id,
            language=language,
            status_callback=status_callback,
            on_progress=on_progress,
            return_info=True,
        )

        if not chunks:
            return False, "", "ERR_NO_SPEECH_DETECTED"

        total_duration = chunks[-1][0] if chunks else 0.0

        # 1. Format metadata header
        from src.services.model_manager import AVAILABLE_MODELS
        meta = AVAILABLE_MODELS.get(target_model_id)
        model_name = meta.display_name if meta else target_model_id

        if detected_lang == "vi":
            lang_display = "Tiếng Việt (vi)"
        elif detected_lang == "en":
            lang_display = "English (en)"
        else:
            lang_display = f"{detected_lang.upper()} ({detected_lang})"

        base_name = os.path.basename(file_path)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        duration_str = format_timestamp(total_duration) if total_duration > 0 else "N/A"
        from src.i18n import t

        md_lines = [
            f"# {os.path.splitext(base_name)[0]}",
            "",
            f"| {t('transcript.info_table_info')} | {t('transcript.info_table_detail')} |",
            "| :--- | :--- |",
            f"| **{t('transcript.info_source_file')}** | `{base_name}` ({file_size_mb:.1f} MB) |",
            f"| **{t('transcript.info_ai_model')}** | {model_name} (`{target_model_id}`) |",
            f"| **{t('transcript.info_language')}** | {lang_display} |",
            f"| **{t('transcript.info_duration')}** | {duration_str} |",
            "",
            "---",
            "",
            f"## {t('transcript.section_speech_transcript')}",
            "",
        ]

        # 2. Group snippets into natural paragraphs by silence gaps and sentence boundaries
        snippets = [{"start": s, "text": t} for s, t in chunks]
        timestamps, paragraph_list = _group_snippets_into_sentences(snippets, pause_threshold=3.5)

        for ts, p_text in zip(timestamps, paragraph_list):
            if include_timestamps:
                ts_str = format_timestamp(ts)
                md_lines.append(f"**[{ts_str}]** {p_text}\n")
            else:
                md_lines.append(f"{p_text}\n")

        markdown_output = "\n".join(md_lines)
        return True, markdown_output, None

    except Exception as e:
        print(f"[DEBUG] transcribe_file error: {e}")
        return False, "", f"ERR_SPEECH_TRANSCRIPTION: {str(e)}"
