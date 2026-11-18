"""So sánh câu trả lời của bộ trích xuất với LLM (API hoặc local) trên cùng danh sách câu hỏi -> compare_report.md

Cách dùng (chạy trong PyCharm Terminal, thư mục dự án):
    1. Tạo file questions.txt: mỗi dòng một câu hỏi.
    2. Đặt trong .env cấu hình LLM bạn muốn so (vd LLM_PROVIDER=gemini + khóa API).
    3. python compare_answers.py questions.txt
Kết quả: compare_report.md, mở ra đọc từng câu và tự chấm đúng / sai.
"""
import sys
from pathlib import Path

from app import config, db
from app.rag.retrieval import index
from app.rag import pipeline


def main(path: str) -> None:
    db.init_db()
    index.reload()
    questions = [l.strip() for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    other = config.LLM_PROVIDER
    out = [f"# So sánh: bộ trích xuất và `{other}`\n"]
    for i, q in enumerate(questions, 1):
        config.LLM_PROVIDER = "extractive"
        a = pipeline.ask(q, [])
        config.LLM_PROVIDER = other
        b = pipeline.ask(q, []) if other not in ("none", "extractive") else {"answer": "(chưa cấu hình LLM để so sánh)", "status": "-"}
        out += [f"## {i}. {q}\n", f"**Trích xuất** ({a['status']}):\n\n{a['answer'] or '(từ chối)'}\n",
                f"**{other}** ({b['status']}):\n\n{b['answer'] or '(từ chối)'}\n", "**Chấm:** trích xuất đúng? [ ]  API đúng? [ ]  văn phong tương đương? [ ]\n", "---\n"]
    Path("compare_report.md").write_text("\n".join(out), encoding="utf-8")
    print(f"Đã ghi compare_report.md ({len(questions)} câu)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "questions.txt")