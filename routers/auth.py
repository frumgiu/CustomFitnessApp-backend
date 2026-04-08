import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from db.database import create_token, get_db, verify_password, verify_token_db

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


@router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    body: LoginRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> LoginResponse:
    """Autentica l'utente e restituisce un session token."""
    async with db.execute(
        "SELECT id, username, password_hash FROM users WHERE username = ?",
        (body.username,),
    ) as cursor:
        row = await cursor.fetchone()

    # Risposta generica per non rivelare se l'username esiste o meno
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenziali non valide.",
        )

    token = await create_token(db, row["id"])
    return LoginResponse(token=token, username=row["username"])
