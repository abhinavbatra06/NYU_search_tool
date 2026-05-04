"""Supabase-backed application logging for search requests."""

import asyncio
from typing import Optional

from supabase import Client, create_client

from ..config import Config
from ..schemas import SearchResult


_supabase_client: Optional[Client] = None


def _get_supabase_client() -> Optional[Client]:
    global _supabase_client

    if _supabase_client is not None:
        return _supabase_client

    if not Config.SUPABASE_URL or not Config.SUPABASE_SERVICE_KEY:
        return None

    _supabase_client = create_client(Config.SUPABASE_URL, Config.SUPABASE_SERVICE_KEY)
    return _supabase_client


def _build_search_log_payload(
    question: str,
    answer: str,
    results: Optional[list[SearchResult]],
    use_hybrid: bool,
    success: bool,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
) -> dict:
    safe_results = results or []
    retrieved_chunks = [result.model_dump(mode="json") for result in safe_results]
    final_faculty = [result.faculty.model_dump(mode="json") for result in safe_results]

    return {
        "question": question,
        "answer": answer,
        "final_faculty": final_faculty,
        "retrieved_chunks": retrieved_chunks,
        "use_hybrid": use_hybrid,
        "success": success,
        "error_message": error_message,
        "error_type": error_type,
    }


def _insert_search_log(payload: dict) -> None:
    client = _get_supabase_client()
    if client is None:
        return

    client.table("search_logs").insert(payload).execute()


async def log_search(
    question: str,
    answer: str,
    results: Optional[list[SearchResult]],
    use_hybrid: bool,
    success: bool = True,
    error_message: Optional[str] = None,
    error_type: Optional[str] = None,
) -> None:
    payload = _build_search_log_payload(
        question=question,
        answer=answer,
        results=results,
        use_hybrid=use_hybrid,
        success=success,
        error_message=error_message,
        error_type=error_type,
    )

    try:
        await asyncio.to_thread(_insert_search_log, payload)
    except Exception:
        return