"""Main search orchestration logic."""

from typing import List, Tuple, Dict, Any, Optional
from openai import OpenAI

from .ranking import extract_keywords, keyword_score, compute_hybrid_score
from .chroma import retrieve_documents, dedupe_by_faculty
from .llm import build_context_from_results, generate_answer


MIN_SCORE_THRESHOLD = 0.3


def search_faculty(
    collection: Any,
    query: str,
    n_results: int = 20,
    similarity_threshold: float = 0.3
) -> List[Tuple[str, Dict[str, Any], float]]:
    """
    Search for relevant faculty using semantic search.
    Returns unique faculty sorted by relevance score.
    """
    documents, metadatas, distances = retrieve_documents(collection, query, n_results=50)

    # Convert distances to similarity scores
    results_with_scores = [
        (doc, meta, 1 - dist)
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]

    # Deduplicate by faculty
    unique_results = dedupe_by_faculty(results_with_scores)

    # Filter by threshold
    filtered = [
        (doc, meta, score)
        for doc, meta, score in unique_results
        if score >= similarity_threshold
    ]

    return filtered[:n_results]


def hybrid_search_faculty(
    collection: Any,
    query: str,
    n_results: int = 20,
    similarity_threshold: float = 0.3,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3
) -> List[Tuple[str, Dict[str, Any], float]]:
    """
    Search using hybrid approach: semantic similarity + keyword matching.
    Returns unique faculty sorted by hybrid score.
    """
    documents, metadatas, distances = retrieve_documents(collection, query, n_results=50)

    # Extract keywords from query
    keywords = extract_keywords(query)

    # Score and combine
    scored_results = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        semantic_score = 1 - dist
        kw_score = keyword_score(doc, meta, keywords)
        final_score = compute_hybrid_score(
            semantic_score,
            kw_score,
            semantic_weight,
            keyword_weight
        )
        scored_results.append((doc, meta, final_score))

    # Sort by final score descending
    scored_results.sort(key=lambda x: x[2], reverse=True)

    # Deduplicate by faculty
    unique_results = dedupe_by_faculty(scored_results)

    # Filter by threshold
    filtered = [
        (doc, meta, score)
        for doc, meta, score in unique_results
        if score >= similarity_threshold
    ]

    return filtered[:n_results]


def search_and_answer(
    client: OpenAI,
    collection: Any,
    query: str,
    use_hybrid: bool = True,
    conversation_history: Optional[List[Dict[str, str]]] = None
) -> Tuple[List[Tuple[str, Dict[str, Any], float]], str]:
    """
    Complete search and answer pipeline.
    Returns (search_results, generated_answer).
    """
    if use_hybrid:
        results = hybrid_search_faculty(collection, query, n_results=5)
    else:
        results = search_faculty(collection, query, n_results=5)

    if not results:
        return results, "I couldn't find any highly relevant faculty for that query. Try rephrasing or using different keywords."

    context = build_context_from_results(results)
    answer = generate_answer(
        client,
        query,
        context,
        conversation_history=conversation_history
    )

    return results, answer
