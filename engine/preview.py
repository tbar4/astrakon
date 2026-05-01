# engine/preview.py
from pydantic import BaseModel
from engine.state import FactionState
from engine.simulation import ConflictResolver, ManeuverBudgetEngine, DebrisEngine


class OperationPreview(BaseModel):
    available: bool
    unavailable_reason: str = ""
    dv_cost: float = 0.0
    dv_remaining: float = 0.0
    nodes_destroyed_estimate: int = 0
    nodes_destroyed_min: int = 0
    nodes_destroyed_max: int = 0
    detection_prob: float = 0.0
    attribution_prob: float = 0.0
    escalation_delta: int = 0
    escalation_rung_new: int = 0
    debris_estimate: float = 0.0
    transit_turns: int = 0
    target_shell: str = ""
    effect_summary: str = ""


class PreviewEngine:
    def compute(
        self,
        action_type: str,
        mission: str,
        attacker_fs: FactionState,
        target_fs: "FactionState | None",
        debris_fields: dict,
        access_windows: dict,
        escalation_rung: int,
    ) -> OperationPreview:
        if action_type == "task_assets":
            return self._preview_task_assets(
                mission, attacker_fs, target_fs, debris_fields, access_windows, escalation_rung
            )
        if action_type == "gray_zone":
            return self._preview_gray_zone(attacker_fs, target_fs, debris_fields, escalation_rung)
        if action_type == "coordinate":
            return self._preview_coordinate(attacker_fs, target_fs)
        return OperationPreview(
            available=True,
            effect_summary="Diplomatic / signalling action — no direct combat effect",
        )

    def _preview_task_assets(
        self, mission, attacker_fs, target_fs, debris_fields, access_windows, escalation_rung
    ) -> OperationPreview:
        if mission == "intercept":
            return self._preview_intercept(
                attacker_fs, target_fs, debris_fields, access_windows, escalation_rung
            )
        summary = (
            "Surveillance only — shows resolve"
            if mission == "patrol"
            else "Intelligence gathering — no combat effect"
        )
        return OperationPreview(available=True, effect_summary=summary)

    def _preview_intercept(
        self, attacker_fs, target_fs, debris_fields, access_windows, escalation_rung
    ) -> OperationPreview:
        if attacker_fs.assets.asat_kinetic == 0:
            return OperationPreview(available=False, unavailable_reason="No kinetic ASAT assets")
        dv_needed = ManeuverBudgetEngine.COSTS["kinetic_intercept"]
        if attacker_fs.maneuver_budget < dv_needed:
            return OperationPreview(
                available=False, unavailable_reason=f"Insufficient DV (need {dv_needed:.1f})"
            )
        if target_fs is None:
            return OperationPreview(available=False, unavailable_reason="No target selected")

        if target_fs.assets.leo_nodes > 0:
            target_shell = "leo"
        elif target_fs.assets.meo_nodes > 0:
            target_shell = "meo"
        elif target_fs.assets.geo_nodes > 0:
            target_shell = "geo"
        elif target_fs.assets.cislunar_nodes > 0:
            target_shell = "cislunar"
        else:
            return OperationPreview(
                available=False, unavailable_reason="Target has no orbital assets"
            )

        result = ConflictResolver().resolve_kinetic_asat(
            attacker_assets=attacker_fs.assets,
            target_assets=target_fs.assets,
            attacker_sda_level=attacker_fs.sda_level(),
        )
        nodes_est = result["nodes_destroyed"]
        current_debris = debris_fields.get(target_shell, 0.0)
        debris_est = min(
            current_debris + DebrisEngine.DEBRIS_PER_NODE_KINETIC * nodes_est, 1.0
        )
        effect_summary = ""
        if not access_windows.get(target_shell, True):
            effect_summary = "ACCESS WINDOW CLOSED — transit may miss target"

        return OperationPreview(
            available=True,
            dv_cost=dv_needed,
            dv_remaining=attacker_fs.maneuver_budget - dv_needed,
            nodes_destroyed_estimate=nodes_est,
            nodes_destroyed_min=nodes_est,
            nodes_destroyed_max=nodes_est,
            detection_prob=0.80,
            attribution_prob=target_fs.sda_level(),
            escalation_delta=max(0, 3 - escalation_rung),
            escalation_rung_new=max(escalation_rung, 3),
            debris_estimate=debris_est,
            transit_turns=2,
            target_shell=target_shell,
            effect_summary=effect_summary,
        )

    def _preview_gray_zone(
        self, attacker_fs, target_fs, debris_fields, escalation_rung
    ) -> OperationPreview:
        if target_fs is None:
            return OperationPreview(available=False, unavailable_reason="No target selected")

        if attacker_fs.assets.asat_deniable > 0:
            dv_needed = ManeuverBudgetEngine.COSTS["deniable_approach"]
            if attacker_fs.maneuver_budget < dv_needed:
                return OperationPreview(
                    available=False,
                    unavailable_reason=f"Insufficient DV (need {dv_needed:.1f})",
                )
            n_min = 1
            n_max = attacker_fs.assets.asat_deniable
            n_est = (n_min + n_max) // 2
            current_leo = debris_fields.get("leo", 0.0)
            debris_est = min(
                current_leo + DebrisEngine.DEBRIS_PER_NODE_DENIABLE * n_est, 1.0
            )
            return OperationPreview(
                available=True,
                dv_cost=dv_needed,
                dv_remaining=attacker_fs.maneuver_budget - dv_needed,
                nodes_destroyed_estimate=n_est,
                nodes_destroyed_min=n_min,
                nodes_destroyed_max=n_max,
                detection_prob=target_fs.sda_level(),
                attribution_prob=target_fs.sda_level() * 0.5,
                escalation_delta=max(0, 2 - escalation_rung),
                escalation_rung_new=max(escalation_rung, 2),
                debris_estimate=debris_est,
                transit_turns=1,
            )

        if attacker_fs.assets.ew_jammers > 0:
            sda_pct = 30 if "jamming_radius" in (attacker_fs.unlocked_techs or []) else 15
            return OperationPreview(
                available=True,
                dv_cost=0.0,
                transit_turns=0,
                debris_estimate=debris_fields.get("leo", 0.0),
                effect_summary=f"Target SDA degraded -{sda_pct}%",
            )

        return OperationPreview(
            available=False,
            unavailable_reason="No deniable ASAT or EW jammer assets",
        )

    def _preview_coordinate(self, attacker_fs, target_fs) -> OperationPreview:
        if target_fs is None or target_fs.coalition_id != attacker_fs.coalition_id:
            return OperationPreview(
                available=True,
                effect_summary="Coordination bonus +SDA (requires allied target)",
            )
        if attacker_fs.cognitive_penalty > 0.75:
            return OperationPreview(
                available=True,
                effect_summary="Coordination will fail — cognitive degradation too severe",
            )
        if attacker_fs.coalition_loyalty < 0.25:
            return OperationPreview(
                available=True,
                effect_summary="Coordination will fail — loyalty too low",
            )
        return OperationPreview(available=True, effect_summary="Coordination bonus +SDA")
