# api/session.py
import aiosqlite
from pathlib import Path
from api.models import GameState

_sessions: dict[str, GameState] = {}
_DEFAULT_DB = "output/sessions.db"


async def _ensure_table(db: aiosqlite.Connection) -> None:
    await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            state_json TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await db.commit()


async def save_session(state: GameState, db_path: str = _DEFAULT_DB) -> None:
    _sessions[state.session_id] = state
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await _ensure_table(db)
        await db.execute(
            "INSERT OR REPLACE INTO sessions (session_id, state_json) VALUES (?, ?)",
            (state.session_id, state.model_dump_json()),
        )
        await db.commit()


async def load_session(session_id: str, db_path: str = _DEFAULT_DB) -> GameState | None:
    if session_id in _sessions:
        return _sessions[session_id]
    try:
        async with aiosqlite.connect(db_path) as db:
            await _ensure_table(db)
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
        async with aiosqlite.connect(db_path) as db:
            await _ensure_table(db)
            await db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            await db.commit()
    except Exception:
        pass
