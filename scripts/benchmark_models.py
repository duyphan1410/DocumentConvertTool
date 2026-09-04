"""
Benchmark script to compare Whisper models (base, small, medium)
on execution time, CPU speed, and transcription output differences.
"""
import os
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.whisper_service import preprocess_audio, transcribe_audio_whisper
from src.services.model_manager import get_installed_models

AUDIO_FILE = r"C:\Users\Admin\Desktop\Test\audio\Set up wave = win .mp3"

def run_benchmark(duration_limit_sec: int = 30):
    print("=" * 80)
    print(f"WHISPER MODELS BENCHMARK (Slice: {duration_limit_sec}s)")
    print(f"Audio File: {AUDIO_FILE}")
    print("=" * 80)

    if not os.path.isfile(AUDIO_FILE):
        print(f"[ERROR] Audio file not found: {AUDIO_FILE}")
        return

    # 1. Preprocess audio once
    print("[1/2] Preprocessing audio to 16kHz float32...")
    t_pre0 = time.time()
    full_audio = preprocess_audio(AUDIO_FILE)
    if full_audio is None:
        print("[ERROR] Failed to preprocess audio.")
        return
    
    total_audio_sec = len(full_audio) / 16000.0
    print(f"-> Full Audio Duration: {total_audio_sec:.1f}s (Preprocessed in {time.time()-t_pre0:.2f}s)")

    if duration_limit_sec > 0:
        slice_samples = int(duration_limit_sec * 16000)
        audio_slice = full_audio[:slice_samples]
        test_sec = min(duration_limit_sec, total_audio_sec)
    else:
        audio_slice = full_audio
        test_sec = total_audio_sec

    installed = get_installed_models()
    test_models = [m for m in ["whisper-base", "whisper-small", "whisper-medium", "whisper-large-v3"] if m in installed]

    print(f"Models to test: {test_models}\n")

    results = {}

    for model_id in test_models:
        print("-" * 80)
        print(f"Testing [{model_id}] on {test_sec:.1f}s audio...")
        t0 = time.time()
        
        chunks, detected_lang = transcribe_audio_whisper(
            audio_input=audio_slice,
            model_id=model_id,
            language=None,  # Auto-detect language (en/vi)
            return_info=True,
        )
        elapsed = time.time() - t0
        rtf = elapsed / test_sec if test_sec > 0 else 0
        speed_factor = test_sec / elapsed if elapsed > 0 else 0

        # Combine text
        full_text = " ".join(txt for _, txt in chunks)
        results[model_id] = {
            "elapsed": elapsed,
            "speed_factor": speed_factor,
            "segments_count": len(chunks),
            "detected_lang": detected_lang,
            "text": full_text,
            "chunks": chunks,
        }

        print(f"-> Completed in: {elapsed:.2f}s | Speed: {speed_factor:.2f}x real-time | Segments: {len(chunks)} | Lang: {detected_lang}")

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY & SPEED COMPARISON")
    print("=" * 80)
    print(f"{'Model':<20} | {'Elapsed Time':<15} | {'Speed Factor':<18} | {'Segments':<10}")
    print("-" * 75)
    for model_id, data in results.items():
        print(f"{model_id:<20} | {data['elapsed']:>6.2f}s         | {data['speed_factor']:>6.2f}x real-time   | {data['segments_count']:<10}")

    print("\n" + "=" * 80)
    print("TRANSCRIPTION TEXT COMPARISON (What each model heard):")
    print("=" * 80)
    for model_id, data in results.items():
        print(f"\n[{model_id.upper()}]:")
        print(f"\"{data['text'][:350]}...\"" if len(data['text']) > 350 else f"\"{data['text']}\"")

if __name__ == "__main__":
    dur = 30
    if len(sys.argv) > 1:
        try:
            dur = int(sys.argv[1])
        except ValueError:
            dur = 30
    run_benchmark(dur)
