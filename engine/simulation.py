import random
from dataclasses import dataclass
from engine.state import FactionAssets, InvestmentAllocation


@dataclass
class InvestmentResult:
    immediate_assets: FactionAssets
    deferred_returns: list[dict]  # [{turn_due, category, amount, faction_id}]
    budget_spent: int


class InvestmentResolver:
    CONSTELLATION_NODE_COST = 5
    SDA_SENSOR_COST = 8
    LAUNCH_CAPACITY_COST = 15
    ASAT_KINETIC_COST = 20
    ASAT_DENIABLE_COST = 25
    EW_JAMMER_COST = 12

    RD_DELAY = 3
    EDUCATION_DELAY = 6

    def resolve(
        self, faction_id: str, budget: int,
        allocation: InvestmentAllocation, turn: int
    ) -> InvestmentResult:
        deferred = []
        spent = 0
        leo_nodes = 0
        launch_capacity = 0
        asat_deniable = 0
        ew_jammers = 0

        if allocation.constellation > 0:
            pts = int(budget * allocation.constellation)
            nodes = pts // self.CONSTELLATION_NODE_COST
            leo_nodes += nodes
            spent += nodes * self.CONSTELLATION_NODE_COST

        if allocation.launch_capacity > 0:
            pts = int(budget * allocation.launch_capacity)
            capacity = pts // self.LAUNCH_CAPACITY_COST
            launch_capacity += capacity
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
            asat_deniable += asat
            spent += asat * self.ASAT_DENIABLE_COST

        if allocation.influence_ops > 0:
            pts = int(budget * allocation.influence_ops)
            jammers = pts // self.EW_JAMMER_COST
            ew_jammers += jammers
            spent += jammers * self.EW_JAMMER_COST

        immediate = FactionAssets(
            leo_nodes=leo_nodes,
            launch_capacity=launch_capacity,
            asat_deniable=asat_deniable,
            ew_jammers=ew_jammers,
        )
        return InvestmentResult(
            immediate_assets=immediate,
            deferred_returns=deferred,
            budget_spent=spent,
        )


class SDAFilter:
    def filter(
        self, adversary_assets: FactionAssets, observer_sda_level: float
    ) -> FactionAssets:
        leo_nodes = int(adversary_assets.leo_nodes * min(observer_sda_level + 0.3, 1.0))
        geo_nodes = int(adversary_assets.geo_nodes * min(observer_sda_level + 0.4, 1.0))
        asat_kinetic = 0
        asat_deniable = 0
        if observer_sda_level >= 0.3:
            asat_kinetic = int(adversary_assets.asat_kinetic * observer_sda_level)
        if observer_sda_level >= 0.6:
            asat_deniable = round(adversary_assets.asat_deniable * (observer_sda_level - 0.5))
        ew_jammers = int(adversary_assets.ew_jammers * observer_sda_level)
        return FactionAssets(
            leo_nodes=leo_nodes,
            geo_nodes=geo_nodes,
            asat_kinetic=asat_kinetic,
            asat_deniable=asat_deniable,
            ew_jammers=ew_jammers,
        )


class ConflictResolver:
    def resolve_kinetic_asat(
        self, attacker_assets: FactionAssets, target_assets: FactionAssets,
        attacker_sda_level: float
    ) -> dict:
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
        total_nodes = sum(a.total_orbital_nodes() for a in all_assets.values())
        if total_nodes == 0:
            return 0.0
        if faction_id not in all_assets:
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
