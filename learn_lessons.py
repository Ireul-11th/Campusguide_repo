"""Để API "học" thay bạn: đọc các câu hỏi bị từ chối / bị chấm "chưa hữu ích", nhờ API đề xuất nhóm từ đồng nghĩa và viết tắt
có thật trong văn bản, ghi vào data/lessons.json với trạng thái pending. Bạn xem và duyệt, chỉ nhóm đã duyệt mới có tác dụng.

    python learn_lessons.py            # xin API đề xuất (cần LEARN_PROVIDER và khóa API trong .env)
    python learn_lessons.py --list     # xem các nhóm đang chờ / đã duyệt
    python learn_lessons.py --approve  # duyệt từng nhóm (y = đồng ý, n = bỏ, Enter = để lại)

API chỉ nhận: các câu hỏi bị từ chối và danh sách tiêu đề Điều. Không gửi nội dung đầy đủ của văn bản.
API chỉ trả về dữ liệu (nhóm từ), không có đoạn mã nào được chạy.
"""
import json
import os
import re
import sys

from app import config, db
from app.rag import lessons, llm
from app.rag.retrieval import index

PROMPT = """Bạn giúp hệ thống hỏi đáp quy chế đại học tìm được đúng điều khoản.
Dưới đây là các câu hỏi của sinh viên mà hệ thống KHÔNG tìm được câu trả lời, và danh sách tiêu đề các Điều có trong văn bản.
Với mỗi câu hỏi, nếu sinh viên dùng từ khác với văn bản (tiếng lóng, viết tắt, viết không dấu, từ đồng nghĩa), hãy đề xuất nhóm từ
cùng nghĩa, trong đó có ít nhất một cụm CÓ trong danh sách tiêu đề. Không bịa nội dung quy chế. Bỏ qua câu hỏi mà văn bản chắc chắn không có.
Chỉ trả về JSON, không giải thích: {"groups": [{"terms": ["cụm 1", "cụm 2"], "note": "lý do ngắn"}]}

CÂU HỎI BỊ TỪ CHỐI:
%s

TIÊU ĐỀ CÁC ĐIỀU:
%s
"""


def failed_questions(limit: int = 60) -> list[str]:
    rows = db.query(
        """SELECT DISTINCT u.content FROM messages a JOIN messages u ON u.conv_id = a.conv_id AND u.id < a.id AND u.role = 'user'
           WHERE a.role = 'assistant' AND (a.status = 'no_basis' OR a.feedback = -1)
             AND u.id = (SELECT MAX(id) FROM messages WHERE conv_id = a.conv_id AND role = 'user' AND id < a.id)
           ORDER BY a.id DESC LIMIT ?""", [limit])
    return [r["content"] for r in rows]


def propose() -> None:
    provider = os.getenv("LEARN_PROVIDER", "").strip()
    if not provider:
        sys.exit("Hãy đặt LEARN_PROVIDER (gemini | anthropic | openai) và khóa API tương ứng trong .env.")
    config.LLM_PROVIDER = provider
    if not llm.is_configured():
        sys.exit(f"Chưa cấu hình khóa API cho {provider}.")
    qs = failed_questions()
    if not qs:
        sys.exit("Chưa có câu hỏi nào bị từ chối hoặc chấm 'chưa hữu ích'. Hãy hỏi thử vài câu trước.")
    index.reload()
    titles = sorted({f"Điều {c['article']}. {c['article_title']}" for c in index.chunks if c["article"]})[:120]
    raw = llm.generate("Bạn chỉ trả về JSON hợp lệ.", PROMPT % ("\n".join(f"- {q}" for q in qs), "\n".join(titles)))
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        groups = json.loads(m.group(0))["groups"] if m else []
    except (ValueError, KeyError):
        sys.exit("API trả về không đúng định dạng. Thử chạy lại.")
    data = lessons.load()
    known = {tuple(sorted(lessons.strip_accents(t) for t in g["terms"])) for g in data["groups"]}
    added = 0
    for g in groups:
        terms = [str(t).strip()[:60] for t in g.get("terms", []) if str(t).strip()][:8]
        key = tuple(sorted(lessons.strip_accents(t) for t in terms))
        if len(terms) >= 2 and key not in known:
            data["groups"].append({"terms": terms, "status": "pending", "note": str(g.get("note", ""))[:200], "source": "api"})
            known.add(key)
            added += 1
    lessons.save(data)
    print(f"Đã thêm {added} nhóm chờ duyệt vào {lessons.LESSONS_PATH}. Chạy: python learn_lessons.py --approve")


def show() -> None:
    for i, g in enumerate(lessons.load()["groups"]):
        print(f"[{i}] {g.get('status', '?'):8} {' = '.join(g['terms'])}  ({g.get('note', '')})")


def approve() -> None:
    data = lessons.load()
    for g in data["groups"]:
        if g.get("status") != "pending":
            continue
        a = input(f"Duyệt nhóm: {' = '.join(g['terms'])}  ({g.get('note', '')}) [y/n/Enter]: ").strip().lower()
        if a == "y":
            g["status"] = "approved"
        elif a == "n":
            g["status"] = "rejected"
    lessons.save(data)
    print("Đã lưu. Khởi động lại server để áp dụng.")


if __name__ == "__main__":
    db.init_db()
    {"--list": show, "--approve": approve}.get(sys.argv[1] if len(sys.argv) > 1 else "", propose)()