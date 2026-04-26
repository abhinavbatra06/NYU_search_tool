"""Backend configuration and environment setup."""

import os
from pathlib import Path
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables from repository root .env file.
load_dotenv(Path(__file__).parent.parent / ".env")


class Config:
    """Configuration for the backend service."""

    # Environment
    ENV = os.getenv("ENV", "development")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

    # Paths
    DATA_DIR = Path(__file__).parent.parent / "data"
    CHROMA_DIR = Path(os.getenv("CHROMA_DIR", str(DATA_DIR / "chroma_db")))

    # Chroma settings (must match the ingestion pipeline)
    CHROMA_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "faculty_search")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

    # API settings
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_TITLE = "NYU Faculty Search API"
    API_DESCRIPTION = "Search for NYU faculty based on research interests"

    # OpenAI settings
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))

    # Supabase settings (for auth)
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
    REQUIRE_SUPABASE = os.getenv("REQUIRE_SUPABASE", "false").lower() == "true"

    # CORS
    CORS_ORIGINS: list = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if o.strip()
    ]

    # Search settings
    SEARCH_MIN_SCORE_THRESHOLD = float(os.getenv("SEARCH_MIN_SCORE_THRESHOLD", "0.3"))
    SEARCH_N_RESULTS = int(os.getenv("SEARCH_N_RESULTS", "5"))
    SEARCH_SEMANTIC_WEIGHT = float(os.getenv("SEARCH_SEMANTIC_WEIGHT", "0.7"))
    SEARCH_KEYWORD_WEIGHT = float(os.getenv("SEARCH_KEYWORD_WEIGHT", "0.3"))

    @classmethod
    def _validate_numeric_ranges(cls, errors: List[str]) -> None:
        """Validate numeric configuration ranges."""
        if cls.API_PORT < 1 or cls.API_PORT > 65535:
            errors.append(f"API_PORT must be between 1 and 65535 (got {cls.API_PORT})")

        if cls.SEARCH_N_RESULTS < 1 or cls.SEARCH_N_RESULTS > 50:
            errors.append(
                f"SEARCH_N_RESULTS must be between 1 and 50 (got {cls.SEARCH_N_RESULTS})"
            )

        if cls.LLM_TEMPERATURE < 0 or cls.LLM_TEMPERATURE > 2:
            errors.append(
                f"LLM_TEMPERATURE must be between 0 and 2 (got {cls.LLM_TEMPERATURE})"
            )

        if cls.SEARCH_MIN_SCORE_THRESHOLD < 0 or cls.SEARCH_MIN_SCORE_THRESHOLD > 1:
            errors.append(
                "SEARCH_MIN_SCORE_THRESHOLD must be between 0 and 1 "
                f"(got {cls.SEARCH_MIN_SCORE_THRESHOLD})"
            )

        if cls.SEARCH_SEMANTIC_WEIGHT < 0 or cls.SEARCH_KEYWORD_WEIGHT < 0:
            errors.append("SEARCH_SEMANTIC_WEIGHT and SEARCH_KEYWORD_WEIGHT must be non-negative")

        if cls.SEARCH_SEMANTIC_WEIGHT + cls.SEARCH_KEYWORD_WEIGHT == 0:
            errors.append("SEARCH_SEMANTIC_WEIGHT + SEARCH_KEYWORD_WEIGHT must be greater than 0")

    @classmethod
    def get_warnings(cls) -> List[str]:
        """Return non-fatal configuration warnings."""
        warnings: List[str] = []

        if not cls.SUPABASE_URL or not cls.SUPABASE_KEY:
            warnings.append(
                "SUPABASE_URL/SUPABASE_KEY not set. API uses placeholder bearer-token auth."
            )

        if cls.ENV == "production" and not cls.REQUIRE_SUPABASE:
            warnings.append(
                "ENV=production with REQUIRE_SUPABASE=false. Consider enabling strict auth."
            )

        return warnings

    @classmethod
    def validate(cls) -> None:
        """Validate that all required configuration is present."""
        errors = []

        # Check OpenAI API key
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY environment variable is not set")

        # Check Chroma directory
        if not cls.CHROMA_DIR.exists():
            errors.append(
                f"Chroma directory not found at {cls.CHROMA_DIR}. "
                f"Please ensure the vector database has been initialized."
            )

        cls._validate_numeric_ranges(errors)

        if cls.REQUIRE_SUPABASE and (not cls.SUPABASE_URL or not cls.SUPABASE_KEY):
            errors.append(
                "REQUIRE_SUPABASE=true but SUPABASE_URL or SUPABASE_KEY is missing"
            )

        if errors:
            raise ValueError("Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    @classmethod
    def to_dict(cls) -> dict:
        """Return configuration as dictionary (excluding secrets)."""
        return {
            "env": cls.ENV,
            "log_level": cls.LOG_LEVEL,
            "api_host": cls.API_HOST,
            "api_port": cls.API_PORT,
            "chroma_dir": str(cls.CHROMA_DIR),
            "chroma_collection": cls.CHROMA_COLLECTION_NAME,
            "embedding_model": cls.EMBEDDING_MODEL,
            "llm_model": cls.LLM_MODEL,
            "require_supabase": cls.REQUIRE_SUPABASE,
            "search_threshold": cls.SEARCH_MIN_SCORE_THRESHOLD,
            "search_n_results": cls.SEARCH_N_RESULTS,
            "search_semantic_weight": cls.SEARCH_SEMANTIC_WEIGHT,
            "search_keyword_weight": cls.SEARCH_KEYWORD_WEIGHT,
        }
