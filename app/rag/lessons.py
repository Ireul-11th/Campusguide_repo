"""Chuẩn hóa câu hỏi trước khi tìm kiếm, gồm 3 lớp:
1. Khôi phục dấu: "hoc bong" -> "học bổng", dựa trên từ vựng của chính các văn bản đã tải lên.
2. Số viết bằng chữ <-> chữ số: "mười bốn tín chỉ" thêm "14", "14 tín chỉ" thêm "mười bốn".
3. "Bài học" (data/lessons.json): nhóm từ đồng nghĩa / viết tắt, do quản trị viên nhập hoặc do API đề xuất
   (learn_lessons.py) rồi được duyệt. Chỉ nhóm đã duyệt (status = approved) mới có tác dụng.

Chỉ dùng quy tắc và dữ liệu, không chạy mã do API sinh ra. Mọi bước chỉ THÊM từ vào câu hỏi, không bao giờ xóa.
"""
import json
import re
import threading
import unicodedata
from collections import Counter

from .. import config

LESSONS_PATH = config.DATA_DIR / "lessons.json"
_lock = threading.Lock()


# ------------------------------------------------------------------ bỏ dấu
def strip_accents(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower().replace("đ", "d"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _has_accent(word: str) -> bool:
    return strip_accents(word) != word.lower()


# ------------------------------------------------------------------ 1. khôi phục dấu
COMMON = ("mười mươi trăm lẻ phải ít nhất nhiều được không đúng có bao nhiêu như thế nào khi nếu cần hoặc hay và của cho "
          "là gì thì sinh viên học kỳ năm tiền thưởng điểm thi lại đăng ký tối thiểu tối đa mức hạn thời gian ngày tháng "
          "bị nợ miễn giảm nộp trễ muộn đủ chưa đã sẽ nhận rớt trượt đóng làm gì "
          "môn cảnh cáo buộc thôi tốt nghiệp bảo lưu chuyển ngành kỷ luật hạnh kiểm rèn luyện xếp loại khá giỏi xuất sắc yếu kém "
          "tín chỉ học phần học phí thang chuẩn đầu ra ngoại ngữ thực tập đồ án khóa luận nghỉ phép vắng mặt đơn "
          "hồ sơ thủ tục quy chế quy định điều khoản chương trình đào tạo trường khoa lớp giảng viên cố vấn").split()
_vocab_cache: dict = {"key": None, "fold": {}, "words": set(), "pairs": set()}


def _vocab(chunks: list[dict]) -> dict:
    key = (id(chunks), len(chunks))
    if _vocab_cache["key"] != key:
        freq: Counter = Counter()
        pairs: set[tuple[str, str]] = set()
        for c in chunks:
            ws = re.findall(r"\w+", unicodedata.normalize("NFC", f"{c['doc_title']} {c['article_title']} {c['text']}").lower())
            freq.update(ws)
            pairs.update(zip(ws, ws[1:]))
        corpus_words = set(freq)
        for w in list(_D) + COMMON:      # từ thông dụng và số viết bằng chữ: nhận ra dù văn bản không có
            freq[w] += 0
        fold: dict[str, list[str]] = {}
        for w, _ in freq.most_common():
            fold.setdefault(strip_accents(w), []).append(w)
        _vocab_cache.update(key=key, fold=fold, words=corpus_words, pairs=pairs)
    return _vocab_cache


def restore_accents(query: str, chunks: list[dict]) -> str:
    """Khôi phục dấu cho từ không dấu. Chọn theo cặp từ đứng cạnh có thật trong văn bản; không có thì ưu tiên
    từ thông dụng, rồi đến từ xuất hiện nhiều nhất. Từ đã có dấu hoặc là số thì giữ nguyên."""
    v = _vocab(chunks)
    toks = re.findall(r"\w+|\W+", unicodedata.normalize("NFC", query))
    word_idx = [i for i, t in enumerate(toks) if re.match(r"\w", t)]
    cands: dict[int, list[str]] = {}
    for i in word_idx:
        t = toks[i]
        if _has_accent(t) or t.isdigit():
            cands[i] = [t.lower()]
        else:
            cands[i] = v["fold"].get(t.lower()) or [t.lower()]
    common = set(COMMON)
    out = list(toks)
    prev = ""
    for k, i in enumerate(word_idx):
        cs = cands[i]
        if len(cs) == 1:
            pick = cs[0]
        else:
            nxt = cands[word_idx[k + 1]] if k + 1 < len(word_idx) else []

            def score(c: str) -> tuple:
                pair = ((prev, c) in v["pairs"]) + any((c, n) in v["pairs"] for n in nxt)
                return (pair, c in common, -cs.index(c))
            pick = max(cs, key=score)
            if pick in ("mười", "mươi") and "mươi" in cs and "mười" in cs:
                pick = "mươi" if prev in _D and _D[prev] >= 2 else "mười"          # "hai mươi", nhưng "mười bốn"
            if "lăm" in cs and "làm" in cs:
                pick = "lăm" if prev in ("mươi", "mười", "trăm") else "làm"
        out[i] = pick
        prev = pick
    return "".join(out)


# ------------------------------------------------------------------ 2. số bằng chữ
_D = {"không": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5, "sáu": 6,
      "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9}
_DW = {1: "một", 2: "hai", 3: "ba", 4: "bốn", 5: "năm", 6: "sáu", 7: "bảy", 8: "tám", 9: "chín"}


def num_to_words(n: int) -> str:
    if n < 10 or n > 999:
        return ""
    h, r = divmod(n, 100)
    t, u = divmod(r, 10)
    parts = [f"{_DW[h]} trăm"] if h else []
    if h and r and t == 0:
        parts.append("lẻ")
    if t == 1:
        parts.append("mười")
    elif t > 1:
        parts.append(f"{_DW[t]} mươi")
    if u:
        parts.append("lăm" if (u == 5 and t >= 1) else "mốt" if (u == 1 and t > 1) else _DW[u])
    return " ".join(parts)


_WORDS_TO_NUM: dict[str, int] = {}
for _n in range(10, 1000):
    _WORDS_TO_NUM[num_to_words(_n)] = _n
    if _n % 10 == 4:
        _WORDS_TO_NUM[num_to_words(_n).rsplit(" ", 1)[0] + " tư"] = _n
_NUM_RE = re.compile(r"(?<!\w)(?:" + "|".join(sorted(map(re.escape, _WORDS_TO_NUM), key=len, reverse=True)) + r")(?!\w)", re.I)


def words_to_digits(query: str) -> str:
    """"mười bốn tín chỉ" -> "14 tín chỉ" (chỉ số từ 10 trở lên)."""
    return _NUM_RE.sub(lambda m: str(_WORDS_TO_NUM[m.group(0).lower()]), query)


def number_variants(query: str) -> list[str]:
    """Số >= 10 thôi: 'một' / 'hai' lẻ là mạo từ chứ không phải số trong tiếng Việt thường ngày."""
    extra: list[str] = []
    q = query.lower()
    for m in re.finditer(r"(?<![\d.,])(\d{2,3})(?![\d.,])", q):
        w = num_to_words(int(m.group(1)))
        if w:
            extra.append(w)
    return extra


# ------------------------------------------------------------------ 3. bài học (đồng nghĩa / viết tắt)
def load() -> dict:
    try:
        return json.loads(LESSONS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"groups": []}


def save(data: dict) -> None:
    with _lock:
        LESSONS_PATH.parent.mkdir(parents=True, exist_ok=True)
        LESSONS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _contains(q_fold: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(strip_accents(term))}(?!\w)", q_fold) is not None


BUILTIN = [{"terms": ["ít nhất", "tối thiểu"], "status": "approved"},
           {"terms": ["nhiều nhất", "tối đa"], "status": "approved"},
           {"terms": ["rớt môn", "trượt môn", "học phần chưa đạt"], "status": "approved"},
           {"terms": ["đóng học phí", "nộp học phí"], "status": "approved"},
           {"terms": ["tiền thưởng học tập", "học bổng"], "status": "approved"}]


def apply_synonyms(query: str, chunks: list[dict]) -> tuple[str, list[str]]:
    """Cụm trong câu hỏi thuộc một nhóm đồng nghĩa thì đổi sang cụm có nhiều từ xuất hiện trong văn bản nhất của nhóm đó,
    các cụm còn lại của nhóm được thêm vào làm từ bổ sung."""
    words = _vocab(chunks)["words"] if chunks else set()
    extra: list[str] = []
    for g in BUILTIN + load().get("groups", []):
        if g.get("status") != "approved":
            continue
        terms = [t.strip().lower() for t in g.get("terms", []) if t.strip()]
        low = query.lower()
        hit = [t for t in terms if re.search(rf"(?<!\w){re.escape(t)}(?!\w)", low)]
        if not hit:
            continue

        def in_corpus(t: str) -> float:
            ws = re.findall(r"\w+", t)
            return sum(w in words for w in ws) / len(ws)
        target = max(terms, key=lambda t: (in_corpus(t), t in hit))     # cụm hợp văn bản nhất, hòa thì giữ cụm người hỏi dùng
        for t in hit:
            if t != target:
                query = re.sub(rf"(?<!\w){re.escape(t)}(?!\w)", target, query, flags=re.I)
        extra += [t for t in terms if t != target]
    return query, extra


# ------------------------------------------------------------------ điểm vào duy nhất
def prepare(query: str, chunks: list[dict]) -> tuple[str, str]:
    """Trả về (câu hỏi đã khôi phục dấu, các từ bổ sung: số / đồng nghĩa). Lỗi gì cũng trả lại câu hỏi nguyên."""
    try:
        q = restore_accents(query, chunks) if chunks else query
        q = words_to_digits(q)
        q, syn = apply_synonyms(q, chunks)
        extra = list(dict.fromkeys(number_variants(q) + syn))
        return q, " ".join(extra)
    except Exception:       # chuẩn hóa chỉ để giúp tìm kiếm, không được làm hỏng luồng hỏi đáp
        return query, ""