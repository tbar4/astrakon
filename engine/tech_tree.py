# engine/tech_tree.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.state import FactionState

TRUNK_IDS = ["trunk_launch", "trunk_capacity", "trunk_budget"]


@dataclass
class TechNode:
    id: str
    name: str
    desc: str
    tier: int           # 1 = trunk, 2 = branch T2, 3 = branch T3
    cost: int           # R&D points to unlock
    prereqs: list[str]  # node IDs required; '_any_trunk' = any trunk node
    archetype: str | None  # None = all factions; else specific archetype ID
    effect_type: str
    effect_params: dict = field(default_factory=dict)


TECH_NODES: list[TechNode] = [
    # ── Shared trunk ──────────────────────────────────────────────────────────
    TechNode(
        id="trunk_launch", name="Efficient Launch",
        desc="LEO deployment divisor changes 5 → 4",
        tier=1, cost=2, prereqs=[], archetype=None,
        effect_type="leo_deploy", effect_params={"cost_divisor": 4},
    ),
    TechNode(
        id="trunk_capacity", name="Integrated Systems",
        desc="+1 max launch capacity",
        tier=1, cost=2, prereqs=[], archetype=None,
        effect_type="budget_replenish", effect_params={"launch_capacity_bonus": 1},
    ),
    TechNode(
        id="trunk_budget", name="Resource Optimization",
        desc="+8 budget per turn",
        tier=1, cost=2, prereqs=[], archetype=None,
        effect_type="budget_replenish", effect_params={"budget_bonus": 8},
    ),
    # ── Mahanian ──────────────────────────────────────────────────────────────
    TechNode(
        id="mah_strike", name="Kinetic Doctrine",
        desc="Kinetic ASAT destroys 2 nodes instead of 1",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype="mahanian",
        effect_type="asat_kinetic", effect_params={"nodes_destroyed_bonus": 1},
    ),
    TechNode(
        id="mah_deterrence", name="Deterrence Operations",
        desc="+15 military deterrence score/turn",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype="mahanian",
        effect_type="deterrence", effect_params={"deterrence_bonus": 15},
    ),
    TechNode(
        id="mah_escalation", name="Escalation Response",
        desc="Gain +1 ASAT kinetic when targeted by kinetic strike (emergency procurement)",
        tier=3, cost=5, prereqs=["mah_strike"], archetype="mahanian",
        effect_type="asat_kinetic", effect_params={"emergency_procurement": True},
    ),
    TechNode(
        id="mah_projection", name="Power Projection",
        desc="GEO/CIS deployment: multiply allocated pts by 1.25 before cost formula",
        tier=3, cost=5, prereqs=["mah_deterrence"], archetype="mahanian",
        effect_type="geo_deploy", effect_params={"pts_multiplier": 1.25},
    ),
    # ── Commercial Broker ─────────────────────────────────────────────────────
    TechNode(
        id="com_market", name="Market Dominance",
        desc="Commercial income multiplier: 1.0× → 1.6×",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype="commercial_broker",
        effect_type="commercial_income", effect_params={"income_multiplier": 1.6},
    ),
    TechNode(
        id="com_revenue", name="Capacity Revenue",
        desc="+3 budget/turn per launch capacity unit",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype="commercial_broker",
        effect_type="budget_replenish", effect_params={"per_capacity_bonus": 3},
    ),
    TechNode(
        id="com_network", name="Orbital Network",
        desc="Market share formula includes MEO nodes (weighted 2×)",
        tier=3, cost=5, prereqs=["com_market"], archetype="commercial_broker",
        effect_type="market_share", effect_params={"include_meo": True},
    ),
    TechNode(
        id="com_economics", name="Scale Economics",
        desc="Passive budget: min(node_count × 0.5, 20)/turn",
        tier=3, cost=5, prereqs=["com_revenue"], archetype="commercial_broker",
        effect_type="budget_replenish", effect_params={"scale_bonus": True},
    ),
    # ── Gray Zone ─────────────────────────────────────────────────────────────
    TechNode(
        id="gz_masking", name="Signature Masking",
        desc="Your asat_deniable count reported as 0 in adversary SDA estimates",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype="gray_zone",
        effect_type="adversary_estimate", effect_params={"asat_deniable_visible": False},
    ),
    TechNode(
        id="gz_jamming", name="Wide-Band Jamming",
        desc="EW jammers affect target shell + one adjacent shell",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype="gray_zone",
        effect_type="jamming_radius", effect_params={"extend_to_adjacent": True},
    ),
    TechNode(
        id="gz_ghost", name="Ghost Presence",
        desc="LEO node count reported as int(count × 0.75) to adversary SDA",
        tier=3, cost=5, prereqs=["gz_masking"], archetype="gray_zone",
        effect_type="adversary_estimate", effect_params={"leo_visibility_fraction": 0.75},
    ),
    TechNode(
        id="gz_influence", name="Deep Influence",
        desc="Gray-zone loyalty reduction: 0.05 → 0.15 per op",
        tier=3, cost=5, prereqs=["gz_jamming"], archetype="gray_zone",
        effect_type="gray_zone_loyalty", effect_params={"loyalty_reduction": 0.15},
    ),
    # ── Rogue Accelerationist ─────────────────────────────────────────────────
    TechNode(
        id="rog_debris", name="Debris Doctrine",
        desc="Your kinetic strikes generate 2× debris",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype="rogue_accelerationist",
        effect_type="asat_kinetic", effect_params={"debris_multiplier": 2.0},
    ),
    TechNode(
        id="rog_ascent", name="Rapid Ascent",
        desc="Kinetic approaches resolve at end of RESPONSE phase of same turn",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype="rogue_accelerationist",
        effect_type="rog_ascent_active", effect_params={"same_turn_resolve": True},
    ),
    TechNode(
        id="rog_cascade", name="Kessler Cascade",
        desc="When a shell goes Kessler, your nodes in adjacent shells take no collateral damage",
        tier=3, cost=5, prereqs=["rog_debris"], archetype="rogue_accelerationist",
        effect_type="rog_cascade_immunity", effect_params={},
    ),
    TechNode(
        id="rog_shock", name="Shock Strike",
        desc="Once per game, one kinetic strike consumes 0 ASAT weapons",
        tier=3, cost=5, prereqs=["rog_ascent"], archetype="rogue_accelerationist",
        effect_type="asat_kinetic", effect_params={"free_strike": True},
    ),
]

_NODE_BY_ID: dict[str, TechNode] = {n.id: n for n in TECH_NODES}


def _prereqs_met(node: TechNode, unlocked: list[str]) -> bool:
    has_any_trunk = any(tid in unlocked for tid in TRUNK_IDS)
    for p in node.prereqs:
        if p == "_any_trunk":
            if not has_any_trunk:
                return False
        elif p not in unlocked:
            return False
    return True


def get_available_nodes(faction_state: "FactionState", rd_points: int) -> list[TechNode]:
    """Return nodes that can be unlocked: prereqs met, not already unlocked, archetype matches, enough R&D pts."""
    unlocked = faction_state.unlocked_techs
    archetype = faction_state.archetype
    result = []
    for node in TECH_NODES:
        if node.id in unlocked:
            continue
        if node.archetype is not None and node.archetype != archetype:
            continue
        if rd_points < node.cost:
            continue
        if not _prereqs_met(node, unlocked):
            continue
        result.append(node)
    return result


def apply_passive_effects(faction_state: "FactionState", context: str) -> dict:
    """Return a modifier dict for the given context key."""
    unlocked = faction_state.unlocked_techs

    if context == "leo_deploy":
        return {"cost_divisor": 4 if "trunk_launch" in unlocked else 5}

    if context == "geo_deploy":
        return {"pts_multiplier": 1.25 if "mah_projection" in unlocked else 1.0}

    if context == "cis_deploy":
        return {"pts_multiplier": 1.25 if "mah_projection" in unlocked else 1.0}

    if context == "commercial_income":
        return {"income_multiplier": 1.6 if "com_market" in unlocked else 1.0}

    if context == "budget_replenish":
        budget_bonus = 0
        if "trunk_budget" in unlocked:
            budget_bonus += 8
        if "com_revenue" in unlocked:
            budget_bonus += 3 * faction_state.assets.launch_capacity
        if "com_economics" in unlocked:
            total_nodes = (
                faction_state.assets.leo_nodes + faction_state.assets.meo_nodes
                + faction_state.assets.geo_nodes + faction_state.assets.cislunar_nodes
            )
            budget_bonus += int(min(total_nodes * 0.5, 20))
        return {
            "budget_bonus": budget_bonus,
            "launch_capacity_bonus": 1 if "trunk_capacity" in unlocked else 0,
        }

    if context == "asat_kinetic":
        return {
            "nodes_destroyed_bonus": 1 if "mah_strike" in unlocked else 0,
            "debris_multiplier": 2.0 if "rog_debris" in unlocked else 1.0,
            "free_strike": "rog_shock" in unlocked and not faction_state.rog_shock_used,
        }

    if context == "adversary_estimate":
        return {
            "asat_deniable_visible": "gz_masking" not in unlocked,
            "leo_visibility_fraction": 0.75 if "gz_ghost" in unlocked else 1.0,
        }

    if context == "market_share":
        return {"include_meo": "com_network" in unlocked}

    if context == "jamming_radius":
        return {"extend_to_adjacent": "gz_jamming" in unlocked}

    if context == "gray_zone_loyalty":
        return {"loyalty_reduction": 0.15 if "gz_influence" in unlocked else 0.05}

    if context == "rog_ascent_active":
        return {"same_turn_resolve": "rog_ascent" in unlocked}

    raise ValueError(f"Unknown tech effect context: {context!r}")
