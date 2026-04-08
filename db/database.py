from pathlib import Path
from typing import AsyncGenerator

import aiosqlite

DB_PATH = Path(__file__).parent / "health_cache.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_db() -> None:
    """Inizializza il database SQLite con lo schema."""
    async with aiosqlite.connect(DB_PATH) as db:
        schema = SCHEMA_PATH.read_text()
        await db.executescript(schema)
        await db.commit()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Dependency FastAPI per ottenere una connessione al DB."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db
