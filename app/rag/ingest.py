"""Xử lý một tài liệu đã tải lên: trích xuất -> chia đoạn -> (embedding) -> lập chỉ mục."""
import logging
from pathlib import Path

from .. import config, db
from . import embedding, vectorstore
from .chunking import chunk_document, search_text
from .extract import ExtractError, extract_pages, quality_warning
from .retrieval import index

log = logging.getLogger("campusguide.ingest")


def _set(doc_id: int, **fields) -> None:
    cols = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE documents SET {cols}, updated_at = datetime('now') WHERE id = ?", [*fields.values(), doc_id])


def _stage(doc_id: int) -> str:
    r = db.one("SELECT proc_status FROM documents WHERE id = ?", [doc_id])
    return r["proc_status"] if r and r["proc_status"] in ("extracting", "chunking", "indexing") else "extracting"


def purge_vectors(doc_id: int) -> None:
    """Xóa vector của tài liệu khỏi Chroma (nếu đang dùng)."""
    if vectorstore.enabled():
        try:
            vectorstore.delete_doc(doc_id)
        except Exception:
            log.exception("Không xóa được vector của tài liệu %s khỏi Chroma", doc_id)


def process_document(doc_id: int) -> None:
    doc = db.one("SELECT * FROM documents WHERE id = ?", [doc_id])
    if not doc:
        return
    path = Path(config.UPLOAD_DIR) / doc["stored_name"]
    try:
        _set(doc_id, proc_status="extracting", error="", failed_stage="")
        pages, note = extract_pages(path, doc["ext"])

        _set(doc_id, proc_status="chunking", pages=len(pages))
        chunks = chunk_document(pages)
        if not chunks:
            raise ExtractError("Không tạo được đoạn văn bản nào từ tài liệu này.")

        _set(doc_id, proc_status="indexing")
        vecs = None
        if embedding.enabled():
            vecs = embedding.encode([search_text(doc["title"], c) for c in chunks])
        use_chroma = vecs is not None and vectorstore.enabled()

        db.execute("DELETE FROM chunks WHERE doc_id = ?", [doc_id])
        if vecs is not None and not use_chroma:
            blobs = [embedding.to_blob(v) for v in vecs]
        else:
            blobs = [None] * len(chunks)
        db.executemany(
            "INSERT INTO chunks (doc_id, ord, chapter, article, article_title, page, text, embedding) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [(doc_id, i, c.chapter, c.article, c.article_title, c.page, c.text, blobs[i]) for i, c in enumerate(chunks)],
        )
        if use_chroma:
            ids = [r["id"] for r in db.query("SELECT id FROM chunks WHERE doc_id = ? ORDER BY ord", [doc_id])]
            vectorstore.upsert(doc_id, ids, vecs)
        else:
            purge_vectors(doc_id)

        # Với tài liệu đã xong, trường error chứa cảnh báo chất lượng (không chặn việc dùng tài liệu)
        warn = " ".join(x for x in (note, quality_warning(pages)) if x)
        _set(doc_id, proc_status="done", n_chunks=len(chunks), error=warn)
    except ExtractError as e:
        _set(doc_id, proc_status="failed", error=str(e), failed_stage=_stage(doc_id))
    except Exception as e:  # lỗi không lường trước: ghi log kỹ thuật, báo gọn cho người dùng
        log.exception("Xử lý tài liệu %s thất bại", doc_id)
        _set(doc_id, proc_status="failed", error=f"Lỗi khi xử lý tài liệu ({type(e).__name__}). Xem log máy chủ để biết chi tiết.", failed_stage=_stage(doc_id))
    finally:
        index.reload()
