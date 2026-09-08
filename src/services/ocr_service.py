"""
OCR Service wrapper for Tesseract OCR.
Handles native binary auto-detection on Windows, custom tessdata management,
and image-to-data / layout-preserving text extraction.
"""
import os
import sys
import shutil
import string
import logging
from typing import Optional, List, Dict, Tuple, Any
from PIL import Image

from src.i18n import t

logger = logging.getLogger(__name__)


_BUNDLED_TESSERACT_VERSION = "5.4.0"


def _get_silent_startupinfo(subprocess_mod):
    """Creates a Windows STARTUPINFO object configured for silent SW_HIDE execution."""
    if hasattr(subprocess_mod, "STARTUPINFO"):
        si = subprocess_mod.STARTUPINFO()
        si.dwFlags |= getattr(subprocess_mod, "STARTF_USESHOWWINDOW", 1)
        si.wShowWindow = 0  # SW_HIDE
        return si
    return None


class OCRService:
    """
    Production-grade wrapper for Tesseract OCR with automatic binary & tessdata resolution.
    Resolution priority:
      1. Explicit environment override (TESSERACT_CMD / TESSDATA_PREFIX)
      2. Bundled assets (<app>/assets/tesseract)
      3. System PATH
      4. Standard Windows installation directories
    """

    _cached_binary: Optional[str] = None
    _cached_tessdata: Optional[str] = None

    @classmethod
    def get_bundled_tesseract_dir(cls) -> str:
        """Returns the path to the bundled assets/tesseract folder."""
        # 1. Check relative to executable directory (packaged onedir mode)
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
            app_bundled = os.path.join(base_dir, "assets", "tesseract")
            if os.path.isdir(app_bundled):
                return app_bundled

        # 2. Check relative to current project root (source dev mode)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        dev_bundled = os.path.join(project_root, "assets", "tesseract")
        return dev_bundled

    @classmethod
    def get_standard_tesseract_locations(cls) -> List[str]:
        """Returns standard file paths where Tesseract-OCR is typically installed on Windows."""
        locs = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]

        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            locs.append(os.path.join(local_app_data, "Programs", "Tesseract-OCR", "tesseract.exe"))

        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            locs.append(os.path.join(user_profile, "AppData", "Local", "Programs", "Tesseract-OCR", "tesseract.exe"))

        return locs

    @classmethod
    def find_tesseract_binary(cls) -> Optional[str]:
        """
        Locates the tesseract executable following strict priority:
          1. Explicit Environment Override (TESSERACT_CMD)
          2. Bundled Asset (assets/tesseract/tesseract.exe)
          3. System PATH (shutil.which)
          4. Standard Windows Installations
        """
        if cls._cached_binary and os.path.isfile(cls._cached_binary):
            return cls._cached_binary

        # 1. Explicit Environment Override
        custom_cmd = os.environ.get("TESSERACT_CMD")
        if custom_cmd and os.path.isfile(custom_cmd):
            cls._cached_binary = custom_cmd
            return custom_cmd

        # 2. Bundled Asset
        bundled_dir = cls.get_bundled_tesseract_dir()
        bundled_exe = os.path.join(bundled_dir, "tesseract.exe")
        if os.path.isfile(bundled_exe):
            cls._cached_binary = bundled_exe
            return bundled_exe

        # 3. System PATH
        which_path = shutil.which("tesseract")
        if which_path and os.path.isfile(which_path):
            cls._cached_binary = which_path
            return which_path

        # 4. Standard Windows Installations
        for path in cls.get_standard_tesseract_locations():
            if os.path.isfile(path):
                cls._cached_binary = path
                return path

        return None

    @classmethod
    def get_tessdata_dir(cls) -> str:
        """
        Resolves active tessdata directory following strict priority:
          1. Explicit Environment Override (TESSDATA_PREFIX)
             Note: In Tesseract 5.x+, TESSDATA_PREFIX must point directly to the folder containing .traineddata files.
          2. Bundled Tessdata (assets/tesseract/tessdata)
          3. User AppData (%APPDATA%/DocConvert/tessdata)
          4. Tesseract Binary Adjacent (tessdata beside tesseract.exe)
        """
        if cls._cached_tessdata and os.path.isdir(cls._cached_tessdata):
            return cls._cached_tessdata

        # 1. Explicit Environment Override
        env_tessdata = os.environ.get("TESSDATA_PREFIX")
        if env_tessdata and os.path.isdir(env_tessdata):
            cls._cached_tessdata = env_tessdata
            return env_tessdata

        # 2. Bundled Tessdata
        bundled_tessdata = os.path.join(cls.get_bundled_tesseract_dir(), "tessdata")
        if os.path.isdir(bundled_tessdata) and os.path.isfile(os.path.join(bundled_tessdata, "vie.traineddata")):
            cls._cached_tessdata = bundled_tessdata
            return bundled_tessdata

        # 3. User AppData
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
        appdata_tess = os.path.join(appdata, "DocConvert", "tessdata")
        if os.path.isfile(os.path.join(appdata_tess, "vie.traineddata")):
            cls._cached_tessdata = appdata_tess
            return appdata_tess

        # 4. Tesseract Binary Adjacent
        tess_bin = cls.find_tesseract_binary()
        if tess_bin:
            install_tess = os.path.join(os.path.dirname(tess_bin), "tessdata")
            if os.path.isdir(install_tess):
                cls._cached_tessdata = install_tess
                return install_tess

        # Fallback to appdata_tess
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
            return False, t("ocr.missing_tesseract_msg")

        tessdata = cls.get_tessdata_dir()
        traineddata_file = os.path.join(tessdata, f"{lang}.traineddata")

        # Also check default installation directory
        default_traineddata = os.path.join(os.path.dirname(bin_path), "tessdata", f"{lang}.traineddata")

        if not os.path.isfile(traineddata_file) and not os.path.isfile(default_traineddata):
            return False, t("ocr.missing_langpack_msg", lang=lang, tessdata=tessdata)

        return True, "Ready"

    @classmethod
    def configure_environment(cls) -> None:
        """Configures pytesseract with detected binary, tessdata paths, and silent headless execution."""
        try:
            import pytesseract
            import subprocess
        except ImportError:
            raise RuntimeError("Thư viện 'pytesseract' chưa được cài đặt trong môi trường Python.")

        bin_path = cls.find_tesseract_binary()
        if bin_path:
            pytesseract.pytesseract.tesseract_cmd = bin_path

        tessdata_dir = cls.get_tessdata_dir()
        if tessdata_dir and os.path.isdir(tessdata_dir):
            os.environ["TESSDATA_PREFIX"] = tessdata_dir

        # Windows headless execution: comprehensively silence all pytesseract subprocess entrypoints
        if sys.platform == "win32":
            # 1. Main OCR process execution (run_tesseract)
            orig_subprocess_args = getattr(pytesseract.pytesseract, "subprocess_args", None)
            if orig_subprocess_args and not getattr(orig_subprocess_args, "_silent_patched", False):
                def _silent_subprocess_args(include_stdout=True):
                    kwargs = orig_subprocess_args(include_stdout)
                    kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    if kwargs.get("startupinfo") is None:
                        kwargs["startupinfo"] = _get_silent_startupinfo(subprocess)
                    return kwargs

                _silent_subprocess_args._silent_patched = True
                pytesseract.pytesseract.subprocess_args = _silent_subprocess_args

            # 2. Version check subprocess (get_tesseract_version)
            orig_get_version = getattr(pytesseract.pytesseract, "get_tesseract_version", None)
            if orig_get_version and not getattr(orig_get_version, "_silent_patched", False):
                _cached_version_obj = [None]

                def _silent_get_tesseract_version(*args, **kwargs):
                    if _cached_version_obj[0] is not None:
                        return _cached_version_obj[0]
                    try:
                        output = subprocess.check_output(
                            [pytesseract.pytesseract.tesseract_cmd, "--version"],
                            stderr=subprocess.STDOUT,
                            env=os.environ,
                            stdin=subprocess.DEVNULL,
                            startupinfo=_get_silent_startupinfo(subprocess),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
                        )
                        raw_version = output.decode(getattr(pytesseract.pytesseract, "DEFAULT_ENCODING", "utf-8"))
                        str_version, *_ = raw_version.lstrip(string.printable[10:]).partition(" ")
                        str_version, *_ = str_version.partition("-")
                        from packaging.version import parse
                        v = parse(str_version)
                        _cached_version_obj[0] = v
                        return v
                    except Exception as exc:
                        logger.warning(f"[OCR] Could not detect tesseract version ({exc}). Using default: {_BUNDLED_TESSERACT_VERSION}")
                        from packaging.version import parse
                        v = parse(_BUNDLED_TESSERACT_VERSION)
                        _cached_version_obj[0] = v
                        return v

                _silent_get_tesseract_version._silent_patched = True
                pytesseract.pytesseract.get_tesseract_version = _silent_get_tesseract_version

            # 3. Language list subprocess (get_languages)
            orig_get_languages = getattr(pytesseract.pytesseract, "get_languages", None)
            if orig_get_languages and not getattr(orig_get_languages, "_silent_patched", False):
                def _silent_get_languages(config=""):
                    cmd_args = [pytesseract.pytesseract.tesseract_cmd, "--list-langs"]
                    if config:
                        import shlex
                        cmd_args += shlex.split(config)
                    try:
                        result = subprocess.run(
                            cmd_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            startupinfo=_get_silent_startupinfo(subprocess),
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
                        )
                        languages = []
                        if result.stdout:
                            linesep = getattr(pytesseract.pytesseract, "linesep", "\n")
                            lang_pattern = getattr(pytesseract.pytesseract, "LANG_PATTERN", None)
                            encoding = getattr(pytesseract.pytesseract, "DEFAULT_ENCODING", "utf-8")
                            for line in result.stdout.decode(encoding).split(linesep):
                                lang = line.strip()
                                if lang_pattern and lang_pattern.match(lang):
                                    languages.append(lang)
                        return languages
                    except Exception as exc:
                        logger.warning(f"[OCR] Could not query tesseract languages ({exc}). Falling back to defaults.")
                        return ["eng", "vie", "osd"]

                _silent_get_languages._silent_patched = True
                pytesseract.pytesseract.get_languages = _silent_get_languages

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
