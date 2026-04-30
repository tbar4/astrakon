# api/runner.py
import uuid
from pathlib import Path
from typing import Optional

from engine.state import Phase, Decision, FactionState, CoalitionState
from engine.simulation import SimulationEngine
from engine.referee import GameReferee
from agents.base import AgentInterface
from agents.web import WebAgent, HumanInputRequired
from agents.rule_based import MahanianAgent
from scenarios.loader import load_scenario, Scenario
from output.audit import AuditTrail
from tui.header import NullGameHeader
from api.models import GameState, GameStateResponse
from api.session import save_session, load_session

_SCENARIOS_DIR = Path("scenarios")
_SESSIONS_DB = "output/sessions.db"


def _load_scenario(scenario_id: str) -> Scenario:
    return load_scenario(_SCENARIOS_DIR / f"{scenario_id}.yaml")


def _make_agents(scenario: Scenario, agent_config: list[dict]) -> dict[str, AgentInterface]:
    cfg_map = {c["faction_id"]: c for c in agent_config}
    agents = {}
    for faction in scenario.factions:
        cfg = cfg_map.get(faction.faction_id, {})
        agent_type = cfg.get("agent_type", "rule_based")
        if agent_type == "web":
            agent = WebAgent()
        elif agent_type == "ai_commander":
            from agents.ai_commander import AICommanderAgent
            from personas.builder import load_archetype
            import io
            from ruamel.yaml import YAML
            yaml = YAML()
            buf = io.StringIO()
            yaml.dump(load_archetype(faction.archetype), buf)
            agent = AICommanderAgent(persona_yaml=buf.getvalue())
        else:
            agent = MahanianAgent()
        agent.initialize(faction)
        agents[faction.faction_id] = agent
    return agents


def _make_referee(scenario: Scenario, agents: dict, state: GameState, audit: "AuditTrail | None" = None) -> tuple:
    """Create a GameReferee pre-loaded with serialized game state."""
    if audit is None:
        Path("output").mkdir(exist_ok=True)
        audit = AuditTrail(f"output/game_audit_{state.session_id[:8]}.db")
    referee = GameReferee(scenario=scenario, agents=agents, audit=audit, header=NullGameHeader())
    referee.load_mutable_state(
        faction_states=state.faction_states,
        coalition_states=state.coalition_states,
        tension_level=state.tension_level,
        debris_level=state.debris_level,
        turn_log=state.turn_log,
        turn_log_summary=state.turn_log_summary,
        coordination_bonuses=state.coordination_bonuses,
        event_sda_malus=state.event_sda_malus,
        prev_turn_ops=state.prev_turn_ops,
        pending_kinetic_approaches=state.pending_kinetic_approaches,
        current_turn=state.turn,
        initial_assets=state.initial_assets,
    )
    return referee, audit


def _sync_state_from_referee(state: GameState, referee: GameReferee) -> None:
    """Write referee's mutable state back into GameState."""
    mutable = referee.dump_mutable_state()
    state.faction_states = {
        fid: FactionState.model_validate(fs) for fid, fs in mutable["faction_states"].items()
    }
    state.coalition_states = {
        cid: CoalitionState.model_validate(cs) for cid, cs in mutable["coalition_states"].items()
    }
    state.tension_level = mutable["tension_level"]
    state.debris_level = mutable["debris_level"]
    state.turn_log = mutable["turn_log"]
    state.turn_log_summary = mutable["turn_log_summary"]
    state.coordination_bonuses = mutable["coordination_bonuses"]
    state.event_sda_malus = mutable["event_sda_malus"]
    state.prev_turn_ops = mutable["prev_turn_ops"]
    state.pending_kinetic_approaches = mutable["pending_kinetic_approaches"]


def _compute_dominance(state: GameState, sim: SimulationEngine) -> dict[str, float]:
    all_assets = {fid: fs.assets for fid, fs in state.faction_states.items()}
    return {
        cid: sim.compute_coalition_dominance(cs.member_ids, all_assets)
        for cid, cs in state.coalition_states.items()
    }


def _check_victory(state: GameState, sim: SimulationEngine, scenario: Scenario) -> Optional[str]:
    dominance = _compute_dominance(state, sim)
    for cid, dom in dominance.items():
        if dom >= state.victory_threshold:
            return cid
    return None


async def create_game(
    scenario_id: str,
    agent_config: list[dict],
    db_path: str = _SESSIONS_DB,
) -> GameState:
    scenario = _load_scenario(scenario_id)
    session_id = str(uuid.uuid4())
    human_faction_ids = [c["faction_id"] for c in agent_config if c["agent_type"] == "web"]
    human_faction_id = human_faction_ids[0] if human_faction_ids else agent_config[0]["faction_id"]
    use_advisor = next(
        (c.get("use_advisor", False) for c in agent_config if c["faction_id"] == human_faction_id),
        False,
    )
    faction_states = {
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
    coalition_states = {
        cid: CoalitionState(coalition_id=cid, member_ids=c.member_ids)
        for cid, c in scenario.coalitions.items()
    }
    coalition_colors = {
        cid: ("green" if i == 0 else "red")
        for i, cid in enumerate(scenario.coalitions)
    }
    state = GameState(
        session_id=session_id,
        scenario_id=scenario_id,
        scenario_name=scenario.name,
        turn=0,
        total_turns=scenario.turns,
        current_phase=Phase.INVEST,
        faction_states=faction_states,
        coalition_states=coalition_states,
        human_faction_id=human_faction_id,
        human_faction_ids=human_faction_ids,
        use_advisor=use_advisor,
        agent_config=agent_config,
        victory_threshold=scenario.victory.coalition_orbital_dominance,
        coalition_colors=coalition_colors,
        initial_assets={f.faction_id: f.starting_assets.model_dump() for f in scenario.factions},
    )
    await save_session(state, db_path=db_path)
    return state


async def advance(
    session_id: str,
    decision: Optional[dict] = None,
    db_path: str = _SESSIONS_DB,
) -> GameStateResponse:
    state = await load_session(session_id, db_path=db_path)
    if state is None:
        raise ValueError(f"Session {session_id} not found")

    state.error = None
    scenario = _load_scenario(state.scenario_id)
    sim = SimulationEngine()

    # Handle inter-turn: frontend called /advance after viewing summary
    if state.awaiting_next_turn:
        state.turn += 1
        state.turn_log = []
        state.events = []
        state.phase_decisions = {}
        state.awaiting_next_turn = False
        _replenish_budgets(state, scenario)
        await save_session(state, db_path=db_path)

    # Start turn 1 if new game
    if state.turn == 0:
        state.turn = 1
        state.turn_log = []
        state.events = []
        state.phase_decisions = {}
        _replenish_budgets(state, scenario)
        await save_session(state, db_path=db_path)

    # Apply human decision if provided
    if decision:
        phase = Phase(decision["phase"])
        dec_payload = {
            "phase": phase.value,
            "faction_id": state.human_faction_id,
        }
        # Merge decision fields into payload
        for k, v in decision.get("decision", {}).items():
            dec_payload[k] = v
        dec = Decision.model_validate(dec_payload)
        state.phase_decisions[state.human_faction_id] = dec.model_dump_json()
        await save_session(state, db_path=db_path)

    # Drive turn loop until human input needed or game over
    faction_ids = sorted(state.faction_states.keys())
    agents = _make_agents(scenario, state.agent_config)

    while not state.game_over:
        undecided = [fid for fid in faction_ids if fid not in state.phase_decisions]

        if not undecided:
            # All decided — resolve this phase
            referee, audit = _make_referee(scenario, agents, state)
            try:
                if state.current_phase == Phase.INVEST:
                    await audit.initialize()
                    await referee.resolve_investment(state.turn, state.phase_decisions)
                    _sync_state_from_referee(state, referee)
                    state.phase_decisions = {}
                    state.current_phase = Phase.OPERATIONS
                    referee.resolve_pending_kinetics(state.turn)
                    _sync_state_from_referee(state, referee)

                elif state.current_phase == Phase.OPERATIONS:
                    await audit.initialize()
                    await referee.resolve_operations(state.turn, state.phase_decisions)
                    _sync_state_from_referee(state, referee)
                    state.phase_decisions = {}
                    # Generate events before RESPONSE
                    events = referee.generate_turn_events(state.turn)
                    _sync_state_from_referee(state, referee)
                    state.events = [
                        {
                            "event_id": e.event_id,
                            "event_type": e.event_type,
                            "description": e.description,
                            "severity": e.severity,
                            "affected_factions": e.affected_factions,
                        }
                        for e in events
                    ]
                    state.current_phase = Phase.RESPONSE

                elif state.current_phase == Phase.RESPONSE:
                    await audit.initialize()
                    from engine.state import CrisisEvent
                    crisis_events = [CrisisEvent.model_validate(e) for e in state.events]
                    await referee.resolve_response(state.turn, state.phase_decisions, crisis_events)
                    _sync_state_from_referee(state, referee)
                    referee._update_faction_metrics()
                    _sync_state_from_referee(state, referee)
                    state.phase_decisions = {}
                    state.current_phase = Phase.INVEST  # signals "summary" to frontend
                    state.game_over = False

                    # Check victory
                    winner = _check_victory(state, sim, scenario)
                    if winner or state.turn >= state.total_turns:
                        state.game_over = True
                        state.result = {
                            "turns_completed": state.turn,
                            "winner_coalition": winner,
                            "final_dominance": _compute_dominance(state, sim),
                        }
                    else:
                        # Advance to next turn — but return summary first
                        # Frontend shows TurnSummary then calls /advance to start next turn
                        state.awaiting_next_turn = True
                        await save_session(state, db_path=db_path)
                        break  # return state to frontend for summary display

            finally:
                await audit.close()

            await save_session(state, db_path=db_path)
            continue

        # Process next undecided faction
        next_fid = undecided[0]
        agent = agents[next_fid]

        if next_fid in state.human_faction_ids:
            # Build snapshot for the currently-active human player
            state.human_faction_id = next_fid
            referee, audit = _make_referee(scenario, agents, state)
            available = {
                Phase.INVEST: ["allocate_budget"],
                Phase.OPERATIONS: ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"],
                Phase.RESPONSE: ["escalate", "de_escalate", "retaliate", "public_statement"],
            }[state.current_phase]
            state.human_snapshot = referee._build_snapshot(
                next_fid, state.current_phase, available
            ).model_dump()
            await save_session(state, db_path=db_path)
            break  # waiting for human

        # AI agent
        referee, audit = _make_referee(scenario, agents, state)
        available = {
            Phase.INVEST: ["allocate_budget"],
            Phase.OPERATIONS: ["task_assets", "coordinate", "gray_zone", "alliance_move", "signal"],
            Phase.RESPONSE: ["escalate", "de_escalate", "retaliate", "public_statement"],
        }[state.current_phase]
        agent.receive_state(referee._build_snapshot(next_fid, state.current_phase, available))

        try:
            dec = await agent.submit_decision(state.current_phase)
            state.phase_decisions[next_fid] = dec.model_dump_json()
        except Exception as e:
            state.error = f"AI agent error: {e}"
            fallback = MahanianAgent()
            fallback.initialize(next(f for f in scenario.factions if f.faction_id == next_fid))
            fallback.receive_state(referee._build_snapshot(next_fid, state.current_phase, available))
            dec = await fallback.submit_decision(state.current_phase)
            state.phase_decisions[next_fid] = dec.model_dump_json()

        await save_session(state, db_path=db_path)  # checkpoint after each agent

    dominance = _compute_dominance(state, sim)
    return GameStateResponse(state=state, coalition_dominance=dominance)


def _replenish_budgets(state: GameState, scenario: Scenario) -> None:
    for faction in scenario.factions:
        fs = state.faction_states.get(faction.faction_id)
        if not fs:
            continue
        fs.current_budget = faction.budget_per_turn
        cid = faction.coalition_id
        if cid and cid in scenario.coalitions and scenario.coalitions[cid].hegemony_pool:
            fs.current_budget = int(fs.current_budget * 1.1)
        # Process deferred returns
        due = [r for r in fs.deferred_returns if r["turn_due"] <= state.turn]
        for r in due:
            if r["category"] == "r_and_d":
                fs.tech_tree["r_and_d"] = fs.tech_tree.get("r_and_d", 0) + r["amount"] // 20
            elif r["category"] == "education":
                fs.tech_tree["education"] = fs.tech_tree.get("education", 0) + r["amount"] // 30
        fs.deferred_returns = [r for r in fs.deferred_returns if r["turn_due"] > state.turn]
