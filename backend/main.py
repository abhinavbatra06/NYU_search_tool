"""FastAPI entrypoint and route definitions."""

from datetime import datetime
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from openai import OpenAI
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import Config
from .startup import validate_startup, get_health_status
from .schemas import SearchRequest, SearchResponse, SearchResult, Faculty, HealthStatus, StartupStatus
from .services.chroma import initialize_chroma
from .services.search import search_and_answer


startup_status = validate_startup()

if startup_status["status"] == "failed":
    checks = startup_status.get("checks", {})
    details = []
    for check_name, check in checks.items():
        if check.get("status") == "error":
            details.append(f"{check_name}: {check.get('message')}")

    raise RuntimeError(
        "Startup validation failed. "
        + (" | ".join(details) if details else str(startup_status))
    )

# Initialize clients
openai_client = OpenAI(api_key=Config.OPENAI_API_KEY)
chroma_client, chroma_collection = initialize_chroma(
    chroma_path=str(Config.CHROMA_DIR),
    collection_name=Config.CHROMA_COLLECTION_NAME,
    embedding_model=Config.EMBEDDING_MODEL,
    openai_api_key=Config.OPENAI_API_KEY
)

# Rate limiter — 20 search requests per minute per IP
limiter = Limiter(key_func=get_remote_address)

# FastAPI app
app = FastAPI(
    title=Config.API_TITLE,
    description=Config.API_DESCRIPTION,
    version="1.0.0"
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow frontend dev server and production origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (compiled frontend)
frontend_dist_path = Path(__file__).parent.parent / "frontend" / "dist"
frontend_assets_path = frontend_dist_path / "assets"
if frontend_assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist_path / "assets")), name="assets")


@app.get("/health", response_model=HealthStatus)
async def health_check():
    """Health check endpoint."""
    health = get_health_status()
    return health


@app.get("/startup", response_model=StartupStatus)
async def startup_check():
    """Startup status endpoint."""
    return startup_status


@app.post("/api/v1/search", response_model=SearchResponse)
@limiter.limit("20/minute")
async def search(
    request: Request,
    body: SearchRequest
):
    """
    Search for faculty based on research interests or questions.
    Rate limited to 20 requests per minute per IP.
    """
    try:
        # Perform search and answer generation
        results, answer = search_and_answer(
            client=openai_client,
            collection=chroma_collection,
            query=body.query,
            use_hybrid=body.use_hybrid,
            conversation_history=None
        )

        # Format results for API response
        formatted_results = []
        for doc, meta, score in results:
            faculty = Faculty(
                name=meta.get('faculty_name', 'Unknown'),
                faculty_id=meta.get('faculty_id', ''),
                chunk_type=meta.get('chunk_type', ''),
                source=meta.get('source'),
                url=meta.get('url'),
                paper_title=meta.get('paper_title'),
                year=meta.get('year'),
                relevance_score=float(score)
            )
            result = SearchResult(
                content=doc,
                faculty=faculty,
                score=float(score)
            )
            formatted_results.append(result)

        response = SearchResponse(
            results=formatted_results,
            answer=answer,
            query=body.query,
            timestamp=datetime.utcnow().isoformat()
        )
        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@app.get("/")
async def root():
    """Serve SPA root when available, otherwise return API info."""
    index_path = frontend_dist_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))

    return {
        "title": Config.API_TITLE,
        "description": Config.API_DESCRIPTION,
        "version": "1.0.0",
        "status": startup_status.get("status", "unknown"),
        "environment": Config.ENV,
        "endpoints": {
            "health": "/health",
            "startup": "/startup",
            "search": "/api/v1/search",
            "docs": "/docs"
        }
    }


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Catch-all route to serve the React SPA for client-side routing."""
    # Don't intercept API and framework routes.
    passthrough_paths = (
        "api/",
        "docs",
        "redoc",
        "openapi.json",
        "health",
        "startup",
        "assets/",
        "favicon.ico",
    )
    if full_path.startswith(passthrough_paths) or full_path in passthrough_paths:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Serve index.html for all non-API routes
    index_path = frontend_dist_path / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"error": "Frontend not built. Run 'npm run build' in the frontend directory."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=Config.API_HOST,
        port=Config.API_PORT,
        log_level=Config.LOG_LEVEL
    )
