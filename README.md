# Astrakon

A multi-agent space wargame simulation engine. Factions compete for orbital dominance across LEO, MEO, GEO, and cislunar space through investment, operations, and crisis response — driven by rule-based AI, Claude-powered commanders, or human players.

Built to explore agentic AI patterns and space strategy concepts.

---

## Scenarios

| Scenario | Setting | Factions |
|---|---|---|
| **Cislunar Crossroads** | Lunar gateway competition, 2035 | NASA/USSF, ESA Consortium, CNSA/PLA, Roscosmos |
| **Pacific Crossroads** | Near-term space competition | US, China, commercial actors |

Each scenario runs for a configurable number of turns (each turn representing a fixed time period, e.g. 3 months). Factions are grouped into coalitions that pool hegemony scores and share intelligence.

---

## Agent Types

Each faction can be assigned one of four agent types:

| Type | Description |
|---|---|
| `rule_based` | Deterministic agents (e.g. `MahanianAgent` — SDA-focused sea control doctrine) |
| `human` | Interactive TUI — human makes all decisions |
| `human+advisor` | Human decides, but an AI advisor panel provides strategic recommendations |
| `ai_commander` | Fully autonomous Claude agent using tool use for structured decisions |

---

## Game Loop

Each turn runs three phases:

1. **Invest** — Allocate budget across R&D, constellation expansion (LEO/MEO/GEO/Cislunar), launch capacity, commercial, influence ops, covert programs, diplomacy
2. **Operations** — Submit operational orders: task assets, coordinate with allies, gray zone actions, alliance moves, signaling
3. **Response** — React to crisis events: escalate, retaliate, or de-escalate with a public statement

Orbital dominance is computed with tier weights: LEO (1×), MEO (2×), GEO (3×), Cislunar (4×). Victory triggers when a coalition crosses the dominance threshold and individual faction conditions are met.

---

## Setup

**Requirements:** Python 3.12+, Node.js 18+ (web frontend only)

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Set API key for AI agent types
export ANTHROPIC_API_KEY=sk-ant-...
```

---

## Running

### Terminal UI (CLI)

```bash
python main.py
```

Prompts you to select a scenario and configure each faction's agent type interactively.

### API Server

```bash
python run_api.py
# Starts FastAPI server at http://localhost:8000
```

### Web Frontend

```bash
cd web
npm install
npm run dev
# Starts Vite dev server at http://localhost:5173
```

---

## Architecture

```
agents/         Agent implementations (rule_based, ai_commander, human, web)
engine/         Game loop: referee, simulation, state, events
scenarios/      YAML scenario definitions and loader
personas/       Faction archetypes (mahanian, gray_zone, commercial_broker, …)
tui/            Rich-based terminal UI panels
api/            FastAPI backend (sessions, routes, runner)
web/            React + TypeScript + Tailwind frontend
output/         Audit trail (SQLite) and strategy library
tests/          33 tests covering agents, engine, API, and integration
```

---

## Testing

```bash
pytest
```

---

## Persona Archetypes

Factions are initialized with one of six strategic archetypes that shape their AI decision-making:

- **mahanian** — SDA-first, constellation balance, diplomatic positioning
- **iron_napoleon** — Aggressive force projection
- **gray_zone** — Ambiguity exploitation, deniable operations
- **commercial_broker** — Market share and commercial partnerships
- **patient_dragon** — Long-horizon infrastructure investment
- **rogue_accelerationist** — Disruption-maximizing, high escalation tolerance
