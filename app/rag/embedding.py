"""Embedding tùy chọn (sentence-transformers). Chỉ chạy khi đặt EMBEDDING_MODEL."""
import threading

import numpy as np

from .. import config

_model = None
_lock = threading.Lock()


def enabled() -> bool:
    return bool(config.EMBEDDING_MODEL)


def _get_model():
    global _model
    with _lock:
        if _model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise RuntimeError(
                    "Đã đặt EMBEDDING_MODEL nhưng chưa cài sentence-transformers "
                    "(pip install sentence-transformers)."
                ) from e
            _model = SentenceTransformer(config.EMBEDDING_MODEL)
        return _model


def encode(texts: list[str]) -> np.ndarray:
    m = _get_model()
    vecs = m.encode(texts, normalize_embeddings=True, batch_size=16, show_progress_bar=False)
    return np.asarray(vecs, dtype=np.float32)


def to_blob(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()


def from_blobs(blobs: list[bytes]) -> np.ndarray:
    return np.vstack([np.frombuffer(b, dtype=np.float32) for b in blobs])
