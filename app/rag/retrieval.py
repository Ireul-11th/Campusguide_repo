"""Truy xuất: BM25 (unigram + bigram tiếng Việt) kết hợp embedding tùy chọn bằng RRF,
ưu tiên văn bản còn hiệu lực/mới nhất, rerank tùy chọn, lọc theo độ phủ từ khóa,
và kéo thêm điều khoản được dẫn tới ("theo Điều 12")."""
import re
import threading
import unicodedata

import numpy as np
from rank_bm25 import BM25Okapi

from .. import config, db
from . import embedding, rerank, vectorstore
from .chunking import search_text

STOP = {
    "là", "và", "của", "các", "có", "được", "cho", "những", "một", "trong", "thì", "gì", "nào",
    "như", "thế", "khi", "để", "với", "bị", "hay", "này", "đó", "em", "tôi", "mình", "không",
    "bao", "nhiêu", "sao", "ra", "thế_nào", "điều", "hỏi", "cần", "phải", "muốn", "về", "ở",
    "nếu", "thì", "làm", "bạn", "cho_biết", "xin",
}
RE_REF = re.compile(r"[Đđ]iều\s+(\d+)")

EXPIRED_PENALTY = 0.6   # văn bản hết hiệu lực / đã thay thế bị giảm điểm
NEWEST_BOOST = 1.05     # bản mới nhất trong cùng loại được cộng nhẹ


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


def content_tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", _norm(text)) if t not in STOP]


def bm25_tokens(text: str) -> list[str]:
    words = re.findall(r"\w+", _norm(text))
    bigrams = [f"{a}_{b}" for a, b in zip(words, words[1:])]
    return [w for w in words if w not in STOP] + bigrams


def _use_chroma() -> bool:
    return vectorstore.enabled() and embedding.enabled()


class Index:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.chunks: list[dict] = []
        self.bm25: BM25Okapi | None = None
        self.sets: list[set[str]] = []
        self.emb: np.ndarray | None = None
        self.prior: np.ndarray = np.ones(0)
        self.chroma = False
        self.by_article: dict[tuple[int, str], list[int]] = {}

    def reload(self) -> None:
        rows = db.query(
            """SELECT c.id AS chunk_id, c.doc_id, c.ord, c.chapter, c.article, c.article_title,
                      c.page, c.text, c.embedding,
                      d.title AS doc_title, d.number AS doc_number, d.doc_type, d.validity,
                      d.issued_date, d.effective_date, d.ext, d.replaced_by
               FROM chunks c JOIN documents d ON d.id = c.doc_id
               WHERE d.proc_status = 'done' ORDER BY c.doc_id, c.ord"""
        )
        chunks = [dict(r) for r in rows]
        corpus = [bm25_tokens(search_text(c["doc_title"], c)) for c in chunks]
        sets = [set(content_tokens(search_text(c["doc_title"], c))) for c in chunks]
        bm25 = BM25Okapi(corpus) if corpus else None

        use_chroma = _use_chroma()
        emb = None
        if embedding.enabled() and not use_chroma and chunks and all(c["embedding"] for c in chunks):
            try:
                emb = embedding.from_blobs([c["embedding"] for c in chunks])
            except ValueError:
                emb = None

        # Ưu tiên theo hiệu lực và độ mới trong cùng loại văn bản
        docs_by_type: dict[str, dict[int, str]] = {}
        for c in chunks:
            docs_by_type.setdefault(c["doc_type"], {})[c["doc_id"]] = c["issued_date"] or ""
        newest: dict[str, str] = {}
        for t, docs in docs_by_type.items():
            dates = [d for d in docs.values() if d]
            if len(docs) > 1 and dates:
                newest[t] = max(dates)
        prior = np.ones(len(chunks))
        for i, c in enumerate(chunks):
            if c["validity"] in ("het_hieu_luc", "da_thay_the"):
                prior[i] *= EXPIRED_PENALTY
            elif c["doc_type"] in newest and c["issued_date"] == newest[c["doc_type"]]:
                prior[i] *= NEWEST_BOOST

        by_article: dict[tuple[int, str], list[int]] = {}
        for i, c in enumerate(chunks):
            c.pop("embedding", None)
            if c["article"]:
                by_article.setdefault((c["doc_id"], c["article"]), []).append(i)
        with self._lock:
            self.chunks, self.bm25, self.sets, self.emb = chunks, bm25, sets, emb
            self.prior, self.chroma, self.by_article = prior, use_chroma, by_article

    @property
    def stats(self) -> dict:
        return {
            "chunks": len(self.chunks),
            "docs": len({c["doc_id"] for c in self.chunks}),
            "semantic": self.emb is not None or self.chroma,
            "vector_store": "chroma" if self.chroma else "sqlite",
            "rerank": rerank.enabled(),
        }

    def _semantic_sims(self, query: str, chunks: list[dict], emb, use_chroma: bool):
        """Độ tương đồng ngữ nghĩa của câu hỏi với từng đoạn (None nếu không có embedding)."""
        try:
            if use_chroma:
                qv = embedding.encode([query])[0]
                hits = vectorstore.query(qv, n=max(50, config.TOP_K * 6))
                if not hits:
                    return None
                return np.array([hits.get(c["chunk_id"], -1.0) for c in chunks], dtype=float)
            if emb is not None:
                return emb @ embedding.encode([query])[0]
        except Exception:
            return None
        return None

    def search(self, query: str, k: int | None = None) -> list[dict]:
        k = k or config.TOP_K
        with self._lock:
            chunks, bm25, sets, emb = self.chunks, self.bm25, self.sets, self.emb
            prior, by_article, use_chroma = self.prior, self.by_article, self.chroma
        if not chunks or bm25 is None:
            return []

        q_content = set(content_tokens(query))
        if not q_content:
            return []
        scores = np.asarray(bm25.get_scores(bm25_tokens(query)), dtype=float)
        sims = self._semantic_sims(query, chunks, emb, use_chroma)

        n = len(chunks)
        bm_rank = {i: r for r, i in enumerate(np.argsort(-scores))}
        if sims is not None:
            em_rank = {i: r for r, i in enumerate(np.argsort(-sims))}
            fused = [((1 / (60 + bm_rank[i]) + 1 / (60 + em_rank[i])) * prior[i], i) for i in range(n)]
        else:
            fused = [(scores[i] * prior[i], i) for i in range(n)]
        fused.sort(reverse=True)

        pool_size = k * 3 if rerank.enabled() else k
        top_score = fused[0][0] if fused else 0.0
        picked: list[dict] = []
        for score, i in fused[: max(pool_size * 4, 20)]:
            cov = len(q_content & sets[i]) / len(q_content)
            sim = float(sims[i]) if sims is not None else None
            ok = cov >= config.MIN_COVERAGE or (sim is not None and sim >= config.EMBEDDING_MIN_SIM)
            if not ok or (sims is None and scores[i] <= 0):
                continue
            # Chỉ dùng BM25: bỏ các đoạn điểm thấp hơn hẳn đoạn đứng đầu (tránh lẫn nguồn không liên quan)
            if sims is None and score < config.REL_SCORE * top_score:
                continue
            c = dict(chunks[i])
            c.update(score=float(score), coverage=round(cov, 2), similarity=sim, is_reference=False)
            picked.append(c)
            if len(picked) >= pool_size:
                break

        if rerank.enabled() and picked:
            picked = rerank.rerank(query, picked)
        picked = picked[:k]

        # Kéo thêm các Điều được dẫn tới trong cùng văn bản (tối đa 2)
        have = {(c["doc_id"], c["article"], c["chunk_id"]) for c in picked}
        refs: list[dict] = []
        for c in picked:
            for m in RE_REF.finditer(c["text"]):
                art = m.group(1)
                if art == c["article"]:
                    continue
                for j in by_article.get((c["doc_id"], art), []):
                    cc = chunks[j]
                    key = (cc["doc_id"], cc["article"], cc["chunk_id"])
                    if key in have:
                        continue
                    have.add(key)
                    r = dict(cc)
                    r.update(score=0.0, coverage=0.0, similarity=None, is_reference=True)
                    refs.append(r)
                    break
                if len(refs) >= 2:
                    break
            if len(refs) >= 2:
                break
        return picked + refs


index = Index()
