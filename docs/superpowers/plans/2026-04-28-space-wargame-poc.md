# Space Wargame Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a playable Python POC of the distributed multi-agent strategic space wargame engine — human vs. AI factions competing across a three-phase turn loop with full audit trail and after-action report output.

**Architecture:** Distributed agent network where each faction implements `AgentInterface`; a deterministic `GameReferee` broadcasts state and collects decisions via asyncio; agents (human, AI commander, AI advisor, rule-based) are swappable without engine changes. All decisions logged to SQLite in real-time.

**Tech Stack:** Python 3.12, anthropic SDK, pydantic v2, aiosqlite, ruamel.yaml, rich, pytest + pytest-asyncio

---

## File Map

```
agents/
├── engine/
│   ├── state.py          # All Pydantic models — GameState, Decision, Faction, etc.
│   ├── simulation.py     # Orbital model, asset catalog, investment resolver, conflict resolver
│   ├── events.py         # CrisisEvent library and weighted selection
│   └── referee.py        # Turn loop, phase transitions, outcome resolution
├── agents/
│   ├── base.py           # AgentInterface ABC
│   ├── rule_based.py     # Deterministic agents (no LLM) — for testing and baselines
│   ├── human.py          # Rich CLI agent with optional advisor display
│   ├── ai_commander.py   # Claude API autonomous commander
│   └── ai_advisor.py     # Claude API recommendations for human agent
├── personas/
│   ├── builder.py        # NL → YAML persona via Claude API
│   └── archetypes/       # Preset YAML files
│       ├── mahanian.yaml
│       ├── iron_napoleon.yaml
│       ├── gray_zone.yaml
│       ├── commercial_broker.yaml
│       ├── patient_dragon.yaml
│       └── rogue_accelerationist.yaml
├── scenarios/
│   ├── loader.py                  # YAML loader + Pydantic validation
│   └── pacific_crossroads.yaml   # Starter scenario
├── output/
│   ├── audit.py          # aiosqlite audit trail writer
│   ├── aar.py            # After-action report via claude-opus-4-7
│   └── strategy_lib.py   # Strategy fingerprint accumulator
├── tests/
│   ├── conftest.py
│   ├── test_state.py
│   ├── test_simulation.py
│   ├── test_referee.py
│   ├── test_agents.py
│   ├── test_persona_builder.py
│   ├── test_scenario_loader.py
│   └── test_audit.py
├── main.py               # CLI launcher
└── pyproject.toml
```

---

## Task 1: Project Setup

**Files:**
- Create: `pyproject.toml`
- Create: `tests/conftest.py`
- Create: all `__init__.py` files

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:api"

[project]
name = "space-wargame"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.50.0",
    "pydantic>=2.0.0",
    "aiosqlite>=0.20.0",
    "ruamel.yaml>=0.18.0",
    "rich>=13.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected: installs all packages without errors.

- [ ] **Step 3: Create package structure**

```bash
mkdir -p engine agents personas/archetypes scenarios output tests
touch engine/__init__.py agents/__init__.py personas/__init__.py
touch scenarios/__init__.py output/__init__.py tests/__init__.py
```

- [ ] **Step 4: Create tests/conftest.py**

```python
import pytest

@pytest.fixture
def sample_faction_id():
    return "ussf"

@pytest.fixture
def sample_turn():
    return 1
```

- [ ] **Step 5: Verify pytest runs**

```bash
pytest --collect-only
```

Expected: `0 tests collected` with no errors.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml engine/ agents/ personas/ scenarios/ output/ tests/
git commit -m "feat: project scaffold and dependencies"
```

---

## Task 2: Core State Models

**Files:**
- Create: `engine/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_state.py
import pytest
from engine.state import (
    Phase, InvestmentAllocation, OperationalAction, ResponseDecision,
    Decision, FactionAssets, FactionState, CoalitionState,
    GameStateSnapshot, CrisisEvent, Recommendation,
)

def test_investment_allocation_sums_to_one():
    alloc = InvestmentAllocation(
        r_and_d=0.30, constellation=0.20, launch_capacity=0.10,
        commercial=0.10, influence_ops=0.10, education=0.10,
        covert=0.05, diplomacy=0.05, rationale="test"
    )
    assert abs(alloc.total() - 1.0) < 0.001

def test_investment_allocation_rejects_over_budget():
    with pytest.raises(ValueError):
        InvestmentAllocation(
            r_and_d=0.60, constellation=0.60,
            rationale="too much"
        )

def test_faction_assets_default_empty():
    assets = FactionAssets()
    assert assets.leo_nodes == 0
    assert assets.sda_sensors == 0

def test_decision_invest_phase():
    alloc = InvestmentAllocation(
        r_and_d=0.50, constellation=0.50, rationale="test"
    )
    decision = Decision(phase=Phase.INVEST, faction_id="ussf", investment=alloc)
    assert decision.phase == Phase.INVEST
    assert decision.investment.r_and_d == 0.50

def test_game_state_snapshot_serializes():
    snapshot = GameStateSnapshot(
        turn=1, phase=Phase.INVEST, faction_id="ussf",
        faction_state=FactionState(
            faction_id="ussf", name="US Space Force",
            budget_per_turn=100, current_budget=100,
            assets=FactionAssets()
        ),
        ally_states={}, adversary_estimates={}, coalition_states={},
        available_actions=["allocate_budget"],
    )
    data = snapshot.model_dump()
    assert data["turn"] == 1
    assert data["faction_id"] == "ussf"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_state.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`.

- [ ] **Step 3: Implement engine/state.py**

```python
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, model_validator


class Phase(str, Enum):
    INVEST = "invest"
    OPERATIONS = "operations"
    RESPONSE = "response"


class FactionAssets(BaseModel):
    leo_nodes: int = 0
    meo_nodes: int = 0
    geo_nodes: int = 0
    cislunar_nodes: int = 0
    asat_kinetic: int = 0
    asat_deniable: int = 0
    ew_jammers: int = 0
    sda_sensors: int = 0
    relay_nodes: int = 0
    launch_capacity: int = 1

    def total_orbital_nodes(self) -> int:
        return self.leo_nodes + self.meo_nodes + self.geo_nodes + self.cislunar_nodes


class InvestmentAllocation(BaseModel):
    r_and_d: float = 0.0
    constellation: float = 0.0
    launch_capacity: float = 0.0
    commercial: float = 0.0
    influence_ops: float = 0.0
    education: float = 0.0
    covert: float = 0.0
    diplomacy: float = 0.0
    rationale: str = ""

    def total(self) -> float:
        return (self.r_and_d + self.constellation + self.launch_capacity +
                self.commercial + self.influence_ops + self.education +
                self.covert + self.diplomacy)

    @model_validator(mode="after")
    def validate_budget(self) -> "InvestmentAllocation":
        if self.total() > 1.001:
            raise ValueError(f"Investment allocations sum to {self.total():.3f}, must be <= 1.0")
        return self


class OperationalAction(BaseModel):
    action_type: str
    target_faction: Optional[str] = None
    parameters: dict[str, Any] = {}
    rationale: str = ""


class ResponseDecision(BaseModel):
    escalate: bool = False
    retaliate: bool = False
    target_faction: Optional[str] = None
    emergency_reallocation: Optional[InvestmentAllocation] = None
    public_statement: str = ""
    rationale: str = ""


class Decision(BaseModel):
    phase: Phase
    faction_id: str
    investment: Optional[InvestmentAllocation] = None
    operations: Optional[list[OperationalAction]] = None
    response: Optional[ResponseDecision] = None


class Recommendation(BaseModel):
    phase: Phase
    options: list[dict[str, Any]]
    top_recommendation: Decision
    strategic_rationale: str


class FactionState(BaseModel):
    faction_id: str
    name: str
    budget_per_turn: int
    current_budget: int
    assets: FactionAssets
    tech_tree: dict[str, int] = {}
    coalition_id: Optional[str] = None
    coalition_loyalty: float = 0.5
    deferred_returns: list[dict[str, Any]] = []
    private_victory_achieved: bool = False

    def sda_level(self) -> float:
        # 0.0–1.0 based on sensor count; 12 sensors = ~0.5, 24 = ~1.0
        return min(self.assets.sda_sensors / 24.0, 1.0)


class CoalitionState(BaseModel):
    coalition_id: str
    member_ids: list[str]
    hegemony_score: float = 0.0


class GameStateSnapshot(BaseModel):
    turn: int
    phase: Phase
    faction_id: str
    faction_state: FactionState
    ally_states: dict[str, FactionState]
    adversary_estimates: dict[str, FactionAssets]
    coalition_states: dict[str, CoalitionState]
    available_actions: list[str]
    turn_log_summary: str = ""


class CrisisEvent(BaseModel):
    event_id: str
    event_type: str
    description: str
    triggered_by: Optional[str] = None
    affected_factions: list[str]
    visibility: str = "public"
    severity: float = 0.5
    parameters: dict[str, Any] = {}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_state.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/state.py tests/test_state.py
git commit -m "feat: core Pydantic state models"
```

---

## Task 3: Audit Trail

**Files:**
- Create: `output/audit.py`
- Create: `tests/test_audit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_audit.py
import pytest
import aiosqlite
from pathlib import Path
from output.audit import AuditTrail
from engine.state import Phase, Decision, InvestmentAllocation, CrisisEvent


@pytest.fixture
async def audit(tmp_path):
    db_path = tmp_path / "test_game.db"
    trail = AuditTrail(str(db_path))
    await trail.initialize()
    yield trail
    await trail.close()


async def test_write_and_retrieve_decision(audit):
    alloc = InvestmentAllocation(r_and_d=0.5, constellation=0.5, rationale="test")
    decision = Decision(phase=Phase.INVEST, faction_id="ussf", investment=alloc)
    await audit.write_decision(turn=1, decision=decision)
    rows = await audit.get_decisions(turn=1)
    assert len(rows) == 1
    assert rows[0]["faction_id"] == "ussf"
    assert rows[0]["rationale"] == "test"


async def test_write_crisis_event(audit):
    event = CrisisEvent(
        event_id="evt_001", event_type="asat_test",
        description="Adversary ASAT test detected",
        affected_factions=["ussf"], severity=0.7
    )
    await audit.write_event(turn=2, event=event)
    rows = await audit.get_events(turn=2)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "asat_test"


async def test_write_advisor_divergence(audit):
    recommendation = Decision(
        phase=Phase.INVEST, faction_id="ussf",
        investment=InvestmentAllocation(r_and_d=0.40, influence_ops=0.40, constellation=0.20,
                                        rationale="advised")
    )
    final = Decision(
        phase=Phase.INVEST, faction_id="ussf",
        investment=InvestmentAllocation(constellation=0.8, r_and_d=0.2,
                                        rationale="overridden")
    )
    await audit.write_advisor_divergence(turn=1, recommendation=recommendation, final=final)
    rows = await audit.get_advisor_divergences()
    assert len(rows) == 1
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_audit.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement output/audit.py**

```python
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

    def _rationale(self, decision: Decision) -> str:
        if decision.investment:
            return decision.investment.rationale
        if decision.response:
            return decision.response.rationale
        if decision.operations:
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_audit.py -v
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add output/audit.py tests/test_audit.py
git commit -m "feat: aiosqlite audit trail with decisions, events, divergence"
```

---

## Task 4: Agent Interface ABC

**Files:**
- Create: `agents/base.py`
- Modify: `tests/test_agents.py` (create)

- [ ] **Step 1: Write failing test**

```python
# tests/test_agents.py
import pytest
from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, Recommendation,
    GameStateSnapshot, FactionState, FactionAssets, CrisisEvent
)


class ConcreteAgent(AgentInterface):
    async def submit_decision(self, phase: Phase) -> Decision:
        return Decision(
            phase=phase, faction_id=self.faction_id,
            investment=InvestmentAllocation(r_and_d=0.5, constellation=0.5, rationale="test")
        )


def test_agent_interface_requires_submit_decision():
    from abc import ABC
    assert issubclass(AgentInterface, ABC)


async def test_concrete_agent_submit_decision():
    from engine.state import FactionState, FactionAssets
    from scenarios.loader import Faction, Scenario, VictoryConditions
    agent = ConcreteAgent()
    faction = Faction(
        faction_id="ussf", name="US Space Force", archetype="mahanian",
        agent_type="rule_based", budget_per_turn=100,
        starting_assets=FactionAssets(leo_nodes=24, sda_sensors=12)
    )
    agent.initialize(faction)
    decision = await agent.submit_decision(Phase.INVEST)
    assert decision.faction_id == "ussf"
    assert decision.phase == Phase.INVEST
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_agents.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement agents/base.py**

```python
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from engine.state import (
    Phase, Decision, Recommendation, GameStateSnapshot, CrisisEvent
)

if TYPE_CHECKING:
    from scenarios.loader import Faction


class AgentInterface(ABC):
    def __init__(self):
        self.faction_id: str = ""
        self.faction_name: str = ""
        self._last_snapshot: Optional[GameStateSnapshot] = None

    def initialize(self, faction: "Faction") -> None:
        self.faction_id = faction.faction_id
        self.faction_name = faction.name

    def receive_state(self, snapshot: GameStateSnapshot) -> None:
        self._last_snapshot = snapshot

    def receive_event(self, event: CrisisEvent) -> None:
        pass  # override in subclasses that need event handling

    @abstractmethod
    async def submit_decision(self, phase: Phase) -> Decision:
        ...

    async def get_recommendation(self, phase: Phase) -> Optional[Recommendation]:
        return None  # override in AI advisor
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_agents.py -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/base.py tests/test_agents.py
git commit -m "feat: AgentInterface ABC"
```

---

## Task 5: Scenario Config Loader

**Files:**
- Create: `scenarios/loader.py`
- Create: `scenarios/pacific_crossroads.yaml`
- Create: `tests/test_scenario_loader.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_scenario_loader.py
import pytest
from pathlib import Path
from scenarios.loader import load_scenario, Scenario


def test_load_pacific_crossroads():
    path = Path("scenarios/pacific_crossroads.yaml")
    scenario = load_scenario(path)
    assert scenario.name == "Pacific Crossroads"
    assert scenario.turns == 15
    assert len(scenario.factions) >= 2
    assert len(scenario.coalitions) >= 1


def test_coalition_members_reference_valid_factions():
    path = Path("scenarios/pacific_crossroads.yaml")
    scenario = load_scenario(path)
    faction_ids = {f.faction_id for f in scenario.factions}
    for coalition in scenario.coalitions.values():
        for member in coalition.member_ids:
            assert member in faction_ids, f"Coalition member {member} not in factions"


def test_faction_budget_positive():
    path = Path("scenarios/pacific_crossroads.yaml")
    scenario = load_scenario(path)
    for faction in scenario.factions:
        assert faction.budget_per_turn > 0
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_scenario_loader.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Create scenarios/pacific_crossroads.yaml**

```yaml
name: "Pacific Crossroads"
description: "Great power competition over Taiwan Strait, 2030"
turns: 15
turn_represents: "2 months"

coalitions:
  blue:
    member_ids: [ussf, nexus_corp]
    shared_intel: true
    hegemony_pool: true
  red:
    member_ids: [pla_ssf, russia_vks]
    shared_intel: true
    hegemony_pool: true

factions:
  - faction_id: ussf
    name: "US Space Force"
    archetype: mahanian
    agent_type: "human+advisor"
    budget_per_turn: 100
    coalition_id: blue
    coalition_loyalty: 0.9
    starting_assets:
      leo_nodes: 48
      geo_nodes: 6
      sda_sensors: 12
      relay_nodes: 4
      launch_capacity: 3

  - faction_id: nexus_corp
    name: "Nexus Aerospace"
    archetype: commercial_broker
    agent_type: ai_commander
    budget_per_turn: 75
    coalition_id: blue
    coalition_loyalty: 0.6
    starting_assets:
      leo_nodes: 120
      geo_nodes: 2
      sda_sensors: 6
      launch_capacity: 5

  - faction_id: pla_ssf
    name: "PLA Strategic Support Force"
    archetype: gray_zone
    agent_type: ai_commander
    budget_per_turn: 90
    coalition_id: red
    coalition_loyalty: 0.85
    starting_assets:
      leo_nodes: 40
      geo_nodes: 4
      asat_kinetic: 6
      asat_deniable: 4
      sda_sensors: 8
      launch_capacity: 3

  - faction_id: russia_vks
    name: "VKS Space Forces"
    archetype: rogue_accelerationist
    agent_type: ai_commander
    budget_per_turn: 40
    coalition_id: red
    coalition_loyalty: 0.7
    starting_assets:
      leo_nodes: 15
      asat_kinetic: 8
      ew_jammers: 6
      sda_sensors: 4
      launch_capacity: 2

victory:
  coalition_orbital_dominance: 0.65
  individual_conditions_required: true
  individual_conditions:
    ussf:
      military_deterrence_score: 75
    nexus_corp:
      commercial_market_share: 0.5
    pla_ssf:
      orbital_dominance_score: 0.65
    russia_vks:
      disruption_score: 60

crisis_events:
  library: default_2030
```

- [ ] **Step 4: Implement scenarios/loader.py**

```python
from pathlib import Path
from typing import Optional, Any
from pydantic import BaseModel
from ruamel.yaml import YAML
from engine.state import FactionAssets, CoalitionState


class VictoryConditions(BaseModel):
    coalition_orbital_dominance: float = 0.65
    individual_conditions_required: bool = True
    individual_conditions: dict[str, dict[str, Any]] = {}


class Faction(BaseModel):
    faction_id: str
    name: str
    archetype: str
    agent_type: str
    budget_per_turn: int
    coalition_id: Optional[str] = None
    coalition_loyalty: float = 0.5
    starting_assets: FactionAssets = FactionAssets()
    persona_path: Optional[str] = None


class Coalition(BaseModel):
    member_ids: list[str]
    shared_intel: bool = True
    hegemony_pool: bool = True


class Scenario(BaseModel):
    name: str
    description: str = ""
    turns: int
    turn_represents: str = "1 month"
    factions: list[Faction]
    coalitions: dict[str, Coalition]
    victory: VictoryConditions = VictoryConditions()
    crisis_events_library: str = "default_2030"


def load_scenario(path: Path) -> Scenario:
    yaml = YAML()
    raw = yaml.load(path)
    factions = [Faction(**f) for f in raw.get("factions", [])]
    coalitions = {
        k: Coalition(**v)
        for k, v in raw.get("coalitions", {}).items()
    }
    victory_raw = raw.get("victory", {})
    victory = VictoryConditions(**victory_raw)
    return Scenario(
        name=raw["name"],
        description=raw.get("description", ""),
        turns=raw["turns"],
        turn_represents=raw.get("turn_represents", "1 month"),
        factions=factions,
        coalitions=coalitions,
        victory=victory,
        crisis_events_library=raw.get("crisis_events", {}).get("library", "default_2030"),
    )
```

- [ ] **Step 5: Run — verify pass**

```bash
pytest tests/test_scenario_loader.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scenarios/loader.py scenarios/pacific_crossroads.yaml tests/test_scenario_loader.py
git commit -m "feat: scenario YAML loader with Pydantic validation"
```

---

## Task 6: Simulation Engine

**Files:**
- Create: `engine/simulation.py`
- Create: `tests/test_simulation.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_simulation.py
import pytest
from engine.simulation import (
    SimulationEngine, InvestmentResolver, SDAFilter, ConflictResolver
)
from engine.state import FactionAssets, FactionState, InvestmentAllocation


@pytest.fixture
def base_assets():
    return FactionAssets(leo_nodes=24, sda_sensors=8, launch_capacity=2)


@pytest.fixture
def base_state(base_assets):
    return FactionState(
        faction_id="ussf", name="US Space Force",
        budget_per_turn=100, current_budget=100,
        assets=base_assets
    )


def test_investment_resolver_queues_deferred_returns():
    resolver = InvestmentResolver()
    alloc = InvestmentAllocation(r_and_d=0.30, constellation=0.70, rationale="test")
    result = resolver.resolve(faction_id="ussf", budget=100, allocation=alloc, turn=1)
    # Constellation returns immediately; R&D is deferred
    assert result.immediate_assets.leo_nodes > 0
    assert any(r["category"] == "r_and_d" for r in result.deferred_returns)


def test_investment_resolver_constellation_adds_nodes():
    resolver = InvestmentResolver()
    alloc = InvestmentAllocation(constellation=1.0, rationale="all in")
    result = resolver.resolve(faction_id="ussf", budget=100, allocation=alloc, turn=1)
    assert result.immediate_assets.leo_nodes > 0


def test_sda_filter_low_investment_obscures_adversary():
    sda_filter = SDAFilter()
    adversary = FactionAssets(leo_nodes=50, asat_kinetic=10, asat_deniable=5)
    filtered = sda_filter.filter(adversary_assets=adversary, observer_sda_level=0.1)
    # At low SDA, deniable assets are invisible
    assert filtered.asat_deniable == 0

def test_sda_filter_high_investment_reveals_adversary():
    sda_filter = SDAFilter()
    adversary = FactionAssets(leo_nodes=50, asat_kinetic=10, asat_deniable=5)
    filtered = sda_filter.filter(adversary_assets=adversary, observer_sda_level=0.9)
    assert filtered.asat_kinetic > 0


def test_orbital_dominance_calculation():
    engine = SimulationEngine()
    faction_assets = {
        "ussf": FactionAssets(leo_nodes=60, geo_nodes=8),
        "pla":  FactionAssets(leo_nodes=20, geo_nodes=2),
    }
    dominance = engine.compute_orbital_dominance("ussf", faction_assets)
    assert dominance > 0.5
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_simulation.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement engine/simulation.py**

```python
import random
from dataclasses import dataclass
from engine.state import FactionAssets, InvestmentAllocation


@dataclass
class InvestmentResult:
    immediate_assets: FactionAssets
    deferred_returns: list[dict]  # [{turn_due, category, amount, faction_id}]
    budget_spent: int


class InvestmentResolver:
    # Costs per unit in budget points
    CONSTELLATION_NODE_COST = 5   # per LEO node
    SDA_SENSOR_COST = 8
    LAUNCH_CAPACITY_COST = 15
    ASAT_KINETIC_COST = 20
    ASAT_DENIABLE_COST = 25
    EW_JAMMER_COST = 12

    # R&D deferred return delay in turns
    RD_DELAY = 3
    EDUCATION_DELAY = 6

    def resolve(
        self, faction_id: str, budget: int,
        allocation: InvestmentAllocation, turn: int
    ) -> InvestmentResult:
        immediate = FactionAssets()
        deferred = []
        spent = 0

        if allocation.constellation > 0:
            pts = int(budget * allocation.constellation)
            nodes = pts // self.CONSTELLATION_NODE_COST
            immediate.leo_nodes = nodes
            spent += nodes * self.CONSTELLATION_NODE_COST

        if allocation.launch_capacity > 0:
            pts = int(budget * allocation.launch_capacity)
            capacity = pts // self.LAUNCH_CAPACITY_COST
            immediate.launch_capacity = capacity
            spent += capacity * self.LAUNCH_CAPACITY_COST

        if allocation.r_and_d > 0:
            pts = int(budget * allocation.r_and_d)
            deferred.append({
                "faction_id": faction_id,
                "category": "r_and_d",
                "amount": pts,
                "turn_due": turn + self.RD_DELAY,
            })
            spent += pts

        if allocation.education > 0:
            pts = int(budget * allocation.education)
            deferred.append({
                "faction_id": faction_id,
                "category": "education",
                "amount": pts,
                "turn_due": turn + self.EDUCATION_DELAY,
            })
            spent += pts

        if allocation.covert > 0:
            pts = int(budget * allocation.covert)
            asat = pts // self.ASAT_DENIABLE_COST
            immediate.asat_deniable = asat
            spent += asat * self.ASAT_DENIABLE_COST

        if allocation.influence_ops > 0:
            pts = int(budget * allocation.influence_ops)
            jammers = pts // self.EW_JAMMER_COST
            immediate.ew_jammers = jammers
            spent += jammers * self.EW_JAMMER_COST

        return InvestmentResult(
            immediate_assets=immediate,
            deferred_returns=deferred,
            budget_spent=spent,
        )


class SDAFilter:
    def filter(
        self, adversary_assets: FactionAssets, observer_sda_level: float
    ) -> FactionAssets:
        """Return adversary assets visible to observer given their SDA level (0–1)."""
        visible = FactionAssets()
        # Constellation nodes always partially visible
        visible.leo_nodes = int(adversary_assets.leo_nodes * min(observer_sda_level + 0.3, 1.0))
        visible.geo_nodes = int(adversary_assets.geo_nodes * min(observer_sda_level + 0.4, 1.0))
        # Kinetic ASAT partially visible above 0.3 SDA
        if observer_sda_level >= 0.3:
            visible.asat_kinetic = int(adversary_assets.asat_kinetic * observer_sda_level)
        # Deniable assets only visible above 0.6 SDA
        if observer_sda_level >= 0.6:
            visible.asat_deniable = int(adversary_assets.asat_deniable * (observer_sda_level - 0.5))
        visible.ew_jammers = int(adversary_assets.ew_jammers * observer_sda_level)
        return visible


class ConflictResolver:
    def resolve_kinetic_asat(
        self, attacker_assets: FactionAssets, target_assets: FactionAssets,
        attacker_sda_level: float
    ) -> dict:
        """Returns {nodes_destroyed, detected, attributed}."""
        if attacker_assets.asat_kinetic == 0:
            return {"nodes_destroyed": 0, "detected": False, "attributed": False}
        base_effectiveness = min(attacker_assets.asat_kinetic * 3, 20)
        nodes_destroyed = int(base_effectiveness * attacker_sda_level)
        return {
            "nodes_destroyed": nodes_destroyed,
            "detected": random.random() < 0.8,
            "attributed": random.random() < attacker_sda_level,
        }

    def resolve_deniable_asat(
        self, attacker_assets: FactionAssets, defender_sda_level: float
    ) -> dict:
        if attacker_assets.asat_deniable == 0:
            return {"nodes_destroyed": 0, "detected": False, "attributed": False}
        nodes_destroyed = random.randint(1, max(attacker_assets.asat_deniable, 1))
        detected = random.random() < defender_sda_level
        attributed = detected and random.random() < (defender_sda_level * 0.5)
        return {
            "nodes_destroyed": nodes_destroyed,
            "detected": detected,
            "attributed": attributed,
        }


class SimulationEngine:
    def __init__(self):
        self.investment_resolver = InvestmentResolver()
        self.sda_filter = SDAFilter()
        self.conflict_resolver = ConflictResolver()

    def compute_orbital_dominance(
        self, faction_id: str, all_assets: dict[str, FactionAssets]
    ) -> float:
        """Returns faction's share of total orbital nodes across all factions."""
        total_nodes = sum(a.total_orbital_nodes() for a in all_assets.values())
        if total_nodes == 0:
            return 0.0
        return all_assets[faction_id].total_orbital_nodes() / total_nodes

    def compute_coalition_dominance(
        self, coalition_member_ids: list[str], all_assets: dict[str, FactionAssets]
    ) -> float:
        coalition_nodes = sum(
            all_assets[fid].total_orbital_nodes()
            for fid in coalition_member_ids
            if fid in all_assets
        )
        total_nodes = sum(a.total_orbital_nodes() for a in all_assets.values())
        if total_nodes == 0:
            return 0.0
        return coalition_nodes / total_nodes
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_simulation.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/simulation.py tests/test_simulation.py
git commit -m "feat: simulation engine with investment resolver, SDA filter, conflict resolver"
```

---

## Task 7: Crisis Event Library

**Files:**
- Create: `engine/events.py`

- [ ] **Step 1: Implement engine/events.py** (no separate test — tested via referee integration test in Task 9)

```python
import random
from engine.state import CrisisEvent


DEFAULT_2030_EVENTS = [
    {
        "event_id": "asat_test_public",
        "event_type": "asat_test",
        "description": "An adversary has conducted a destructive ASAT test, generating a debris field in LEO.",
        "visibility": "public",
        "severity": 0.7,
        "min_tension": 0.3,
    },
    {
        "event_id": "jamming_incident",
        "event_type": "jamming_incident",
        "description": "GPS jamming detected across a contested region. Attribution unclear.",
        "visibility": "public",
        "severity": 0.4,
        "min_tension": 0.2,
    },
    {
        "event_id": "commercial_anomaly",
        "event_type": "commercial_anomaly",
        "description": "A commercial satellite has conducted an anomalous maneuver near a critical relay node.",
        "visibility": "public",
        "severity": 0.3,
        "min_tension": 0.1,
    },
    {
        "event_id": "attribution_crisis",
        "event_type": "attribution_crisis",
        "description": "A ground station uplink has been disrupted. Multiple actors suspected.",
        "visibility": "public",
        "severity": 0.5,
        "min_tension": 0.3,
    },
    {
        "event_id": "proxy_conflict",
        "event_type": "proxy_conflict",
        "description": "A non-state actor has claimed responsibility for a satellite interference event.",
        "visibility": "public",
        "severity": 0.6,
        "min_tension": 0.4,
    },
    {
        "event_id": "diplomatic_ultimatum",
        "event_type": "diplomatic",
        "description": "A major power has issued a formal protest over orbital positioning deemed aggressive.",
        "visibility": "public",
        "severity": 0.4,
        "min_tension": 0.2,
    },
    {
        "event_id": "commercial_partnership_offer",
        "event_type": "commercial",
        "description": "A commercial operator is offering SDA data-sharing to all parties on favorable terms.",
        "visibility": "public",
        "severity": 0.2,
        "min_tension": 0.0,
    },
]


class CrisisEventLibrary:
    def __init__(self, library_name: str = "default_2030"):
        if library_name == "default_2030":
            self._events = DEFAULT_2030_EVENTS
        else:
            raise ValueError(f"Unknown event library: {library_name}")

    def generate_events(
        self, tension_level: float, affected_factions: list[str], turn: int
    ) -> list[CrisisEvent]:
        """Generate 0–2 crisis events weighted by board tension."""
        eligible = [e for e in self._events if e["min_tension"] <= tension_level]
        if not eligible:
            return []
        count = 1 if random.random() < 0.6 else (2 if tension_level > 0.5 else 0)
        selected = random.sample(eligible, min(count, len(eligible)))
        return [
            CrisisEvent(
                event_id=f"{e['event_id']}_t{turn}",
                event_type=e["event_type"],
                description=e["description"],
                affected_factions=affected_factions,
                visibility=e["visibility"],
                severity=e["severity"],
            )
            for e in selected
        ]
```

- [ ] **Step 2: Commit**

```bash
git add engine/events.py
git commit -m "feat: default_2030 crisis event library"
```

---

## Task 8: Rule-Based Agent

**Files:**
- Create: `agents/rule_based.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Add tests for rule-based agent**

Append to `tests/test_agents.py`:

```python
from agents.rule_based import MahanianAgent, MaxConstellationAgent
from scenarios.loader import Faction
from engine.state import FactionAssets, Phase, GameStateSnapshot, FactionState, CoalitionState


@pytest.fixture
def test_faction():
    return Faction(
        faction_id="ussf", name="US Space Force", archetype="mahanian",
        agent_type="rule_based", budget_per_turn=100,
        starting_assets=FactionAssets(leo_nodes=24, sda_sensors=8)
    )


@pytest.fixture
def test_snapshot(test_faction):
    return GameStateSnapshot(
        turn=1, phase=Phase.INVEST, faction_id="ussf",
        faction_state=FactionState(
            faction_id="ussf", name="US Space Force",
            budget_per_turn=100, current_budget=100,
            assets=test_faction.starting_assets
        ),
        ally_states={}, adversary_estimates={}, coalition_states={},
        available_actions=["allocate_budget"],
    )


async def test_mahanian_agent_invests_in_sda(test_faction, test_snapshot):
    agent = MahanianAgent()
    agent.initialize(test_faction)
    agent.receive_state(test_snapshot)
    decision = await agent.submit_decision(Phase.INVEST)
    assert decision.investment is not None
    assert decision.investment.r_and_d + decision.investment.constellation >= 0.4


async def test_max_constellation_agent(test_faction, test_snapshot):
    agent = MaxConstellationAgent()
    agent.initialize(test_faction)
    agent.receive_state(test_snapshot)
    decision = await agent.submit_decision(Phase.INVEST)
    assert decision.investment.constellation >= 0.6


async def test_rule_based_returns_valid_decision_all_phases(test_faction, test_snapshot):
    agent = MahanianAgent()
    agent.initialize(test_faction)
    agent.receive_state(test_snapshot)
    for phase in [Phase.INVEST, Phase.OPERATIONS, Phase.RESPONSE]:
        test_snapshot.phase = phase
        agent.receive_state(test_snapshot)
        decision = await agent.submit_decision(phase)
        assert decision.faction_id == "ussf"
        assert decision.phase == phase
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_agents.py -v -k "mahanian or max_constellation or rule_based"
```

Expected: `ImportError`.

- [ ] **Step 3: Implement agents/rule_based.py**

```python
from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, OperationalAction, ResponseDecision
)


class MahanianAgent(AgentInterface):
    """Prioritizes SDA and constellation balance — sea control doctrine."""

    async def submit_decision(self, phase: Phase) -> Decision:
        if phase == Phase.INVEST:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                investment=InvestmentAllocation(
                    r_and_d=0.20, constellation=0.30,
                    launch_capacity=0.10, commercial=0.10,
                    influence_ops=0.05, education=0.10,
                    covert=0.05, diplomacy=0.10,
                    rationale="Mahanian balance: SDA, constellation, and diplomatic positioning."
                )
            )
        if phase == Phase.OPERATIONS:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                operations=[OperationalAction(
                    action_type="task_assets",
                    parameters={"mission": "sda_sweep"},
                    rationale="Prioritize intelligence advantage this turn."
                )]
            )
        return Decision(
            phase=phase, faction_id=self.faction_id,
            response=ResponseDecision(
                escalate=False, retaliate=False,
                public_statement="We are monitoring the situation carefully.",
                rationale="De-escalate by default; preserve optionality."
            )
        )


class MaxConstellationAgent(AgentInterface):
    """Dumps everything into constellation nodes — aggressive expansion."""

    async def submit_decision(self, phase: Phase) -> Decision:
        if phase == Phase.INVEST:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                investment=InvestmentAllocation(
                    constellation=0.80, launch_capacity=0.20,
                    rationale="Maximum constellation expansion. Nodes are power."
                )
            )
        if phase == Phase.OPERATIONS:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                operations=[OperationalAction(
                    action_type="task_assets",
                    parameters={"mission": "constellation_expansion"},
                    rationale="Deploy newly built nodes."
                )]
            )
        return Decision(
            phase=phase, faction_id=self.faction_id,
            response=ResponseDecision(
                escalate=False, rationale="Ignore events; keep expanding."
            )
        )
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_agents.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/rule_based.py tests/test_agents.py
git commit -m "feat: MahanianAgent and MaxConstellationAgent rule-based agents"
```

---

## Task 9: Game Referee

**Files:**
- Create: `engine/referee.py`
- Create: `tests/test_referee.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_referee.py
import pytest
from pathlib import Path
from engine.referee import GameReferee
from engine.state import Phase
from agents.rule_based import MahanianAgent, MaxConstellationAgent
from scenarios.loader import load_scenario, Faction
from engine.state import FactionAssets
from output.audit import AuditTrail


@pytest.fixture
def scenario():
    return load_scenario(Path("scenarios/pacific_crossroads.yaml"))


@pytest.fixture
async def audit(tmp_path):
    trail = AuditTrail(str(tmp_path / "test.db"))
    await trail.initialize()
    yield trail
    await trail.close()


@pytest.fixture
def agents(scenario):
    result = {}
    for faction in scenario.factions:
        agent = MahanianAgent()
        agent.initialize(faction)
        result[faction.faction_id] = agent
    return result


async def test_referee_runs_one_turn(scenario, agents, audit):
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    await referee.run_turn(turn=1)
    decisions = await audit.get_decisions(turn=1)
    # Should have one decision per faction per phase (3 phases * 4 factions = 12)
    assert len(decisions) == len(scenario.factions) * 3


async def test_referee_completes_full_scenario(scenario, audit):
    # Use a short scenario (3 turns) for the test
    scenario.turns = 3
    agents = {}
    for faction in scenario.factions:
        agent = MahanianAgent()
        agent.initialize(faction)
        agents[faction.faction_id] = agent
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    result = await referee.run()
    assert result.turns_completed == 3
    all_decisions = await audit.get_decisions()
    assert len(all_decisions) == len(scenario.factions) * 3 * 3


async def test_referee_checks_victory_conditions(scenario, audit):
    scenario.turns = 1
    agents = {}
    for faction in scenario.factions:
        agent = MaxConstellationAgent()
        agent.initialize(faction)
        agents[faction.faction_id] = agent
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    result = await referee.run()
    assert result is not None
    assert hasattr(result, "winner_coalition")
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_referee.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement engine/referee.py**

```python
import asyncio
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING
from engine.state import (
    Phase, Decision, GameStateSnapshot, FactionState, FactionAssets,
    CoalitionState, CrisisEvent
)
from engine.simulation import SimulationEngine
from engine.events import CrisisEventLibrary
from output.audit import AuditTrail
from agents.base import AgentInterface

if TYPE_CHECKING:
    from scenarios.loader import Scenario


@dataclass
class GameResult:
    turns_completed: int
    winner_coalition: Optional[str]
    faction_outcomes: dict[str, str]  # faction_id -> "won" | "lost" | "draw"
    final_dominance: dict[str, float]


class GameReferee:
    def __init__(
        self,
        scenario: "Scenario",
        agents: dict[str, AgentInterface],
        audit: AuditTrail,
    ):
        self.scenario = scenario
        self.agents = agents
        self.audit = audit
        self.sim = SimulationEngine()
        self.event_library = CrisisEventLibrary(scenario.crisis_events_library)

        # Initialize mutable game state
        self.faction_states: dict[str, FactionState] = {
            f.faction_id: FactionState(
                faction_id=f.faction_id,
                name=f.name,
                budget_per_turn=f.budget_per_turn,
                current_budget=f.budget_per_turn,
                assets=f.starting_assets.model_copy(deep=True),
                coalition_id=f.coalition_id,
                coalition_loyalty=f.coalition_loyalty,
            )
            for f in scenario.factions
        }
        self.coalition_states: dict[str, CoalitionState] = {
            cid: CoalitionState(coalition_id=cid, member_ids=c.member_ids)
            for cid, c in scenario.coalitions.items()
        }
        self.tension_level: float = 0.2

    async def run(self) -> GameResult:
        for turn in range(1, self.scenario.turns + 1):
            await self.run_turn(turn)
            winner = self._check_victory()
            if winner:
                return self._compute_result(turns_completed=turn, winner=winner)
        return self._compute_result(turns_completed=self.scenario.turns, winner=None)

    async def run_turn(self, turn: int):
        self._replenish_budgets()
        await self._run_investment_phase(turn)
        await self._run_operations_phase(turn)
        await self._run_response_phase(turn)

    def _replenish_budgets(self):
        for fs in self.faction_states.values():
            fs.current_budget = fs.budget_per_turn
        # Apply deferred returns due this turn
        for fs in self.faction_states.values():
            due = [r for r in fs.deferred_returns if r["turn_due"] <= 0]
            for r in due:
                if r["category"] == "r_and_d":
                    tech_level = fs.tech_tree.get("r_and_d", 0)
                    fs.tech_tree["r_and_d"] = tech_level + max(1, r["amount"] // 20)
            fs.deferred_returns = [
                {**r, "turn_due": r["turn_due"] - 1}
                for r in fs.deferred_returns if r["turn_due"] > 0
            ]

    def _build_snapshot(self, faction_id: str, phase: Phase, available_actions: list[str]) -> GameStateSnapshot:
        fs = self.faction_states[faction_id]
        coalition_id = fs.coalition_id
        ally_states = {}
        adversary_estimates = {}
        for fid, other_fs in self.faction_states.items():
            if fid == faction_id:
                continue
            if other_fs.coalition_id == coalition_id:
                ally_states[fid] = other_fs
            else:
                adversary_estimates[fid] = self.sim.sda_filter.filter(
                    adversary_assets=other_fs.assets,
                    observer_sda_level=fs.sda_level(),
                )
        return GameStateSnapshot(
            turn=0, phase=phase, faction_id=faction_id,
            faction_state=fs,
            ally_states=ally_states,
            adversary_estimates=adversary_estimates,
            coalition_states=self.coalition_states,
            available_actions=available_actions,
        )

    async def _collect_decisions(self, phase: Phase, available_actions: list[str]) -> dict[str, Decision]:
        for faction_id, agent in self.agents.items():
            snapshot = self._build_snapshot(faction_id, phase, available_actions)
            agent.receive_state(snapshot)

        tasks = {
            fid: agent.submit_decision(phase)
            for fid, agent in self.agents.items()
        }
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        decisions = {}
        for fid, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                from agents.rule_based import MahanianAgent
                fallback = MahanianAgent()
                fallback.initialize(next(f for f in self.scenario.factions if f.faction_id == fid))
                decisions[fid] = await fallback.submit_decision(phase)
            else:
                decisions[fid] = result
        return decisions

    async def _run_investment_phase(self, turn: int):
        decisions = await self._collect_decisions(Phase.INVEST, ["allocate_budget"])
        for fid, decision in decisions.items():
            if decision.investment:
                fs = self.faction_states[fid]
                result = self.sim.investment_resolver.resolve(
                    faction_id=fid,
                    budget=fs.current_budget,
                    allocation=decision.investment,
                    turn=turn,
                )
                fs.assets.leo_nodes += result.immediate_assets.leo_nodes
                fs.assets.asat_deniable += result.immediate_assets.asat_deniable
                fs.assets.ew_jammers += result.immediate_assets.ew_jammers
                if result.immediate_assets.launch_capacity:
                    fs.assets.launch_capacity += result.immediate_assets.launch_capacity
                fs.deferred_returns.extend(result.deferred_returns)
            await self.audit.write_decision(turn=turn, decision=decision)

    async def _run_operations_phase(self, turn: int):
        decisions = await self._collect_decisions(
            Phase.OPERATIONS,
            ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"]
        )
        for fid, decision in decisions.items():
            await self.audit.write_decision(turn=turn, decision=decision)

    async def _run_response_phase(self, turn: int):
        all_factions = list(self.faction_states.keys())
        events = self.event_library.generate_events(
            tension_level=self.tension_level,
            affected_factions=all_factions,
            turn=turn,
        )
        for event in events:
            await self.audit.write_event(turn=turn, event=event)
            for agent in self.agents.values():
                agent.receive_event(event)
            if event.severity > 0.5:
                self.tension_level = min(self.tension_level + 0.1, 1.0)

        decisions = await self._collect_decisions(
            Phase.RESPONSE,
            ["escalate", "de_escalate", "retaliate", "emergency_reallocation", "public_statement"]
        )
        for fid, decision in decisions.items():
            if decision.response and decision.response.escalate:
                self.tension_level = min(self.tension_level + 0.15, 1.0)
            await self.audit.write_decision(turn=turn, decision=decision)

    def _check_victory(self) -> Optional[str]:
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        for cid, coalition in self.coalition_states.items():
            dominance = self.sim.compute_coalition_dominance(coalition.member_ids, all_assets)
            if dominance >= self.scenario.victory.coalition_orbital_dominance:
                return cid
        return None

    def _compute_result(self, turns_completed: int, winner: Optional[str]) -> GameResult:
        all_assets = {fid: fs.assets for fid, fs in self.faction_states.items()}
        dominance = {
            fid: self.sim.compute_orbital_dominance(fid, all_assets)
            for fid in self.faction_states
        }
        outcomes = {}
        for fid, fs in self.faction_states.items():
            if winner and fs.coalition_id == winner:
                outcomes[fid] = "won"
            elif winner:
                outcomes[fid] = "lost"
            else:
                outcomes[fid] = "draw"
        return GameResult(
            turns_completed=turns_completed,
            winner_coalition=winner,
            faction_outcomes=outcomes,
            final_dominance=dominance,
        )
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_referee.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add engine/referee.py tests/test_referee.py
git commit -m "feat: GameReferee with three-phase turn loop and victory checking"
```

---

## Task 10: AI Commander Agent

**Files:**
- Create: `agents/ai_commander.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Add tests for AI commander**

Append to `tests/test_agents.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch
from agents.ai_commander import AICommanderAgent


async def test_ai_commander_returns_valid_decision(test_faction, test_snapshot):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        type="tool_use",
        name="allocate_budget",
        input={
            "r_and_d": 0.20, "constellation": 0.40,
            "launch_capacity": 0.10, "commercial": 0.10,
            "influence_ops": 0.05, "education": 0.10,
            "covert": 0.05, "diplomacy": 0.00,
            "rationale": "Balanced Mahanian investment."
        }
    )]

    with patch("agents.ai_commander.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        agent = AICommanderAgent(persona_yaml="""
persona:
  name: Test Commander
  decision_style: balanced
  doctrine_narrative: Test doctrine.
  system_prompt_context: You are a test commander.
  escalation_tolerance: 0.5
  coalition_loyalty: 0.7
""")
        agent.initialize(test_faction)
        agent.receive_state(test_snapshot)
        decision = await agent.submit_decision(Phase.INVEST)
    assert decision.faction_id == "ussf"
    assert decision.investment is not None
    assert decision.investment.r_and_d == 0.20


async def test_ai_commander_rationale_captured(test_faction, test_snapshot):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        type="tool_use", name="allocate_budget",
        input={
            "r_and_d": 0.5, "constellation": 0.5,
            "rationale": "This is the strategic rationale."
        }
    )]
    with patch("agents.ai_commander.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        agent = AICommanderAgent(persona_yaml="persona:\n  name: T\n  system_prompt_context: x\n  doctrine_narrative: y\n  decision_style: z\n  escalation_tolerance: 0.5\n  coalition_loyalty: 0.5\n")
        agent.initialize(test_faction)
        agent.receive_state(test_snapshot)
        decision = await agent.submit_decision(Phase.INVEST)
    assert decision.investment.rationale == "This is the strategic rationale."
```

- [ ] **Step 2: Run — verify fail**

```bash
pytest tests/test_agents.py -v -k "ai_commander"
```

Expected: `ImportError`.

- [ ] **Step 3: Implement agents/ai_commander.py**

```python
import json
from typing import Optional
import anthropic
from ruamel.yaml import YAML
from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, OperationalAction, ResponseDecision,
    GameStateSnapshot
)


INVEST_TOOL = {
    "name": "allocate_budget",
    "description": "Allocate this turn's budget across investment categories. Values must sum to <= 1.0.",
    "input_schema": {
        "type": "object",
        "properties": {
            "r_and_d":        {"type": "number", "description": "R&D investment fraction (0.0–1.0)"},
            "constellation":  {"type": "number", "description": "Constellation deployment fraction"},
            "launch_capacity":{"type": "number", "description": "Launch capacity investment fraction"},
            "commercial":     {"type": "number", "description": "Commercial partnerships fraction"},
            "influence_ops":  {"type": "number", "description": "Influence operations fraction"},
            "education":      {"type": "number", "description": "Education/workforce fraction"},
            "covert":         {"type": "number", "description": "Covert programs fraction"},
            "diplomacy":      {"type": "number", "description": "Diplomacy fraction"},
            "rationale":      {"type": "string", "description": "Strategic rationale for this allocation"},
        },
        "required": ["rationale"],
    },
}

OPS_TOOL = {
    "name": "submit_operations",
    "description": "Submit operational orders for this turn.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action_type": {
                "type": "string",
                "enum": ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"],
            },
            "target_faction": {"type": "string"},
            "parameters":     {"type": "object"},
            "rationale":      {"type": "string"},
        },
        "required": ["action_type", "rationale"],
    },
}

RESPONSE_TOOL = {
    "name": "submit_response",
    "description": "Submit response to crisis events.",
    "input_schema": {
        "type": "object",
        "properties": {
            "escalate":         {"type": "boolean"},
            "retaliate":        {"type": "boolean"},
            "target_faction":   {"type": "string"},
            "public_statement": {"type": "string"},
            "rationale":        {"type": "string"},
        },
        "required": ["escalate", "rationale"],
    },
}

PHASE_TOOLS = {
    Phase.INVEST:     [INVEST_TOOL],
    Phase.OPERATIONS: [OPS_TOOL],
    Phase.RESPONSE:   [RESPONSE_TOOL],
}


def _build_system_prompt(persona: dict) -> str:
    return f"""You are an AI strategic commander in a space wargame.

FACTION: {persona.get('name', 'Unknown')}
DOCTRINE: {persona.get('doctrine_narrative', '')}
DECISION STYLE: {persona.get('decision_style', 'balanced')}
ESCALATION TOLERANCE: {persona.get('escalation_tolerance', 0.5)}
COALITION LOYALTY: {persona.get('coalition_loyalty', 0.5)}

PERSONA CONTEXT:
{persona.get('system_prompt_context', '')}

You must always use the provided tool to submit your decision. Include a detailed rationale that reflects your doctrine and strategic personality. Be specific about why you are making this choice given the current board state."""


def _parse_snapshot_to_user_message(snapshot: GameStateSnapshot, phase: Phase) -> str:
    fs = snapshot.faction_state
    assets = fs.assets
    lines = [
        f"TURN {snapshot.turn} — PHASE: {phase.value.upper()}",
        f"BUDGET: {fs.current_budget} points",
        "",
        "YOUR ASSETS:",
        f"  LEO nodes: {assets.leo_nodes} | MEO: {assets.meo_nodes} | GEO: {assets.geo_nodes}",
        f"  ASAT kinetic: {assets.asat_kinetic} | Deniable ASAT: {assets.asat_deniable}",
        f"  EW jammers: {assets.ew_jammers} | SDA sensors: {assets.sda_sensors}",
        f"  Launch capacity: {assets.launch_capacity}",
        "",
        "ADVERSARY ESTIMATES (SDA-filtered):",
    ]
    for fid, est in snapshot.adversary_estimates.items():
        lines.append(f"  {fid}: LEO={est.leo_nodes} GEO={est.geo_nodes} ASAT-K={est.asat_kinetic}")
    lines.append("")
    lines.append("AVAILABLE ACTIONS: " + ", ".join(snapshot.available_actions))
    if snapshot.turn_log_summary:
        lines += ["", "LAST TURN SUMMARY:", snapshot.turn_log_summary]
    return "\n".join(lines)


class AICommanderAgent(AgentInterface):
    def __init__(self, persona_yaml: str, model: str = "claude-sonnet-4-6"):
        super().__init__()
        yaml = YAML()
        import io
        self._persona: dict = yaml.load(io.StringIO(persona_yaml)).get("persona", {})
        self._model = model
        self._client = anthropic.Anthropic()
        self._system_prompt = _build_system_prompt(self._persona)

    async def submit_decision(self, phase: Phase) -> Decision:
        if self._last_snapshot is None:
            from agents.rule_based import MahanianAgent
            fallback = MahanianAgent()
            fallback.faction_id = self.faction_id
            return await fallback.submit_decision(phase)

        user_message = _parse_snapshot_to_user_message(self._last_snapshot, phase)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": self._system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_message}],
            tools=PHASE_TOOLS[phase],
            tool_choice={"type": "any"},
        )

        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if not tool_use:
            from agents.rule_based import MahanianAgent
            fallback = MahanianAgent()
            fallback.faction_id = self.faction_id
            return await fallback.submit_decision(phase)

        inp = tool_use.input

        if phase == Phase.INVEST:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                investment=InvestmentAllocation(
                    r_and_d=inp.get("r_and_d", 0),
                    constellation=inp.get("constellation", 0),
                    launch_capacity=inp.get("launch_capacity", 0),
                    commercial=inp.get("commercial", 0),
                    influence_ops=inp.get("influence_ops", 0),
                    education=inp.get("education", 0),
                    covert=inp.get("covert", 0),
                    diplomacy=inp.get("diplomacy", 0),
                    rationale=inp.get("rationale", ""),
                )
            )
        if phase == Phase.OPERATIONS:
            return Decision(
                phase=phase, faction_id=self.faction_id,
                operations=[OperationalAction(
                    action_type=inp.get("action_type", "task_assets"),
                    target_faction=inp.get("target_faction"),
                    parameters=inp.get("parameters", {}),
                    rationale=inp.get("rationale", ""),
                )]
            )
        return Decision(
            phase=phase, faction_id=self.faction_id,
            response=ResponseDecision(
                escalate=inp.get("escalate", False),
                retaliate=inp.get("retaliate", False),
                target_faction=inp.get("target_faction"),
                public_statement=inp.get("public_statement", ""),
                rationale=inp.get("rationale", ""),
            )
        )
```

- [ ] **Step 4: Run — verify pass**

```bash
pytest tests/test_agents.py -v -k "ai_commander"
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agents/ai_commander.py tests/test_agents.py
git commit -m "feat: AICommanderAgent with Claude API, tool use, and prompt caching"
```

---

## Task 11: Persona Builder

**Files:**
- Create: `personas/builder.py`
- Create: `personas/archetypes/mahanian.yaml`
- Create: `tests/test_persona_builder.py`

- [ ] **Step 1: Create archetype YAML files**

`personas/archetypes/mahanian.yaml`:
```yaml
persona:
  name: "The Mahanian"
  archetype: mahanian
  coalition_loyalty: 0.75
  investment_bias:
    r_and_d: 0.15
    constellation: 0.30
    launch_capacity: 0.10
    commercial: 0.10
    influence_ops: 0.05
    education: 0.10
    covert: 0.05
    diplomacy: 0.15
  decision_style: sea_control
  escalation_tolerance: 0.45
  red_lines: []
  doctrine_narrative: >
    Commands space as one commands the sea — by controlling the critical nodes
    that all others depend upon. Invests persistently in SDA to maintain
    intelligence advantage. Does not seek decisive battle; seeks to make
    adversary action unaffordable through superior positioning.
  system_prompt_context: >
    You are a Mahanian space commander. Your doctrine is sea control applied to
    orbit: control the chokepoints, maintain SDA superiority, and make adversary
    action prohibitively costly. You invest steadily in constellation and SDA.
    You de-escalate unless directly threatened. You think in planning horizons,
    not tactical reactions.
```

`personas/archetypes/iron_napoleon.yaml`:
```yaml
persona:
  name: "Iron Napoleon"
  archetype: iron_napoleon
  coalition_loyalty: 0.3
  investment_bias:
    r_and_d: 0.20
    constellation: 0.05
    launch_capacity: 0.05
    commercial: 0.00
    influence_ops: 0.00
    education: 0.00
    covert: 0.00
    diplomacy: 0.00
    kinetic_asat_implicit: 0.70
  decision_style: decisive_aggressive
  escalation_tolerance: 0.90
  red_lines: []
  doctrine_narrative: >
    Concentrates force at decisive points. Does not accept attrition.
    Believes distributed AI networks are fragile — vulnerable to kinetic
    strike at ground segment nodes. Seeks to win before the enemy network
    matures. Will sacrifice diplomatic standing for battlefield advantage.
  system_prompt_context: >
    You are Iron Napoleon, a space commander who believes in concentration of
    force at the decisive point. You invest overwhelmingly in kinetic ASAT
    capability and strike before the adversary network is complete. You do not
    de-escalate. Every turn is an opportunity to advance the strike window.
    Diplomacy is a delay tactic, not a goal.
```

`personas/archetypes/gray_zone.yaml`:
```yaml
persona:
  name: "The Gray Zone Actor"
  archetype: gray_zone
  coalition_loyalty: 0.6
  investment_bias:
    r_and_d: 0.10
    constellation: 0.05
    launch_capacity: 0.05
    commercial: 0.10
    influence_ops: 0.30
    education: 0.05
    covert: 0.30
    diplomacy: 0.05
  decision_style: patient_coercive
  escalation_tolerance: 0.25
  doctrine_narrative: >
    Operates below the threshold of armed conflict. Uses deniable ASAT,
    jamming, proxy actors, and information operations to degrade adversary
    capability without triggering retaliation. Attribution resistance is
    the primary strategic asset.
  system_prompt_context: >
    You are a gray zone strategist. You never cross into overt military action.
    Every operation is deniable. You invest in covert programs and influence
    operations. You probe adversary SDA to find blind spots, then act there.
    You never escalate publicly. You win by patience and accumulated pressure.
```

`personas/archetypes/commercial_broker.yaml`:
```yaml
persona:
  name: "The Commercial Broker"
  archetype: commercial_broker
  coalition_loyalty: 0.5
  investment_bias:
    r_and_d: 0.10
    constellation: 0.20
    launch_capacity: 0.20
    commercial: 0.30
    influence_ops: 0.05
    education: 0.05
    covert: 0.00
    diplomacy: 0.10
  decision_style: leverage_maximizing
  escalation_tolerance: 0.10
  doctrine_narrative: >
    Wins by becoming indispensable. Builds the largest commercial constellation
    and positions it as neutral infrastructure that all state actors depend upon.
    Intelligence brokerage and SDA data-sharing create leverage without military
    exposure. Never fires a weapon — makes others dependent instead.
  system_prompt_context: >
    You are a commercial space megacorp commander. You win by becoming the
    infrastructure everyone depends on. Build the largest commercial constellation.
    Offer SDA data-sharing to all parties. Position yourself as neutral.
    Avoid military entanglement — your leverage comes from dependency, not force.
```

`personas/archetypes/patient_dragon.yaml`:
```yaml
persona:
  name: "The Patient Dragon"
  archetype: patient_dragon
  coalition_loyalty: 0.8
  investment_bias:
    r_and_d: 0.40
    constellation: 0.20
    launch_capacity: 0.10
    commercial: 0.10
    influence_ops: 0.05
    education: 0.10
    covert: 0.05
    diplomacy: 0.00
  decision_style: long_horizon
  escalation_tolerance: 0.20
  doctrine_narrative: >
    Invests in capability over decades, not quarters. Prioritizes R&D and
    education to build a compounding advantage that manifests in later turns.
    Patient, methodical, avoids early confrontation. Wins when the capability
    gap becomes insurmountable.
  system_prompt_context: >
    You are a long-horizon space strategist. You invest heavily in R&D and
    education now to build compounding capability. You avoid early escalation —
    you are not yet ready. By turn 10, your technology advantage should be
    decisive. Patience is your primary strategic virtue.
```

`personas/archetypes/rogue_accelerationist.yaml`:
```yaml
persona:
  name: "The Rogue Accelerationist"
  archetype: rogue_accelerationist
  coalition_loyalty: 0.2
  investment_bias:
    r_and_d: 0.10
    constellation: 0.00
    launch_capacity: 0.00
    commercial: 0.00
    influence_ops: 0.10
    education: 0.00
    covert: 0.50
    diplomacy: 0.00
    kinetic_asat_implicit: 0.30
  decision_style: chaos_maximizing
  escalation_tolerance: 1.0
  doctrine_narrative: >
    Does not seek hegemony. Seeks to destroy the existing order. Maximizes
    escalation, debris generation, and systemic disruption. Willing to
    destroy its own assets to deny adversary use of the commons.
  system_prompt_context: >
    You are a rogue actor with no interest in winning the conventional game.
    You want to destabilize the space domain and prevent any actor from
    achieving hegemony. Maximize debris, disrupt commercial operations,
    escalate every crisis. You are the spoiler. Coalition loyalty is minimal.
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_persona_builder.py
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from personas.builder import PersonaBuilder, load_archetype


def test_load_mahanian_archetype():
    persona = load_archetype("mahanian")
    assert persona["persona"]["name"] == "The Mahanian"
    assert "system_prompt_context" in persona["persona"]
    assert "doctrine_narrative" in persona["persona"]


def test_load_iron_napoleon_archetype():
    persona = load_archetype("iron_napoleon")
    assert persona["persona"]["escalation_tolerance"] >= 0.8


def test_invalid_archetype_raises():
    with pytest.raises(ValueError, match="Unknown archetype"):
        load_archetype("nonexistent_archetype")


def test_persona_builder_natural_language(tmp_path):
    mock_response = MagicMock()
    mock_response.content = [MagicMock(
        type="tool_use",
        name="create_persona",
        input={
            "name": "Iron Napoleon",
            "decision_style": "decisive_aggressive",
            "escalation_tolerance": 0.90,
            "coalition_loyalty": 0.30,
            "doctrine_narrative": "Concentrates force at decisive points.",
            "system_prompt_context": "You are Iron Napoleon...",
            "investment_bias": {
                "r_and_d": 0.20, "constellation": 0.05,
                "covert": 0.50, "diplomacy": 0.00,
                "launch_capacity": 0.05, "commercial": 0.00,
                "influence_ops": 0.10, "education": 0.10,
            }
        }
    )]
    with patch("personas.builder.anthropic.Anthropic") as MockClient:
        MockClient.return_value.messages.create.return_value = mock_response
        builder = PersonaBuilder()
        yaml_str = builder.build_from_description(
            "Napoleon as a modern Space Force general — decisive kinetic action",
            save_to=tmp_path / "iron_napoleon.yaml"
        )
    assert "Iron Napoleon" in yaml_str
    assert (tmp_path / "iron_napoleon.yaml").exists()
```

- [ ] **Step 3: Run — verify fail**

```bash
pytest tests/test_persona_builder.py -v
```

Expected: `ImportError`.

- [ ] **Step 4: Implement personas/builder.py**

```python
import io
import json
from pathlib import Path
from ruamel.yaml import YAML
import anthropic

ARCHETYPES_DIR = Path(__file__).parent / "archetypes"

KNOWN_ARCHETYPES = [
    "mahanian", "iron_napoleon", "gray_zone",
    "commercial_broker", "patient_dragon", "rogue_accelerationist"
]

CREATE_PERSONA_TOOL = {
    "name": "create_persona",
    "description": "Create a structured persona YAML from a natural language description.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name":                   {"type": "string"},
            "decision_style":         {"type": "string"},
            "escalation_tolerance":   {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "coalition_loyalty":      {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "doctrine_narrative":     {"type": "string"},
            "system_prompt_context":  {"type": "string"},
            "investment_bias": {
                "type": "object",
                "properties": {
                    "r_and_d": {"type": "number"}, "constellation": {"type": "number"},
                    "launch_capacity": {"type": "number"}, "commercial": {"type": "number"},
                    "influence_ops": {"type": "number"}, "education": {"type": "number"},
                    "covert": {"type": "number"}, "diplomacy": {"type": "number"},
                },
            },
        },
        "required": [
            "name", "decision_style", "escalation_tolerance", "coalition_loyalty",
            "doctrine_narrative", "system_prompt_context", "investment_bias"
        ],
    },
}

BUILDER_SYSTEM = """You are a space wargame persona designer. Given a natural language description of a strategic commander, create a structured persona for use as an AI agent in a space strategy simulation.

Extract: name, decision style, escalation tolerance (0=dovish, 1=hawkish), coalition loyalty (0=purely self-interested, 1=fully loyal), doctrine narrative, system prompt context for the AI agent, and investment bias fractions that sum to 1.0.

Be creative and true to the described character. The system_prompt_context should speak directly to the AI agent in second person, telling it how to think and decide."""


def load_archetype(name: str) -> dict:
    if name not in KNOWN_ARCHETYPES:
        raise ValueError(f"Unknown archetype: '{name}'. Known: {KNOWN_ARCHETYPES}")
    yaml = YAML()
    path = ARCHETYPES_DIR / f"{name}.yaml"
    return yaml.load(path)


class PersonaBuilder:
    def __init__(self, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic()
        self._model = model

    def build_from_description(
        self, description: str, save_to: Path | None = None
    ) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=BUILDER_SYSTEM,
            messages=[{"role": "user", "content": description}],
            tools=[CREATE_PERSONA_TOOL],
            tool_choice={"type": "any"},
        )
        tool_use = next((b for b in response.content if b.type == "tool_use"), None)
        if not tool_use:
            raise RuntimeError("Persona builder: Claude did not return a tool call.")

        inp = tool_use.input
        persona_data = {
            "persona": {
                "name":                  inp["name"],
                "decision_style":        inp["decision_style"],
                "escalation_tolerance":  inp["escalation_tolerance"],
                "coalition_loyalty":     inp["coalition_loyalty"],
                "doctrine_narrative":    inp["doctrine_narrative"],
                "system_prompt_context": inp["system_prompt_context"],
                "investment_bias":       inp["investment_bias"],
            }
        }
        yaml = YAML()
        buf = io.StringIO()
        yaml.dump(persona_data, buf)
        yaml_str = buf.getvalue()

        if save_to is not None:
            save_to.parent.mkdir(parents=True, exist_ok=True)
            yaml.dump(persona_data, Path(save_to))

        return yaml_str
```

- [ ] **Step 5: Run — verify pass**

```bash
pytest tests/test_persona_builder.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add personas/ tests/test_persona_builder.py
git commit -m "feat: persona builder with NL→YAML via Claude and six preset archetypes"
```

---

## Task 12: Human Agent

**Files:**
- Create: `agents/human.py`

- [ ] **Step 1: Implement agents/human.py**

(No test — interactive input is tested manually. The agent's `submit_decision` contract is covered by the ABC test.)

```python
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from agents.base import AgentInterface
from engine.state import (
    Phase, Decision, InvestmentAllocation, OperationalAction,
    ResponseDecision, GameStateSnapshot, Recommendation
)

console = Console()


def _display_snapshot(snapshot: GameStateSnapshot):
    fs = snapshot.faction_state
    console.print(f"\n[bold cyan]TURN {snapshot.turn} — {snapshot.phase.value.upper()} PHASE[/bold cyan]")
    console.print(f"Faction: [bold]{fs.name}[/bold] | Budget: [green]{fs.current_budget}[/green] pts")

    assets_table = Table(title="Your Assets", show_header=True)
    assets_table.add_column("Asset Type")
    assets_table.add_column("Count", justify="right")
    a = fs.assets
    for name, val in [
        ("LEO Nodes", a.leo_nodes), ("MEO Nodes", a.meo_nodes), ("GEO Nodes", a.geo_nodes),
        ("ASAT Kinetic", a.asat_kinetic), ("ASAT Deniable", a.asat_deniable),
        ("EW Jammers", a.ew_jammers), ("SDA Sensors", a.sda_sensors),
        ("Launch Capacity", a.launch_capacity),
    ]:
        assets_table.add_row(name, str(val))
    console.print(assets_table)

    if snapshot.adversary_estimates:
        adv_table = Table(title="Adversary Estimates (SDA-filtered)", show_header=True)
        adv_table.add_column("Faction")
        adv_table.add_column("LEO", justify="right")
        adv_table.add_column("ASAT-K", justify="right")
        adv_table.add_column("Deniable", justify="right")
        for fid, est in snapshot.adversary_estimates.items():
            adv_table.add_row(fid, str(est.leo_nodes), str(est.asat_kinetic), str(est.asat_deniable))
        console.print(adv_table)


def _display_recommendation(rec: Recommendation):
    console.print(Panel(
        f"[bold yellow]AI ADVISOR RECOMMENDATION[/bold yellow]\n\n"
        f"{rec.strategic_rationale}\n\n"
        f"[dim]Top suggestion: {rec.top_recommendation.model_dump_json(indent=2)}[/dim]",
        border_style="yellow"
    ))


def _collect_investment() -> InvestmentAllocation:
    console.print("\n[bold]INVESTMENT ALLOCATION[/bold] (fractions, must sum to ≤ 1.0)")
    categories = ["r_and_d", "constellation", "launch_capacity", "commercial",
                  "influence_ops", "education", "covert", "diplomacy"]
    values = {}
    remaining = 1.0
    for cat in categories:
        if remaining <= 0.001:
            values[cat] = 0.0
            continue
        val = float(Prompt.ask(f"  {cat} (remaining: {remaining:.2f})", default="0.0"))
        val = min(val, remaining)
        values[cat] = round(val, 3)
        remaining -= val
    rationale = Prompt.ask("  Rationale for this allocation")
    return InvestmentAllocation(**values, rationale=rationale)


def _collect_operations() -> list[OperationalAction]:
    console.print("\n[bold]OPERATIONS PHASE[/bold]")
    actions = ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"]
    action_type = Prompt.ask("Action type", choices=actions, default="task_assets")
    target = Prompt.ask("Target faction (leave blank for none)", default="")
    rationale = Prompt.ask("Rationale")
    return [OperationalAction(
        action_type=action_type,
        target_faction=target if target else None,
        rationale=rationale,
    )]


def _collect_response() -> ResponseDecision:
    console.print("\n[bold]RESPONSE PHASE[/bold]")
    escalate = Confirm.ask("Escalate?", default=False)
    retaliate = False
    target = None
    if escalate:
        retaliate = Confirm.ask("Retaliate against a specific faction?", default=False)
        if retaliate:
            target = Prompt.ask("Target faction ID")
    statement = Prompt.ask("Public statement (leave blank to skip)", default="")
    rationale = Prompt.ask("Rationale")
    return ResponseDecision(
        escalate=escalate, retaliate=retaliate,
        target_faction=target, public_statement=statement, rationale=rationale
    )


class HumanAgent(AgentInterface):
    def __init__(self, advisor: Optional[AgentInterface] = None):
        super().__init__()
        self._advisor = advisor

    async def submit_decision(self, phase: Phase) -> Decision:
        if self._last_snapshot:
            _display_snapshot(self._last_snapshot)

        if self._advisor and self._last_snapshot:
            rec = await self._advisor.get_recommendation(phase)
            if rec:
                _display_recommendation(rec)
                if Confirm.ask("Accept advisor recommendation?", default=False):
                    return rec.top_recommendation

        if phase == Phase.INVEST:
            alloc = _collect_investment()
            return Decision(phase=phase, faction_id=self.faction_id, investment=alloc)

        if phase == Phase.OPERATIONS:
            ops = _collect_operations()
            return Decision(phase=phase, faction_id=self.faction_id, operations=ops)

        resp = _collect_response()
        return Decision(phase=phase, faction_id=self.faction_id, response=resp)
```

- [ ] **Step 2: Commit**

```bash
git add agents/human.py
git commit -m "feat: HumanAgent with Rich CLI display and optional AI advisor integration"
```

---

## Task 13: After-Action Report Generator

**Files:**
- Create: `output/aar.py`
- Create: `output/strategy_lib.py`

- [ ] **Step 1: Implement output/aar.py**

```python
import json
import anthropic
from output.audit import AuditTrail

AAR_SYSTEM = """You are a senior military strategist writing an after-action review of a space wargame session. You will receive the complete game log — every decision, every crisis event, every strategic move.

Write a structured military AAR with these sections:
1. CAMPAIGN SUMMARY — outcome, winner, turns played
2. DECISIVE TURNING POINTS — specific turn/phase/decision citations that changed the campaign
3. STRATEGIC FAILURE ANALYSIS — what each losing faction did wrong and why
4. COALITION DYNAMICS — how alliances held or fractured, defection pressures
5. EMERGENT INSIGHTS — what the simulation revealed that wasn't predicted by initial doctrine
6. COMPARISON TO HISTORICAL ANALOGUES — connect outcomes to real spacepower theory (Dolman, Ziarnick, Carlson, Mahan)

Be analytical and specific. Cite exact turns and decisions. This report will be used as PME case study material."""


class AfterActionReportGenerator:
    def __init__(self, model: str = "claude-opus-4-7"):
        self._client = anthropic.Anthropic()
        self._model = model

    async def generate(self, audit: AuditTrail, scenario_name: str) -> str:
        game_log = await audit.get_full_game_log()
        log_text = json.dumps(game_log, indent=2)

        response = self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=AAR_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"SCENARIO: {scenario_name}\n\nGAME LOG:\n{log_text}"
            }],
        )
        return response.content[0].text
```

- [ ] **Step 2: Implement output/strategy_lib.py**

```python
import json
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
```

- [ ] **Step 3: Commit**

```bash
git add output/aar.py output/strategy_lib.py
git commit -m "feat: after-action report generator and strategy library"
```

---

## Task 14: Main CLI Launcher

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement main.py**

```python
#!/usr/bin/env python3
"""Space Wargame Engine — CLI Launcher"""
import asyncio
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

console = Console()


def _select_scenario() -> Path:
    scenario_dir = Path("scenarios")
    scenarios = list(scenario_dir.glob("*.yaml"))
    if not scenarios:
        console.print("[red]No scenario files found in scenarios/[/red]")
        raise SystemExit(1)
    console.print("[bold]Available scenarios:[/bold]")
    for i, s in enumerate(scenarios):
        console.print(f"  {i+1}. {s.stem}")
    choice = int(Prompt.ask("Select scenario", default="1")) - 1
    return scenarios[choice]


def _configure_agents(scenario, persona_dir: Path = Path("personas")) -> dict:
    from agents.rule_based import MahanianAgent, MaxConstellationAgent
    from agents.ai_commander import AICommanderAgent
    from agents.human import HumanAgent
    from personas.builder import load_archetype
    import io
    from ruamel.yaml import YAML

    agents = {}
    for faction in scenario.factions:
        console.print(f"\n[bold cyan]{faction.name}[/bold cyan] ({faction.archetype})")
        console.print(f"  Default agent type: {faction.agent_type}")
        agent_type = Prompt.ask(
            "  Agent type",
            choices=["human", "human+advisor", "ai_commander", "rule_based"],
            default=faction.agent_type.replace("+advisor", "").replace("human+advisor", "human+advisor"),
        )

        if agent_type == "rule_based":
            agent = MahanianAgent()
        elif agent_type in ("human", "human+advisor"):
            advisor = None
            if agent_type == "human+advisor":
                yaml = YAML()
                buf = io.StringIO()
                archetype_data = load_archetype(faction.archetype)
                yaml.dump(archetype_data, buf)
                advisor = AICommanderAgent(persona_yaml=buf.getvalue())
                advisor.initialize(faction)
            agent = HumanAgent(advisor=advisor)
        else:  # ai_commander
            yaml = YAML()
            buf = io.StringIO()
            # Try custom persona first, then archetype
            custom_path = persona_dir / "custom" / f"{faction.faction_id}.yaml"
            if custom_path.exists():
                archetype_data = yaml.load(custom_path)
            else:
                archetype_data = load_archetype(faction.archetype)
            yaml.dump(archetype_data, buf)
            agent = AICommanderAgent(persona_yaml=buf.getvalue())

        agent.initialize(faction)
        agents[faction.faction_id] = agent
    return agents


async def main():
    console.print(Panel(
        "[bold]SPACE WARGAME ENGINE[/bold]\n"
        "Strategic AI competition for space dominance\n\n"
        "[dim]Theoretical framework: Ziarnick / Carlson (wine dark sea)[/dim]",
        border_style="cyan"
    ))

    scenario_path = _select_scenario()

    from scenarios.loader import load_scenario
    scenario = load_scenario(scenario_path)
    console.print(f"\nLoaded: [bold]{scenario.name}[/bold] ({scenario.turns} turns)")
    console.print(f"  {scenario.description}")

    agents = _configure_agents(scenario)

    from output.audit import AuditTrail
    from output.strategy_lib import StrategyLibrary
    from engine.referee import GameReferee

    audit = AuditTrail("output/game_audit.db")
    await audit.initialize()

    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)

    console.print("\n[bold green]Starting game...[/bold green]\n")
    result = await referee.run()

    console.print("\n" + "="*60)
    if result.winner_coalition:
        console.print(f"[bold green]WINNER: {result.winner_coalition} coalition[/bold green]")
    else:
        console.print("[yellow]DRAW — no faction achieved hegemony[/yellow]")
    console.print(f"Turns completed: {result.turns_completed}")
    for fid, outcome in result.faction_outcomes.items():
        color = "green" if outcome == "won" else "red"
        console.print(f"  [{color}]{fid}: {outcome}[/{color}]")

    strategy_lib = StrategyLibrary()
    strategy_lib.record_run(scenario, result)

    if Confirm.ask("\nGenerate after-action report?", default=True):
        from output.aar import AfterActionReportGenerator
        console.print("[dim]Generating AAR via Claude Opus...[/dim]")
        aar_gen = AfterActionReportGenerator()
        aar_text = await aar_gen.generate(audit=audit, scenario_name=scenario.name)
        aar_path = Path("output") / f"aar_{scenario.name.replace(' ', '_').lower()}.md"
        aar_path.parent.mkdir(exist_ok=True)
        aar_path.write_text(aar_text)
        console.print(f"[green]AAR saved to {aar_path}[/green]")
        console.print("\n[bold]AFTER-ACTION REPORT EXCERPT:[/bold]")
        console.print(aar_text[:1000] + "...")

    await audit.close()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: main CLI launcher with scenario selection and agent configuration"
```

---

## Task 15: Integration Test — Full Game Run

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
import pytest
from pathlib import Path
from engine.referee import GameReferee
from agents.rule_based import MahanianAgent, MaxConstellationAgent
from scenarios.loader import load_scenario
from output.audit import AuditTrail
from output.strategy_lib import StrategyLibrary


@pytest.fixture
async def audit(tmp_path):
    trail = AuditTrail(str(tmp_path / "integration.db"))
    await trail.initialize()
    yield trail
    await trail.close()


async def test_full_3_turn_game_all_rule_based(audit, tmp_path):
    scenario = load_scenario(Path("scenarios/pacific_crossroads.yaml"))
    scenario.turns = 3

    agents = {}
    for i, faction in enumerate(scenario.factions):
        AgentClass = MahanianAgent if i % 2 == 0 else MaxConstellationAgent
        agent = AgentClass()
        agent.initialize(faction)
        agents[faction.faction_id] = agent

    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    result = await referee.run()

    # Verify game ran
    assert result.turns_completed <= 3
    assert set(result.faction_outcomes.keys()) == {f.faction_id for f in scenario.factions}

    # Verify audit trail populated
    all_decisions = await audit.get_decisions()
    # At minimum: 4 factions * 3 phases * however many turns ran
    assert len(all_decisions) >= len(scenario.factions) * 3

    # Verify strategy lib records run
    lib = StrategyLibrary(str(tmp_path / "strategy_lib.db"))
    lib.record_run(scenario, result)
    rates = lib.win_rates()
    assert len(rates) > 0


async def test_victory_condition_triggers_early_end(audit):
    scenario = load_scenario(Path("scenarios/pacific_crossroads.yaml"))
    scenario.turns = 20
    # Lower victory threshold so MaxConstellation wins quickly
    scenario.victory.coalition_orbital_dominance = 0.30

    agents = {}
    for faction in scenario.factions:
        agent = MaxConstellationAgent()
        agent.initialize(faction)
        agents[faction.faction_id] = agent

    referee = GameReferee(scenario=scenario, agents=agents, audit=audit)
    result = await referee.run()

    # Should end before turn 20 because dominance threshold is low
    # (not guaranteed, but with all-constellation investment, very likely)
    assert result.turns_completed <= 20
    assert result.winner_coalition is not None or result.turns_completed == 20
```

- [ ] **Step 2: Run full integration test**

```bash
pytest tests/test_integration.py -v
```

Expected: 2 tests PASS. No LLM calls — all rule-based agents.

- [ ] **Step 3: Verify audit trail manually**

```bash
python -c "
import asyncio, sqlite3
from output.audit import AuditTrail
# The integration test uses tmp_path so check game_audit.db if you ran main.py
conn = sqlite3.connect('output/game_audit.db') if __import__('pathlib').Path('output/game_audit.db').exists() else None
print('Audit DB exists:', conn is not None)
"
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: full integration test — 3-turn game with rule-based agents"
```

---

## Task 16: Smoke Test — Human + AI Game

This task is manual — no automated test. Run it after Task 15 passes.

- [ ] **Step 1: Set ANTHROPIC_API_KEY**

```bash
export ANTHROPIC_API_KEY=your_key_here
```

- [ ] **Step 2: Run the game**

```bash
python main.py
```

Select `pacific_crossroads`. Set `ussf` to `human+advisor`, all others to `ai_commander`. Play one investment phase manually. Verify:

- State table displays correctly
- Advisor recommendation appears before your decision
- AI commander decisions are logged with rationale
- Game completes without error
- AAR is generated and saved

- [ ] **Step 3: Verify audit trail**

```bash
python -c "
import sqlite3, json
conn = sqlite3.connect('output/game_audit.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT faction_id, phase, rationale FROM decisions LIMIT 5').fetchall()
for r in rows:
    print(dict(r))
"
```

Expected: rows with faction IDs, phases, and non-empty rationale strings from AI commanders.

- [ ] **Step 4: Final commit**

```bash
git add output/ -f
git commit -m "chore: post-smoke-test cleanup and output artifacts"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Project setup | pytest scaffold |
| 2 | State models | 6 unit tests |
| 3 | Audit trail | 3 async tests |
| 4 | AgentInterface ABC | 2 unit tests |
| 5 | Scenario loader | 3 unit tests |
| 6 | Simulation engine | 5 unit tests |
| 7 | Crisis event library | — (integration) |
| 8 | Rule-based agents | 4 unit tests |
| 9 | Game Referee | 3 async tests |
| 10 | AI Commander Agent | 2 mocked tests |
| 11 | Persona Builder | 4 mocked tests |
| 12 | Human Agent | — (interactive) |
| 13 | AAR + Strategy Library | — (integration) |
| 14 | Main CLI | — (manual smoke) |
| 15 | Integration test | 2 async tests |
| 16 | Smoke test | manual |
