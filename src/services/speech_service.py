"""
Local AI Speech-to-Text Transcription Service.
Transcribes audio from videos using locally installed faster-whisper models.
Requires a model to be downloaded via the Model Hub — no internet needed at runtime.
Adheres to the project Lazy Import standard.
"""
import os
import shutil
import tempfile
from typing import List, Optional, Tuple

from src.services.youtube_service import extract_video_id, fetch_video_metadata, format_timestamp


def download_youtube_audio(video_id: str, target_dir: str) -> Optional[str]:
    """
    Downloads lightweight audio stream from YouTube video into target_dir.
    Returns the absolute path to the downloaded audio file (.m4a/.webm).
    """
    try:
        import yt_dlp
    except ImportError as e:
        print(f"[DEBUG] Missing yt_dlp: {e}")
        return None

    out_template = os.path.join(target_dir, f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/18/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
            }
        },
    }

    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        for fname in os.listdir(target_dir):
            if fname.startswith(video_id):
                return os.path.join(target_dir, fname)
    except Exception as e:
        print(f"[DEBUG] yt-dlp audio download failed: {e}")

    return None


def get_best_installed_model() -> Optional[str]:
    """
    Returns the best available installed model ID.
    Priority order: whisper-small > whisper-base > whisper-tiny.
    Returns None if no model is installed.
    """
    from src.services.model_manager import is_model_installed

    priority = ["whisper-small", "whisper-base", "whisper-tiny"]
    for model_id in priority:
        if is_model_installed(model_id):
            return model_id
    return None


def preprocess_audio(
    input_file: str,
    target_sr: int = 16000,
) -> Optional[object]:
    """
    Decodes, downmixes, resamples, removes DC offset, and normalizes audio.
    Converts any video or audio format (MP4, MKV, WebM, MP3, WAV, etc.) to
    16,000 Hz Mono float32 PCM array ready for Whisper.

    Returns:
        np.ndarray of float32 samples in range [-1.0, 1.0], or None on error.
    """
    try:
        import av
        import numpy as np
        import io
        import gc
    except ImportError as e:
        print(f"[DEBUG] Missing dependencies for audio preprocessing: {e}")
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
        # Convert s16 back to f32 [-1.0, 1.0]
        audio = audio.astype(np.float32) / 32768.0

        # 1. DC Offset Removal (triệt tiêu lệch một chiều)
        audio = audio - np.mean(audio)

        # 2. Peak & RMS Volume Normalization
        max_peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
        if max_peak > 1e-4:
            # Normalize to -0.9 dBFS (~0.90), limit boost to 10.0x (20 dB) to avoid amplifying quiet noise
            gain = min(0.90 / max_peak, 10.0)
            audio = np.clip(audio * gain, -1.0, 1.0)
            print(f"[SPEECH] Audio preprocessed: {len(audio)} samples ({len(audio)/target_sr:.1f}s), peak={max_peak:.3f}->{np.max(np.abs(audio)):.3f}, gain={gain:.2f}x")
        else:
            print(f"[SPEECH] Audio preprocessed: near-silent audio ({len(audio)} samples)")

        return audio
    except Exception as e:
        print(f"[DEBUG] preprocess_audio failed: {e}")
        return None


def transcribe_audio_whisper(
    audio_input: object,
    model_id: str,
    language: Optional[str] = "vi",
    status_callback=None,
    return_info: bool = False,
):
    """
    Transcribes an audio file or preprocessed numpy array using a locally installed
    faster-whisper model with Silero VAD filtering and anti-hallucination settings.

    Args:
        audio_input: Path to audio/video file OR preprocessed 1D float32 numpy array.
        model_id: The installed model ID (e.g. 'whisper-base').
        language: Language code ('vi', 'en', 'auto', or None for auto-detect).
        status_callback: Optional callable(stage_name) for UI progress updates.
        return_info: If True, returns (results, detected_language).

    Returns:
        List of (start_timestamp_seconds, text) tuples, OR (results, detected_lang) if return_info=True.
    """
    try:
        import numpy as np  # noqa: F401 — must precede ctranslate2 for correct init order
        import ctranslate2  # noqa: F401
        from faster_whisper import WhisperModel
    except ImportError as e:
        print(f"[DEBUG] faster_whisper not available: {e}")
        return ([], "") if return_info else []

    from src.services.model_manager import get_model_path

    model_dir = get_model_path(model_id)
    if not os.path.isdir(model_dir):
        print(f"[DEBUG] Model directory not found: {model_dir}")
        return ([], "") if return_info else []

    # Preprocess audio if a file path was passed
    audio_data = audio_input
    if isinstance(audio_input, str):
        if status_callback:
            try:
                status_callback("preprocessing")
            except Exception:
                pass
        preprocessed = preprocess_audio(audio_input)
        if preprocessed is not None:
            audio_data = preprocessed

    # Language mapping: None or "auto" triggers Whisper's built-in 99-language detector
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

        print(f"[SPEECH] Loading {model_id} from {model_dir}...")
        model = WhisperModel(model_dir, device="cpu", compute_type="int8")

        transcribe_kwargs = {
            "beam_size": 5,
            # Silero VAD filter: removes silence and non-speech noise, eliminates 99% hallucinations
            "vad_filter": True,
            "vad_parameters": dict(
                min_silence_duration_ms=500,
                speech_pad_ms=300,
                threshold=0.5,
            ),
            # CRITICAL: Do NOT condition on previous text to avoid cascading error loops
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
            # Post-processing: deduplicate consecutive identical lines
            if text and text != last_text:
                results.append((seg.start, text))
                last_text = text

        detected_lang = getattr(info, "language", lang_code or "vi")
        del model  # Release memory
        print(f"[SPEECH] Transcription complete: {len(results)} segments (lang={detected_lang}).")

        if return_info:
            return results, detected_lang
        return results

    except Exception as e:
        print(f"[DEBUG] transcribe_audio_whisper failed: {e}")
        return ([], "") if return_info else []


def transcribe_youtube_speech(
    url_or_id: str,
    language: Optional[str] = "vi",
    include_timestamps: bool = True,
    status_callback=None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Full pipeline to transcribe speech from a YouTube video using local Whisper AI.
    No internet connection required for transcription (only for audio download).

    Args:
        url_or_id: YouTube video URL or ID.
        language: Language code ('vi', 'en', 'auto', or None for auto-detect).
        include_timestamps: Whether to prepend timestamp markers.
        status_callback: Optional callable(stage_name) for UI progress updates.

    Returns:
        (success: bool, markdown_content: str, error_code: Optional[str])
    """
    video_id = extract_video_id(url_or_id)
    if not video_id:
        return False, "", "ERR_INVALID_URL"

    # Check local model availability
    model_id = get_best_installed_model()
    if not model_id:
        return False, "", "ERR_NO_LOCAL_MODEL"

    # Check yt_dlp available for audio download
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return False, "", "ERR_MISSING_YTDLP"

    temp_dir = tempfile.mkdtemp(prefix="docconvert_speech_")
    try:
        # 1. Fetch Video Metadata
        meta = fetch_video_metadata(video_id)
        video_title = meta.get("title") or f"YouTube Video ({video_id})"
        author_name = meta.get("author") or ""

        # 2. Download audio stream
        if status_callback:
            status_callback("downloading")
        audio_file = download_youtube_audio(video_id, temp_dir)
        if not audio_file or not os.path.exists(audio_file):
            return False, "", "ERR_AUDIO_DOWNLOAD_FAILED"

        # 3. Preprocess & Transcribe with local Whisper
        print(f"[SPEECH] Starting Whisper transcription with model: {model_id}")
        chunks, detected_lang = transcribe_audio_whisper(
            audio_file,
            model_id=model_id,
            language=language,
            status_callback=status_callback,
            return_info=True,
        )
        if not chunks:
            return False, "", "ERR_NO_SPEECH_DETECTED"

        # 4. Format into Markdown
        from src.services.model_manager import AVAILABLE_MODELS
        model_display = AVAILABLE_MODELS.get(model_id, {})
        model_name = getattr(model_display, "display_name", model_id) if model_display else model_id

        if detected_lang == "vi":
            lang_display = "Vietnamese (vi)"
        elif detected_lang == "en":
            lang_display = "English (en)"
        else:
            lang_display = f"{detected_lang.upper()} ({detected_lang})"

        md_lines = [
            f"# {video_title}",
            "",
        ]
        if author_name:
            md_lines.append(f"- **Channel / Author**: {author_name}")
        md_lines.extend([
            f"- **Source URL**: https://www.youtube.com/watch?v={video_id}",
            f"- **Language**: {lang_display} [AI Transcription — {model_name}]",
            "",
            "---",
            "",
            "## Speech Transcript",
            "",
        ])

        # Group snippets into coherent paragraphs (similar to standard YouTube transcripts)
        from src.services.youtube_service import _group_snippets_into_sentences
        snippets = [{"start": s, "text": t} for s, t in chunks]
        timestamps, paragraph_list = _group_snippets_into_sentences(snippets)

        for ts, p_text in zip(timestamps, paragraph_list):
            if include_timestamps:
                ts_str = format_timestamp(ts)
                sec = int(ts)
                md_lines.append(f"**[[{ts_str}]](yt://{video_id}?t={sec})** {p_text}\n")
            else:
                md_lines.append(f"{p_text}\n")

        markdown_output = "\n".join(md_lines)
        return True, markdown_output, None

    except Exception as e:
        return False, "", f"ERR_SPEECH_TRANSCRIPTION: {str(e)}"
    finally:
        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass


def transcribe_drive_speech(
    file_id: str,
    audio_path: str,
    file_name: str = "",
    language: Optional[str] = "vi",
    include_timestamps: bool = True,
    status_callback=None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Transcribes speech from a locally downloaded Google Drive audio/video file.

    Args:
        file_id: Google Drive file ID.
        audio_path: Local path to the downloaded audio/video file.
        file_name: Original filename for Markdown header.
        language: Language code ('vi', 'en', 'auto', or None for auto-detect).
        include_timestamps: Whether to include timestamp markers.
        status_callback: Optional callable(stage_name) for UI progress updates.

    Returns:
        (success: bool, markdown_content: str, error_code: Optional[str])
    """
    # Check local model availability
    model_id = get_best_installed_model()
    if not model_id:
        return False, "", "ERR_NO_LOCAL_MODEL"

    if not audio_path or not os.path.exists(audio_path):
        return False, "", "ERR_AUDIO_DOWNLOAD_FAILED"

    try:
        # Transcribe with local Whisper + Audio Preprocessing
        print(f"[SPEECH] Starting Whisper transcription (Drive) with model: {model_id}")
        chunks, detected_lang = transcribe_audio_whisper(
            audio_path,
            model_id=model_id,
            language=language,
            status_callback=status_callback,
            return_info=True,
        )
        if not chunks:
            return False, "", "ERR_NO_SPEECH_DETECTED"

        # Format into Markdown
        from src.services.model_manager import AVAILABLE_MODELS
        model_meta = AVAILABLE_MODELS.get(model_id)
        model_name = model_meta.display_name if model_meta else model_id

        if detected_lang == "vi":
            lang_display = "Vietnamese (vi)"
        elif detected_lang == "en":
            lang_display = "English (en)"
        else:
            lang_display = f"{detected_lang.upper()} ({detected_lang})"

        title = file_name or f"Google Drive Video ({file_id})"
        drive_url = f"https://drive.google.com/file/d/{file_id}/view"

        md_lines = [
            f"# {title}",
            "",
            f"- **Source URL**: {drive_url}",
            f"- **Language**: {lang_display} [AI Transcription — {model_name}]",
            "",
            "---",
            "",
            "## Speech Transcript",
            "",
        ]

        # Group snippets into coherent paragraphs (similar to standard YouTube transcripts)
        from src.services.youtube_service import _group_snippets_into_sentences
        snippets = [{"start": s, "text": t} for s, t in chunks]
        timestamps, paragraph_list = _group_snippets_into_sentences(snippets)

        for ts, p_text in zip(timestamps, paragraph_list):
            if include_timestamps:
                ts_str = format_timestamp(ts)
                md_lines.append(f"**[{ts_str}]** {p_text}\n")
            else:
                md_lines.append(f"{p_text}\n")

        return True, "\n".join(md_lines), None

    except Exception as e:
        return False, "", f"ERR_SPEECH_TRANSCRIPTION: {str(e)}"
