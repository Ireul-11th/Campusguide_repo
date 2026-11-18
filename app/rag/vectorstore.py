"""Kho vector tùy chọn bằng ChromaDB (VECTOR_STORE=chroma).

Mặc định (VECTOR_STORE=sqlite) vector nằm trong SQLite và so khớp bằng numpy.
Chroma chỉ có tác dụng khi đã bật EMBEDDING_MODEL.
"""
import threading

import numpy as np

from .. import config

_lock = threading.Lock()
_coll = None


def enabled() -> bool:
    return config.VECTOR_STORE == "chroma"


def _collection():
    global _coll
    with _lock:
        if _coll is None:
            try:
                import chromadb
            except ImportError as e:
                raise RuntimeError("Đã đặt VECTOR_STORE=chroma nhưng chưa cài chromadb (pip install chromadb).") from e
            client = chromadb.PersistentClient(path=str(config.DATA_DIR / "chroma"))
            _coll = client.get_or_create_collection("chunks", metadata={"hnsw:space": "cosine"})
        return _coll


def reset_for_tests() -> None:
    global _coll
    _coll = None


def delete_doc(doc_id: int) -> None:
    _collection().delete(where={"doc_id": doc_id})


def upsert(doc_id: int, chunk_ids: list[int], vecs: np.ndarray) -> None:
    c = _collection()
    c.delete(where={"doc_id": doc_id})
    if not chunk_ids:
        return
    c.add(
        ids=[f"c{i}" for i in chunk_ids],
        embeddings=[np.asarray(v, dtype=np.float32).tolist() for v in vecs],
        metadatas=[{"doc_id": doc_id} for _ in chunk_ids],
    )


def count() -> int:
    return _collection().count()


def query(qvec: np.ndarray, n: int) -> dict[int, float]:
    """Trả về {chunk_id: độ tương đồng cosine} cho n đoạn gần nhất."""
    c = _collection()
    total = c.count()
    if total == 0:
        return {}
    res = c.query(query_embeddings=[np.asarray(qvec, dtype=np.float32).tolist()], n_results=min(n, total))
    out: dict[int, float] = {}
    for cid, dist in zip(res["ids"][0], res["distances"][0]):
        out[int(cid[1:])] = 1.0 - float(dist)
    return out
