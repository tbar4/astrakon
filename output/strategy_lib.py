import sqlite3
from pathlib import Path
from engine.referee import GameResult
from scenarios.loader import Scenario


class StrategyLibrary:
    def __init__(self, db_path: str = "output/strategy_library.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_name TEXT,
                    faction_id TEXT,
                    archetype TEXT,
                    outcome TEXT,
                    turns_completed INTEGER,
                    final_dominance REAL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def record_run(self, scenario: Scenario, result: GameResult):
        with sqlite3.connect(self.db_path) as conn:
            for faction_id, outcome in result.faction_outcomes.items():
                faction = next((f for f in scenario.factions if f.faction_id == faction_id), None)
                archetype = faction.archetype if faction else "unknown"
                dominance = result.final_dominance.get(faction_id, 0.0)
                conn.execute(
                    "INSERT INTO runs (scenario_name, faction_id, archetype, outcome, "
                    "turns_completed, final_dominance) VALUES (?,?,?,?,?,?)",
                    (scenario.name, faction_id, archetype, outcome,
                     result.turns_completed, dominance)
                )

    def win_rates(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT archetype,
                       COUNT(*) as total_runs,
                       SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) as wins,
                       ROUND(AVG(CASE WHEN outcome='won' THEN 1.0 ELSE 0.0 END), 3) as win_rate,
                       ROUND(AVG(final_dominance), 3) as avg_dominance
                FROM runs
                GROUP BY archetype
                ORDER BY win_rate DESC
            """)
            return [dict(r) for r in cursor.fetchall()]
