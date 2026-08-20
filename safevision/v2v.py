"""
Vehicle-to-vehicle hazard relay.

A single sensor sees ~77 m, which at 80 km/h is about 3 seconds of warning. The
15-second horizon SafeVision targets comes from the fleet: a hazard confirmed by
one car is broadcast, and every car approaching the same spot is warned long
before its own radar can see it.

This module holds the shared hazard map and the logic that decides whether a
reported hazard is relevant to an approaching vehicle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from .hazard import WARNING_HORIZON_S, Hazard, WarningLevel

# Hazards are keyed to a point on the road; two reports within this distance are
# treated as the same hazard.
MERGE_RADIUS_M = 15.0
# Confidence needed before a hazard is broadcast to other vehicles.
BROADCAST_CONFIDENCE = 0.5


@dataclass
class RoadHazard:
    """A hazard pinned to a position along the road, shared by the fleet."""

    position_m: float          # distance along the road from a fixed origin
    level: WarningLevel
    confidence: float
    reports: int = 1

    def reinforce(self, confidence: float) -> None:
        """Fold in an independent confirmation from another vehicle.

        Repeated sightings raise confidence but never reach certainty, so a
        one-off reflection can be outvoted while a real pothole is not.
        """
        self.reports += 1
        self.confidence = 1.0 - (1.0 - self.confidence) * (1.0 - confidence)


@dataclass
class HazardMap:
    """Shared map of confirmed road hazards."""

    hazards: List[RoadHazard] = field(default_factory=list)

    def report(self, position_m: float, hazard: Hazard) -> RoadHazard | None:
        """Submit a hazard seen by one vehicle. Returns the merged entry."""
        if hazard.confidence < BROADCAST_CONFIDENCE:
            return None
        for existing in self.hazards:
            if abs(existing.position_m - position_m) <= MERGE_RADIUS_M:
                existing.reinforce(hazard.confidence)
                if hazard.level.value > existing.level.value:
                    existing.level = hazard.level
                return existing
        entry = RoadHazard(position_m=position_m, level=hazard.level, confidence=hazard.confidence)
        self.hazards.append(entry)
        return entry

    def ahead_of(self, position_m: float, speed_mps: float, horizon_s: float = WARNING_HORIZON_S) -> List[RoadHazard]:
        """Hazards a vehicle will reach within ``horizon_s`` seconds.

        This is what gives the driver a 15-second warning: the hazard is already
        in the map before their own radar can see it.
        """
        if speed_mps <= 0.0:
            return []
        reach = position_m + speed_mps * horizon_s
        upcoming = [h for h in self.hazards if position_m < h.position_m <= reach]
        upcoming.sort(key=lambda h: h.position_m)
        return upcoming


def relay_frame(
    hazard_map: HazardMap,
    vehicle_position_m: float,
    hazards: List[Hazard],
) -> Dict[str, int]:
    """Push one vehicle's frame of hazards into the shared map."""
    published = 0
    for hazard in hazards:
        if hazard_map.report(vehicle_position_m + hazard.range_m, hazard) is not None:
            published += 1
    return {"published": published, "map_size": len(hazard_map.hazards)}
