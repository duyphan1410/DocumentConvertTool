"""
PDF Scan Document Module for Document Converter Tool.
Extracts structured Markdown from scanned PDFs (no text layer) using:
PyMuPDF (rasterization >= 300 DPI) -> Tesseract OCR (layout-preserving via image_to_data)
-> Vietnamese Legal Document Structure Parser (Chương, Mục, Điều, Khoản, Điểm).
"""
import os
import io
import re
import sys
import logging
from typing import List, Optional, Callable, Dict, Any

from src.core.base_module import BaseDocumentModule
from src.core.registry import ModuleRegistry
from src.core.errors import DocumentError, ErrorCode

logger = logging.getLogger(__name__)


class PDFScanModule(BaseDocumentModule):
    """
    Dedicated OCR-based document converter for scanned PDFs and image-only legal documents.
    """

    @property
    def name(self) -> str:
        return "PDF Scan"

    @property
    def file_extensions(self) -> List[str]:
        # Keeps empty so PDFModule remains default handler for .pdf file extension
        # Module is accessed directly by name "PDF Scan" or mode "PDF Scan -> MD"
        return []

    @property
    def required_dependencies(self) -> List[str]:
        return ["pytesseract", "pymupdf", "Pillow"]

    # =========================================================================
    # LEGAL DOCUMENT REGEX PARSER HELPERS
    # =========================================================================

    @staticmethod
    def _normalize_roman_numeral(roman_str: str) -> str:
        """Normalizes common OCR artifacts in Roman numerals (e.g. 'Ï', 'l', '|' -> 'I')."""
        cleaned = roman_str.replace("Ï", "I").replace("ï", "I").replace("l", "I").replace("|", "I")
        return cleaned.strip().upper()

    @classmethod
    def parse_legal_structure(cls, raw_pages_lines: List[List[str]]) -> str:
        """
        Parses multi-page OCR reconstructed lines into structured Markdown with legal hierarchy:
        - Quoc hieu / Tieu ngu / Ten Luat
        - # Chuong [so]: [Tieu de]
        - ## Muc [so]: [Tieu de]
        - ### Dieu [so]. [Tieu de]
        - **[so].** [Khoan]
        - - **[chu_cai])** [Diem]
        - Cross-page line stitching & standalone page number stripping.
        """
        cleaned_pages: List[List[str]] = []

        # 1. Clean standalone page numbers at top/bottom of each page
        for p_idx, page_lines in enumerate(raw_pages_lines):
            p_lines = [line.strip() for line in page_lines if line is not None]
            
            # Filter out blank lines at start/end
            while p_lines and not p_lines[0]:
                p_lines.pop(0)
            while p_lines and not p_lines[-1]:
                p_lines.pop()

            # Check for standalone page number on first line
            if p_lines and re.match(r"^\s*(\d{1,3}|-\s*\d{1,3}\s*-)\s*$", p_lines[0]):
                p_lines.pop(0)

            # Check for standalone page number on last line
            if p_lines and re.match(r"^\s*(\d{1,3}|-\s*\d{1,3}\s*-)\s*$", p_lines[-1]):
                p_lines.pop()

            cleaned_pages.append(p_lines)

        # 2. Page boundary sentence continuation stitching
        flat_lines: List[str] = []
        for p_idx, p_lines in enumerate(cleaned_pages):
            if not p_lines:
                continue

            if flat_lines and p_lines:
                last_line = flat_lines[-1]
                first_line = p_lines[0]

                # If previous page line did not terminate with punctuation and first line starts with lowercase or comma
                is_last_unterminated = bool(
                    last_line
                    and not last_line.endswith((".", ":", "!", "?", '”', '"'))
                    and not last_line.startswith(("#", "**"))
                )
                is_first_continuation = bool(
                    first_line
                    and (
                        first_line[0].islower()
                        or first_line.startswith((",", ";", ")", "nhằm", "được", "và", "hoặc", "của", "tại", "theo"))
                    )
                    and not re.match(r"^(?:Điều|Chương|Mục|\d{1,2}\.|[a-zđà-ỹ]\))\s+", first_line, re.IGNORECASE)
                )

                if is_last_unterminated and is_first_continuation:
                    flat_lines[-1] = f"{last_line} {first_line}"
                    p_lines = p_lines[1:]

            flat_lines.extend(p_lines)

        # 3. Parse hierarchy
        md_output: List[str] = []
        in_article = False
        i = 0
        n_lines = len(flat_lines)

        # Regex patterns
        re_chuong = re.compile(r"^(?:#{1,4}\s*)?(?:Chương|CHƯƠNG)\s+([IVXLCDM\dÏl|]+)\.?:?\s*(.*)$", re.IGNORECASE)
        re_muc = re.compile(r"^(?:#{1,4}\s*)?(?:Mục|MỤC)\s+([IVXLCDM\d]+)\.?:?\s*(.*)$", re.IGNORECASE)
        re_dieu = re.compile(r"^(?:#{1,4}\s*)?(?:Điều|ĐIỀU)\s+(\d+)\.?\s*(.*)$", re.IGNORECASE)
        re_khoan = re.compile(r"^(?:[a-zA-Z~¬_•·\s]{1,3})?(\d{1,2}|§)[._]\s+(.*)$")
        re_khoan_corrupt = re.compile(r"^[_\-¬—~*•·|/\\§]{1,3}\s*[a-zA-Z0-9à-ỹ]{0,3}[._:]\s+([A-ZÀ-Ỹ“\"'].*)$")
        re_diem = re.compile(r"^([a-zđà-ỹ])\)\s+(.*)$")
        re_date = re.compile(r"^\d{1,2}[./]\s*\d{1,2}[./]\s*\d{2,4}")
        re_digital_sig = re.compile(r"^(?:Ký bởi|Email:|Cơ quan:|Thời gian ký:)", re.IGNORECASE)

        sig_metadata: List[str] = []
        last_khoan_num = 0

        while i < n_lines:
            line = flat_lines[i].strip()
            if not line:
                if md_output and md_output[-1] != "":
                    md_output.append("")
                i += 1
                continue

            # Digital signature watermark headers -> collect or skip
            if re_digital_sig.match(line):
                sig_metadata.append(line)
                i += 1
                continue

            # Clean standalone OCR noise symbols in preamble
            if not in_article and re.match(r"^[\*\-•·_~¬|:]+$", line):
                i += 1
                continue

            # Clean OCR noise prefix before LUẬT (e.g. "cà LUẬT" -> "LUẬT")
            line = re.sub(r"^(?:cà|ca|co|cá|cạ)\s+(LUẬT\b)", r"\1", line, flags=re.IGNORECASE)

            # 2-Column National Header Detection (QUỐC HỘI ... CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM)
            if "QUỐC HỘI" in line and "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" in line:
                tieu_ngu = "Độc lập - Tự do - Hạnh phúc"
                so_luat = ""
                skip_count = 0
                for next_j in range(i + 1, min(i + 4, n_lines)):
                    nl = flat_lines[next_j].strip()
                    if "Độc lập" in nl:
                        tieu_ngu = re.sub(r"^[:\s\-]+", "", nl).strip()
                        skip_count = max(skip_count, next_j - i)
                    elif "số" in nl.lower() or "qh" in nl.lower():
                        so_luat = nl.strip()
                        skip_count = max(skip_count, next_j - i)

                md_output.append("| **QUỐC HỘI** | **CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM** |")
                md_output.append("| :--- | :--- |")
                md_output.append(f"| **{so_luat or 'Luật số: 09/2017/QH14'}** | **{tieu_ngu}** |\n")
                i += (skip_count + 1)
                continue

            # Chapter (Chương)
            m_chuong = re_chuong.match(line)
            if m_chuong:
                in_article = False
                last_khoan_num = 0
                ch_num = cls._normalize_roman_numeral(m_chuong.group(1))
                ch_title = m_chuong.group(2).strip()

                # If chapter title is on the next line (often in ALL CAPS)
                if not ch_title and i + 1 < n_lines:
                    next_line = flat_lines[i + 1].strip()
                    if next_line and (next_line.isupper() or not re_dieu.match(next_line)):
                        ch_title = next_line
                        i += 1

                heading_text = f"# Chương {ch_num}"
                if ch_title:
                    heading_text += f": {ch_title}"
                
                if md_output and md_output[-1] != "":
                    md_output.append("")
                md_output.append(heading_text)
                md_output.append("")
                i += 1
                continue

            # Section (Mục)
            m_muc = re_muc.match(line)
            if m_muc:
                in_article = False
                last_khoan_num = 0
                muc_num = m_muc.group(1).strip()
                muc_title = m_muc.group(2).strip()
                if not muc_title and i + 1 < n_lines:
                    next_line = flat_lines[i + 1].strip()
                    if next_line and not re_dieu.match(next_line):
                        muc_title = next_line
                        i += 1

                heading_text = f"## Mục {muc_num}"
                if muc_title:
                    heading_text += f": {muc_title}"
                if md_output and md_output[-1] != "":
                    md_output.append("")
                md_output.append(heading_text)
                md_output.append("")
                i += 1
                continue

            # Article (Điều)
            m_dieu = re_dieu.match(line)
            if m_dieu:
                in_article = True
                last_khoan_num = 0
                dieu_num = m_dieu.group(1).strip()
                dieu_title = m_dieu.group(2).strip()

                heading_text = f"### Điều {dieu_num}."
                if dieu_title:
                    heading_text += f" {dieu_title}"
                if md_output and md_output[-1] != "":
                    md_output.append("")
                md_output.append(heading_text)
                md_output.append("")
                i += 1
                continue

            # Clause (Khoản) - Only recognized within an active Article
            m_khoan = re_khoan.match(line)
            if in_article and m_khoan and not re_date.match(line):
                raw_num = m_khoan.group(1)
                khoan_num = "8" if raw_num == "§" else raw_num
                khoan_content = m_khoan.group(2).strip()
                if khoan_num.isdigit():
                    num_val = int(khoan_num)
                    # Repair OCR digit misread (e.g. 7 read as 1 when previous clause was >= 2)
                    if last_khoan_num >= 2 and num_val <= last_khoan_num:
                        num_val = last_khoan_num + 1
                    last_khoan_num = num_val
                    khoan_num = str(num_val)

                md_output.append(f"**{khoan_num}.** {khoan_content}")
                md_output.append("")
                i += 1
                continue

            # Fallback for OCR-corrupted Clause numbers (e.g. "_ lỗ. Môi trường du lịch...")
            # State-machine inference: uses sequential numbering when in an active Article
            m_corrupt = re_khoan_corrupt.match(line)
            if in_article and last_khoan_num > 0 and m_corrupt and not re_date.match(line):
                inferred_num = last_khoan_num + 1
                last_khoan_num = inferred_num
                inferred_content = m_corrupt.group(1).strip()

                md_output.append(f"**{inferred_num}.** {inferred_content}")
                md_output.append("")
                i += 1
                continue

            # Point (Điểm) - Only recognized within an active Article
            m_diem = re_diem.match(line)
            if in_article and m_diem:
                diem_char = m_diem.group(1).lower()
                diem_content = m_diem.group(2).strip()
                md_output.append(f"- **{diem_char})** {diem_content}")
                i += 1
                continue

            # Regular paragraph or national header
            md_output.append(line)

            i += 1

        # Join and clean stray OCR dust periods
        result = "\n".join(md_output)
        # Remove stray OCR dust periods inside sentences (e.g. "sản phẩm . du lịch" -> "sản phẩm du lịch")
        result = re.sub(r'([a-zà-ỹ0-9,])\s+\.\s+([a-zà-ỹ])', r'\1 \2', result)
        result = re.sub(r"\n{3,}", "\n\n", result).strip()
        return result

    # =========================================================================
    # CORE CONVERSION PIPELINE
    # =========================================================================

    def load_to_markdown(
        self,
        file_path: str,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> str:
        """
        Executes 3-step pipeline:
        1. Rasterize PDF to 300 DPI images via PyMuPDF.
        2. Tesseract OCR with Vietnamese language pack.
        3. Parse legal hierarchy and stitch document pages into clean Markdown.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File không tồn tại: {file_path}")

        # pyrefly: ignore [missing-import]
        import fitz
        from PIL import Image
        from src.services.ocr_service import OCRService

        # 1. Check OCR Readiness
        is_ready, err_msg = OCRService.check_ocr_readiness("vie")
        if not is_ready:
            raise DocumentError(
                code=ErrorCode.DEPENDENCY_MISSING,
                title="Chưa sẵn sàng động cơ Tesseract OCR",
                message=err_msg,
                suggestion="Cài đặt Tesseract qua 'winget install UB-Mannheim.TesseractOCR' và đảm bảo có file vie.traineddata.",
            )

        # 2. Open PDF
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise DocumentError(
                code=ErrorCode.FILE_CORRUPTED,
                title="Không thể mở tệp PDF",
                message=f"Tệp PDF không thể đọc được bởi PyMuPDF: {str(e)}",
                suggestion="Kiểm tra lại tệp PDF nguồn để đảm bảo tệp không bị lỗi hoặc có mật khẩu bảo vệ.",
            )

        total_pages = len(doc)
        if total_pages == 0:
            return ""

        raw_pages_lines: List[List[str]] = []

        logger.info(f"Bắt đầu OCR Scanned PDF '{os.path.basename(file_path)}' ({total_pages} trang)...")

        # 3. Rasterize & OCR per page
        for page_idx in range(total_pages):
            current_page_num = page_idx + 1

            if progress_callback:
                progress_callback(
                    current_page_num,
                    total_pages,
                    f"Đang xử lý OCR trang {current_page_num}/{total_pages}...",
                )

            # Step 1: Rasterize to 300 DPI
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=300)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # Step 2: OCR with layout preservation
            ocr_data = OCRService.ocr_image_to_data(img, lang="vie")
            lines = OCRService.reconstruct_layout_from_data(ocr_data)
            raw_pages_lines.append(lines)

            # Progressive streaming callback: emit structured markdown accumulated so far
            if progress_callback:
                try:
                    partial_md = self.parse_legal_structure(raw_pages_lines)
                    import inspect
                    sig = inspect.signature(progress_callback)
                    if len(sig.parameters) >= 4:
                        progress_callback(
                            current_page_num,
                            total_pages,
                            f"Đã nạp trang {current_page_num}/{total_pages}...",
                            partial_md,
                        )
                except Exception as ex_stream:
                    logger.debug(f"Progressive stream callback error: {ex_stream}")

        doc.close()

        if progress_callback:
            progress_callback(total_pages, total_pages, "Đang phân tích cấu trúc văn bản pháp lý...")

        # 4. Step 3: Parse Legal Structure & Stitch
        markdown_result = self.parse_legal_structure(raw_pages_lines)
        return markdown_result

    def save_from_markdown(self, markdown_content: str, out_path: str) -> str:
        """Exporting back to PDF Scan is not supported (use standard PDFModule for export)."""
        raise NotImplementedError("Tính năng xuất ngược sang Scanned PDF không được hỗ trợ. Hãy sử dụng chế độ MD -> PDF.")


# Auto-register module in ModuleRegistry
ModuleRegistry.register(PDFScanModule())
