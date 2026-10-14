"""Meaning-based search over policy clauses, alongside the word-match search.

Everyday wording ("my dishwasher hose leaked") rarely shares words with the form ("accidental
discharge or overflow of water"). A small local embedding model turns each clause and the question
into vectors, and clauses whose meaning is close to the question are scored even when no word
matches. The model runs on the CPU inside this service: no API key, no external call per question,
no database change. Clause vectors are held in memory and recomputed only when a clause's text
changes.

If the model cannot be loaded (not installed, no network for the first download, or switched off
with SEMANTIC_SEARCH=off), retrieval carries on with word match alone and says so in its stats.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path
from typing import Iterable, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# The clause text that is embedded: what the clause is about, in the form's words and in plain words.
MAX_CLAUSE_CHARS = 1500


def clause_text(clause) -> str:
    parts = [clause.heading or "", clause.plain_language or "", clause.text or ""]
    return ". ".join(p.strip() for p in parts if p and p.strip())[:MAX_CLAUSE_CHARS]


class SemanticIndex:
    """Lazily loaded embedding model plus an in-memory cache of clause vectors."""

    def __init__(self, model_name: str, cache_dir: Optional[str], enabled: bool):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.enabled = enabled
        self._model = None
        self._error: Optional[str] = None if enabled else "switched off (SEMANTIC_SEARCH=off)"
        self._vectors: dict[str, tuple[str, object]] = {}
        self._lock = threading.Lock()

    @property
    def unavailable_reason(self) -> Optional[str]:
        if self._error:
            return self._error
        return None if self._model is not None else "the model is still loading"


    def _load(self, wait: bool = True) -> bool:
        """Load the model once. With wait=False a question never waits for a load in progress."""
        if self._model is not None:
            return True
        if self._error is not None:
            return False
        if not self._lock.acquire(blocking=wait):
            return False
        try:
            if self._model is None and self._error is None:
                try:
                    from fastembed import TextEmbedding

                    kwargs = {"cache_dir": self.cache_dir} if self.cache_dir else {}
                    self._model = TextEmbedding(self.model_name, **kwargs)
                    logger.info("Meaning search model loaded: %s", self.model_name)
                except Exception as exc:  # the model is optional: word match still works without it
                    self._error = f"{type(exc).__name__}: {exc}"[:200]
                    logger.warning("Meaning search unavailable, using word match only: %s", self._error)
        finally:
            self._lock.release()
        return self._model is not None

    def warm_up(self, session_factory) -> None:
        """Load the model and embed every clause ahead of the first question (run in the background
        at startup, so the first question is not kept waiting)."""
        if not self._load(wait=True):
            return
        from app.models.policy import Clause

        db = session_factory()
        try:
            clauses = db.query(Clause).all()
            self.similarities("warm up", clauses)
            logger.info("Meaning search ready: %d clauses embedded", len(clauses))
        except Exception as exc:
            logger.warning("Meaning search warm-up failed; clauses will be embedded on first use: %s", exc)
        finally:
            db.close()

    def _clause_vectors(self, clauses: Iterable) -> dict[str, object]:
        import numpy as np

        wanted: dict[str, tuple[str, str]] = {}
        for clause in clauses:
            text = clause_text(clause)
            digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
            cached = self._vectors.get(clause.id)
            if cached is None or cached[0] != digest:
                wanted[clause.id] = (digest, text)
        if wanted:
            ids = list(wanted)
            vectors = list(self._model.embed([wanted[i][1] for i in ids]))
            for clause_id, vector in zip(ids, vectors):
                v = np.asarray(vector, dtype="float32")
                self._vectors[clause_id] = (wanted[clause_id][0], v / (np.linalg.norm(v) or 1.0))
        return {cid: vec for cid, (_, vec) in self._vectors.items()}

    def similarities(self, question: str, clauses: list) -> Optional[dict[str, float]]:
        """Cosine similarity between the question and each clause, or None when unavailable."""
        if not clauses or not question.strip() or not self._load(wait=False):
            return None
        import numpy as np

        try:
            vectors = self._clause_vectors(clauses)
            q = np.asarray(next(iter(self._model.query_embed([question]))), dtype="float32")
            q = q / (np.linalg.norm(q) or 1.0)
            return {c.id: float(vectors[c.id] @ q) for c in clauses if c.id in vectors}
        except Exception as exc:
            logger.warning("Meaning search failed for this question, using word match only: %s", exc)
            return None

    def lifts(self, question: str, candidates: list, corpus: list) -> Optional[dict[str, float]]:
        """How far each candidate's similarity stands above the question's baseline.

        Raw similarity drifts from question to question (a short question is "close" to everything),
        so a clause counts by how much it stands out: its similarity minus the median similarity of
        the question to every distinct clause in the library.
        """
        import statistics

        everything = {c.id: c for c in [*corpus, *candidates]}
        sims = self.similarities(question, list(everything.values()))
        if sims is None:
            return None
        distinct: dict[str, float] = {}
        for clause in everything.values():
            if clause.id in sims:
                distinct.setdefault(clause_text(clause), sims[clause.id])
        baseline = statistics.median(distinct.values()) if distinct else 0.0
        return {c.id: sims[c.id] - baseline for c in candidates if c.id in sims}


def _cache_dir() -> Optional[str]:
    configured = settings.SEMANTIC_CACHE_DIR
    if configured:
        return configured
    # ai-service/.model_cache: kept with the service, out of git.
    return str(Path(__file__).resolve().parents[3] / ".model_cache")


semantic_index = SemanticIndex(
    model_name=settings.SEMANTIC_MODEL,
    cache_dir=_cache_dir(),
    enabled=settings.SEMANTIC_SEARCH.lower() not in ("off", "false", "0", "no"),
)
