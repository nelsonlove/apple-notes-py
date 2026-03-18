"""LanceDB + sentence-transformers semantic search with FTS and RRF fusion.

Requires optional dependencies: pip install 'apple-notes-py[search]'
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_DATA_DIR = Path.home() / ".apple-notes" / "data"
_TABLE_NAME = "notes"
_MODEL_NAME = "all-MiniLM-L6-v2"
_NDIMS = 384
_RRF_K = 60


class SearchIndex:
    """Lazy-loaded semantic search index backed by LanceDB.

    Requires optional dependencies: lancedb, sentence-transformers.
    Install with: pip install 'apple-notes-py[search]'
    """

    def __init__(self, data_dir: str | Path | None = None):
        self._data_dir = Path(data_dir) if data_dir else _DATA_DIR
        self._db = None
        self._model = None

    # ── lazy accessors ───────────────────────────────────────────────

    def _get_db(self):
        if self._db is None:
            try:
                import lancedb
            except ModuleNotFoundError:
                raise RuntimeError(
                    "Semantic search requires the 'search' extras.\n"
                    "Install with: pip install 'apple-notes-py[search]'"
                )
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(str(self._data_dir))
        return self._db

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(_MODEL_NAME)
        return self._model

    def _embed(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        embeddings = model.encode(texts, show_progress_bar=False)
        return [e.tolist() for e in embeddings]

    def _embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    # ── table management ─────────────────────────────────────────────

    def _get_table(self):
        db = self._get_db()
        return db.open_table(_TABLE_NAME)

    def _table_exists(self) -> bool:
        db = self._get_db()
        return _TABLE_NAME in db.table_names()

    # ── build index ──────────────────────────────────────────────────

    def build(self, notes: list[dict[str, Any]], *, force: bool = False) -> int:
        """Build the search index from decoded notes.

        Each note dict must have: pk, title, folder, modifiedAt, content.
        """
        db = self._get_db()

        if force and self._table_exists():
            db.drop_table(_TABLE_NAME)

        # Prepare text for embedding: title + content
        texts = [f"{n['title']}\n{n['content']}" for n in notes]
        vectors = self._embed(texts)

        records = []
        for note, vec in zip(notes, vectors):
            records.append({
                "pk": note["pk"],
                "title": note["title"],
                "folder": note.get("folder", ""),
                "modifiedAt": note.get("modifiedAt", ""),
                "content": note["content"],
                "vector": vec,
            })

        import pyarrow as pa

        schema = pa.schema([
            pa.field("pk", pa.int64()),
            pa.field("title", pa.utf8()),
            pa.field("folder", pa.utf8()),
            pa.field("modifiedAt", pa.utf8()),
            pa.field("content", pa.utf8()),
            pa.field("vector", pa.list_(pa.float32(), _NDIMS)),
        ])

        if self._table_exists() and not force:
            table = self._get_table()
            table.add(records)
        else:
            table = db.create_table(_TABLE_NAME, data=records, schema=schema, mode="overwrite")

        # Create FTS index on content
        table.create_fts_index("content", replace=True)

        return len(records)

    # ── search ───────────────────────────────────────────────────────

    def vector_search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Pure vector similarity search."""
        table = self._get_table()
        vec = self._embed_query(query)
        results = table.search(vec).limit(limit).to_list()
        return [_clean_result(r) for r in results]

    def fts_search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Pure full-text search on content."""
        table = self._get_table()
        results = table.search(query, query_type="fts").limit(limit).to_list()
        return [_clean_result(r) for r in results]

    def hybrid_search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """RRF fusion of vector + FTS search results."""
        table = self._get_table()
        vec = self._embed_query(query)

        vector_results = table.search(vec).limit(limit).to_list()
        fts_results = table.search(query, query_type="fts").limit(limit).to_list()

        return _rrf_fuse(vector_results, fts_results, limit=limit)

    # ── status ───────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return index stats."""
        if not self._table_exists():
            return {"indexed": False, "count": 0, "path": str(self._data_dir)}
        table = self._get_table()
        return {
            "indexed": True,
            "count": table.count_rows(),
            "path": str(self._data_dir),
        }


# ── helpers ──────────────────────────────────────────────────────────────

def _clean_result(row: dict) -> dict:
    """Strip vector and distance fields from a LanceDB result row."""
    out = {k: v for k, v in row.items() if k not in ("vector", "_distance", "_rowid", "_relevance_score")}
    if "_distance" in row:
        out["score"] = 1.0 / (1.0 + row["_distance"])  # convert distance → similarity
    if "_relevance_score" in row:
        out["score"] = row["_relevance_score"]
    return out


def _rrf_fuse(
    vector_results: list[dict],
    fts_results: list[dict],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion (k=60) using pk as dedup key."""
    scores: dict[int, float] = {}
    docs: dict[int, dict] = {}

    for rank, row in enumerate(vector_results):
        pk = row["pk"]
        scores[pk] = scores.get(pk, 0.0) + 1.0 / (_RRF_K + rank)
        docs.setdefault(pk, row)

    for rank, row in enumerate(fts_results):
        pk = row["pk"]
        scores[pk] = scores.get(pk, 0.0) + 1.0 / (_RRF_K + rank)
        docs.setdefault(pk, row)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [
        {**_clean_result(docs[pk]), "score": score}
        for pk, score in ranked
    ]
