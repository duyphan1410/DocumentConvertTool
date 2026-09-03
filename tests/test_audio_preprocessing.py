import os
import tempfile
import unittest
import numpy as np
import av

from src.services.speech_service import preprocess_audio
from src.services.drive_service import extract_drive_file_id, is_drive_url


class TestAudioPreprocessing(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_audio_preproc_")

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_synth_wav(self, duration_s=1.0, sample_rate=44100, channels=2, peak=0.15, dc_offset=0.05):
        """Creates a synthetic WAV file with stereo, DC offset, and quiet peak amplitude."""
        num_samples = int(duration_s * sample_rate)
        t = np.linspace(0, duration_s, num_samples, endpoint=False)
        # 440 Hz tone + DC offset
        signal = peak * np.sin(2 * np.pi * 440 * t) + dc_offset

        if channels == 2:
            data = np.stack([signal, signal * 0.8], axis=1)  # stereo
            layout = "stereo"
        else:
            data = signal[:, np.newaxis]
            layout = "mono"

        # Scale to 16-bit PCM (interleaved packed format)
        pcm_data = np.clip(data * 32767.0, -32768, 32767).astype(np.int16).reshape(1, -1)

        out_path = os.path.join(self.temp_dir, f"synth_{channels}ch_{sample_rate}hz.wav")
        container = av.open(out_path, mode="w")
        stream = container.add_stream("pcm_s16le", rate=sample_rate)
        stream.layout = layout

        frame = av.AudioFrame.from_ndarray(pcm_data, format="s16", layout=layout)
        frame.rate = sample_rate
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
        container.close()

        return out_path

    def test_preprocess_resample_and_normalize(self):
        """Verify audio preprocessing resamples to 16kHz mono, removes DC offset, and normalizes peak."""
        synth_file = self._create_synth_wav(duration_s=1.5, sample_rate=44100, channels=2, peak=0.10, dc_offset=0.03)

        audio = preprocess_audio(synth_file, target_sr=16000)

        self.assertIsNotNone(audio)
        self.assertIsInstance(audio, np.ndarray)
        self.assertEqual(audio.dtype, np.float32)

        # Length should be ~1.5s * 16000 = 24000 samples (+/- small filter margin)
        expected_samples = int(1.5 * 16000)
        self.assertAlmostEqual(len(audio), expected_samples, delta=100)

        # 1. DC offset should be nearly 0.0 after removal
        self.assertAlmostEqual(float(np.mean(audio)), 0.0, places=3)

        # 2. Peak amplitude should be normalized near 0.90 (-0.9 dBFS)
        max_peak = float(np.max(np.abs(audio)))
        self.assertAlmostEqual(max_peak, 0.90, places=2)

        # 3. Audio values must remain within [-1.0, 1.0]
        self.assertTrue(np.all(audio >= -1.0) and np.all(audio <= 1.0))

    def test_preprocess_nonexistent_and_empty_file(self):
        """Verify preprocess_audio returns None on invalid or empty files."""
        self.assertIsNone(preprocess_audio("non_existent_file.mp3"))

        empty_file = os.path.join(self.temp_dir, "empty.wav")
        with open(empty_file, "wb") as f:
            pass
        self.assertIsNone(preprocess_audio(empty_file))

    def test_drive_url_extraction(self):
        """Verify Google Drive URL parsing across standard sharing formats."""
        file_id = "1A2B3C4D5E6F7G8H9I0J1K2L3M4N5O6P"

        urls = [
            f"https://drive.google.com/file/d/{file_id}/view",
            f"https://drive.google.com/file/d/{file_id}/view?usp=sharing",
            f"https://drive.google.com/open?id={file_id}",
            f"https://drive.google.com/uc?id={file_id}",
            f"https://docs.google.com/file/d/{file_id}/edit",
        ]

        for url in urls:
            self.assertTrue(is_drive_url(url), f"Failed is_drive_url for: {url}")
            extracted = extract_drive_file_id(url)
            self.assertEqual(extracted, file_id, f"Failed extract_drive_file_id for: {url}")

        self.assertFalse(is_drive_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))
        self.assertIsNone(extract_drive_file_id("https://example.com/not-drive"))


if __name__ == "__main__":
    unittest.main()
