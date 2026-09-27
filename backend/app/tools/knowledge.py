"""Policy retrieval with BM25 over markdown sections. No embeddings or network required."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

DOCS_DIR = Path(__file__).resolve().parent.parent / "data" / "docs"

_STOPWORDS = frozenset(
    [
        "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does", "for", "from", "has",
        "have", "how", "i", "if", "in", "is", "it", "its", "my", "of", "on", "or", "our", "please", "so",
        "that", "the", "their", "them", "there", "this", "to", "was", "we", "what", "when", "where", "which",
        "who", "why", "will", "with", "you", "your", "me", "am", "just", "about", "get", "got", "were",
        "been", "being", "had", "did", "any", "anymore", "yet", "some", "something", "up",
    ]
)
_SUFFIXES = ("ing", "ed", "es", "e", "s")


def _stem(word: str) -> str:
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOPWORDS]


@dataclass(frozen=True)
class Passage:
    source: str
    section: str
    text: str
    score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _split_sections(path: Path) -> list[Passage]:
    passages: list[Passage] = []
    section, lines = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            if section and lines:
                passages.append(Passage(path.name, section, " ".join(lines).strip()))
            section, lines = line[3:].strip(), []
        elif section and line.strip():
            lines.append(line.strip())
    if section and lines:
        passages.append(Passage(path.name, section, " ".join(lines).strip()))
    return passages


class KnowledgeBase:
    def __init__(self, docs_dir: Path = DOCS_DIR) -> None:
        self.passages = [p for f in sorted(docs_dir.glob("*.md")) for p in _split_sections(f)]
        # Section titles are repeated so a heading match outweighs a passing mention in body text.
        corpus = [tokenize(f"{p.section} {p.section} {p.text}") for p in self.passages]
        self._bm25 = BM25Okapi(corpus)

    def search(self, query: str, k: int = 2, min_ratio: float = 0.5) -> list[Passage]:
        """Top-k passages, dropping anything scoring below min_ratio of the best hit."""
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(zip(self.passages, scores, strict=True), key=lambda x: x[1], reverse=True)
        if not ranked or ranked[0][1] <= 0:
            return []
        best = ranked[0][1]
        return [
            Passage(p.source, p.section, p.text, round(float(s), 3))
            for p, s in ranked[:k]
            if s >= best * min_ratio
        ]
