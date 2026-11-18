"""Rerank tùy chọn bằng cross-encoder (RERANK_MODEL, ví dụ BAAI/bge-reranker-v2-m3)."""
import logging
import threading

from .. import config
from .chunking import search_text

log = logging.getLogger("campusguide.rerank")
_model = None
_failed = False
_lock = threading.Lock()


def enabled() -> bool:
    return bool(config.RERANK_MODEL) and not _failed


def _get_model():
    global _model
    with _lock:
        if _model is None:
            from sentence_transformers import CrossEncoder

            _model = CrossEncoder(config.RERANK_MODEL)
        return _model


def rerank(query: str, cands: list[dict]) -> list[dict]:
    """Sắp xếp lại các ứng viên theo điểm cross-encoder. Lỗi thì giữ nguyên thứ tự cũ."""
    global _failed
    if not cands or not enabled():
        return cands
    try:
        model = _get_model()
        scores = model.predict([(query, search_text(c["doc_title"], c)) for c in cands])
    except Exception:
        log.exception("Rerank thất bại, bỏ qua bước rerank")
        _failed = True
        return cands
    out = []
    for c, s in zip(cands, scores):
        c = dict(c)
        c["rerank"] = float(s)
        out.append(c)
    out.sort(key=lambda c: c["rerank"], reverse=True)
    if config.RERANK_MIN_SCORE > 0:
        out = [c for c in out if c["rerank"] >= config.RERANK_MIN_SCORE]
    return out
