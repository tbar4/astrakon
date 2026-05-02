# engine/tech_tree.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from engine.state import FactionState

TRUNK_IDS = ["trunk_launch", "trunk_capacity", "trunk_budget", "trunk_sda", "trunk_resilience"]


@dataclass
class TechNode:
    id: str
    name: str
    desc: str
    tier: int               # 1 = trunk, 2 = T1, 3 = T2, 4 = T3, 5 = T4
    cost: int               # R&D points to unlock (before archetype discount)
    # '_any_trunk' means at least one trunk node must be unlocked before this can be taken.
    # All threat-tree T1 nodes use this so factions must invest in infrastructure first.
    prereqs: list[str]
    # archetype_discount: if this matches the faction's archetype, cost is reduced by 1.
    # Does NOT gate access — all factions can unlock any node.
    archetype_discount: str | None
    effect_type: str
    effect_params: dict = field(default_factory=dict)


TECH_NODES: list[TechNode] = [

    # ── Shared Trunk ──────────────────────────────────────────────────────────
    TechNode(
        id="trunk_launch", name="Efficient Launch",
        desc="LEO deployment divisor 5 → 4 (cheaper constellation expansion)",
        tier=1, cost=2, prereqs=[], archetype_discount=None,
        effect_type="leo_deploy", effect_params={"cost_divisor": 4},
    ),
    TechNode(
        id="trunk_capacity", name="Integrated Systems",
        desc="+1 max launch capacity (one-time, applied on unlock)",
        tier=1, cost=2, prereqs=[], archetype_discount=None,
        effect_type="budget_replenish", effect_params={"launch_capacity_bonus": 1},
    ),
    TechNode(
        id="trunk_budget", name="Resource Optimization",
        desc="+8 budget per turn",
        tier=1, cost=2, prereqs=[], archetype_discount=None,
        effect_type="budget_replenish", effect_params={"budget_bonus": 8},
    ),
    TechNode(
        id="trunk_sda", name="Space Domain Awareness",
        desc="+4 effective SDA sensors (one-time, applied on unlock); earlier detection of incoming approaches",
        tier=1, cost=2, prereqs=[], archetype_discount=None,
        effect_type="trunk_sda_onetime", effect_params={"sda_bonus": 4},
    ),
    TechNode(
        id="trunk_resilience", name="Hardened Systems",
        desc="Non-kinetic attacks (deniable, EW) destroy 1 fewer node per strike (min 0)",
        tier=1, cost=2, prereqs=[], archetype_discount=None,
        effect_type="resilience", effect_params={"damage_reduction": 1},
    ),

    # ── Tree 1: Kinetic Weapons ───────────────────────────────────────────────
    # Archetype discount: Mahanian (hard-power deterrence, force projection)
    TechNode(
        id="kin_ground_strike", name="Terrestrial Strike",
        desc="Ground-based attacks on adversary uplink/launch infrastructure. Prerequisite for all kinetic tree nodes.",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype_discount="mahanian",
        effect_type="kin_ground_strike", effect_params={},
    ),
    TechNode(
        id="kin_da_asat", name="Direct-Ascent ASAT",
        desc="Kinetic interceptor destroys 2 nodes instead of 1 per strike",
        tier=3, cost=4, prereqs=["kin_ground_strike"], archetype_discount="mahanian",
        effect_type="asat_kinetic", effect_params={"nodes_destroyed_bonus": 1},
    ),
    TechNode(
        id="kin_deterrence", name="Deterrence Operations",
        desc="+15 military deterrence score per turn",
        tier=3, cost=4, prereqs=["kin_ground_strike"], archetype_discount="mahanian",
        effect_type="deterrence", effect_params={"deterrence_bonus": 15},
    ),
    TechNode(
        id="kin_rapid_ascent", name="Rapid Ascent",
        desc="Kinetic interceptors resolve same turn they are launched (no 2-turn transit). Also grants once-per-game free strike that does not consume a weapon.",
        tier=4, cost=5, prereqs=["kin_da_asat"], archetype_discount="mahanian",
        effect_type="rapid_ascent_active", effect_params={"same_turn_resolve": True},
    ),
    TechNode(
        id="kin_intercept_k", name="Kinetic Intercept",
        desc="When your satellites are struck by a kinetic attack, emergency procurement grants +1 ASAT kinetic. Represents resilient deterrence posture.",
        tier=4, cost=5, prereqs=["kin_deterrence"], archetype_discount="mahanian",
        effect_type="emergency_procurement", effect_params={"asat_on_struck": 1},
    ),
    TechNode(
        id="kin_cascade_doctrine", name="Kessler Doctrine",
        desc="[T4 DOCTRINE] Deliberate cascade: once per game, trigger debris saturation of a shell. Destroys ~30% of all nodes in that shell for all factions. Extreme escalation.",
        tier=5, cost=8, prereqs=["kin_rapid_ascent"], archetype_discount="mahanian",
        effect_type="kin_cascade_immunity", effect_params={},
    ),

    # ── Tree 2: Non-Kinetic Weapons ───────────────────────────────────────────
    # Archetype discount: Rogue Accelerationist (chaos doctrine, debris amplification)
    TechNode(
        id="nk_dazzle", name="Laser Dazzle",
        desc="Directed-energy blinding of adversary SDA sensors. Prerequisite for all non-kinetic tree nodes.",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype_discount="rogue_accelerationist",
        effect_type="nk_dazzle", effect_params={},
    ),
    TechNode(
        id="nk_directed_energy", name="Directed Energy Weapon",
        desc="Space-based laser destroys 1 adversary node with no debris created. Activated via gray_zone op.",
        tier=3, cost=4, prereqs=["nk_dazzle"], archetype_discount="rogue_accelerationist",
        effect_type="nk_directed_energy", effect_params={},
    ),
    TechNode(
        id="nk_debris_doctrine", name="Debris Doctrine",
        desc="Kinetic strikes generate 2× debris — deliberately weaponizing orbital pollution",
        tier=3, cost=4, prereqs=["nk_dazzle"], archetype_discount="rogue_accelerationist",
        effect_type="asat_kinetic", effect_params={"debris_multiplier": 2.0},
    ),
    TechNode(
        id="nk_power_projection", name="Power Projection",
        desc="GEO and cislunar deployment: multiply allocated pts by 1.25× before cost formula. Reach beyond LEO economically.",
        tier=4, cost=5, prereqs=["nk_directed_energy"], archetype_discount="rogue_accelerationist",
        effect_type="geo_deploy", effect_params={"pts_multiplier": 1.25},
    ),
    TechNode(
        id="nk_precision_de", name="Precision DE",
        desc="Directed-energy weapon can disable a satellite (offline 2 turns) rather than destroy it. No debris either way.",
        tier=4, cost=5, prereqs=["nk_debris_doctrine"], archetype_discount="rogue_accelerationist",
        effect_type="nk_precision_de", effect_params={},
    ),
    TechNode(
        id="nk_starfish", name="Starfish Prime Doctrine",
        desc="[T4 DOCTRINE] Once per game: high-altitude nuclear detonation creates wide-area EMP. Destroys ~40% of nodes in target shell for ALL factions. Permanent debris. Maximum escalation.",
        tier=5, cost=8, prereqs=["nk_power_projection"], archetype_discount="rogue_accelerationist",
        effect_type="nk_starfish_doctrine", effect_params={},
    ),

    # ── Tree 3: Electronic Weapons ────────────────────────────────────────────
    # Archetype discount: Gray Zone (deniability, below-threshold operations)
    TechNode(
        id="ew_jamming", name="Signal Jamming",
        desc="Electronic warfare disrupts adversary satellite comms in target shell. Prerequisite for all EW tree nodes.",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype_discount="gray_zone",
        effect_type="ew_jamming", effect_params={},
    ),
    TechNode(
        id="ew_wideband", name="Wide-Band Jamming",
        desc="EW jammers affect target shell + one adjacent shell simultaneously",
        tier=3, cost=4, prereqs=["ew_jamming"], archetype_discount="gray_zone",
        effect_type="jamming_radius", effect_params={"extend_to_adjacent": True},
    ),
    TechNode(
        id="ew_spoofing", name="GPS Spoofing",
        desc="Manipulate adversary navigation signals. Their kinetic intercept success rate −20% while this is held.",
        tier=3, cost=4, prereqs=["ew_jamming"], archetype_discount="gray_zone",
        effect_type="ew_spoofing", effect_params={"intercept_accuracy_penalty": 0.2},
    ),
    TechNode(
        id="ew_signature_mask", name="Signature Masking",
        desc="Adversary SDA reports your ASAT-deniable count as 0, and LEO node count as 75% of actual. Denies accurate intelligence.",
        tier=4, cost=5, prereqs=["ew_wideband"], archetype_discount="gray_zone",
        effect_type="adversary_estimate", effect_params={"asat_deniable_visible": False, "leo_visibility_fraction": 0.75},
    ),
    TechNode(
        id="ew_deep_influence", name="Deep Influence",
        desc="Gray-zone influence operations reduce adversary coalition loyalty 0.05 → 0.15 per op",
        tier=4, cost=5, prereqs=["ew_spoofing"], archetype_discount="gray_zone",
        effect_type="gray_zone_loyalty", effect_params={"loyalty_reduction": 0.15},
    ),
    TechNode(
        id="ew_full_spectrum", name="Full-Spectrum Denial",
        desc="[T4 DOCTRINE] Once per game: combined jam + spoof + uplink denial freezes all adversary operations for 1 full turn.",
        tier=5, cost=8, prereqs=["ew_signature_mask"], archetype_discount="gray_zone",
        effect_type="ew_full_spectrum_doctrine", effect_params={},
    ),

    # ── Tree 4: Cyber Operations ──────────────────────────────────────────────
    # Archetype discount: Commercial Broker (dual-use infrastructure, supply chain leverage)
    TechNode(
        id="cyber_intrusion", name="Command Link Intrusion",
        desc="Cyber intrusion capability: prerequisite for all cyber tree nodes. Passively improves deniable-op attribution resistance.",
        tier=2, cost=3, prereqs=["_any_trunk"], archetype_discount="commercial_broker",
        effect_type="cyber_intrusion", effect_params={},
    ),
    TechNode(
        id="com_market", name="Market Dominance",
        desc="Commercial income multiplier 1.0× → 1.6×",
        tier=3, cost=4, prereqs=["cyber_intrusion"], archetype_discount="commercial_broker",
        effect_type="commercial_income", effect_params={"income_multiplier": 1.6},
    ),
    TechNode(
        id="com_revenue", name="Capacity Revenue",
        desc="+3 budget/turn per launch capacity unit",
        tier=3, cost=4, prereqs=["cyber_intrusion"], archetype_discount="commercial_broker",
        effect_type="budget_replenish", effect_params={"per_capacity_bonus": 3},
    ),
    TechNode(
        id="com_network", name="Orbital Network",
        desc="Market share formula includes MEO nodes (weighted 2×)",
        tier=4, cost=5, prereqs=["com_market"], archetype_discount="commercial_broker",
        effect_type="market_share", effect_params={"include_meo": True},
    ),
    TechNode(
        id="com_economics", name="Scale Economics",
        desc="Passive budget: min(node_count × 0.5, 20)/turn",
        tier=4, cost=5, prereqs=["com_revenue"], archetype_discount="commercial_broker",
        effect_type="budget_replenish", effect_params={"scale_bonus": True},
    ),
    TechNode(
        id="cyber_darknet", name="Space Darknet",
        desc="[T4 DOCTRINE] Establish covert comms: your next 3 turns of gray_zone ops are detected but never attributed. Coalition loyalty immune to adversary influence during window.",
        tier=5, cost=8, prereqs=["com_network"], archetype_discount="commercial_broker",
        effect_type="cyber_darknet_doctrine", effect_params={},
    ),
]

NODE_BY_ID: dict[str, TechNode] = {n.id: n for n in TECH_NODES}


def effective_cost(node: TechNode, archetype: str | None) -> int:
    """Return R&D cost after applying archetype discount (-1 if archetype matches)."""
    if node.archetype_discount and node.archetype_discount == archetype:
        return max(1, node.cost - 1)
    return node.cost


def prereqs_met(node: TechNode, unlocked: list[str]) -> bool:
    has_any_trunk = any(tid in unlocked for tid in TRUNK_IDS)
    for p in node.prereqs:
        if p == "_any_trunk":
            if not has_any_trunk:
                return False
        elif p not in unlocked:
            return False
    return True


def get_available_nodes(faction_state: "FactionState", rd_points: int) -> list[TechNode]:
    """Return nodes that can be unlocked: prereqs met, not already unlocked, enough R&D pts.
    All nodes are available to all factions — archetype_discount reduces cost but never gates access.
    """
    unlocked = faction_state.unlocked_techs
    archetype = faction_state.archetype
    result = []
    for node in TECH_NODES:
        if node.id in unlocked:
            continue
        cost = effective_cost(node, archetype)
        if rd_points < cost:
            continue
        if not prereqs_met(node, unlocked):
            continue
        result.append(node)
    return result


# NOTE: Several effect_types are handled directly in referee.py with NO dispatcher case here:
# - "deterrence" (kin_deterrence): _update_faction_metrics adds +15 deterrence score directly
# - "kin_cascade_immunity" (kin_cascade_doctrine): debris_engine.apply_debris_effects checks unlocked_techs
# - "trunk_sda_onetime" (trunk_sda): applied as one-time +sda_sensors in resolve_investment
# - "emergency_procurement" (kin_intercept_k): _resolve_kinetic_approach checks unlocked_techs
# - "rapid_ascent_active" context is checked via direct ID lookup in referee.py approach dict
# Calling apply_passive_effects with these context strings will raise ValueError (by design).
def apply_passive_effects(faction_state: "FactionState", context: str) -> dict:
    """Return a modifier dict for the given context key."""
    unlocked = faction_state.unlocked_techs

    if context == "leo_deploy":
        return {"cost_divisor": 4 if "trunk_launch" in unlocked else 5}

    if context == "geo_deploy":
        return {"pts_multiplier": 1.25 if "nk_power_projection" in unlocked else 1.0}

    if context == "cis_deploy":
        return {"pts_multiplier": 1.25 if "nk_power_projection" in unlocked else 1.0}

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
        return {"budget_bonus": budget_bonus}

    if context == "asat_kinetic":
        return {
            "nodes_destroyed_bonus": 1 if "kin_da_asat" in unlocked else 0,
            "debris_multiplier": 2.0 if "nk_debris_doctrine" in unlocked else 1.0,
            # kin_rapid_ascent absorbs the old rog_shock free-strike capability
            "free_strike": "kin_rapid_ascent" in unlocked and not faction_state.rog_shock_used,
        }

    if context == "adversary_estimate":
        return {
            "asat_deniable_visible": "ew_signature_mask" not in unlocked,
            # ew_signature_mask combines old gz_masking + gz_ghost into one node
            "leo_visibility_fraction": 0.75 if "ew_signature_mask" in unlocked else 1.0,
        }

    if context == "market_share":
        return {"include_meo": "com_network" in unlocked}

    if context == "jamming_radius":
        return {"extend_to_adjacent": "ew_wideband" in unlocked}

    if context == "gray_zone_loyalty":
        return {"loyalty_reduction": 0.15 if "ew_deep_influence" in unlocked else 0.05}

    if context == "resilience":
        return {"damage_reduction": 1 if "trunk_resilience" in unlocked else 0}

    if context == "ew_spoofing":
        return {"intercept_accuracy_penalty": 0.2 if "ew_spoofing" in unlocked else 0.0}

    raise ValueError(f"Unknown tech effect context: {context!r}")
