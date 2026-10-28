"""Local persistent memory package."""

from .embeddings import HashingEmbedder, cosine_similarity, keyword_score, normalize_text, tokenize
from .schemas import (
    MemoryCreate,
    MemoryCreateResult,
    MemoryEvent,
    MemoryExport,
    MemoryKind,
    MemoryRecord,
    MemorySearchResult,
    MemoryStats,
    MemoryUpdate,
)
from .service import MemoryService

__all__ = [
    "HashingEmbedder",
    "MemoryCreate",
    "MemoryCreateResult",
    "MemoryEvent",
    "MemoryExport",
    "MemoryKind",
    "MemoryRecord",
    "MemorySearchResult",
    "MemoryService",
    "MemoryStats",
    "MemoryUpdate",
    "cosine_similarity",
    "keyword_score",
    "normalize_text",
    "tokenize",
]
