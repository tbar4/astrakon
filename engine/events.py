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
        self,
        tension_level: float,
        affected_factions: list[str],
        turn: int,
        prev_ops: list[str] | None = None,
    ) -> list[CrisisEvent]:
        """Generate 0–2 crisis events weighted by board tension and prior operations."""
        eligible = [e for e in self._events if e["min_tension"] <= tension_level]
        if not eligible:
            return []

        # Bias event pool when kinetic strikes occurred last turn
        kinetic_last_turn = prev_ops and any(
            op in prev_ops for op in ("kinetic_strike", "deniable_strike")
        )
        if kinetic_last_turn:
            # Force at least one attribution/ASAT event when strikes happened
            priority_types = {"asat_test", "attribution_crisis", "proxy_conflict"}
            priority = [e for e in eligible if e["event_type"] in priority_types]
            others = [e for e in eligible if e["event_type"] not in priority_types]
            # Guarantee count >= 1 when there were strikes
            weights = [0.1, 0.5, 0.4] if tension_level > 0.5 else [0.2, 0.5, 0.3]
            count = max(1, random.choices([0, 1, 2], weights=weights)[0])
            selected = []
            if priority:
                selected.append(random.choice(priority))
                if count > 1 and others:
                    selected.append(random.choice(others))
            else:
                selected = random.sample(eligible, min(count, len(eligible)))
        else:
            weights = [0.2, 0.5, 0.3] if tension_level > 0.5 else [0.4, 0.5, 0.1]
            count = random.choices([0, 1, 2], weights=weights)[0]
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
