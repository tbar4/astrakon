import random
from dataclasses import dataclass
from engine.state import FactionAssets, InvestmentAllocation


@dataclass
class InvestmentResult:
    immediate_assets: FactionAssets
    deferred_returns: list[dict]  # [{turn_due, category, amount, faction_id}]
    budget_spent: int


class InvestmentResolver:
    CONSTELLATION_NODE_COST = 5    # LEO — cheap, fast to deploy
    MEO_NODE_COST = 12             # GPS/navigation regime — 2× dominance weight
    GEO_NODE_COST = 25             # Strategic persistent orbit — 3× dominance weight
    CISLUNAR_NODE_COST = 40        # Strategic high ground — 4× dominance weight
    LAUNCH_CAPACITY_COST = 15
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
        meo_nodes = 0
        geo_nodes = 0
        cislunar_nodes = 0
        launch_capacity = 0
        asat_deniable = 0
        ew_jammers = 0

        if allocation.constellation > 0:
            pts = int(budget * allocation.constellation)
            nodes = pts // self.CONSTELLATION_NODE_COST
            leo_nodes += nodes
            spent += nodes * self.CONSTELLATION_NODE_COST

        if allocation.meo_deployment > 0:
            pts = int(budget * allocation.meo_deployment)
            nodes = pts // self.MEO_NODE_COST
            meo_nodes += nodes
            spent += nodes * self.MEO_NODE_COST

        if allocation.geo_deployment > 0:
            pts = int(budget * allocation.geo_deployment)
            nodes = pts // self.GEO_NODE_COST
            geo_nodes += nodes
            spent += nodes * self.GEO_NODE_COST

        if allocation.cislunar_deployment > 0:
            pts = int(budget * allocation.cislunar_deployment)
            nodes = pts // self.CISLUNAR_NODE_COST
            cislunar_nodes += nodes
            spent += nodes * self.CISLUNAR_NODE_COST

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
            meo_nodes=meo_nodes,
            geo_nodes=geo_nodes,
            cislunar_nodes=cislunar_nodes,
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
        meo_nodes = int(adversary_assets.meo_nodes * min(observer_sda_level + 0.2, 1.0))
        geo_nodes = int(adversary_assets.geo_nodes * min(observer_sda_level + 0.4, 1.0))
        cislunar_nodes = int(adversary_assets.cislunar_nodes * observer_sda_level)
        asat_kinetic = 0
        asat_deniable = 0
        if observer_sda_level >= 0.3:
            asat_kinetic = int(adversary_assets.asat_kinetic * observer_sda_level)
        if observer_sda_level >= 0.6:
            asat_deniable = round(adversary_assets.asat_deniable * (observer_sda_level - 0.5))
        ew_jammers = int(adversary_assets.ew_jammers * observer_sda_level)
        return FactionAssets(
            leo_nodes=leo_nodes,
            meo_nodes=meo_nodes,
            geo_nodes=geo_nodes,
            cislunar_nodes=cislunar_nodes,
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
            return {"nodes_destroyed": 0, "regime": "none", "detected": False, "attributed": False}
        # Target priority: LEO (most accessible) → MEO → GEO
        # Effectiveness degrades with higher orbits (harder to reach)
        if target_assets.leo_nodes > 0:
            regime = "leo"
            effectiveness = min(attacker_assets.asat_kinetic * 3, 20)
        elif target_assets.meo_nodes > 0:
            regime = "meo"
            effectiveness = min(attacker_assets.asat_kinetic * 2, 10)
        elif target_assets.geo_nodes > 0:
            regime = "geo"
            effectiveness = min(attacker_assets.asat_kinetic * 1, 5)
        elif target_assets.cislunar_nodes > 0:
            regime = "cislunar"
            effectiveness = max(attacker_assets.asat_kinetic - 2, 0)
        else:
            return {"nodes_destroyed": 0, "regime": "none", "detected": True, "attributed": True}

        nodes_destroyed = int(effectiveness * attacker_sda_level)
        return {
            "nodes_destroyed": nodes_destroyed,
            "regime": regime,
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


class DebrisEngine:
    SHELLS = ["leo", "meo", "geo", "cislunar"]
    # LEO debris decays fast (atmospheric drag); cislunar is permanent on human timescales
    DECAY_RATE: dict[str, float] = {"leo": 0.06, "meo": 0.025, "geo": 0.01, "cislunar": 0.004}
    KESSLER_THRESHOLD = 0.8        # at or above this, shell is effectively unusable
    DEBRIS_PER_NODE_KINETIC = 0.12 # each node destroyed by kinetic adds this much debris
    DEBRIS_PER_NODE_DENIABLE = 0.05

    def add_debris(self, fields: dict[str, float], shell: str, amount: float) -> dict[str, float]:
        result = dict(fields)
        result[shell] = min(result.get(shell, 0.0) + amount, 1.0)
        return result

    def decay(self, fields: dict[str, float]) -> dict[str, float]:
        return {
            shell: max(0.0, sev - self.DECAY_RATE.get(shell, 0.02))
            for shell, sev in fields.items()
        }

    def operational_penalty(self, fields: dict[str, float], shell: str) -> float:
        """Probability 0.0–1.0 that a node in this shell is disrupted per turn."""
        sev = fields.get(shell, 0.0)
        if sev >= self.KESSLER_THRESHOLD:
            return 1.0
        return sev * 0.5  # linear: 50% disruption at Kessler threshold

    def apply_debris_effects(
        self, faction_states: dict, fields: dict[str, float]
    ) -> tuple[dict, list[str]]:
        import random
        log: list[str] = []
        shell_attr = {
            "leo": "leo_nodes", "meo": "meo_nodes",
            "geo": "geo_nodes", "cislunar": "cislunar_nodes",
        }
        for shell in self.SHELLS:
            penalty = self.operational_penalty(fields, shell)
            if penalty == 0:
                continue
            attr = shell_attr[shell]
            for fid, fs in faction_states.items():
                nodes = getattr(fs.assets, attr)
                if nodes > 0 and random.random() < penalty:
                    lost = max(1, round(nodes * min(penalty, 0.5) * 0.25))
                    setattr(fs.assets, attr, max(0, nodes - lost))
                    label = "UNUSABLE — KESSLER" if penalty >= 1.0 else f"{penalty:.0%} debris hazard"
                    log.append(
                        f"Debris field ({shell.upper()} {label}): {fs.name} lost {lost} nodes"
                    )
        return faction_states, log


class SimulationEngine:
    def __init__(self):
        self.investment_resolver = InvestmentResolver()
        self.sda_filter = SDAFilter()
        self.conflict_resolver = ConflictResolver()
        self.debris_engine = DebrisEngine()

    def compute_orbital_dominance(
        self, faction_id: str, all_assets: dict[str, FactionAssets]
    ) -> float:
        total_weighted = sum(a.weighted_orbital_nodes() for a in all_assets.values())
        if total_weighted == 0:
            return 0.0
        if faction_id not in all_assets:
            return 0.0
        return all_assets[faction_id].weighted_orbital_nodes() / total_weighted

    def compute_coalition_dominance(
        self, coalition_member_ids: list[str], all_assets: dict[str, FactionAssets]
    ) -> float:
        coalition_weighted = sum(
            all_assets[fid].weighted_orbital_nodes()
            for fid in coalition_member_ids
            if fid in all_assets
        )
        total_weighted = sum(a.weighted_orbital_nodes() for a in all_assets.values())
        if total_weighted == 0:
            return 0.0
        return coalition_weighted / total_weighted
