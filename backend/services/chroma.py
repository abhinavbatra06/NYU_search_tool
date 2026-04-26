"""Chroma vector store initialization and retrieval."""

from pathlib import Path
from typing import Tuple, List, Dict, Any
import chromadb
from chromadb.utils import embedding_functions


def initialize_chroma(
    chroma_path: str,
    collection_name: str = "faculty_search",
    embedding_model: str = "text-embedding-3-small",
    openai_api_key: str = None
) -> Tuple[chromadb.PersistentClient, Any]:
    """Initialize Chroma client and get the collection."""
    client = chromadb.PersistentClient(path=chroma_path)

    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=openai_api_key,
        model_name=embedding_model
    )

    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=openai_ef
        )
    except Exception as e:
        raise ValueError(
            f"Collection '{collection_name}' not found at {chroma_path}. "
            f"Please ensure the Chroma database has been initialized. Error: {e}"
        )

    return client, collection


def retrieve_documents(
    collection: Any,
    query: str,
    n_results: int = 50
) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
    """Retrieve documents from Chroma using semantic search."""
    results = collection.query(query_texts=[query], n_results=n_results)

    documents = results['documents'][0] if results['documents'] else []
    metadatas = results['metadatas'][0] if results['metadatas'] else []
    distances = results['distances'][0] if results['distances'] else []

    return documents, metadatas, distances


def dedupe_by_faculty(
    results: List[Tuple[str, Dict[str, Any], float]],
    max_per_faculty: int = 1
) -> List[Tuple[str, Dict[str, Any], float]]:
    """Deduplicate results to show at most one per faculty member."""
    seen_faculty = set()
    deduped = []

    for doc, meta, score in results:
        faculty_id = meta.get('faculty_id', '')
        if faculty_id not in seen_faculty:
            seen_faculty.add(faculty_id)
            deduped.append((doc, meta, score))

    return deduped
