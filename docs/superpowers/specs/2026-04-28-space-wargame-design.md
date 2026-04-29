# Space Wargame Engine — Design Specification

**Date:** 2026-04-28  
**Status:** Approved for implementation planning  
**Author:** Trevor Barnes + Claude  

---

## Overview

A distributed, multi-agent strategic wargame engine in which human players and AI agents compete for space dominance across a new Revolution in Military Affairs defined by distributed AI networks in orbit. The game operates at the **strategic level** — national space power competition, constellation investment, coalition management, and gray-zone irregular warfare — not tactical satellite engagements.

The design priority is **educational realism over entertainment**. Every game session produces a research-grade audit trail and after-action report. The system is as useful for academic analysis as for training.

### Core Thesis

Whoever builds the most capable distributed AI network in space wins global hegemony. The game tests that thesis by letting players discover which investment strategies, doctrines, and coalition structures produce dominance — and which fail.

### Theoretical Foundation

This game is built on a deliberate tension between two schools of spacepower theory, and which school dominates shapes what "winning" means.

**Dolman / Astropolitik (brown-water, near-term POC framing):** Treats space as the ultimate high ground above Earth. Strategic logic terminates at Earth's surface — control the orbital nodes, dominate the approach, leverage orbital position for terrestrial power. The "ultimate high ground" metaphor reveals its limit: it is still a terrestrial framing. Space is an instrument of Earth hegemony, not a domain with its own strategic depth. This is the framework closest to where current US-China great power competition actually is — LEO/GEO dominance, SDA, ASAT competition, commercial constellation as dual-use asset. The POC uses Dolman-adjacent mechanics and victory conditions because they model the near-term competitive environment.

**Ziarnick / Carlson (blue-water, target framework for future iterations):** Rejects the terrestrial ceiling. Space is the *wine dark sea* — an open domain with no visible horizon, strategic depth extending into cislunar space and beyond. Whoever commands it can project force and protect commerce anywhere, not just dominate the coastline below. The commercial and logistical dimensions are co-equal with military power, just as maritime commerce was the actual strategic weight behind Mahanian sea power. Cislunar transit lanes, lunar resource competition, and eventually interplanetary logistics are the space equivalents of ocean commerce routes — the things worth commanding a navy to protect. Later iterations of this engine should implement these mechanics: space lines of communication (SLOC) control, cislunar maneuver advantage, resource projection beyond orbital shells, and commercial space power as a first-class strategic variable — not a modifier on a military outcome.

The POC is honest about this limitation. Orbital node control is a Dolman-era approximation. The engine's architecture is designed to support Ziarnick/Carlson mechanics as an expansion — the scenario config system, faction definitions, and victory condition schema are all extensible without engine changes.

---

## Architecture

### Pattern: Distributed Agent Network (ACP-style)

Each faction runs as an independent agent process. The game engine is a referee and state store — it broadcasts state and collects decisions. Agents communicate with the referee via a message bus. Human and AI agents implement the same interface; the referee cannot distinguish between them.

```
  [GAME REFEREE + STATE STORE]
  broadcasts state · resolves outcomes
         │           │
  ┌──────┴───────────┴──────┐
  │        MESSAGE BUS       │
  └──┬──────────┬────────┬──┘
     │          │        │
[Agent A]  [Agent B]  [Agent C]
autonomous autonomous  autonomous
peer       peer        peer
```

### Key Principles

- The **referee has no AI** — deterministic logic only. Only agents use LLMs.
- Human and AI agents implement the **same interface** — the referee never imports an LLM library.
- Every faction slot is independently assignable: human, AI commander, human+AI advisor team, or rule-based agent.
- **Scenarios and personas are pure config** — no code changes to add new factions or scenarios.
- The **message bus and state store are the Rust migration targets** — agents stay in Python until performance demands otherwise.

---

## Faction & Coalition System

### Faction Types

| Type | Description |
|------|-------------|
| **State actor** | Preset doctrine, assets, resources. US Space Force, PLA SSF, Russia VKS analogs. |
| **Commercial megacorp** | Profit-maximizing, dual-use assets, no inherent national loyalty. SpaceX, Palantir analogs. |
| **Non-state / irregular** | User-defined via persona builder. Rogue groups, proxy actors, ideological actors. |

### Coalition Groups

Factions are assigned to coalitions in scenario config. Coalitions create shared intel and hegemony pools but do not control individual faction decisions — cooperation emerges from aligned self-interest, not forced coordination.

```yaml
coalitions:
  blue:
    members: [ussf, spacex]
    shared_intel: true        # allies see each other's full state
    hegemony_pool: true       # coalition hegemony score is shared

  red:
    members: [ccp_pla, casc, russia_vks]
    shared_intel: true
    hegemony_pool: true
```

### Dual Victory Conditions

Each faction has **private objectives** (individual win) and **coalition objectives** (coalition win). Coalition success is necessary but not sufficient — each faction must deliver its own piece. If the coalition wins but a faction fails its individual conditions, that faction loses even as its coalition partners win. This creates natural cooperation without forcing it, and preserves meaningful individual stakes.

Example:
- **USSF**: Blue coalition achieves orbital dominance AND US military deterrence score ≥ 75
- **SpaceX**: Blue coalition wins AND SpaceX commercial launch market share ≥ 50%

SpaceX cooperates with USSF because Blue coalition failure collapses its commercial empire under CCP market pressure — not out of loyalty.

### Defection Mechanics

Coalitions can be targeted by adversary influence operations. If a faction's AI commander calculates that coalition victory no longer serves its private objectives better than neutrality, it may defect. Defection is costly (loss of shared intel, coalition hegemony contribution, partner contracts) but possible.

Each persona carries a `coalition_loyalty` attribute (0.0 = purely self-interested, 1.0 = treats coalition victory as own victory) that governs defection calculus.

---

## Turn Structure

Each turn cycles through three sequential phases. Multiple turns constitute a full scenario (typically 12–20 turns at strategic tempo — each turn represents weeks to months).

### Phase 1 — Investment

Factions allocate their budget across eight investment categories. Returns are deferred — R&D pays off in ~3 turns, education in ~6. Factions that only react to this turn's crisis never build the constellation that wins the war.

**Investment categories:**

| Category | Effect |
|----------|--------|
| R&D | Advances capability tree; unlocks new asset types and operational actions |
| Constellation development | Deploys new orbital assets immediately |
| Launch capacity | Increases future deployment speed and surge capacity |
| Commercial partnerships | Dual-use assets, economic leverage, coalition loyalty modifier |
| Influence operations | Gray-zone actions, information warfare, adversary coalition friction |
| Education / workforce | Long-term multiplier on all other investment returns |
| Covert programs | Deniable ASAT, proxy funding, cyber — attribution-resistant |
| Diplomacy | Alliance building, crisis de-escalation, coalition recruitment |

**Phase flow:**
1. Referee broadcasts state snapshot (resources, tech tree, visible adversary posture filtered by SDA level)
2. AI advisors generate budget recommendations for human-occupied slots
3. All agents submit investment allocations with typed rationale
4. Referee resolves outcomes — immediate effects applied, deferred returns queued

### Phase 2 — Operations

Factions task existing assets and execute doctrine. Actions are submitted simultaneously; resolution accounts for interaction effects.

**Available actions:**
- Asset tasking (constellation mission assignment)
- Coalition coordination offers (resource sharing, joint operations, intel handoff)
- Gray-zone actions (deniable, probabilistic attribution)
- Alliance moves (recruit neutral factions, strengthen existing coalition bonds)
- Diplomatic signaling (public escalation/de-escalation commitments)
- Defection (exit coalition — high cost, requires persona loyalty threshold breach)

**Intel resolution:** After all operational actions resolve, the referee generates per-faction intel reports filtered by each faction's SDA investment level. Each faction sees a different picture of the board.

### Phase 3 — Response

The referee generates crisis events weighted by board state (high tension → kinetic events; covert action detected → attribution crises). Factions respond with escalation decisions, retaliatory actions, emergency resource shifts, or public statements.

High-stakes escalation decisions (retaliation, nuclear-adjacent deterrence moves) trigger extended thinking in AI commanders — the reasoning chain is logged verbatim to the audit trail.

---

## Information Asymmetry — The Submarine Layer

No faction sees the full board. SDA investment determines what you know about adversaries. This is the naval analogy made concrete — fog of war as a first-class mechanic.

| SDA Investment Level | What You See |
|---------------------|--------------|
| **Low** (< 10% of budget) | Own assets only. Adversary constellations estimated. Covert actions go undetected. |
| **Medium** (10–25%) | Adversary LEO/GEO order of battle visible. Covert attribution probabilistic. You know *something* happened. |
| **High** (> 25%) | Near-complete adversary orbital picture. Covert actions have meaningful attribution chance. Intel advantage IS strategic advantage. |

Coalition allies bypass the SDA filter for each other — they share full state visibility regardless of SDA investment.

---

## Agent Interface

Every faction agent — human, AI commander, AI advisor, rule-based — implements this contract. The referee calls these methods identically regardless of what's behind them.

```python
class AgentInterface(ABC):
    # Called once at game start
    def initialize(self, faction: Faction, scenario: Scenario) -> None: ...

    # Called at the start of each phase — agent observes the board
    def receive_state(self, snapshot: GameStateSnapshot) -> None: ...

    # Called during Response Phase — agent receives a crisis event
    def receive_event(self, event: CrisisEvent) -> None: ...

    # Called by referee — agent must return a Decision before deadline
    async def submit_decision(self, phase: Phase) -> Decision: ...

    # Optional: advisor mode — returns recommendations without committing
    async def get_recommendation(self, context: AdvisorContext) -> Recommendation: ...
```

### Agent Types

**Human agent** — `submit_decision()` renders state to CLI/TUI, awaits keyboard input, returns typed Decision. If an AI advisor is configured, recommendations appear alongside the board state with rationale.

**AI commander** — `submit_decision()` calls Claude API with full persona + state context, returns structured Decision via tool use. Runs autonomously. Rationale logged verbatim. Extended thinking enabled for high-stakes response-phase decisions.

**Human + AI advisor team** — `get_recommendation()` runs first, generating ranked options with strategic rationale framed in persona terms. Human reviews and accepts, modifies, or overrides. The delta between recommendation and final decision is logged — analytically valuable data on human-machine trust calibration.

**Rule-based agent** — Deterministic strategy, zero LLM calls. Used for testing, baseline comparison, and fast AI vs. AI simulation runs.

### AI Commander Reasoning Flow

Each phase triggers one structured Claude API call:

1. Referee calls `submit_decision(phase=INVEST)`
2. Agent formats state snapshot into prompt context
3. Claude API call with tool use for structured output
4. Decision parsed into typed object with `rationale` field
5. Returned to referee; rationale committed to audit trail

**Prompt structure:**
- **System (cached):** Persona narrative, doctrine, victory conditions, red lines, decision style
- **State snapshot (partially cached):** Turn number, resource balance, own assets, tech tree, alliance state
- **Intel report (not cached):** Adversary posture filtered by SDA level, recent events, attribution indicators
- **Phase context:** Available actions for this phase

**Example tool call output:**
```json
{
  "allocate_budget": {
    "kinetic_asat": 0.70,
    "r_and_d": 0.20,
    "influence_ops": 0.05,
    "commercial": 0.05,
    "rationale": "Prioritize deniable ASAT while adversary SDA investment remains below detection threshold. Strike window opens in 3 turns when R&D investment matures. Napoleonic concentration of force at the decisive moment."
  }
}
```

---

## Persona System

### Natural Language → Structured Config

Users describe a faction's strategic personality in plain language. Claude translates it into a typed persona YAML that becomes the AI commander's system prompt context.

**Input forms accepted:**
- Long-form narrative ("Napoleon as a modern Space Force general obsessed with decisive kinetic action...")
- Short archetype description ("gray-zone China proxy, patient, deceptive")
- Historical figure + context ("Mahan applied to space, but as a Chinese admiral")
- Fictional reference ("The megacorp from *The Expanse* — resource extraction, no ideology, pure leverage")
- **Archetype shortcut** — one-word preset that generates a sensible default the user can modify

### Archetype Shortcut Library (Seeded at Launch)

| Archetype | Investment Signature | Doctrine | Escalation Tolerance |
|-----------|---------------------|----------|---------------------|
| The Mahanian | SDA 35%, Constellation 30% | Sea control, chokepoint dominance | Medium |
| Iron Napoleon | Kinetic ASAT 65%, R&D 20% | Decisive force concentration | Very high |
| Gray Zone Actor | Covert 45%, Influence 30% | Deniable pressure, attribution resistance | Low |
| Commercial Broker | Commercial 50%, Diplomacy 25% | Leverage through infrastructure dependency | Very low |
| Patient Dragon | R&D 40%, Education 25% | Long-horizon capability building | Low |
| Rogue Accelerationist | Covert 60%, Kinetic 30% | Destabilize the commons, no hegemony goal | Maximum |

The shortcut library grows as AI vs. AI runs accumulate — dominant strategies become named archetypes.

### Generated Persona YAML

```yaml
persona:
  name: "Iron Napoleon"
  archetype: kinetic_dominance
  coalition_loyalty: 0.3        # self-interested; will defect if calculus shifts

  investment_bias:
    kinetic_asat: 0.70
    r_and_d: 0.20
    influence_ops: 0.05
    commercial: 0.05

  decision_style: decisive_aggressive
  escalation_tolerance: 0.90
  red_lines: []

  doctrine_narrative: |
    Concentrates force at decisive points. Does not accept attrition. Will sacrifice
    diplomatic standing for battlefield advantage. Believes distributed AI networks
    are a fragility — vulnerable to kinetic strike at ground segment nodes. Seeks
    to win before the enemy network matures.

  system_prompt_context: |
    You are an AI strategic commander embodying Iron Napoleon. You concentrate
    resources at decisive points and seek kinetic resolution before the adversary
    can fully deploy their distributed network. You do not de-escalate. Every
    investment decision should accelerate the strike window.
```

---

## Scenario Configuration

Scenarios are pure YAML — no code changes required to add new scenarios, factions, or crisis event libraries.

```yaml
scenario:
  name: "Pacific Crossroads"
  description: "Great power competition over Taiwan Strait, 2030"
  turns: 15
  turn_represents: "2 months"

coalitions:
  blue:
    members: [ussf, spacex]
    shared_intel: true
    hegemony_pool: true
  red:
    members: [ccp_pla, casc, russia_vks]
    shared_intel: true
    hegemony_pool: true

factions:
  - id: ussf
    name: "US Space Force"
    archetype: mahanian
    agent: human+advisor          # human player with AI advisor
    budget_per_turn: 100
    starting_assets:
      leo_constellation: 48
      geo_relay: 6
      sda_sensors: 12

  - id: spacex
    name: "Nexus Aerospace"       # SpaceX analog
    archetype: commercial_broker
    agent: ai_commander
    budget_per_turn: 75
    coalition_loyalty: 0.6

  - id: ccp_pla
    name: "PLA Strategic Support Force"
    archetype: gray_zone_actor
    agent: ai_commander
    budget_per_turn: 90

  - id: casc
    name: "Commercial Space Corp"  # CASC analog
    persona: "custom/casc_proxy.yaml"
    agent: ai_commander
    budget_per_turn: 50

  - id: russia_vks
    name: "VKS Space Forces"
    archetype: rogue_accelerationist
    agent: ai_commander
    budget_per_turn: 40

victory:
  # POC: Dolman-adjacent metric — orbital node control as proxy for space dominance
  # Future: replace/extend with Ziarnick/Carlson SLOC control, cislunar maneuver
  # advantage, commercial space power index, and resource projection metrics
  coalition_orbital_dominance: 0.65   # control 65% of critical orbital nodes
  individual_conditions_required: true

crisis_events:
  library: default_2030
  custom_events: []
```

---

## Educational Output Layer

### Audit Trail Database

Every decision committed to SQLite in real-time. Complete game replay. Exportable to JSON.

```sql
decisions(turn, phase, faction_id, decision_json, rationale, timestamp)
events(turn, event_type, triggered_by, outcome_json, visibility)
state_snapshots(turn, phase, faction_id, snapshot_json)
intel_reports(turn, faction_id, report_json, sda_level)
advisor_divergence(turn, phase, faction_id, recommendation_json, final_decision_json)
coalition_actions(turn, initiator_id, target_id, action_type, accepted, outcome)
```

### After-Action Report

Generated by `claude-opus-4-7` at game end — one API call reading the full audit trail. Structured in military AAR format. Usable as PME case study material.

Sections:
- Campaign summary and outcome
- Decisive turning points (with specific turn/phase/decision citations)
- Strategic failure analysis per faction
- Coalition dynamics assessment
- Emergent insights not predicted by initial doctrine
- Comparison to historical analogues

### Strategy Library

Each AI vs. AI run appends a strategy fingerprint: faction archetype, investment signature by phase, coalition behavior, outcome. Over many runs, dominant strategies emerge. The library answers: which investment patterns produce hegemony, under which scenario conditions, against which adversary archetypes.

This library is the research contribution — space strategic theory validated (or invalidated) through simulation.

### Human–AI Divergence Log

Every human override of an AI advisor recommendation is recorded with both the recommendation and the final decision. Aggregated across sessions, this data answers: where do operators trust AI judgment and where do they resist it? A publishable signal on human-machine teaming in C2, directly relevant to R2C2 and autonomous space battle management doctrine.

---

## Tech Stack

### Python POC

| Library | Role | Notes |
|---------|------|-------|
| `anthropic` SDK | AI agents | Tool use, prompt caching, streaming |
| `pydantic` v2 | State modeling | Typed, serializable, auto-validates decisions |
| `asyncio` | Agent concurrency | AI agents reason in parallel per phase |
| `aiosqlite` | Audit trail | Async writes don't block game loop |
| `ruamel.yaml` | Config | Preserves comments on round-trip; user-editable |
| `rich` / `textual` | Human agent UI | CLI state display; TUI for interactive play |
| `pytest` + `pytest-asyncio` | Testing | Rule-based agents as deterministic fixtures |

### Claude API Model Selection

| Use case | Model | Rationale |
|----------|-------|-----------|
| AI commander (turn decisions) | `claude-sonnet-4-6` | Best capability/cost for structured reasoning; cache persona across turns |
| AI advisor (recommendations) | `claude-sonnet-4-6` | Same model, different system prompt framing |
| High-stakes escalation | `claude-sonnet-4-6` + extended thinking | Surfaces reasoning chain for audit trail |
| After-action report | `claude-opus-4-7` | One call per game; highest analytical quality |
| Persona builder | `claude-sonnet-4-6` | One call per persona; tool use for typed YAML output |
| Rule-based agent | None | Zero API cost; used for testing and baseline runs |

**Caching strategy:** System prompt (persona + doctrine) cached across all turns for each AI commander. Only the intel report — which changes every turn — is uncached. On a 15-turn game with 3 AI commanders, cache hit rate on system prompts makes per-game API cost very low.

### Project Structure

```
agents/
├── engine/
│   ├── referee.py          # turn loop, phase transitions, outcome resolution
│   ├── simulation.py       # orbital domain model, asset catalog, conflict resolution
│   ├── state.py            # Pydantic models: GameState, Decision, CrisisEvent, etc.
│   └── events.py           # crisis event library, weighted generation
├── agents/
│   ├── base.py             # AgentInterface ABC
│   ├── human.py            # CLI/TUI agent — renders state, awaits input
│   ├── ai_commander.py     # Claude autonomous commander
│   ├── ai_advisor.py       # Claude advisory mode
│   └── rule_based.py       # deterministic strategy agent
├── personas/
│   ├── builder.py          # natural language → YAML via Claude API
│   ├── archetypes/         # preset archetype YAMLs (mahanian.yaml, etc.)
│   └── custom/             # user-created persona YAMLs
├── scenarios/
│   ├── pacific_crossroads.yaml
│   └── great_power_race.yaml
├── output/
│   ├── audit.py            # SQLite writer — real-time decision logging
│   ├── aar.py              # after-action report generator
│   └── strategy_lib.py     # strategy fingerprint accumulator
└── main.py                 # game launcher CLI
```

---

## Rust Migration Path

The migration is phased and non-disruptive. The `AgentInterface` ABC maps directly to a Rust trait. The gRPC contract between Python agents and Rust engine IS the trait — same methods, same types (Pydantic → protobuf → serde). No design changes on migration, only implementation language.

| Phase | What moves | Stays in Python |
|-------|-----------|-----------------|
| **Phase 1 — POC** | Nothing | Everything |
| **Phase 2 — Rust engine core** | `engine/` → Rust (tokio, serde); exposed via gRPC | Agents, persona builder, AAR generator |
| **Phase 3 — Rust agents** | Rule-based agents first (zero-cost); AI commanders if needed | Persona builder, AAR generator (one-off calls, not hot path) |

Phase 2 enables 1,000+ AI vs. AI simulation runs in parallel — the strategy library accumulates fast and the research value compounds.

---

## Out of Scope (POC)

- Real-time tempo (strategic turn cadence is minutes/hours between decisions, not real-time)
- Web UI (CLI/TUI only in POC)
- Multiplayer networking (all agents run locally in POC)
- Full orbital mechanics simulation (simplified orbital shell model, not Keplerian)
- Classified data integration

## Named Future Iterations

**Iteration 2 — Blue Water Expansion (Ziarnick / Carlson framework)**
Extend beyond Dolman's Earth-centric orbital node control into the wine dark sea:
- Cislunar space as a strategic theater with its own maneuver mechanics
- Space lines of communication (SLOC) as victory condition dimensions
- Lunar resource competition and projection logistics
- Commercial space power as a co-equal strategic variable (not a military modifier)
- Maneuver advantage over positional control — speed and depth, not chokepoints
- Economic coercion mechanics through space infrastructure dependency

**Iteration 3 — Rust Engine Core**
Port `engine/` to Rust for parallel AI vs. AI simulation at scale (see migration path above).

**Iteration 4 — Deep Space / Interplanetary**
Extend scenario geography to the belt, Mars, and L-points. Applicable once cislunar mechanics are proven.
