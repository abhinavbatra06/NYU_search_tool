"""Request and response schemas for the API."""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Request body for faculty search."""
    query: str = Field(..., description="Search query or research question")
    n_results: int = Field(default=5, ge=1, le=20, description="Number of results to return")
    use_hybrid: bool = Field(default=True, description="Use hybrid search (semantic + keyword) vs pure semantic")


class Faculty(BaseModel):
    """Faculty member in search results."""
    name: str
    faculty_id: str
    chunk_type: str
    source: Optional[str] = None
    url: Optional[str] = None
    paper_title: Optional[str] = None
    year: Optional[int] = None
    relevance_score: float = Field(..., description="Relevance score 0.0-1.0")


class SearchResult(BaseModel):
    """Single search result with content and metadata."""
    content: str = Field(..., description="Retrieved document content")
    faculty: Faculty = Field(..., description="Faculty member information")
    score: float = Field(..., description="Relevance score")


class SearchResponse(BaseModel):
    """Response body for faculty search."""
    results: List[SearchResult] = Field(..., description="Search results")
    answer: str = Field(..., description="AI-generated answer")
    query: str = Field(..., description="Original query")
    timestamp: str = Field(..., description="ISO timestamp of response")


class HealthStatus(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Overall status: healthy, degraded, or unhealthy")
    checks: Dict[str, Any] = Field(..., description="Status of individual checks")


class StartupStatus(BaseModel):
    """Startup validation response."""
    status: str = Field(..., description="Startup status: ready, initializing, or failed")
    checks: Dict[str, Any] = Field(..., description="Status of initialization checks")


class ErrorResponse(BaseModel):
    """Error response body."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    timestamp: str = Field(..., description="ISO timestamp of error")
