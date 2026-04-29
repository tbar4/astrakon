import json
import aiosqlite
from engine.state import Decision, CrisisEvent


class AuditTrail:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn INTEGER, phase TEXT, faction_id TEXT,
                decision_json TEXT, rationale TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn INTEGER, event_id TEXT, event_type TEXT,
                description TEXT, triggered_by TEXT, affected_factions TEXT,
                visibility TEXT, severity REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS advisor_divergence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn INTEGER, phase TEXT, faction_id TEXT,
                recommendation_json TEXT, final_decision_json TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS state_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn INTEGER, phase TEXT, faction_id TEXT,
                snapshot_json TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await self._conn.commit()

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    def _rationale(self, decision: Decision) -> str:
        if decision.investment is not None:
            return decision.investment.rationale
        if decision.response is not None:
            return decision.response.rationale
        if decision.operations is not None:
            return "; ".join(a.rationale for a in decision.operations)
        return ""

    async def write_decision(self, turn: int, decision: Decision):
        await self._conn.execute(
            "INSERT INTO decisions (turn, phase, faction_id, decision_json, rationale) VALUES (?,?,?,?,?)",
            (turn, decision.phase.value, decision.faction_id,
             decision.model_dump_json(), self._rationale(decision))
        )
        await self._conn.commit()

    async def write_event(self, turn: int, event: CrisisEvent):
        await self._conn.execute(
            "INSERT INTO events (turn, event_id, event_type, description, triggered_by, "
            "affected_factions, visibility, severity) VALUES (?,?,?,?,?,?,?,?)",
            (turn, event.event_id, event.event_type, event.description,
             event.triggered_by, json.dumps(event.affected_factions),
             event.visibility, event.severity)
        )
        await self._conn.commit()

    async def write_advisor_divergence(self, turn: int, recommendation: Decision, final: Decision):
        await self._conn.execute(
            "INSERT INTO advisor_divergence (turn, phase, faction_id, recommendation_json, final_decision_json) "
            "VALUES (?,?,?,?,?)",
            (turn, recommendation.phase.value, recommendation.faction_id,
             recommendation.model_dump_json(), final.model_dump_json())
        )
        await self._conn.commit()

    async def write_snapshot(self, turn: int, phase: str, faction_id: str, snapshot_json: str):
        await self._conn.execute(
            "INSERT INTO state_snapshots (turn, phase, faction_id, snapshot_json) VALUES (?,?,?,?)",
            (turn, phase, faction_id, snapshot_json)
        )
        await self._conn.commit()

    async def get_decisions(self, turn: int | None = None) -> list[dict]:
        if turn is not None:
            cursor = await self._conn.execute(
                "SELECT * FROM decisions WHERE turn=?", (turn,)
            )
        else:
            cursor = await self._conn.execute("SELECT * FROM decisions")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_events(self, turn: int | None = None) -> list[dict]:
        if turn is not None:
            cursor = await self._conn.execute(
                "SELECT * FROM events WHERE turn=?", (turn,)
            )
        else:
            cursor = await self._conn.execute("SELECT * FROM events")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_advisor_divergences(self) -> list[dict]:
        cursor = await self._conn.execute("SELECT * FROM advisor_divergence")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_full_game_log(self) -> dict:
        return {
            "decisions": await self.get_decisions(),
            "events": await self.get_events(),
            "divergences": await self.get_advisor_divergences(),
        }
