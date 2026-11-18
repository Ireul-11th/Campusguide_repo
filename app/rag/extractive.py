"""Bộ trả lời trích xuất: soạn câu trả lời bằng cách chọn đúng câu / khoản trong các đoạn đã truy xuất,
KHÔNG dùng mô hình sinh văn bản. Mọi chữ trong câu trả lời đều là nguyên văn của văn bản gốc, nên không thể bịa
số liệu hay điều khoản. Chạy offline, không cần GPU hay khóa API.

Bật bằng LLM_PROVIDER=extractive trong .env.
"""
import math
import re

from .. import config
from .retrieval import RE_REF, STOP, _norm

NO_INFO = "KHONG_CO_THONG_TIN"

RE_ARTICLE_HDR = re.compile(r"^\s*Điều\s+\d+\s*[\.:]")
RE_CHAPTER_HDR = re.compile(r"^\s*(?:CHƯƠNG|Chương)\s+")
RE_CLAUSE = re.compile(r"^(\d+)\.\s+(.*)$")
RE_SUB = re.compile(r"^(?:[a-zđ]\)|[-•+–])\s+(.*)$")
RE_NUMERIC_Q = re.compile(r"bao nhiêu|mấy|bao lâu|tối thiểu|tối đa|mức|tỷ lệ|tỉ lệ|%|điểm|hạn|thời gian", re.I)
RE_HAS_DIGIT = re.compile(r"\d")
ASK_WORDS = {"bao", "nhiêu", "mấy", "nào", "gì", "sao", "thế", "lúc", "khi", "ai", "đâu", "như", "thì", "được", "không", "có"}
MAX_UNIT_CHARS = 320
MAX_ANSWER_CHARS = 1600


def _words(text: str) -> list[str]:
    return re.findall(r"\w+", _norm(text))


def _content(text: str) -> set[str]:
    return {w for w in _words(text) if w not in STOP}


def _pairs(text: str) -> set[str]:
    w = _words(text)
    return {f"{a}_{b}" for a, b in zip(w, w[1:]) if a not in STOP and b not in STOP}


def _split_sentences(text: str) -> list[str]:
    if len(text) <= MAX_UNIT_CHARS:
        return [text]
    parts, cur = [], ""
    for s in re.split(r"(?<=[.;])\s+", text):
        if cur and len(cur) + len(s) + 1 > MAX_UNIT_CHARS:
            parts.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        parts.append(cur)
    return parts


def _is_boilerplate(ln: str) -> bool:
    """Quốc hiệu, tiêu đề IN HOA, dòng 'Căn cứ ...', số hiệu, nơi nhận: không phải nội dung quy định."""
    letters = [c for c in ln if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        return True
    if re.match(r"^[^,]{2,25},\s*ngày\s+\d", ln):          # "Đà Nẵng, ngày 12 tháng 8 năm 2024"
        return True
    return bool(re.match(r"(?i)^(căn cứ|xét đề nghị|nơi nhận|số\s*:|cộng hòa|độc lập|về việc|v/v)", ln)) or "CỘNG HÒA XÃ HỘI" in ln


def _units(src: dict, si: int) -> list[dict]:
    """Tách một đoạn truy xuất thành các đơn vị nhỏ: từng Khoản, từng ý a) b) -, hoặc từng câu của đoạn dài."""
    lines: list[dict] = []
    for raw in src["text"].splitlines():
        ln = re.sub(r"\s+", " ", raw).strip()
        if not ln or RE_ARTICLE_HDR.match(ln) or RE_CHAPTER_HDR.match(ln) or _is_boilerplate(ln):
            continue
        m, s = RE_CLAUSE.match(ln), RE_SUB.match(ln)
        if m:
            lines.append({"label": f"Khoản {m.group(1)}", "text": m.group(2), "sub": False})
        elif s:
            lines.append({"label": "", "text": s.group(1), "sub": True})
        elif lines and not re.search(r"[.;:?!]$", lines[-1]["text"]):
            lines[-1]["text"] += " " + ln          # dòng bị ngắt do xuống hàng trong PDF
        else:
            lines.append({"label": "", "text": ln, "sub": False})

    units: list[dict] = []
    parent = -1
    for ln in lines:
        if not ln["sub"]:
            parent = len(units)
        for k, piece in enumerate(_split_sentences(ln["text"])):
            units.append({
                "si": si, "idx": len(units), "label": ln["label"] if k == 0 else "", "text": piece,
                "parent": parent if ln["sub"] and parent >= 0 else None,
            })
    return units


def answer(query: str, sources: list[dict]) -> str:
    """Trả về câu trả lời (Markdown, có [n]) hoặc NO_INFO nếu không đủ căn cứ."""
    units: list[dict] = []
    per_src: list[list[dict]] = []
    for si, s in enumerate(sources):
        u = _units(s, si)
        per_src.append(u)
        units += u
    if not units:
        return NO_INFO

    q_words, q_pairs = _content(query) - ASK_WORDS, _pairs(query)
    if not q_words:
        return NO_INFO
    df: dict[str, int] = {}
    uw = [_content(u["text"]) for u in units]
    for ws in uw:
        for w in ws:
            df[w] = df.get(w, 0) + 1
    n = len(units)
    idf = {w: math.log(1 + n / (1 + df.get(w, 0))) for w in q_words}
    den = sum(idf.values()) or 1.0
    # Từ khóa của câu hỏi không xuất hiện ở bất kỳ đâu trong các đoạn tìm được (vd. "cảnh cáo"): tài liệu không nói về nó
    titles = set().union(*(_content(f"{x['article_title']} {x['doc_title']}") for x in sources))
    gone = [w for w in q_words if w not in df and w not in titles]
    if len(gone) >= 2 and sum(idf[w] for w in gone) / den >= config.EXTRACT_MAX_MISSING:
        return NO_INFO
    numeric_q = bool(RE_NUMERIC_Q.search(query))

    for u, ws in zip(units, uw):
        s = sources[u["si"]]
        got = sum(idf[w] for w in q_words if w in ws)
        lead = per_src[u["si"]][u["parent"]]["text"] if u["parent"] is not None else ""
        ctx = _content(f"{lead} {s['article_title']} {s['doc_title']}") - ws          # tiêu đề Điều, ý dẫn của Khoản
        got += 0.6 * sum(idf[w] for w in q_words if w in ctx)
        cov = min(1.0, got / den)
        phrase = min(0.3, 0.1 * len(q_pairs & _pairs(u["text"])))
        boost = 0.12 if numeric_q and RE_HAS_DIGIT.search(u["text"]) else 0.0
        u["score"] = cov + phrase + boost + (0.05 if u["si"] == 0 else 0.0)

    asked = {m.group(1) for m in RE_REF.finditer(query)}          # "Điều 4 quy định gì?" -> lấy cả Điều đó
    chosen: list[dict] = []
    if asked:
        for si, s in enumerate(sources):
            if s["article"] in asked:
                chosen += per_src[si][:10]
    if not chosen:
        best = max(u["score"] for u in units)
        if config.EXTRACT_DEBUG:
            print("[extractive]", round(best, 2), [(round(u["score"], 2), u["text"][:40]) for u in sorted(units, key=lambda u: -u["score"])[:4]])
        if best < config.EXTRACT_MIN_SCORE:
            return NO_INFO
        cut = max(config.EXTRACT_MIN_SCORE, 0.7 * best)
        ranked = sorted((u for u in units if u["score"] >= cut), key=lambda u: -u["score"])
        chosen = ranked[: config.EXTRACT_MAX_UNITS]
        # câu hỏi khớp tiêu đề của Điều ("Điều kiện xét học bổng") thì lấy đủ các Khoản của Điều đó
        full = {u["si"] for u in chosen
                if len(q_words & _content(sources[u["si"]]["article_title"])) >= max(2, 0.5 * len(q_words))}
        for si in sorted(full):
            chosen += [u for u in per_src[si][:8] if u not in chosen]

    # kèm ý dẫn của Khoản khi chọn một ý con; bỏ trùng; giữ thứ tự gốc
    picked: dict[tuple[int, int], dict] = {}
    for u in chosen:
        if u["parent"] is not None:
            p = per_src[u["si"]][u["parent"]]
            picked[(p["si"], p["idx"])] = p
        picked[(u["si"], u["idx"])] = u
    seen_text: set[str] = set()
    ordered = []
    for key in sorted(picked, key=lambda k: (k[0], k[1])):
        u = picked[key]
        t = _norm(u["text"])
        if t in seen_text:
            continue
        seen_text.add(t)
        ordered.append(u)

    groups: dict[tuple, list[dict]] = {}
    for u in ordered:
        s = sources[u["si"]]
        groups.setdefault((s["doc_id"], s["article"] or s["chapter"] or ""), []).append(u)

    multi_doc = len({sources[u["si"]]["doc_id"] for u in ordered}) > 1
    out = ["Các quy định liên quan trong văn bản đã tải lên:"]
    total = 0
    for (_, _), us in groups.items():
        s0 = sources[us[0]["si"]]
        head = []
        if s0["article"]:
            head.append(f"Điều {s0['article']}. {s0['article_title']}".strip(" ."))
        elif s0["chapter"]:
            head.append(s0["chapter"])
        doc = s0["doc_title"] + (f" (số {s0['doc_number']})" if s0["doc_number"] else "")
        if head or multi_doc:
            out.append("")
            out.append("### " + " — ".join(head + [doc]))
        for u in us:
            text = (f"{u['label']}: " if u["label"] else "") + u["text"]
            total += len(text)
            if total > MAX_ANSWER_CHARS and len(out) > 3:
                break
            out.append(f"- {text} [{sources[u['si']]['id']}]")
    return "\n".join(out)