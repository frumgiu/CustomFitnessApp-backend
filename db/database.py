import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator

import aiosqlite
import bcrypt

DB_PATH = Path(__file__).parent / "health_cache.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

TOKEN_TTL_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


async def create_token(db: aiosqlite.Connection, user_id: int) -> str:
    """Genera un token sicuro, lo salva nel DB e lo restituisce."""
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC).isoformat()
    await db.execute(
        "INSERT INTO session_tokens (token, user_id, created_at) VALUES (?, ?, ?)",
        (token, user_id, now),
    )
    await db.commit()
    return token


async def verify_token_db(db: aiosqlite.Connection, token: str) -> int | None:
    """
    Valida il token contro il DB.
    Restituisce lo user_id se valido e non scaduto, altrimenti None.
    """
    cutoff = (datetime.now(UTC) - timedelta(days=TOKEN_TTL_DAYS)).isoformat()
    async with db.execute(
        "SELECT user_id FROM session_tokens WHERE token = ? AND created_at >= ?",
        (token, cutoff),
    ) as cursor:
        row = await cursor.fetchone()
    return row["user_id"] if row else None


async def init_db() -> None:
    """Inizializza il database SQLite con lo schema e l'utente di default."""
    async with aiosqlite.connect(DB_PATH) as db:
        schema = SCHEMA_PATH.read_text()
        await db.executescript(schema)

        # Inserisce l'utente di default solo se non esiste già
        async with db.execute("SELECT id FROM users WHERE username = ?", ("Giulia",)) as cursor:
            existing = await cursor.fetchone()

        if not existing:
            hashed = hash_password("sono1peppia")
            await db.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("Giulia", hashed),
            )

        await db.commit()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Dependency FastAPI per ottenere una connessione al DB."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
