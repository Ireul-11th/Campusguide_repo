"""Trích xuất văn bản từ PDF, DOCX, TXT/MD thành danh sách trang."""
import re
import unicodedata
from pathlib import Path

from .. import config


class ExtractError(Exception):
    pass


_VI_ONE_LETTER = set("aàáảãạeèéẻẽẹêềếểễệiìíỉĩịoòóỏõọôồốổỗộơờớởỡợuùúủũụưừứửữựyỳýỷỹỵ")


def quality_warning(pages: list[str]) -> str:
    """Phát hiện chữ tiếng Việt bị hỏng khi trích xuất (lỗi font/encoding trong PDF).
    Trả về chuỗi cảnh báo, hoặc "" nếu văn bản trông bình thường."""
    text = unicodedata.normalize("NFC", "\n".join(pages))
    if "(cid:" in text:
        return "Văn bản trích ra có mã ký tự lỗi (cid:...), nhiều khả năng font trong PDF không có bảng Unicode."
    tokens = re.findall(r"[^\W\d_]+", text)
    if len(tokens) < 30:
        return ""
    bad = sum(1 for t in tokens if len(t) == 1 and t.lower() not in _VI_ONE_LETTER)
    if bad / len(tokens) >= 0.08:
        return ("Chữ trích ra từ file có vẻ bị vỡ dấu tiếng Việt (nhiều chữ cái đứng rời). "
                "Việc tìm kiếm sẽ kém chính xác. Hãy thử xuất lại PDF từ Word (font Unicode như Times New Roman) "
                "hoặc tải bản DOCX/TXT của văn bản.")
    return ""


def ocr_pdf(path: Path) -> list[str]:
    """OCR từng trang PDF bằng Tesseract (cần: pypdfium2, pytesseract và chương trình Tesseract)."""
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError as e:
        raise ExtractError(
            "OCR đã bật nhưng chưa cài thư viện. Chạy: pip install pypdfium2 pytesseract pillow"
        ) from e
    if config.TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = config.TESSERACT_CMD
    try:
        # Tesseract im lặng bỏ qua gói ngôn ngữ bị thiếu (ví dụ chỉ còn tiếng Anh, mất hết dấu tiếng Việt),
        # nên phải kiểm tra trước thay vì tin vào việc "không báo lỗi".
        have = set(pytesseract.get_languages(config=""))
        missing = [lg for lg in config.OCR_LANG.split("+") if lg and lg not in have]
        if missing:
            raise ExtractError(
                f"Tesseract chưa có gói ngôn ngữ: {', '.join(missing)}. Hãy cài thêm (tiếng Việt là 'vie') "
                f"hoặc đổi OCR_LANG trong .env. Đang có: {', '.join(sorted(have))}."
            )
        pdf = pdfium.PdfDocument(str(path))
        out = []
        for page in pdf:
            img = page.render(scale=2.5).to_pil()
            out.append(pytesseract.image_to_string(img, lang=config.OCR_LANG))
        return out
    except ExtractError:
        raise
    except pytesseract.TesseractNotFoundError as e:
        raise ExtractError(
            "Không tìm thấy chương trình Tesseract. Hãy cài Tesseract OCR "
            "(hoặc đặt TESSERACT_CMD trong .env trỏ tới tesseract.exe)."
        ) from e
    except pytesseract.TesseractError as e:
        raise ExtractError(
            f"Tesseract báo lỗi: {str(e)[:200]}. Nếu là lỗi ngôn ngữ, hãy cài gói ngôn ngữ "
            f"'{config.OCR_LANG}' (tiếng Việt: vie) hoặc đổi OCR_LANG trong .env."
        ) from e
    except Exception as e:
        raise ExtractError(f"OCR thất bại: {type(e).__name__}: {str(e)[:200]}") from e


def extract_pages(path: Path, ext: str) -> tuple[list[str], str]:
    """Trả về (các trang, ghi chú). Ghi chú không rỗng khi văn bản được tạo bằng OCR."""
    ext = ext.lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        try:
            reader = PdfReader(str(path))
            pages = [(p.extract_text() or "") for p in reader.pages]
        except Exception as e:  # file hỏng, có mật khẩu...
            raise ExtractError(f"Không đọc được file PDF: {e}") from e
        if sum(len(p.strip()) for p in pages) < 50:
            if not config.OCR_ENABLED:
                raise ExtractError(
                    "PDF gần như không có lớp chữ (nhiều khả năng là bản scan). OCR đang tắt: "
                    "đặt OCR=1 trong .env (và cài Tesseract) để đọc bản scan, hoặc dùng file DOCX/TXT."
                )
            pages = ocr_pdf(path)
            if sum(len(p.strip()) for p in pages) < 50:
                raise ExtractError("OCR không nhận dạng được chữ nào từ file này.")
            return pages, "Văn bản được nhận dạng bằng OCR nên có thể sai chính tả hoặc số liệu. Hãy đối chiếu với bản gốc."
        return pages, ""

    if ext == ".docx":
        import docx

        try:
            d = docx.Document(str(path))
        except Exception as e:
            raise ExtractError(f"Không đọc được file DOCX: {e}") from e
        parts = [p.text for p in d.paragraphs]
        for t in d.tables:
            for row in t.rows:
                parts.append(" | ".join(c.text.strip() for c in row.cells))
        text = "\n".join(parts)
        if len(text.strip()) < 20:
            raise ExtractError("File DOCX không có nội dung văn bản.")
        return [text], ""

    if ext in (".txt", ".md"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text.strip()) < 20:
            raise ExtractError("File văn bản quá ngắn hoặc rỗng.")
        return [text], ""

    raise ExtractError(f"Định dạng {ext} chưa được hỗ trợ.")
