"""Chia đoạn theo cấu trúc văn bản pháp quy: Chương > Điều > Khoản.

Mỗi chunk giữ metadata: chương, số Điều, tiêu đề Điều, trang bắt đầu.
Nếu văn bản không có "Điều N" (thông báo, sổ tay...), dùng cửa sổ theo đoạn văn.
"""
import re
from dataclasses import dataclass

MAX_CHARS = 1500
FALLBACK_CHARS = 900
FALLBACK_OVERLAP = 150

RE_CHAPTER = re.compile(r"^\s*(?:CHƯƠNG|Chương)\s+([IVXLC]+|\d+)\b\s*[\.:\-–]?\s*(.*)$")
RE_ARTICLE = re.compile(r"^\s*Điều\s+(\d+)\s*[\.:]\s*(.*)$")
RE_CLAUSE = re.compile(r"^\s*\d+\.\s+\S")


@dataclass
class Chunk:
    chapter: str
    article: str
    article_title: str
    page: int
    text: str


def _clean(line: str) -> str:
    return re.sub(r"[ \t ]+", " ", line).strip()


def _lines(pages: list[str]) -> list[tuple[int, str]]:
    out = []
    for pno, text in enumerate(pages, start=1):
        for raw in text.splitlines():
            line = _clean(raw)
            if line:
                out.append((pno, line))
    return out


def _split_long(body_lines: list[str]) -> list[str]:
    """Tách một Điều quá dài theo Khoản, gộp lại tới ~MAX_CHARS."""
    pieces: list[list[str]] = []
    for ln in body_lines:
        if RE_CLAUSE.match(ln) or not pieces:
            pieces.append([ln])
        else:
            pieces[-1].append(ln)
    merged: list[str] = []
    cur = ""
    for p in pieces:
        t = "\n".join(p)
        if cur and len(cur) + len(t) > MAX_CHARS:
            merged.append(cur)
            cur = t
        else:
            cur = f"{cur}\n{t}" if cur else t
    if cur:
        merged.append(cur)
    # Một khoản đơn lẻ vẫn quá dài: cắt theo độ dài
    final: list[str] = []
    for m in merged:
        while len(m) > MAX_CHARS * 1.5:
            cut = m.rfind(". ", 0, MAX_CHARS)
            cut = cut + 1 if cut > 200 else MAX_CHARS
            final.append(m[:cut].strip())
            m = m[cut:].strip()
        if m:
            final.append(m)
    return final


def _fallback_windows(lines: list[tuple[int, str]]) -> list[Chunk]:
    chunks: list[Chunk] = []
    buf: list[str] = []
    size = 0
    start_page = lines[0][0] if lines else 1
    for pno, ln in lines:
        if not buf:
            start_page = pno
        buf.append(ln)
        size += len(ln) + 1
        if size >= FALLBACK_CHARS:
            text = "\n".join(buf)
            chunks.append(Chunk("", "", "", start_page, text))
            tail = text[-FALLBACK_OVERLAP:]
            buf = [tail] if tail else []
            size = len(tail)
            start_page = pno
    if buf and "\n".join(buf).strip():
        text = "\n".join(buf)
        if not chunks or text != chunks[-1].text[-len(text):]:
            chunks.append(Chunk("", "", "", start_page, text))
    return chunks


def chunk_document(pages: list[str]) -> list[Chunk]:
    lines = _lines(pages)
    if not lines:
        return []

    has_article = any(RE_ARTICLE.match(ln) for _, ln in lines)
    if not has_article:
        return _fallback_windows(lines)

    chunks: list[Chunk] = []
    chapter = ""
    cur: dict | None = None
    preamble: list[tuple[int, str]] = []

    def flush():
        nonlocal cur
        if not cur or not cur["lines"]:
            cur = None
            return
        parts = _split_long(cur["lines"]) if sum(len(x) for x in cur["lines"]) > MAX_CHARS else ["\n".join(cur["lines"])]
        for part in parts:
            chunks.append(Chunk(cur["chapter"], cur["num"], cur["title"], cur["page"], part))
        cur = None

    i = 0
    while i < len(lines):
        pno, ln = lines[i]
        m_ch = RE_CHAPTER.match(ln)
        m_ar = RE_ARTICLE.match(ln)
        if m_ch and not m_ar:
            flush()
            title = m_ch.group(2).strip()
            # Tiêu đề chương thường nằm ở dòng kế tiếp
            if not title and i + 1 < len(lines):
                nxt = lines[i + 1][1]
                if not RE_ARTICLE.match(nxt) and not RE_CHAPTER.match(nxt) and len(nxt) < 120:
                    title = nxt
                    i += 1
            chapter = f"Chương {m_ch.group(1)}" + (f". {title}" if title else "")
        elif m_ar:
            flush()
            cur = {
                "num": m_ar.group(1),
                "title": m_ar.group(2).strip(),
                "page": pno,
                "chapter": chapter,
                "lines": [],
            }
        elif cur is not None:
            cur["lines"].append(ln)
        else:
            preamble.append((pno, ln))
        i += 1
    flush()

    if preamble and sum(len(x[1]) for x in preamble) > 80:
        head = _fallback_windows(preamble)
        for h in head:
            h.article_title = "Phần mở đầu"
        chunks = head + chunks
    return chunks


def search_text(doc_title: str, c: "Chunk | dict") -> str:
    """Chuỗi dùng để lập chỉ mục: có kèm tên văn bản/chương/điều để tăng khả năng khớp."""
    get = (lambda k: getattr(c, k)) if isinstance(c, Chunk) else (lambda k: c[k])
    head = [doc_title]
    if get("chapter"):
        head.append(get("chapter"))
    if get("article"):
        head.append(f"Điều {get('article')}. {get('article_title')}")
    elif get("article_title"):
        head.append(get("article_title"))
    return " | ".join(head) + "\n" + get("text")
