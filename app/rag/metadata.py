"""Gợi ý thông tin văn bản (tên, loại, số hiệu, cơ quan, ngày, văn bản bị thay thế) từ nội dung file.

Dùng quy tắc theo thể thức văn bản hành chính Việt Nam, không cần LLM. Chỉ là gợi ý: người quản trị phải kiểm tra.
Trường nào không tìm chắc chắn sẽ để trống thay vì đoán.
"""
import re
from datetime import date

DATE_WORDS = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I)
DATE_SLASH = re.compile(r"(?<!\d)(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})(?!\d)")
DATE_ANY = rf"(?:{DATE_WORDS.pattern}|{DATE_SLASH.pattern})"

NUMBER = re.compile(r"(?im)^\s*Số(?:\s+hiệu)?\s*[:：]?\s*(\d+(?:/[0-9A-Za-zĐđ][0-9A-Za-zĐđ.\-]*)+)")
HEAD_KIND = re.compile(
    r"^(QUY CHẾ|QUY ĐỊNH|QUYẾT ĐỊNH|THÔNG BÁO|HƯỚNG DẪN|KẾ HOẠCH|CHƯƠNG TRÌNH|SỔ TAY|QUY TRÌNH|NỘI QUY|ĐIỀU LỆ)\b")
ORG_LINE = re.compile(r"^(ĐẠI HỌC|TRƯỜNG|HỌC VIỆN|PHÒNG|KHOA|BAN|TRUNG TÂM|VIỆN|BỘ|SỞ|UBND|ỦY BAN)\b")
NATION = re.compile(r"CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM|Độc lập\s*[-–]\s*Tự do\s*[-–]\s*Hạnh phúc", re.I)
SMALL = {"và", "của", "về", "cho", "các", "tại", "trong", "với", "để", "theo"}


def _mk_date(d: str, m: str, y: str) -> str:
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return ""


def _find_date(text: str) -> str:
    m = DATE_WORDS.search(text)
    if m:
        return _mk_date(*m.groups())
    m = DATE_SLASH.search(text)
    return _mk_date(*m.groups()) if m else ""


def _title_case(s: str) -> str:
    words = s.lower().split()
    return " ".join(w if (i and w in SMALL) else w[:1].upper() + w[1:] for i, w in enumerate(words))


def _sentence_case(s: str) -> str:
    s = s.strip()
    if s.isupper():
        s = s.lower()
    return s[:1].upper() + s[1:]


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines() if ln.strip()]


def _issuer(head: list[str]) -> str:
    cand = ""
    for ln in head:
        if re.match(r"(?i)^số\b", ln) or HEAD_KIND.match(ln):
            break
        ln = NATION.sub("", ln).strip(" -–")
        if ORG_LINE.match(ln) and len(ln) <= 120:
            cand = ln          # dòng cuối là cơ quan trực tiếp ban hành (dòng trên là cơ quan chủ quản)
    return _title_case(cand) if cand.isupper() else cand


def _title(lines: list[str]) -> str:
    for i, ln in enumerate(lines[:40]):
        if not HEAD_KIND.match(ln):
            continue
        parts = [ln]
        for nxt in lines[i + 1:i + 3]:
            if re.match(r"(?i)^(chương|điều|mục|căn cứ)\b", nxt) or ORG_LINE.match(nxt):
                break
            if re.match(r"(?i)^(về việc|v/v|về)\b", nxt) or (nxt.isupper() and len(nxt) < 150) or nxt.startswith("("):
                if nxt.startswith("("):
                    break
                parts.append(nxt)
                if not nxt.isupper():
                    break
            else:
                break
        t = " ".join(x.lower() if x.isupper() else (x[:1].lower() + x[1:] if k else x) for k, x in enumerate(parts))
        return _sentence_case(t)[:300]
    return ""


def _doc_type(title: str, head: str) -> str:
    t = (title + " " + head[:600]).lower()
    first = title.lower()
    for key, kinds in (("hoc_bong", ("học bổng",)), ("hoc_phi", ("học phí",)), ("so_tay", ("sổ tay",))):
        if any(k in first for k in kinds):
            return key
    if first.startswith("thông báo"):
        return "thong_bao"
    if "quy chế" in first or ("đào tạo" in first and ("quy định" in first or "quyết định" in first)):
        return "quy_che_dao_tao"
    for key, kinds in (("hoc_bong", ("học bổng",)), ("hoc_phi", ("học phí",)), ("so_tay", ("sổ tay",))):
        if any(k in t for k in kinds):
            return key
    return "quy_che_dao_tao" if "quy chế" in t else ""


def _effective(text: str) -> str:
    pat = re.compile(
        rf"(?:có\s+hiệu\s+lực|hiệu\s+lực\s+thi\s+hành|được\s+áp\s+dụng|áp\s+dụng)[^.\n]{{0,60}}?từ\s+(?:ngày\s+)?({DATE_ANY}|\d{{1,2}}\s+tháng\s+\d{{1,2}}\s+năm\s+\d{{4}})",
        re.I)
    for m in pat.finditer(text):
        frag = m.group(1)
        d = _find_date(frag if re.search(r"\d{4}", frag) and "ngày" in frag.lower() else "ngày " + frag)
        if d:
            return d
    return ""


def _replaces(text: str) -> str:
    m = re.search(r"(?i)\b(thay\s+thế|bãi\s+bỏ)\s+(?:cho\s+)?((?:Quy chế|Quyết định|Thông báo|Quy định|Hướng dẫn|Sổ tay|Kế hoạch)[^.;\n]{4,160})", text)
    if not m:
        return ""
    return f"{m.group(1).strip().capitalize()} {m.group(2).strip()}"[:300]


def detect(pages: list[str]) -> dict:
    """Trả về dict chỉ gồm các trường tìm được: title, doc_type, number, issuer, issued_date, effective_date, replaced_by."""
    text = "\n".join(pages)
    lines = _lines(text)
    head_lines = lines[:25]
    head = "\n".join(head_lines)
    out: dict[str, str] = {}

    title = _title(lines)
    if title:
        out["title"] = title
    dt = _doc_type(title, head)
    if dt:
        out["doc_type"] = dt
    m = NUMBER.search(head)
    if m:
        out["number"] = m.group(1).rstrip(".-")
    issuer = _issuer(head_lines)
    if issuer:
        out["issuer"] = issuer

    # Ngày ban hành: dòng địa danh "Đà Nẵng, ngày ... tháng ... năm ..." ở phần đầu văn bản
    issued = ""
    for ln in head_lines:
        if re.search(r",\s*ngày\s+\d", ln, re.I):
            issued = _find_date(ln)
            if issued:
                break
    if issued:
        out["issued_date"] = issued
    eff = _effective(text)
    if eff:
        out["effective_date"] = eff
    rep = _replaces(text)
    if rep:
        out["replaced_by"] = rep
    return out
