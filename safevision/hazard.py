"""
Hazard assessment: turn radar detections into driver warnings.

The rule that matters for the driver is not "there is an object" but "how long
until I reach it". SafeVision therefore ranks every detection by time-to-contact
(TTC) and issues the earliest possible warning that is still actionable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Sequence

from .radar import Detection

# Warning is issued this far ahead of contact - the headline 15 s figure.
WARNING_HORIZON_S = 15.0
CRITICAL_HORIZON_S = 5.0
# Perception-reaction time of an average driver (AASHTO green book).
DRIVER_REACTION_S = 2.5


class WarningLevel(Enum):
    NONE = 0
    INFO = 1      # object tracked, no action needed yet
    CAUTION = 2   # hazard ahead, lift off the accelerator
    CRITICAL = 3  # brake now

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return self.name


@dataclass(frozen=True)
class Hazard:
    """A detection promoted to a driver-facing warning."""

    range_m: float
    closing_speed_mps: float
    time_to_contact_s: float
    level: WarningLevel
    confidence: float

    @property
    def message(self) -> str:
        """English driver-facing text, ready for the HUD or the audio prompt."""
        if self.level is WarningLevel.CRITICAL:
            return f"Brake now - hazard {self.range_m:.0f} m ahead"
        if self.level is WarningLevel.CAUTION:
            return (
                f"Hazard {self.range_m:.0f} m ahead, "
                f"{self.time_to_contact_s:.0f} s - slow down"
            )
        if self.level is WarningLevel.INFO:
            return f"Object detected {self.range_m:.0f} m ahead"
        return "Road clear"


def time_to_contact(range_m: float, closing_speed_mps: float) -> float:
    """Seconds until the vehicle reaches the object.

    Returns infinity when the gap is not closing, so a receding object can never
    outrank a real hazard.
    """
    if closing_speed_mps <= 0.0:
        return math.inf
    return range_m / closing_speed_mps


def braking_distance(speed_mps: float, friction: float = 0.7) -> float:
    """Distance needed to stop, including driver reaction time, in metres.

    ``friction`` is the tyre/road coefficient: ~0.7 dry asphalt, ~0.4 wet,
    ~0.15 ice. The wet and icy cases are exactly where a 50 m radar horizon
    beats the driver's own eyes.
    """
    reaction = speed_mps * DRIVER_REACTION_S
    return reaction + speed_mps**2 / (2.0 * friction * 9.81)


def _confidence(snr_db: float) -> float:
    """Map detector SNR onto a 0..1 confidence, saturating at 25 dB."""
    return max(0.0, min(1.0, (snr_db - 8.0) / 17.0))


def classify(
    detection: Detection,
    ego_speed_mps: float,
    min_confidence: float = 0.30,
    velocity_tolerance_mps: float = 2.0,
) -> Optional[Hazard]:
    """Assess one detection. Returns ``None`` when it is not worth reporting."""
    confidence = _confidence(detection.snr_db)
    if confidence < min_confidence:
        return None

    # The measured radial velocity is negative when the gap is shrinking. A
    # stationary obstacle reads as roughly zero only when the car itself is
    # stopped; while moving, it is closed on at the ego speed.
    if detection.velocity_mps < -velocity_tolerance_mps:
        closing = -detection.velocity_mps
    elif abs(detection.velocity_mps) <= velocity_tolerance_mps:
        closing = ego_speed_mps
    else:
        # Genuinely moving away - not a hazard for this vehicle.
        return None

    ttc = time_to_contact(detection.range_m, closing)
    if ttc > WARNING_HORIZON_S:
        level = WarningLevel.INFO
    elif ttc > CRITICAL_HORIZON_S and detection.range_m > braking_distance(ego_speed_mps):
        level = WarningLevel.CAUTION
    else:
        level = WarningLevel.CRITICAL

    return Hazard(
        range_m=detection.range_m,
        closing_speed_mps=closing,
        time_to_contact_s=ttc,
        level=level,
        confidence=confidence,
    )


def assess(detections: Sequence[Detection], ego_speed_mps: float) -> List[Hazard]:
    """Assess a full frame. Most urgent hazard first."""
    hazards = [h for h in (classify(d, ego_speed_mps) for d in detections) if h is not None]
    hazards.sort(key=lambda h: h.time_to_contact_s)
    return hazards
