"""
Hardware Detector Service for Document Converter Tool.
Scans system CPU, RAM, NVIDIA GPU (Driver, CUDA version, VRAM)
without requiring PyTorch overhead, providing smart model recommendations.
"""
from dataclasses import dataclass
import os
import platform
import subprocess
import sys
from typing import Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class HardwareInfo:
    """Dataclass holding normalized system hardware metrics."""
    cpu_name: str = "Unknown CPU"
    cpu_cores: int = 1
    ram_total_gb: float = 0.0
    ram_free_gb: float = 0.0
    has_nvidia_gpu: bool = False
    gpu_name: Optional[str] = None
    gpu_driver_version: Optional[str] = None
    gpu_cuda_version: Optional[str] = None
    vram_total_mb: float = 0.0
    vram_free_mb: float = 0.0
    cpu_mhz: Optional[int] = None
    cuda_usable: bool = False

    def get_summary_text(self) -> str:
        """Returns a formatted hardware summary line for UI headers."""
        freq_str = f" @ {self.cpu_mhz / 1000.0:.1f}GHz" if self.cpu_mhz else ""
        cpu_text = f"{self.cpu_name} ({self.cpu_cores} Cores{freq_str})"
        ram_text = f"{self.ram_total_gb:.1f}GB RAM"
        if self.has_nvidia_gpu and self.gpu_name:
            vram_text = f"{self.vram_total_mb / 1024:.1f}GB VRAM"
            cuda_text = f", CUDA {self.gpu_cuda_version}" if self.gpu_cuda_version else ""
            driver_text = f", Driver {self.gpu_driver_version}" if self.gpu_driver_version else ""
            gpu_text = f"GPU: {self.gpu_name} ({vram_text}{driver_text}{cuda_text})"
        elif self.gpu_name:
            driver_text = f" (Driver {self.gpu_driver_version})" if self.gpu_driver_version else ""
            gpu_text = f"GPU: {self.gpu_name}{driver_text}"
        else:
            gpu_text = "GPU: CPU/Integrated Graphics"
        return f"{cpu_text} | {ram_text} | {gpu_text}"


def _get_cpu_info() -> tuple[str, int, Optional[int]]:
    """Extracts CPU model name, physical/logical core count, and clock speed in MHz."""
    cores = os.cpu_count() or 1
    cpu_name = platform.processor() or "Generic CPU"
    cpu_mhz: Optional[int] = None
    
    # On Windows, try to get friendly CPU string and ~MHz from registry
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            cpu_name = winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
            try:
                cpu_mhz = int(winreg.QueryValueEx(key, "~MHz")[0])
            except Exception:
                pass
            winreg.CloseKey(key)
        except Exception:
            cpu_name = os.environ.get("PROCESSOR_IDENTIFIER", cpu_name)
            
    return cpu_name, cores, cpu_mhz


def _get_ram_info() -> tuple[float, float]:
    """Extracts total and free system RAM in GB."""
    try:
        if sys.platform == "win32":
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_gb = stat.ullTotalPhys / (1024 ** 3)
                free_gb = stat.ullAvailPhys / (1024 ** 3)
                return round(total_gb, 2), round(free_gb, 2)
    except Exception as e:
        logger.debug(f"Direct Windows RAM query failed: {e}")
        
    # Safe fallback if query fails (0.0 means unknown)
    return 0.0, 0.0


def _query_gpu_nvml() -> Optional[dict]:
    """Queries NVIDIA GPU properties via official nvidia-ml-py bindings."""
    try:
        # Lazy import nvidia_ml_py or pynvml
        try:
            import pynvml
            nvml = pynvml
        except ImportError:
            import nvidia_ml_py as nvml

        nvml.nvmlInit()
        device_count = nvml.nvmlDeviceGetCount()
        if device_count == 0:
            nvml.nvmlShutdown()
            return None

        # Query the primary device (index 0)
        handle = nvml.nvmlDeviceGetHandleByIndex(0)
        name_raw = nvml.nvmlDeviceGetName(handle)
        gpu_name = name_raw.decode("utf-8") if isinstance(name_raw, bytes) else str(name_raw)

        driver_raw = nvml.nvmlSystemGetDriverVersion()
        driver_ver = driver_raw.decode("utf-8") if isinstance(driver_raw, bytes) else str(driver_raw)

        cuda_ver_str = None
        try:
            cuda_ver_int = nvml.nvmlSystemGetCudaDriverVersion_v2()
            major = cuda_ver_int // 1000
            minor = (cuda_ver_int % 1000) // 10
            cuda_ver_str = f"{major}.{minor}"
        except Exception:
            try:
                cuda_ver_int = nvml.nvmlSystemGetCudaDriverVersion()
                major = cuda_ver_int // 1000
                minor = (cuda_ver_int % 1000) // 10
                cuda_ver_str = f"{major}.{minor}"
            except Exception:
                pass

        mem_info = nvml.nvmlDeviceGetMemoryInfo(handle)
        vram_total_mb = mem_info.total / (1024 ** 2)
        vram_free_mb = mem_info.free / (1024 ** 2)

        nvml.nvmlShutdown()

        return {
            "name": gpu_name,
            "driver": driver_ver,
            "cuda": cuda_ver_str,
            "total_mb": round(vram_total_mb, 1),
            "free_mb": round(vram_free_mb, 1),
        }
    except Exception as e:
        logger.debug(f"NVML detection failed or not available: {e}")
        return None


def _query_gpu_nvidia_smi() -> Optional[dict]:
    """Fallback query via nvidia-smi CLI command."""
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=gpu_name,driver_version,memory.total,memory.free",
            "--format=csv,noheader,nounits",
        ]
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode == 0 and result.stdout.strip():
            line = result.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 4:
                return {
                    "name": parts[0],
                    "driver": parts[1],
                    "cuda": None,
                    "total_mb": float(parts[2]),
                    "free_mb": float(parts[3]),
                }
    except Exception as e:
        logger.debug(f"nvidia-smi CLI query failed: {e}")
    return None


def _query_gpu_windows_registry() -> Optional[dict]:
    """Queries any installed GPU display adapters (AMD, Intel, NVIDIA) from Windows Registry."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        gpus = []
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(k, i)
                i += 1
                if sub.isdigit():
                    sk = winreg.OpenKey(k, sub)
                    try:
                        name = winreg.QueryValueEx(sk, "DriverDesc")[0]
                        driver = winreg.QueryValueEx(sk, "DriverVersion")[0]
                        if name and not str(name).lower().startswith("microsoft basic"):
                            gpus.append({"name": str(name), "driver": str(driver)})
                    except Exception:
                        pass
                    winreg.CloseKey(sk)
            except OSError:
                break
        winreg.CloseKey(k)

        if not gpus:
            return None

        # Prioritize dedicated/discrete GPUs over integrated graphics
        for g in gpus:
            lower = g["name"].lower()
            if any(term in lower for term in ["rtx", "gtx", "radeon rx", " rx ", "arc", "geforce", "discrete"]):
                return {
                    "name": g["name"],
                    "driver": g["driver"],
                    "cuda": None,
                    "total_mb": 0.0,
                    "free_mb": 0.0,
                }
        return {
            "name": gpus[0]["name"],
            "driver": gpus[0]["driver"],
            "cuda": None,
            "total_mb": 0.0,
            "free_mb": 0.0,
        }
    except Exception as e:
        logger.debug(f"Windows Registry GPU query failed: {e}")
        return None


_CACHED_HARDWARE: Optional[HardwareInfo] = None


def detect_hardware(force_refresh: bool = False) -> HardwareInfo:
    """
    Main detection entrypoint. Evaluates CPU, RAM, and GPU metrics.
    Results are cached in-memory after the first scan for 0ms instant retrieval.
    Pass force_refresh=True to force a hardware re-scan.
    """
    global _CACHED_HARDWARE
    if _CACHED_HARDWARE is not None and not force_refresh:
        return _CACHED_HARDWARE

    cpu_name, cpu_cores, cpu_mhz = _get_cpu_info()
    ram_total_gb, ram_free_gb = _get_ram_info()

    # Query GPU: Try NVML first, fallback to nvidia-smi CLI, fallback to Windows Registry (AMD/Intel)
    gpu_data = _query_gpu_nvml()
    is_nvidia = True
    if not gpu_data:
        gpu_data = _query_gpu_nvidia_smi()
    if not gpu_data:
        gpu_data = _query_gpu_windows_registry()
        is_nvidia = False

    if gpu_data and is_nvidia:
        vram_total = gpu_data.get("total_mb", 0.0)
        vram_free = gpu_data.get("free_mb", 0.0)
        driver_ver = gpu_data.get("driver")
        cuda_ver = gpu_data.get("cuda")

        # Evaluate cuda_usable condition:
        # 1. Total VRAM >= 2048 MB
        # 2. Driver version exists and is modern (>= 450)
        cuda_usable = False
        if vram_total >= 2048:
            try:
                major_driver = float(driver_ver.split(".")[0]) if driver_ver else 0
                if major_driver >= 450:
                    cuda_usable = True
            except Exception:
                cuda_usable = True  # If parsing fails but driver exists, give benefit of doubt

        info = HardwareInfo(
            cpu_name=cpu_name,
            cpu_cores=cpu_cores,
            cpu_mhz=cpu_mhz,
            ram_total_gb=ram_total_gb,
            ram_free_gb=ram_free_gb,
            has_nvidia_gpu=True,
            gpu_name=gpu_data.get("name", "NVIDIA GPU"),
            gpu_driver_version=driver_ver,
            gpu_cuda_version=cuda_ver,
            vram_total_mb=vram_total,
            vram_free_mb=vram_free,
            cuda_usable=cuda_usable,
        )
    elif gpu_data:
        # Non-NVIDIA GPU detected (e.g. AMD Radeon RX 5500M, Intel Iris)
        info = HardwareInfo(
            cpu_name=cpu_name,
            cpu_cores=cpu_cores,
            cpu_mhz=cpu_mhz,
            ram_total_gb=ram_total_gb,
            ram_free_gb=ram_free_gb,
            has_nvidia_gpu=False,
            gpu_name=gpu_data.get("name"),
            gpu_driver_version=gpu_data.get("driver"),
            gpu_cuda_version=None,
            vram_total_mb=0.0,
            vram_free_mb=0.0,
            cuda_usable=False,
        )
    else:
        # No GPU found
        info = HardwareInfo(
            cpu_name=cpu_name,
            cpu_cores=cpu_cores,
            cpu_mhz=cpu_mhz,
            ram_total_gb=ram_total_gb,
            ram_free_gb=ram_free_gb,
            has_nvidia_gpu=False,
            cuda_usable=False,
        )

    freq_str = f" @ {info.cpu_mhz / 1000.0:.1f}GHz" if info.cpu_mhz else ""
    print(
        f"[DEBUG] [HARDWARE] Detected: {info.cpu_name} ({info.cpu_cores} Cores{freq_str}) | "
        f"RAM: {info.ram_total_gb:.1f}GB ({info.ram_free_gb:.1f}GB free) | "
        f"GPU: {info.gpu_name or 'CPU/Integrated'} (VRAM: {info.vram_total_mb:.0f}MB, "
        f"Driver: {info.gpu_driver_version or 'N/A'}, CUDA: {info.gpu_cuda_version or 'N/A'}, "
        f"CUDA Usable: {info.cuda_usable})"
    )
    _CACHED_HARDWARE = info
    return info


def recommend_model(hw: HardwareInfo) -> str:
    """
    Evaluates hardware specs and returns the optimal recommended model_id:
    - 'whisper-small': If CUDA usable with ample VRAM (>= 3GB) or High-end CPU with >= 16GB RAM
    - 'whisper-base': Balanced default for standard laptops/PCs (>= 8GB RAM)
    - 'whisper-tiny': Ultra lightweight for low-spec PCs (< 8GB RAM)
    """
    rec = "whisper-tiny"
    # 1. Check GPU CUDA capability
    if hw.cuda_usable and hw.vram_free_mb >= 3000:
        rec = "whisper-small"
    elif hw.cuda_usable and hw.vram_free_mb >= 1500:
        rec = "whisper-base"
    # 2. CPU fallback based on system RAM
    elif hw.ram_total_gb >= 16:
        rec = "whisper-small"
    elif hw.ram_total_gb >= 8:
        rec = "whisper-base"

    print(f"[DEBUG] [HARDWARE] Evaluated Recommendation -> '{rec}' for {hw.cpu_name}")
    return rec


get_hardware_info = detect_hardware
