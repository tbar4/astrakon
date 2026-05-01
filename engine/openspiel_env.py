# engine/openspiel_env.py
from __future__ import annotations
import json
import pyspiel
from pathlib import Path
from engine.core_game import CoreGame
from engine.action_space import ActionSpace
from engine.state import FactionAssets, Phase
from scenarios.loader import load_scenario, Scenario

_GAME_TYPE = pyspiel.GameType(
    short_name="astrakon",
    long_name="Astrakon Space Wargame",
    dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
    chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
    information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
    utility=pyspiel.GameType.Utility.GENERAL_SUM,
    reward_model=pyspiel.GameType.RewardModel.TERMINAL,
    max_num_players=4,
    min_num_players=2,
    provides_information_state_string=True,
    provides_information_state_tensor=True,
    provides_observation_string=True,
    provides_observation_tensor=True,
    parameter_specification={"scenario_path": ""},
)


class AstrakonGame(pyspiel.Game):
    def __init__(self, params: dict | None = None):
        params = params or {}
        scenario_path = params.get("scenario_path", "scenarios/pacific_crossroads.yaml")
        self._scenario: Scenario = load_scenario(Path(scenario_path))
        self._action_space = ActionSpace(self._scenario)
        game_info = pyspiel.GameInfo(
            num_distinct_actions=self._action_space.TOTAL_ACTIONS,
            max_chance_outcomes=0,
            num_players=len(self._scenario.factions),
            min_utility=-1.0,
            max_utility=1.0,
            max_game_length=self._scenario.turns * 3 * len(self._scenario.factions),
        )
        super().__init__(_GAME_TYPE, game_info, params)

    def new_initial_state(self) -> "AstrakonState":
        core = CoreGame(self._scenario)
        return AstrakonState(self, core)

    def make_py_observer(self, iig_obs_type, params):
        return _AstrakonObserver(iig_obs_type, params, self._action_space, self._scenario)


try:
    pyspiel.register_game(_GAME_TYPE, AstrakonGame)
except Exception:
    pass  # already registered (e.g., if module is re-imported)


class AstrakonState(pyspiel.State):
    def __init__(self, game: AstrakonGame, core: CoreGame):
        super().__init__(game)
        self._game = game
        self._core = core

    def current_player(self) -> int:
        if self._core.is_terminal():
            return pyspiel.PlayerId.TERMINAL
        return self._core.acting_faction_idx()

    def _legal_actions(self, player: int) -> list[int]:
        """Override the C++ virtual — called by the public legal_actions() wrapper."""
        if self._core.is_terminal():
            return []
        return sorted(self._core.legal_actions(player))

    def _apply_action(self, action: int) -> None:
        self._core.apply_action(self._core.acting_faction_idx(), action)

    def _action_to_string(self, player: int, action: int) -> str:
        asp = self._core._action_space
        if action < asp.INVEST_COUNT:
            return asp.invest_portfolio_name(action)
        elif action < asp.OPS_OFFSET + asp.OPS_COUNT:
            entry = asp.ops_action_from_index(action)
            return f"ops:{entry['action_type']}:{entry.get('target_faction_id', 'none')}:{entry.get('mission', '')}"
        else:
            entry = asp.response_action_from_index(action)
            return f"resp:esc={entry['escalate']}:ret={entry['retaliate']}:{entry.get('target_faction_id', 'none')}"

    def is_terminal(self) -> bool:
        return self._core.is_terminal()

    def returns(self) -> list[float]:
        return self._core.returns()

    def information_state_string(self, player: int | None = None) -> str:
        if player is None:
            player = self._core.acting_faction_idx()
        return self._core.information_state_string(player)

    def information_state_tensor(self, player: int | None = None) -> list[float]:
        if player is None:
            player = self._core.acting_faction_idx()
        return _encode_information_state(self._core, player)

    def observation_string(self, player: int | None = None) -> str:
        if player is None:
            player = self._core.acting_faction_idx()
        core = self._core
        return (
            f"T{core.current_turn()}/{core._total_turns}|ESC{core.escalation_rung}|"
            "COAL:" + ",".join(f"{c}={d:.3f}" for c, d in sorted(core.coalition_dominance.items()))
        )

    def observation_tensor(self, player: int | None = None) -> list[float]:
        if player is None:
            player = self._core.acting_faction_idx()
        core = self._core
        result = []
        for _, d in sorted(core.coalition_dominance.items()):
            result.append(d)
        result.append(core.escalation_rung / 5.0)
        result.append(core.current_turn() / core._total_turns)
        for shell in ("leo", "meo", "geo", "cislunar"):
            result.append(core.debris_fields[shell])
        return result

    def serialize(self) -> str:
        core = self._core
        return json.dumps({
            "turn": core._turn,
            "phase": core._phase.value,
            "acting_faction_idx": core._acting_faction_idx,
            "escalation_rung": core.escalation_rung,
            "debris_fields": core.debris_fields,
            "coalition_dominance": core.coalition_dominance,
            "winner_coalition": core._winner_coalition,
            "draw": core._draw,
            "faction_states": {
                fid: {
                    "current_budget": fs.current_budget,
                    "assets": fs.assets.model_dump(),
                    "partial_invest": fs.partial_invest,
                }
                for fid, fs in core.faction_states.items()
            },
            "pending_kinetics": core.pending_kinetics,
        })

    def deserialize(self, data: str) -> None:
        d = json.loads(data)
        core = self._core
        core._turn = d["turn"]
        core._phase = Phase(d["phase"])
        core._acting_faction_idx = d["acting_faction_idx"]
        core.escalation_rung = d["escalation_rung"]
        core.debris_fields = d["debris_fields"]
        core.coalition_dominance = d["coalition_dominance"]
        core._winner_coalition = d["winner_coalition"]
        core._draw = d["draw"]
        for fid, fdata in d["faction_states"].items():
            fs = core.faction_states[fid]
            fs.current_budget = fdata["current_budget"]
            fs.assets = FactionAssets(**fdata["assets"])
            fs.partial_invest = fdata["partial_invest"]
        core.pending_kinetics = d["pending_kinetics"]

    def __str__(self) -> str:
        core = self._core
        lines = [f"Turn {core.current_turn()}/{core._total_turns} | Phase: {core.current_phase().value}"]
        for cid, dom in sorted(core.coalition_dominance.items()):
            lines.append(f"  {cid}: {dom:.1%}")
        return "\n".join(lines)


def _encode_information_state(core: CoreGame, player_idx: int) -> list[float]:
    """Encode information state as a float vector for neural network input."""
    fid = core.faction_order[player_idx]
    fs = core.faction_states[fid]
    a = fs.assets
    result = []

    _MAX = {"leo_nodes": 100, "meo_nodes": 40, "geo_nodes": 20, "cislunar_nodes": 10,
            "asat_kinetic": 20, "asat_deniable": 20, "ew_jammers": 20,
            "sda_sensors": 30, "relay_nodes": 20, "launch_capacity": 10}
    for field, cap in _MAX.items():
        result.append(min(getattr(a, field) / cap, 1.0))

    result.append(fs.deterrence_score / 100.0)
    result.append(fs.disruption_score / 100.0)
    result.append(fs.market_share)
    result.append(fs.current_budget / fs.budget_per_turn if fs.budget_per_turn > 0 else 0.0)

    for _, dom in sorted(core.coalition_dominance.items()):
        result.append(dom)

    for other_fid, other_fs in sorted(core.faction_states.items()):
        if other_fs.coalition_id != fs.coalition_id:
            est = core._estimate_adversary_assets(fid, other_fid)
            for field, cap in _MAX.items():
                result.append(min(getattr(est, field) / cap, 1.0))

    for other_fid, other_fs in sorted(core.faction_states.items()):
        if other_fid != fid and other_fs.coalition_id == fs.coalition_id:
            oa = other_fs.assets
            for field, cap in _MAX.items():
                result.append(min(getattr(oa, field) / cap, 1.0))

    result.append(core.escalation_rung / 5.0)
    for shell in ("leo", "meo", "geo", "cislunar"):
        result.append(core.debris_fields[shell])
    result.append(core.current_turn() / core._total_turns)
    result.append(core._total_turns / 20.0)

    result.append(1.0 if core.current_phase() == Phase.INVEST else 0.0)
    result.append(1.0 if core.current_phase() == Phase.OPERATIONS else 0.0)
    result.append(1.0 if core.current_phase() == Phase.RESPONSE else 0.0)

    return result


class _AstrakonObserver:
    """Required by OpenSpiel's make_py_observer protocol.

    OpenSpiel's random_sim_test and related utilities expect:
      - .tensor  — flat list/array of floats
      - .dict    — dict of named tensor pieces (may be empty for custom games)
      - .set_from(state, player) — populate tensor from state
      - .string_from(state, player) -> str — human-readable observation
    """

    def __init__(self, iig_obs_type, params, action_space: ActionSpace, scenario: Scenario):
        self._iig_obs_type = iig_obs_type
        self._action_space = action_space
        self._tensor: list[float] = []
        self.dict: dict = {}

    def set_from(self, state: AstrakonState, player: int) -> None:
        self._tensor = state.information_state_tensor(player)
        # Expose tensor as a single named piece so callers iterating .dict work
        self.dict = {"observation": self._tensor}

    def string_from(self, state: AstrakonState, player: int) -> str:
        return state.information_state_string(player)

    @property
    def tensor(self) -> list[float]:
        return self._tensor
