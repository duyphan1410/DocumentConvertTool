"""
Setup script to ensure Tesseract OCR Portable is present in assets/tesseract.
Verifies cryptographic SHA256 hashes against scripts/tesseract_manifest.json (Fail-Hard on mismatch).
Used by local development and CI/CD (GitHub Actions) packaging pipelines.
"""
import os
import sys
import time
import json
import shutil
import zipfile
import hashlib
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Security: Lock down trusted release host to prevent supply chain URL redirection
TRUSTED_URL_PREFIX = "https://github.com/duyphan1410/DocumentConvertTool/releases/download/"
MAX_DOWNLOAD_RETRIES = 3
RETRY_BACKOFF_SECONDS = 3


def compute_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().lower()


def safe_extract_zip(zip_file_path: str, extract_to_dir: str) -> bool:
    """
    Extracts zip archive with Zip Slip path traversal defenses and error boundary.
    """
    try:
        abs_extract_to = os.path.abspath(extract_to_dir)
        with zipfile.ZipFile(zip_file_path, "r") as zf:
            for member in zf.infolist():
                dest_path = os.path.abspath(os.path.join(abs_extract_to, member.filename))
                if not (dest_path == abs_extract_to or dest_path.startswith(abs_extract_to + os.sep)):
                    logger.critical(f"[SECURITY] Zip Slip path traversal attempt detected in: {member.filename}")
                    return False
            zf.extractall(abs_extract_to)
        return True
    except Exception as exc:
        logger.error(f"[ERROR] Failed to extract archive {zip_file_path}: {exc}")
        return False


def verify_extracted_files(target_dir: str, manifest_files: dict) -> bool:
    for rel_path, expected_hash in manifest_files.items():
        normalized_rel = rel_path.replace("/", os.sep).replace("\\", os.sep)
        full_path = os.path.join(target_dir, normalized_rel)
        if not os.path.isfile(full_path):
            logger.error(f"[SECURITY] Missing required file: {normalized_rel}")
            return False
        actual_hash = compute_sha256(full_path)
        if actual_hash != expected_hash.lower():
            logger.error(f"[SECURITY] Checksum mismatch for {normalized_rel}!")
            logger.error(f"  Expected: {expected_hash}")
            logger.error(f"  Actual:   {actual_hash}")
            return False
    return True


def ensure_tesseract(project_root: str = None) -> bool:
    if project_root is None:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    manifest_path = os.path.join(project_root, "scripts", "tesseract_manifest.json")
    if not os.path.isfile(manifest_path):
        logger.error(f"Cannot find manifest file at: {manifest_path}")
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    target_dir = os.path.join(project_root, "assets", "tesseract")
    expected_zip_hash = manifest.get("zip_sha256", "").lower()
    release_url = manifest.get("zip_url", "")
    manifest_files = manifest.get("files", {})

    # Security Check: Verify URL adheres strictly to trusted repository domain
    if not release_url.startswith(TRUSTED_URL_PREFIX):
        logger.critical(f"[SECURITY] Untrusted download URL detected in manifest: {release_url}")
        logger.critical(f"Expected URL to start with: {TRUSTED_URL_PREFIX}")
        return False

    # 1. Check if already present and all files pass cryptographic checksum audit
    target_exe = os.path.join(target_dir, "tesseract.exe")
    if os.path.isfile(target_exe):
        logger.info(f"Auditing existing Tesseract files at: {target_dir}")
        if verify_extracted_files(target_dir, manifest_files):
            logger.info("All Tesseract Portable binaries verified against SHA256 manifest.")
            return True
        else:
            logger.warning("Existing Tesseract files failed hash audit. Purging stale/corrupt directory...")
            shutil.rmtree(target_dir, ignore_errors=True)

    os.makedirs(target_dir, exist_ok=True)
    candidate_local_zips = [
        os.path.join(project_root, "dist", "tesseract-portable-win-x64.zip"),
        os.path.join(project_root, "dist", "installer", "tesseract-portable-win-x64.zip"),
    ]
    local_zip = next((p for p in candidate_local_zips if os.path.isfile(p)), None)

    # 2. Check local pre-built archive if present
    if local_zip:
        logger.info(f"Verifying local archive: {local_zip}")
        actual_zip_hash = compute_sha256(local_zip)
        if actual_zip_hash != expected_zip_hash:
            logger.error(f"[SECURITY] Local zip checksum mismatch ({actual_zip_hash} != {expected_zip_hash})")
            return False
        logger.info("Local archive checksum PASSED. Extracting...")
        if not safe_extract_zip(local_zip, target_dir):
            logger.critical("[ERROR] Local archive extraction failed.")
            return False
        return verify_extracted_files(target_dir, manifest_files)

    # 3. Download from official GitHub Releases repository asset with retries & fail-hard verification
    temp_zip = os.path.join(target_dir, "_download_temp.zip")
    logger.info(f"Downloading Tesseract Portable (~15.3 MB) from official repository release...")
    logger.info(f"URL: {release_url}")

    for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
        if os.path.exists(temp_zip):
            try:
                os.remove(temp_zip)
            except OSError:
                pass

        logger.info(f"Download attempt {attempt}/{MAX_DOWNLOAD_RETRIES}...")
        try:
            req = urllib.request.Request(
                release_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                    "Accept": "application/octet-stream, */*",
                },
            )
            with urllib.request.urlopen(req, timeout=45) as response, open(temp_zip, "wb") as out_file:
                total_size = int(response.headers.get("Content-Length", 0))
                downloaded_size = 0
                chunk_size = 512 * 1024  # 512 KB per chunk for high throughput

                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded_size += len(chunk)
                    if total_size > 0:
                        percent = min(100.0, (downloaded_size / total_size) * 100)
                        sys.stdout.write(f"\rDownloading: {percent:.1f}% ({downloaded_size / (1024*1024):.1f}/{total_size / (1024*1024):.1f} MB)")
                        sys.stdout.flush()

            print()
            logger.info("Verifying downloaded archive checksum...")
            downloaded_hash = compute_sha256(temp_zip)
            if downloaded_hash != expected_zip_hash:
                logger.critical("[SECURITY] Downloaded archive checksum mismatch! Supply chain tampering or incomplete download detected.")
                logger.critical(f"  Expected: {expected_zip_hash}")
                logger.critical(f"  Actual:   {downloaded_hash}")
                if os.path.exists(temp_zip):
                    os.remove(temp_zip)
                if attempt < MAX_DOWNLOAD_RETRIES:
                    time.sleep(RETRY_BACKOFF_SECONDS)
                    continue
                return False

            logger.info("Downloaded archive checksum PASSED. Extracting...")
            extracted_ok = safe_extract_zip(temp_zip, target_dir)
            if os.path.exists(temp_zip):
                os.remove(temp_zip)

            if not extracted_ok:
                logger.critical("[ERROR] Archive extraction failed.")
                return False

            if not verify_extracted_files(target_dir, manifest_files):
                logger.critical("[SECURITY] Extracted files failed SHA256 validation!")
                return False

            logger.info("Tesseract Portable setup and security verification completed successfully.")
            return True
        except Exception as exc:
            logger.error(f"Download attempt {attempt} failed: {exc}")
            if os.path.exists(temp_zip):
                try:
                    os.remove(temp_zip)
                except OSError:
                    pass
            if attempt < MAX_DOWNLOAD_RETRIES:
                logger.info(f"Retrying in {RETRY_BACKOFF_SECONDS}s...")
                time.sleep(RETRY_BACKOFF_SECONDS)

    logger.critical(f"[FAIL-HARD] Failed to download and verify Tesseract Portable after {MAX_DOWNLOAD_RETRIES} attempts.")
    return False


if __name__ == "__main__":
    success = ensure_tesseract()
    if not success:
        logger.critical("[ERROR] Tesseract setup failed. Aborting pipeline.")
        sys.exit(1)
    sys.exit(0)
