"""
Model Manager Service for Document Converter Tool.
Manages AI Model Hub Marketplace models, asynchronous downloads from HuggingFace,
dynamic drive space monitoring, local lifecycle (storage, deletion, cleanup),
and 2-Layer verification (File integrity & Independent runtime test).
"""
import asyncio
import hashlib
import logging
import os
import shutil
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from src.i18n import t

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata describing an AI Transcriber model."""
    model_id: str
    repo_id: str
    display_name: str
    size_mb: int
    speed_rating: int  # 1 (slow) to 5 (fast)
    accuracy_rating: int  # 1 (basic) to 5 (excellent)
    recommended_ram_gb: int
    recommended_vram_gb: int
    required_files: list[str] = field(default_factory=lambda: [
        "model.bin",
        "config.json",
        "vocabulary.txt",
        "tokenizer.json",
    ])
    description_vi: str = ""
    description_en: str = ""
    expected_sha256: dict[str, str] = field(default_factory=dict)


# Official Systran faster-whisper models for v1.9.0 with verified HuggingFace SHA256 checksums
AVAILABLE_MODELS: dict[str, ModelMetadata] = {
    "whisper-base": ModelMetadata(
        model_id="whisper-base",
        repo_id="Systran/faster-whisper-base",
        display_name="Whisper Base",
        size_mb=145,
        speed_rating=5,
        accuracy_rating=3,
        recommended_ram_gb=1,
        recommended_vram_gb=0,
        required_files=["model.bin", "config.json", "vocabulary.txt", "tokenizer.json"],
        description_vi="Nhẹ nhàng, tốc độ nhanh, phù hợp cho máy cấu hình cơ bản hoặc ghi chú ngắn.",
        description_en="Lightweight, fast speed, ideal for basic specs or short voice notes.",
        expected_sha256={
            "config.json": "56a6d8110d311f19c8f0471e562832c7527f146b567275bfca59fcf7c184da9a",
            "model.bin": "d01c3014881c9c6f3133c182f3d2887eb6ca1c789a7538c5c007196857a0a6a9",
            "tokenizer.json": "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
            "vocabulary.txt": "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
        },
    ),
    "whisper-small": ModelMetadata(
        model_id="whisper-small",
        repo_id="Systran/faster-whisper-small",
        display_name="Whisper Small",
        size_mb=480,
        speed_rating=4,
        accuracy_rating=4,
        recommended_ram_gb=2,
        recommended_vram_gb=2,
        required_files=["model.bin", "config.json", "vocabulary.txt", "tokenizer.json"],
        description_vi="Cân bằng hoàn hảo giữa tốc độ và độ chính xác cho văn phòng, podcast hàng ngày.",
        description_en="Perfect balance between speed and accuracy for daily office workflows and podcasts.",
        expected_sha256={
            "config.json": "b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828",
            "model.bin": "3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671",
            "tokenizer.json": "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
            "vocabulary.txt": "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
        },
    ),
    "whisper-medium": ModelMetadata(
        model_id="whisper-medium",
        repo_id="Systran/faster-whisper-medium",
        display_name="Whisper Medium",
        size_mb=1500,
        speed_rating=2,
        accuracy_rating=5,
        recommended_ram_gb=3,
        recommended_vram_gb=3,
        required_files=["model.bin", "config.json", "vocabulary.txt", "tokenizer.json"],
        description_vi="Độ chính xác cao, xử lý tuyệt vời bài giảng, video tiếng Việt và thuật ngữ chuyên ngành.",
        description_en="High accuracy multilingual recognition, excellent for Vietnamese lectures and specialized audio.",
        expected_sha256={
            "config.json": "3622a2ddc41ec0e0fd4e68c13c6830f03b90c38d89aaad184de02c8c642cf807",
            "model.bin": "9b45e1009dcc4ab601eff815b61d80e60ce3fd8c74c1a14f4a282258286b51ae",
            "tokenizer.json": "fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab",
            "vocabulary.txt": "34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913",
        },
    ),
    "whisper-large-v3": ModelMetadata(
        model_id="whisper-large-v3",
        repo_id="Systran/faster-whisper-large-v3",
        display_name="Whisper Large v3",
        size_mb=3100,
        speed_rating=1,
        accuracy_rating=5,
        recommended_ram_gb=5,
        recommended_vram_gb=6,
        required_files=["model.bin", "config.json", "vocabulary.json", "tokenizer.json"],
        description_vi="Đỉnh cao độ chính xác, xử lý các file hội thảo chuyên sâu, ngữ cảnh phức tạp và đa phương ngữ.",
        description_en="State of the art accuracy, handles deep seminars, accents, and complex acoustic contexts.",
        expected_sha256={
            "config.json": "a9306624f5ec14270a014b647e5c316b6e03a662c369758d1b90697a7b0655b9",
            "model.bin": "69f74147e3334731bc3a76048724833325d2ec74642fb52620eda87352e3d4f1",
            "tokenizer.json": "6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca",
            "vocabulary.json": "c69260f2ab26d659b7c398f9a2b2b48ed0df16c3b47d7326782fd9cba71690c1",
        },
    ),
}


def get_models_dir() -> str:
    """
    Returns the absolute directory path where AI models are stored:
    %APPDATA%\\DocConvert\\models (on Windows) or ~/.docconvert/models (on Unix).
    Ensures directory exists.
    """
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if not appdata:
            appdata = os.path.expanduser("~\\AppData\\Roaming")
        base_dir = os.path.join(appdata, "DocConvert", "models")
    else:
        base_dir = os.path.expanduser("~/.docconvert/models")

    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def get_target_drive() -> str:
    """
    Dynamically resolves the drive letter containing the models directory.
    Avoids hardcoding 'C:' for redirected profile environments.
    """
    models_dir = get_models_dir()
    drive = os.path.splitdrive(models_dir)[0]
    if not drive:
        drive = Path(models_dir).drive or "C:"
    return drive.upper()


def get_model_path(model_id: str) -> str:
    """Returns the local folder path for a specific model."""
    return os.path.join(get_models_dir(), model_id)


def is_model_installed(model_id: str) -> bool:
    """
    Checks if all required model files exist locally and are non-empty.
    """
    meta = AVAILABLE_MODELS.get(model_id)
    if not meta:
        return False

    model_dir = get_model_path(model_id)
    if not os.path.isdir(model_dir):
        return False

    for req_file in meta.required_files:
        fpath = os.path.join(model_dir, req_file)
        if not os.path.isfile(fpath) or os.path.getsize(fpath) == 0:
            return False

    return True


def get_installed_models() -> list[str]:
    """Returns a list of all model_ids currently installed and verified."""
    return [m_id for m_id in AVAILABLE_MODELS if is_model_installed(m_id)]


def get_storage_usage() -> tuple[float, float, str]:
    """
    Returns:
    - used_mb: Total disk space used by installed models in MB.
    - free_gb: Free space on the target drive in GB.
    - target_drive: Drive letter (e.g., 'C:', 'D:').
    """
    models_dir = get_models_dir()
    drive = get_target_drive()

    # 1. Calculate used size in models folder
    total_bytes = 0
    if os.path.exists(models_dir):
        for root, _, files in os.walk(models_dir):
            for f in files:
                fp = os.path.join(root, f)
                try:
                    total_bytes += os.path.getsize(fp)
                except OSError:
                    pass

    used_mb = round(total_bytes / (1024 ** 2), 1)

    # 2. Query free space on the drive
    try:
        usage = shutil.disk_usage(models_dir)
        free_gb = round(usage.free / (1024 ** 3), 1)
    except Exception as e:
        logger.debug(f"Failed to query disk usage on {models_dir}: {e}")
        free_gb = 0.0

    return used_mb, free_gb, drive


def delete_model(model_id: str) -> bool:
    """
    Safely removes an installed model directory.
    Returns True if deletion succeeded or folder did not exist.
    """
    model_dir = get_model_path(model_id)
    if os.path.exists(model_dir):
        try:
            shutil.rmtree(model_dir)
            logger.info(f"Deleted model directory: {model_dir}")
            print(f"[MODEL_HUB] Đã xóa model [{model_id}] thành công khỏi thư mục lưu trữ.")
            return True
        except Exception as e:
            logger.error(f"Failed to delete model {model_id}: {e}")
            print(f"[MODEL_HUB] [ERROR] Lỗi khi xóa model [{model_id}]: {e}")
            return False
    return True


def clean_all_models() -> bool:
    """
    Deletes all downloaded models to free disk space immediately.
    """
    models_dir = get_models_dir()
    success = True
    if os.path.exists(models_dir):
        for item in os.listdir(models_dir):
            item_path = os.path.join(models_dir, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except Exception as e:
                logger.error(f"Failed to remove {item_path}: {e}")
                print(f"[MODEL_HUB] [ERROR] Lỗi khi dọn dẹp {item_path}: {e}")
                success = False
    if success:
        print("[MODEL_HUB] Đã dọn dẹp toàn bộ các model AI đã tải xuống.")
    return success


def _compute_file_sha256(filepath: str) -> str:
    """Computes the SHA256 hex digest of a local file reading in 64KB blocks."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_model_files(model_id: str) -> bool:
    """
    Layer 1 Verification: Checks that all required weight and config files
    exist in the model directory, have non-zero size, and strictly match
    the official HuggingFace SHA256 checksums.
    """
    meta = AVAILABLE_MODELS.get(model_id)
    if not meta:
        return False

    model_dir = get_model_path(model_id)
    if not os.path.exists(model_dir):
        return False

    for req_file in meta.required_files:
        fpath = os.path.join(model_dir, req_file)
        if not os.path.exists(fpath):
            logger.warning(f"Model {model_id} is missing required file: {req_file}")
            return False
        # Size sanity check
        if os.path.getsize(fpath) == 0:
            logger.warning(f"Model {model_id} file {req_file} has 0 bytes.")
            return False

        # Strict SHA256 checksum verification against HuggingFace ground truth
        expected_hash = meta.expected_sha256.get(req_file)
        if expected_hash:
            actual_hash = _compute_file_sha256(fpath)
            if actual_hash.lower() != expected_hash.lower():
                logger.error(
                    f"Model {model_id} file {req_file} checksum mismatch! "
                    f"Expected: {expected_hash}, Actual: {actual_hash}"
                )
                print(f"[MODEL_HUB] [ERROR] File {req_file} sai mã băm SHA256 ({actual_hash[:8]} != {expected_hash[:8]}).")
                return False

    return True


def verify_model_runtime(model_id: str, device: str = "cpu") -> bool:
    """
    Layer 2 Verification: Tests instantiate of WhisperModel in memory.
    Ensures that libcublas/cudnn or CPU backend works with downloaded weights.
    """
    if not is_model_installed(model_id):
        return False

    model_dir = get_model_path(model_id)
    try:
        # Enforce safety import order rule: numpy -> ctranslate2 -> faster_whisper
        import numpy
        import ctranslate2
        from faster_whisper import WhisperModel

        logger.info(f"Testing runtime load of {model_id} from {model_dir} on {device}...")
        # Instantiate model with minimal int8 compute
        model = WhisperModel(model_dir, device=device, compute_type="int8")
        del model  # Release memory
        logger.info(f"Layer 2 runtime verification succeeded for {model_id}!")
        return True
    except Exception as e:
        logger.error(f"Layer 2 runtime verification failed for {model_id}: {e}")
        return False


_ACTIVE_DOWNLOADS: dict[str, threading.Event] = {}
_DOWNLOAD_PROGRESS: dict[str, dict] = {}
_PROGRESS_LISTENERS: dict[str, list[Callable[[float, str], None]]] = {}


def is_model_downloading(model_id: str) -> bool:
    """Returns True if the specified model is currently being downloaded."""
    return model_id in _ACTIVE_DOWNLOADS


def get_model_download_progress(model_id: str) -> Optional[dict]:
    """Returns the latest progress snapshot for an actively downloading model."""
    return _DOWNLOAD_PROGRESS.get(model_id)


def add_download_listener(model_id: str, callback: Callable[[float, str], None]):
    """Registers a UI listener for live download progress updates across views."""
    if model_id not in _PROGRESS_LISTENERS:
        _PROGRESS_LISTENERS[model_id] = []
    if callback not in _PROGRESS_LISTENERS[model_id]:
        _PROGRESS_LISTENERS[model_id].append(callback)


def remove_download_listener(model_id: str, callback: Callable[[float, str], None]):
    """Unregisters a UI listener when control/card is unmounted."""
    if model_id in _PROGRESS_LISTENERS:
        _PROGRESS_LISTENERS[model_id] = [cb for cb in _PROGRESS_LISTENERS[model_id] if cb != callback]


def _notify_progress(model_id: str, pct: float, msg: str, direct_callback: Optional[Callable[[float, str], None]] = None):
    """Updates global state and broadcasts progress to all active listeners."""
    _DOWNLOAD_PROGRESS[model_id] = {"pct": pct, "msg": msg}
    if direct_callback:
        try:
            direct_callback(pct, msg)
        except Exception:
            pass
    for listener in list(_PROGRESS_LISTENERS.get(model_id, [])):
        try:
            listener(pct, msg)
        except Exception:
            pass


def register_model_download(model_id: str) -> threading.Event:
    """Registers an active download event before async thread execution."""
    evt = threading.Event()
    _ACTIVE_DOWNLOADS[model_id] = evt
    _DOWNLOAD_PROGRESS[model_id] = {"pct": 0.05, "msg": t("model_hub.progress_starting")}
    return evt


def cancel_model_download(model_id: str) -> bool:
    """Signals cancellation to an active download thread if one exists."""
    evt = _ACTIVE_DOWNLOADS.pop(model_id, None)
    _DOWNLOAD_PROGRESS.pop(model_id, None)
    _PROGRESS_LISTENERS.pop(model_id, None)
    if evt:
        evt.set()
        logger.info(f"Cancellation signal sent for model download: {model_id}")
        print(f"[MODEL_HUB] Đã gửi tín hiệu hủy tải cho model [{model_id}]...")
        return True
    return False


def download_model(
    model_id: str,
    progress_callback: Optional[Callable[[float, str], None]] = None,
    cancel_event: Optional[threading.Event] = None,
) -> bool:
    """
    Downloads model weights snapshot from HuggingFace directly to %APPDATA%\\DocConvert\\models\\<model_id>.
    Uses chunked streaming to enable instant cancellation and accurate MB progress updates.
    
    Args:
        model_id: The identifier from AVAILABLE_MODELS.
        progress_callback: Callback(percent: float, message: str) for real-time UI updates.
        cancel_event: threading.Event to signal user cancellation.
        
    Returns:
        bool: True if download and Layer 1 verification completed successfully.
    """
    meta = AVAILABLE_MODELS.get(model_id)
    if not meta:
        raise ValueError(f"Unknown model_id: {model_id}")

    evt = cancel_event or _ACTIVE_DOWNLOADS.get(model_id) or threading.Event()
    _ACTIVE_DOWNLOADS[model_id] = evt

    target_dir = get_model_path(model_id)
    os.makedirs(target_dir, exist_ok=True)
    print(f"[MODEL_HUB] Bắt đầu tải model [{model_id}] từ {meta.repo_id} (~{meta.size_mb} MB)...")

    _notify_progress(model_id, 0.05, t("model_hub.progress_connecting", repo=meta.repo_id), progress_callback)

    try:
        import requests
        from huggingface_hub import hf_hub_url

        total_files = len(meta.required_files)
        total_model_bytes = meta.size_mb * 1024 * 1024
        downloaded_total_bytes = 0
        last_notify_time = 0.0

        for i, fname in enumerate(meta.required_files):
            if evt.is_set():
                print(f"[MODEL_HUB] Đã hủy tải model [{model_id}] thành công. Đang dọn dẹp file tạm...")
                delete_model(model_id)
                return False

            file_url = hf_hub_url(repo_id=meta.repo_id, filename=fname)
            dest_file = os.path.join(target_dir, fname)
            tmp_file = dest_file + ".tmp"

            response = requests.get(file_url, stream=True, timeout=20)
            response.raise_for_status()

            with open(tmp_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if evt.is_set():
                        f.close()
                        if os.path.exists(tmp_file):
                            try:
                                os.remove(tmp_file)
                            except Exception:
                                pass
                        print(f"[MODEL_HUB] Đã hủy tải model [{model_id}] thành công. Đang dọn dẹp file tạm...")
                        delete_model(model_id)
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded_total_bytes += len(chunk)
                        now = time.time()
                        # Throttle progress notifications to ~6-7 per second (every 0.15s)
                        if now - last_notify_time >= 0.15:
                            last_notify_time = now
                            pct = min(0.92, max(0.05, downloaded_total_bytes / max(1, total_model_bytes)))
                            mb_done = downloaded_total_bytes / (1024 * 1024)
                            _notify_progress(
                                model_id,
                                pct,
                                t("model_hub.progress_downloading", file=fname, done=f"{mb_done:.1f}", total=meta.size_mb),
                                progress_callback,
                            )

            if os.path.exists(tmp_file):
                os.replace(tmp_file, dest_file)

        if evt.is_set():
            delete_model(model_id)
            return False

        _notify_progress(model_id, 0.95, t("model_hub.progress_verifying"), progress_callback)

        # Layer 1 File Integrity verification
        if not verify_model_files(model_id):
            user_err = t("model_hub.error_corrupted")
            logger.error(f"Model files verification failed for {model_id} after download.")
            print(f"[MODEL_HUB] [ERROR] Xác thực file thất bại cho model [{model_id}].")
            _notify_progress(model_id, 0.0, user_err, progress_callback)
            delete_model(model_id)
            return False

        _notify_progress(model_id, 1.0, t("model_hub.progress_complete"), progress_callback)

        print(f"[MODEL_HUB] Tải và xác thực model [{model_id}] thành công! (Dung lượng: ~{meta.size_mb} MB)")
        return True

    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "Too Many Requests" in err_msg:
            user_err = t("model_hub.error_rate_limit")
        elif "SSL" in err_msg or "Certificate" in err_msg:
            user_err = t("model_hub.error_ssl_network")
        elif "No space left on device" in err_msg or "Disk full" in err_msg:
            user_err = t("model_hub.error_disk_full")
        elif "Permission denied" in err_msg or "Access is denied" in err_msg:
            user_err = t("model_hub.error_permission")
        else:
            user_err = t("model_hub.download_failed", name=meta.display_name, error=err_msg[:80])

        logger.error(f"Download failed for model {model_id}: {e}")
        print(f"[MODEL_HUB] [ERROR] Tải model [{model_id}] thất bại: {e}")
        _notify_progress(model_id, 0.0, user_err, progress_callback)
        delete_model(model_id)
        return False
    finally:
        _ACTIVE_DOWNLOADS.pop(model_id, None)
        _DOWNLOAD_PROGRESS.pop(model_id, None)
        _PROGRESS_LISTENERS.pop(model_id, None)
