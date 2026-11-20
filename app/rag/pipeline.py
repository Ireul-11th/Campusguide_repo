"""Luồng hỏi đáp: viết lại câu hỏi nối tiếp -> truy xuất -> LLM -> tách trạng thái."""
import os

import query

from .. import config
from ..constants import VALIDITY
from . import extractive, lessons, llm
from .retrieval import content_tokens, index

NO_INFO = "KHONG_CO_THONG_TIN"

SYSTEM = (
    "Bạn là trợ lý hỏi đáp quy chế và thông tin đào tạo của một trường đại học. "
    "Chỉ được dùng thông tin trong các đoạn trích đánh số [1], [2]... do hệ thống cung cấp. "
    "Quy tắc:\n"
    "- Trả lời bằng tiếng Việt, ngắn gọn, rõ ràng; dùng gạch đầu dòng nếu có nhiều điều kiện.\n"
    "- Mỗi ý quan trọng phải kèm số nguồn, ví dụ [1] hoặc [2][3].\n"
    "- Không thêm điều khoản, con số, thời hạn nào không có trong đoạn trích; không dùng kiến thức bên ngoài.\n"
    f"- Nếu các đoạn trích không đủ để trả lời, chỉ trả lời đúng một dòng: {NO_INFO}\n"
    "- Nếu các đoạn trích thuộc nhiều văn bản khác nhau và có thể mâu thuẫn, nêu rõ từng văn bản."
)


def _source_dict(n: int, c: dict, q_terms: set[str]) -> dict:
    text_terms = set(content_tokens(c["text"]))
    return {
        "id": n,
        "chunk_id": c["chunk_id"],
        "doc_id": c["doc_id"],
        "doc_title": c["doc_title"],
        "doc_number": c["doc_number"] or "",
        "doc_type": c["doc_type"],
        "validity": c["validity"],
        "validity_label": VALIDITY.get(c["validity"], "Chưa xác minh"),
        "issued_date": c["issued_date"] or "",
        "effective_date": c["effective_date"] or "",
        "chapter": c["chapter"] or "",
        "article": c["article"] or "",
        "article_title": c["article_title"] or "",
        "page": c["page"] or 0,
        "text": c["text"],
        "highlight": sorted(q_terms & text_terms, key=len, reverse=True),
        "replaced_by": c.get("replaced_by") or "",
        "is_reference": bool(c.get("is_reference")),
        "file_url": f"/api/files/{c['doc_id']}",
        "is_pdf": c.get("ext") == ".pdf",
    }


def _context_block(s: dict) -> str:
    where = [s["doc_title"]]
    if s["doc_number"]:
        where.append(f"số hiệu {s['doc_number']}")
    if s["chapter"]:
        where.append(s["chapter"])
    if s["article"]:
        where.append(f"Điều {s['article']}. {s['article_title']}".strip())
    if s["page"]:
        where.append(f"trang {s['page']}")
    return f"[{s['id']}] ({'; '.join(where)})\n{s['text']}"


def _standalone_query(question: str, history: list[dict]) -> str:
    """Hỏi nối tiếp ("còn trường hợp rớt thì sao?") cần được viết lại thành câu độc lập."""
    prev_users = [m["content"] for m in history if m["role"] == "user"]
    if not prev_users:
        return question
    if llm.is_configured() and not llm.is_extractive():
        convo = "\n".join(
            f"{'Sinh viên' if m['role'] == 'user' else 'Trợ lý'}: {m['content'][:400]}" for m in history[-6:]
        )
        try:
            out = llm.generate(
                "Viết lại câu hỏi cuối của sinh viên thành một câu hỏi đầy đủ, độc lập, giữ nguyên ý, "
                "dựa vào hội thoại trước đó. Chỉ trả về đúng câu hỏi đã viết lại.",
                f"{convo}\nSinh viên: {question}",
                max_tokens=120,
            )
            if out and len(out) < 400:
                return out
        except llm.LLMError:
            pass
    return f"{prev_users[-1]} {question}"


def ask(question: str, history: list[dict]) -> dict:
    """Trả về dict: status, answer, sources, warnings, query.

    status:
      ok             có câu trả lời từ LLM kèm nguồn
      retrieval_only chưa cấu hình LLM, chỉ có các đoạn truy xuất được
      no_basis       không tìm thấy căn cứ đủ để trả lời
      empty_index    chưa có tài liệu nào được lập chỉ mục
    """
    if not index.chunks:
        return {"status": "empty_index", "answer": "", "sources": [], "warnings": [], "query": question}

    query = _standalone_query(question, history)
    query, extra = lessons.prepare(query, index.chunks)
    found = index.search(query, extra=extra)
    if not found:
        return {"status": "no_basis", "answer": "", "sources": [], "warnings": [], "query": query}

    q_terms = set(content_tokens(f"{query} {extra}"))
    sources = [_source_dict(i, c, q_terms) for i, c in enumerate(found, start=1)]
    warnings: list[str] = []

    by_type: dict[str, set[int]] = {}
    for s in sources:
        by_type.setdefault(s["doc_type"], set()).add(s["doc_id"])
    if any(len(v) > 1 for v in by_type.values()):
        warnings.append(
            "Các nguồn thuộc nhiều văn bản cùng loại, có thể là nhiều phiên bản. "
            "Hãy đối chiếu số hiệu và ngày ban hành trước khi áp dụng."
        )
    bad = {s["validity_label"] for s in sources if s["validity"] in ("het_hieu_luc", "da_thay_the")}
    if bad:
        warnings.append(f"Có nguồn được đánh dấu: {', '.join(sorted(bad))}.")

    if not llm.is_configured():
        return {"status": "retrieval_only", "answer": "", "sources": sources, "warnings": warnings, "query": query}

    context = "\n\n".join(_context_block(s) for s in sources)
    user = f"CÁC ĐOẠN TRÍCH:\n{context}\n\nCÂU HỎI: {query}"
    try:
        answer = extractive.answer(query, sources, extra) if llm.is_extractive() else llm.generate(SYSTEM, user)
    except llm.LLMError as e:
        return {
            "status": "llm_error",
            "answer": "",
            "sources": sources,
            "warnings": warnings,
            "error": str(e),
            "query": query,
        }

    if NO_INFO in answer or not answer.strip():
        return {"status": "no_basis", "answer": "", "sources": [], "warnings": [], "query": query}
    return {"status": "ok", "answer": answer, "sources": sources, "warnings": warnings, "query": query}
