import os
import sys
import hashlib
import requests

# Force UTF-8 encoding on Windows CI runners (prevents cp1252 UnicodeEncodeError)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.services.model_manager import AVAILABLE_MODELS


def verify_live_huggingface_hashes() -> bool:
    print("=" * 70)
    print("  GITHUB ACTIONS CI - LIVE HUGGING FACE SHA256 CHECKSUM AUDITOR")
    print("=" * 70)

    try:
        from huggingface_hub import HfApi
        api = HfApi()
    except ImportError:
        print("[!] CRITICAL: huggingface_hub is required for release audit but not installed.")
        return False

    mismatches = []

    for mid, meta in AVAILABLE_MODELS.items():
        print(f"\n[+] Auditing Model: {meta.display_name} ({meta.repo_id})...")
        try:
            info = api.model_info(meta.repo_id, files_metadata=True)
        except Exception as ex:
            print(f"    [FAIL] Failed to connect to Hugging Face API ({ex})")
            mismatches.append(f"[{mid}] API connection failed: {ex}")
            continue

        # 1. Audit Git LFS binary files (model.bin) directly from API metadata (0 bytes downloaded)
        for s in info.siblings:
            if s.rfilename == "model.bin" and s.lfs:
                remote_sha = s.lfs.sha256.lower()
                expected_sha = meta.expected_sha256.get("model.bin", "").lower()
                if remote_sha != expected_sha:
                    mismatches.append(
                        f"[{mid}] model.bin SHA256 mismatch! HuggingFace={remote_sha} vs Code={expected_sha}"
                    )
                    print(f"    [FAIL] model.bin: MISMATCH (HF: {remote_sha[:8]} != Code: {expected_sha[:8]})")
                else:
                    print(f"    [PASS] model.bin: MATCH (LFS Metadata SHA256)")

        # 2. Audit small text config files (config.json, tokenizer.json, vocabulary.txt/json)
        text_files = [fn for fn in meta.expected_sha256.keys() if fn != "model.bin"]
        for fname in text_files:
            expected_sha = meta.expected_sha256.get(fname, "").lower()
            if not expected_sha:
                continue
            
            raw_url = f"https://huggingface.co/{meta.repo_id}/raw/main/{fname}"
            try:
                resp = requests.get(raw_url, timeout=10)
                if resp.status_code == 200:
                    actual_sha = hashlib.sha256(resp.content).hexdigest().lower()
                    if actual_sha != expected_sha:
                        mismatches.append(
                            f"[{mid}] {fname} SHA256 mismatch! HuggingFace={actual_sha} vs Code={expected_sha}"
                        )
                        print(f"    [FAIL] {fname}: MISMATCH (HF: {actual_sha[:8]} != Code: {expected_sha[:8]})")
                    else:
                        print(f"    [PASS] {fname}: MATCH (Raw SHA256)")
                else:
                    err_msg = f"[{mid}] Failed to fetch {fname} (HTTP {resp.status_code})"
                    mismatches.append(err_msg)
                    print(f"    [FAIL] {fname}: HTTP Error {resp.status_code}")
            except Exception as ex:
                err_msg = f"[{mid}] Error downloading {fname}: {ex}"
                mismatches.append(err_msg)
                print(f"    [FAIL] {fname}: Network Exception: {ex}")

    print("\n" + "=" * 70)
    if mismatches:
        print("[CRITICAL] MODEL CHECKSUM MISMATCH DETECTED!")
        for m in mismatches:
            print(f"  - {m}")
        print("\nPlease update expected_sha256 in src/services/model_manager.py before releasing.")
        print("=" * 70)
        return False

    print("[OK] SUCCESS: All Model SHA256 hashes are 100% synchronized with Hugging Face!")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = verify_live_huggingface_hashes()
    if not success:
        sys.exit(1)
