"""
Unit Test Suite for Hardware Detector Service.
Tests 100% mocked hardware scenarios (Modern NVIDIA GPU, Legacy Driver GPU, CPU only, CLI fallback)
and validates model recommendation thresholds without flaky CI dependencies.
"""
import unittest
from unittest.mock import patch, MagicMock

from src.services.hardware_detector import (
    HardwareInfo,
    detect_hardware,
    recommend_model,
    _query_gpu_nvidia_smi,
)


class TestHardwareDetector(unittest.TestCase):
    """Test cases for hardware detection logic and recommendations."""

    def test_recommendation_modern_gpu(self):
        """High-end NVIDIA GPU with ample VRAM should recommend whisper-small."""
        hw = HardwareInfo(
            cpu_name="Intel Core i7-13700H",
            cpu_cores=16,
            ram_total_gb=32.0,
            ram_free_gb=18.0,
            has_nvidia_gpu=True,
            gpu_name="NVIDIA GeForce RTX 4070",
            gpu_driver_version="555.85",
            gpu_cuda_version="12.4",
            vram_total_mb=8192.0,
            vram_free_mb=6200.0,
            cuda_usable=True,
        )
        self.assertEqual(recommend_model(hw), "whisper-small")
        self.assertIn("RTX 4070", hw.get_summary_text())
        self.assertIn("CUDA 12.4", hw.get_summary_text())

    def test_recommendation_mid_gpu(self):
        """Moderate NVIDIA GPU with ~2GB free VRAM should recommend whisper-base."""
        hw = HardwareInfo(
            cpu_name="AMD Ryzen 5 3600",
            cpu_cores=6,
            ram_total_gb=16.0,
            ram_free_gb=8.0,
            has_nvidia_gpu=True,
            gpu_name="NVIDIA GeForce GTX 1650",
            gpu_driver_version="535.100",
            gpu_cuda_version="12.0",
            vram_total_mb=4096.0,
            vram_free_mb=2000.0,
            cuda_usable=True,
        )
        self.assertEqual(recommend_model(hw), "whisper-base")

    def test_recommendation_legacy_driver_gpu_fallback_cpu(self):
        """GPU with outdated driver / cuda_usable=False falls back to CPU RAM thresholds."""
        hw = HardwareInfo(
            cpu_name="Intel Core i5-6500",
            cpu_cores=4,
            ram_total_gb=8.0,
            ram_free_gb=4.0,
            has_nvidia_gpu=True,
            gpu_name="GeForce GT 730",
            gpu_driver_version="388.13",
            vram_total_mb=2048.0,
            vram_free_mb=1800.0,
            cuda_usable=False,  # Outdated driver < 450
        )
        # RAM is 8GB -> whisper-base
        self.assertEqual(recommend_model(hw), "whisper-base")

    def test_recommendation_low_spec_cpu_only(self):
        """Low-spec PC with < 8GB RAM and no dedicated GPU should recommend whisper-tiny."""
        hw = HardwareInfo(
            cpu_name="Intel Celeron N4020",
            cpu_cores=2,
            ram_total_gb=4.0,
            ram_free_gb=1.5,
            has_nvidia_gpu=False,
            cuda_usable=False,
        )
        self.assertEqual(recommend_model(hw), "whisper-tiny")
        self.assertIn("CPU/Integrated Graphics", hw.get_summary_text())

    @patch("src.services.hardware_detector._query_gpu_nvml")
    @patch("src.services.hardware_detector._query_gpu_nvidia_smi")
    @patch("src.services.hardware_detector._get_ram_info")
    @patch("src.services.hardware_detector._get_cpu_info")
    def test_detect_hardware_mocked_nvml(self, mock_cpu, mock_ram, mock_smi, mock_nvml):
        """Validates detect_hardware parses NVML dict properly."""
        mock_cpu.return_value = ("Mock Ryzen 7", 8, 3200)
        mock_ram.return_value = (16.0, 10.0)
        mock_nvml.return_value = {
            "name": "NVIDIA RTX 3060",
            "driver": "551.86",
            "cuda": "12.2",
            "total_mb": 6144.0,
            "free_mb": 4500.0,
        }

        hw = detect_hardware(force_refresh=True)
        self.assertEqual(hw.cpu_name, "Mock Ryzen 7")
        self.assertEqual(hw.cpu_cores, 8)
        self.assertEqual(hw.cpu_mhz, 3200)
        self.assertEqual(hw.ram_total_gb, 16.0)
        self.assertTrue(hw.has_nvidia_gpu)
        self.assertTrue(hw.cuda_usable)
        self.assertEqual(hw.gpu_name, "NVIDIA RTX 3060")
        self.assertEqual(hw.gpu_driver_version, "551.86")
        self.assertEqual(hw.gpu_cuda_version, "12.2")

    @patch("subprocess.run")
    def test_query_gpu_nvidia_smi_cli(self, mock_subproc):
        """Validates parsing of nvidia-smi CSV CLI output."""
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "NVIDIA GeForce RTX 2060, 528.49, 6144, 4096\n"
        mock_subproc.return_value = mock_res

        res = _query_gpu_nvidia_smi()
        self.assertIsNotNone(res)
        self.assertEqual(res["name"], "NVIDIA GeForce RTX 2060")
        self.assertEqual(res["driver"], "528.49")
        self.assertEqual(res["total_mb"], 6144.0)
        self.assertEqual(res["free_mb"], 4096.0)


if __name__ == "__main__":
    unittest.main()
