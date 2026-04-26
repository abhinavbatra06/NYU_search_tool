"""Supabase authentication and authorization for API endpoints."""

from typing import Dict
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer
import jwt
from jwt import PyJWKClient

from .config import Config

security = HTTPBearer()

# Cached JWKS client — fetched once and reused
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        if not Config.SUPABASE_URL:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Server authentication is not configured",
            )
        jwks_url = f"{Config.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def _verify_supabase_jwt(token: str) -> Dict[str, str]:
    """
    Verify a Supabase-issued JWT using the project's JWKS endpoint.
    Supports both RS256 and HS256. Returns {"user_id": ..., "email": ...}.
    """
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "RS256")

        if alg in ("RS256", "RS384", "RS512", "ES256", "ES384", "ES512"):
            # Asymmetric — verify via JWKS
            client = _get_jwks_client()
            signing_key = client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
            )
        elif alg in ("HS256", "HS384", "HS512"):
            # Symmetric — verify via JWT secret
            secret = Config.SUPABASE_JWT_SECRET
            if not secret:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Server authentication is not configured",
                )
            payload = jwt.decode(
                token,
                secret,
                algorithms=[alg],
                audience="authenticated",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unsupported token algorithm",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    email = payload.get("email", "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    return {"user_id": user_id, "email": email}


async def get_current_user(credentials=Depends(security)) -> Dict[str, str]:
    """FastAPI dependency — validates bearer token and returns user info."""
    token = credentials.credentials
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _verify_supabase_jwt(token)
