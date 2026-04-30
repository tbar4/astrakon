# api/session.py
import asyncio
import aiosqlite
from pathlib import Path
from api.models import GameState

_sessions: dict[str, GameState] = {}
_DEFAULT_DB = "output/sessions.db"
_db_initialized = False
# Serialize all writes so concurrent AAR generations never race on the write lock.
_write_lock = asyncio.Lock()


async def initialize_db(db_path: str = _DEFAULT_DB) -> None:
    """Create tables and enable WAL mode. Called once at startup."""
    global _db_initialized
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path, timeout=30) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS aars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                focus TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, focus)
            )
        """)
        await db.commit()
    _db_initialized = True


async def save_aar(session_id: str, focus: str, text: str, db_path: str = _DEFAULT_DB) -> None:
    async with _write_lock:
        async with aiosqlite.connect(db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute(
                "INSERT OR REPLACE INTO aars (session_id, focus, text) VALUES (?, ?, ?)",
                (session_id, focus.strip(), text),
            )
            await db.commit()


async def load_aar(session_id: str, focus: str, db_path: str = _DEFAULT_DB) -> str | None:
    try:
        async with aiosqlite.connect(db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            async with db.execute(
                "SELECT text FROM aars WHERE session_id = ? AND focus = ?",
                (session_id, focus.strip()),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
    except Exception:
        return None


async def list_aars(session_id: str, db_path: str = _DEFAULT_DB) -> list[dict]:
    try:
        async with aiosqlite.connect(db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            async with db.execute(
                "SELECT focus, text, created_at FROM aars WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [{"focus": r[0], "text": r[1], "created_at": r[2]} for r in rows]
    except Exception:
        return []


async def save_session(state: GameState, db_path: str = _DEFAULT_DB) -> None:
    _sessions[state.session_id] = state
    async with _write_lock:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute(
                "INSERT OR REPLACE INTO sessions (session_id, state_json) VALUES (?, ?)",
                (state.session_id, state.model_dump_json()),
            )
            await db.commit()


async def load_session(session_id: str, db_path: str = _DEFAULT_DB) -> GameState | None:
    if session_id in _sessions:
        return _sessions[session_id]
    try:
        async with aiosqlite.connect(db_path, timeout=30) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            async with db.execute(
                "SELECT state_json FROM sessions WHERE session_id = ?", (session_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    state = GameState.model_validate_json(row[0])
                    _sessions[session_id] = state
                    return state
    except Exception:
        pass
    return None


async def clear_session(session_id: str, db_path: str = _DEFAULT_DB) -> None:
    _sessions.pop(session_id, None)
    try:
        async with _write_lock:
            async with aiosqlite.connect(db_path, timeout=30) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                await db.commit()
    except Exception:
        pass
