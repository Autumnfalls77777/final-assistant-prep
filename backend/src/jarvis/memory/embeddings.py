"""Local, deterministic embeddings and lexical scoring."""

from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from itertools import pairwise

_WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "did",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "with",
    }
)


def normalize_text(text: str) -> str:
    """Normalize text for exact deduplication."""

    return " ".join(text.casefold().split())


def tokenize(text: str) -> list[str]:
    """Tokenize text into meaningful lowercase words."""

    return [
        token
        for token in (match.group(0).casefold() for match in _WORD_PATTERN.finditer(text))
        if len(token) > 1 and token not in _STOPWORDS
    ]


def keyword_score(query_tokens: Sequence[str], content_tokens: Sequence[str]) -> float:
    """Return query-token coverage in the content."""

    query_set = set(query_tokens)
    if not query_set:
        return 0.0
    content_set = set(content_tokens)
    return len(query_set & content_set) / len(query_set)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Compute cosine similarity, with safe handling for zero vectors."""

    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


class HashingEmbedder:
    """Deterministic local hashing embedder for vector retrieval.

    This is intentionally lightweight and dependency-free. It captures lexical
    similarity with unigrams and bigrams and can be replaced by a model-backed
    local embedder later without changing the memory service contract.
    """

    def __init__(self, dimension: int = 384) -> None:
        if dimension < 32:
            raise ValueError("Embedding dimension must be at least 32")
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = tokenize(text)
        if not tokens:
            return vector

        features = list(tokens)
        features.extend(f"{left}_{right}" for left, right in pairwise(tokens))
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            number = int.from_bytes(digest, "big")
            index = number % self.dimension
            sign = 1.0 if (number >> 63) & 1 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return vector
        return [value / norm for value in vector]
