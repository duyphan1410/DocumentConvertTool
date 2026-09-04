"""
OCR Service wrapper for Tesseract OCR.
Handles native binary auto-detection on Windows, custom tessdata management,
and image-to-data / layout-preserving text extraction.
"""
import os
import sys
import shutil
import logging
from typing import Optional, List, Dict, Tuple, Any
from PIL import Image

logger = logging.getLogger(__name__)


class OCRService:
    """
    Production-grade wrapper for Tesseract OCR with automatic binary & tessdata resolution.
    """

    _cached_binary: Optional[str] = None
    _cached_tessdata: Optional[str] = None

    @classmethod
    def get_standard_tesseract_locations(cls) -> List[str]:
        """Returns standard file paths where Tesseract-OCR is typically installed on Windows."""
        locs = []
        # Custom environment variable
        custom_cmd = os.environ.get("TESSERACT_CMD")
        if custom_cmd and os.path.isfile(custom_cmd):
            locs.append(custom_cmd)

        # Standard program files
        locs.extend([
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ])

        # Local AppData
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            locs.append(os.path.join(local_app_data, "Programs", "Tesseract-OCR", "tesseract.exe"))

        # User profile
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            locs.append(os.path.join(user_profile, "AppData", "Local", "Programs", "Tesseract-OCR", "tesseract.exe"))

        return locs

    @classmethod
    def find_tesseract_binary(cls) -> Optional[str]:
        """
        Locates the tesseract executable on the host machine.
        Returns the absolute path or None if not installed.
        """
        if cls._cached_binary and os.path.isfile(cls._cached_binary):
            return cls._cached_binary

        # 1. Check if 'tesseract' is available directly on PATH
        which_path = shutil.which("tesseract")
        if which_path and os.path.isfile(which_path):
            cls._cached_binary = which_path
            return which_path

        # 2. Check standard Windows installations
        for path in cls.get_standard_tesseract_locations():
            if os.path.isfile(path):
                cls._cached_binary = path
                return path

        return None

    @classmethod
    def get_tessdata_dir(cls) -> str:
        """
        Resolves the active tessdata folder, prioritizing user AppData where
        additional language packs (e.g. vie.traineddata) are installed without admin permissions.
        """
        if cls._cached_tessdata and os.path.isdir(cls._cached_tessdata):
            return cls._cached_tessdata

        # 1. Check User AppData (DocConvert data dir)
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        appdata_tess = os.path.join(appdata, "DocConvert", "tessdata")
        vie_in_appdata = os.path.join(appdata_tess, "vie.traineddata")
        if os.path.isfile(vie_in_appdata):
            cls._cached_tessdata = appdata_tess
            return appdata_tess

        # 2. Check Tesseract installation dir tessdata
        tess_bin = cls.find_tesseract_binary()
        if tess_bin:
            install_tess = os.path.join(os.path.dirname(tess_bin), "tessdata")
            if os.path.isfile(os.path.join(install_tess, "vie.traineddata")):
                cls._cached_tessdata = install_tess
                return install_tess

        # Fallback to appdata_tess (even if not yet populated)
        os.makedirs(appdata_tess, exist_ok=True)
        cls._cached_tessdata = appdata_tess
        return appdata_tess

    @classmethod
    def check_ocr_readiness(cls, lang: str = "vie") -> Tuple[bool, str]:
        """
        Checks if Tesseract binary and the required language pack are installed and usable.
        Returns (is_ready, status_message).
        """
        bin_path = cls.find_tesseract_binary()
        if not bin_path:
            return False, (
                "Chưa tìm thấy Tesseract OCR trên hệ thống. "
                "Vui lòng cài đặt Tesseract (ví dụ: 'winget install UB-Mannheim.TesseractOCR') "
                "hoặc tải từ https://github.com/UB-Mannheim/tesseract/wiki."
            )

        tessdata = cls.get_tessdata_dir()
        traineddata_file = os.path.join(tessdata, f"{lang}.traineddata")

        # Also check default installation directory
        default_traineddata = os.path.join(os.path.dirname(bin_path), "tessdata", f"{lang}.traineddata")

        if not os.path.isfile(traineddata_file) and not os.path.isfile(default_traineddata):
            return False, (
                f"Chưa tìm thấy gói ngôn ngữ '{lang}.traineddata' trong thư mục tessdata: {tessdata}. "
                f"Vui lòng tải gói ngôn ngữ vào thư mục này để bắt đầu nhận diện tiếng Việt."
            )

        return True, "Ready"

    @classmethod
    def configure_environment(cls) -> None:
        """Configures pytesseract with detected binary and tessdata paths."""
        try:
            import pytesseract
        except ImportError:
            raise RuntimeError("Thư viện 'pytesseract' chưa được cài đặt trong môi trường Python.")

        bin_path = cls.find_tesseract_binary()
        if bin_path:
            pytesseract.pytesseract.tesseract_cmd = bin_path

        tessdata_dir = cls.get_tessdata_dir()
        if tessdata_dir and os.path.isdir(tessdata_dir):
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

    @classmethod
    def ocr_image_to_data(
        cls,
        image: Image.Image,
        lang: str = "vie",
        config: str = "",
    ) -> Dict[str, List[Any]]:
        """
        Executes Tesseract image_to_data on a PIL Image.
        Returns dict containing ['level', 'page_num', 'block_num', 'par_num',
        'line_num', 'word_num', 'left', 'top', 'width', 'height', 'conf', 'text'].
        """
        import pytesseract
        cls.configure_environment()

        tessdata_dir = cls.get_tessdata_dir()
        combined_config = config
        if tessdata_dir and os.path.isdir(tessdata_dir):
            combined_config = f'--tessdata-dir "{tessdata_dir}" {config}'.strip()

        try:
            return pytesseract.image_to_data(
                image,
                lang=lang,
                config=combined_config,
                output_type=pytesseract.Output.DICT,
            )
        except Exception:
            # Fallback if quotes caused an issue with certain tesseract builds
            return pytesseract.image_to_data(
                image,
                lang=lang,
                config=config,
                output_type=pytesseract.Output.DICT,
            )

    @classmethod
    def ocr_image_to_text(
        cls,
        image: Image.Image,
        lang: str = "vie",
        config: str = "",
    ) -> str:
        """
        Executes Tesseract image_to_string on a PIL Image.
        """
        import pytesseract
        cls.configure_environment()

        tessdata_dir = cls.get_tessdata_dir()
        combined_config = config
        if tessdata_dir and os.path.isdir(tessdata_dir):
            combined_config = f'--tessdata-dir "{tessdata_dir}" {config}'.strip()

        try:
            return pytesseract.image_to_string(image, lang=lang, config=combined_config)
        except Exception:
            return pytesseract.image_to_string(image, lang=lang, config=config)

    @classmethod
    def reconstruct_layout_from_data(
        cls,
        ocr_data: Dict[str, List[Any]],
        min_confidence: int = 15,
    ) -> List[str]:
        """
        Reconstructs structured lines and paragraphs from image_to_data dictionary tokens,
        preserving line grouping by (block_num, par_num, line_num).
        """
        if not ocr_data or "text" not in ocr_data:
            return []

        # Group words by (block_num, par_num, line_num)
        lines_dict: Dict[Tuple[int, int, int], List[str]] = {}
        n_tokens = len(ocr_data["text"])

        for i in range(n_tokens):
            raw_text = str(ocr_data["text"][i]).strip()
            if not raw_text:
                continue

            conf = int(ocr_data["conf"][i]) if "conf" in ocr_data and str(ocr_data["conf"][i]).lstrip("-").isdigit() else 0
            # Filter noise tokens with very low confidence (< min_confidence) unless long text
            # CRITICAL: Structural tokens (e.g. "1.", "a)", "đ)", "2.") must NOT be dropped even with low confidence
            import re
            is_structural = bool(re.match(r"^(?:[a-z0-9đ]{1,2}[)._:]|[IVXLCDM]{1,4}[)._:]|\d{1,2}\.?)$", raw_text, re.IGNORECASE))
            if conf < min_confidence and len(raw_text) <= 2 and not is_structural:
                continue

            b = ocr_data["block_num"][i]
            p = ocr_data["par_num"][i]
            l = ocr_data["line_num"][i]
            key = (b, p, l)

            if key not in lines_dict:
                lines_dict[key] = []
            lines_dict[key].append(raw_text)

        # Build lines with paragraph breaks
        lines_out: List[str] = []
        last_block = -1
        last_par = -1

        for (b, p, l), words in sorted(lines_dict.items()):
            line_str = " ".join(words).strip()
            if not line_str:
                continue

            # Separate different blocks/paragraphs with blank line indicator if needed
            if last_block != -1 and (b != last_block or p != last_par):
                if lines_out and lines_out[-1] != "":
                    lines_out.append("")

            lines_out.append(line_str)
            last_block = b
            last_par = p

        return lines_out
