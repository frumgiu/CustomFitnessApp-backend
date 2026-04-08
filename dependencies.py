import aiosqlite
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db.database import get_db, verify_token_db

_bearer = HTTPBearer()


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: aiosqlite.Connection = Depends(get_db),
) -> int:
    """
    Dependency FastAPI: valida il Bearer token e restituisce lo user_id.
    Lancia 401 se il token è assente, non valido o scaduto.
    """
    user_id = await verify_token_db(db, credentials.credentials)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o scaduto.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user_id
