"""Startup and health checks for the backend service."""

from typing import Dict, Any, Tuple
from datetime import datetime, timezone

from .config import Config
from .services.chroma import initialize_chroma


def check_chroma_collection() -> Tuple[bool, str]:
    """Check if the Chroma collection exists and is accessible."""
    try:
        _, collection = initialize_chroma(
            chroma_path=str(Config.CHROMA_DIR),
            collection_name=Config.CHROMA_COLLECTION_NAME,
            embedding_model=Config.EMBEDDING_MODEL,
            openai_api_key=Config.OPENAI_API_KEY
        )
        count = collection.count()
        return True, f"Collection has {count} documents"
    except Exception as e:
        return False, f"Failed to access collection: {str(e)}"


def validate_startup() -> Dict[str, Any]:
    """Run all startup validation checks."""
    startup_status = {
        "status": "initializing",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "warnings": []
    }

    # Check config
    try:
        Config.validate()
        startup_status["checks"]["config"] = {
            "status": "ok",
            "message": "Configuration validated"
        }
    except ValueError as e:
        startup_status["checks"]["config"] = {
            "status": "error",
            "message": str(e)
        }
        startup_status["status"] = "failed"
        return startup_status

    # Non-fatal warnings
    startup_status["warnings"] = Config.get_warnings()

    # Check path readability
    chroma_path_exists = Config.CHROMA_DIR.exists()
    startup_status["checks"]["chroma_path"] = {
        "status": "ok" if chroma_path_exists else "error",
        "message": f"Path: {Config.CHROMA_DIR}"
    }
    if not chroma_path_exists:
        startup_status["status"] = "failed"
        return startup_status

    # Check Chroma
    success, message = check_chroma_collection()
    startup_status["checks"]["chroma"] = {
        "status": "ok" if success else "error",
        "message": message
    }
    if not success:
        startup_status["status"] = "failed"

    # If we got here without fatal errors, we're ready
    if startup_status["status"] != "failed":
        startup_status["status"] = "ready"

    return startup_status


def get_health_status() -> Dict[str, Any]:
    """Get current health status of the service."""
    health = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {},
        "warnings": Config.get_warnings()
    }

    health["checks"]["config"] = {
        "status": "ok",
        "message": "Service configuration loaded"
    }

    # Check Chroma accessibility
    success, message = check_chroma_collection()
    health["checks"]["chroma"] = {
        "status": "ok" if success else "error",
        "message": message
    }
    if not success:
        health["status"] = "degraded"

    return health
