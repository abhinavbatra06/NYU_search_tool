"""Hybrid search ranking and keyword extraction."""

import re
from typing import Set


STOPWORDS = {
    'the', 'and', 'for', 'that', 'with', 'are', 'this', 'from', 'was', 'were',
    'been', 'have', 'has', 'had', 'will', 'would', 'could', 'should', 'may',
    'can', 'who', 'what', 'which', 'how', 'why', 'where', 'when', 'about',
    'into', 'through', 'during', 'before', 'after', 'above', 'below', 'between',
    'under', 'again', 'further', 'then', 'once', 'here', 'there', 'all', 'each',
    'both', 'few', 'more', 'most', 'other', 'some', 'such', 'only', 'own', 'same',
    'than', 'too', 'very', 'just', 'also', 'now', 'related', 'results', 'relevant'
}


def extract_keywords(text: str) -> Set[str]:
    """Extract meaningful keywords from text (3+ chars, lowercase)."""
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return {w for w in words if w not in STOPWORDS}


def keyword_score(doc: str, meta: dict, keywords: Set[str]) -> float:
    """Score document based on keyword matches."""
    if not keywords:
        return 0.0

    # Combine searchable text
    searchable = doc.lower()
    if meta.get('paper_title'):
        searchable += ' ' + meta['paper_title'].lower()
    if meta.get('faculty_name'):
        searchable += ' ' + meta['faculty_name'].lower()

    # Count keyword matches
    matches = sum(1 for kw in keywords if kw in searchable)
    return matches / len(keywords)


def compute_hybrid_score(
    semantic_score: float,
    keyword_score_val: float,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> float:
    """Compute hybrid score combining semantic and keyword matching."""
    return (semantic_weight * semantic_score) + (keyword_weight * keyword_score_val)
