"""
Synthetic FMCW scene generator.

Produces the raw ADC beat signal that a 24 GHz sensor would deliver for a set of
targets, so the whole detection chain can be exercised and regression-tested
without hardware.

Beat signal for a target at range R with radial velocity v:

    s(t, m) = A * exp(j*2*pi*(f_beat*t + f_doppler*m*T_chirp))
    f_beat    = 2*R*slope/c
    f_doppler = 2*v/lambda
"""

from __future__ import annotations

import cmath
import math
import random
from dataclasses import dataclass
from typing import List, Sequence

from .radar import SPEED_OF_LIGHT, RadarConfig


@dataclass(frozen=True)
class Target:
    """A physical object in front of the vehicle."""

    range_m: float
    velocity_mps: float  # negative = closing on the sensor
    rcs: float = 1.0     # radar cross-section, m^2 (pothole ~0.5, car ~10)
    label: str = "object"


def simulate_frame(
    targets: Sequence[Target],
    cfg: RadarConfig,
    noise_sigma: float = 0.05,
    seed: int | None = None,
) -> List[List[complex]]:
    """Generate one ADC frame, indexed ``[chirp][sample]``."""
    rng = random.Random(seed)
    frame: List[List[complex]] = []

    for chirp in range(cfg.chirps_per_frame):
        row: List[complex] = []
        chirp_time = chirp * cfg.chirp_duration
        for sample in range(cfg.samples_per_chirp):
            t = sample / cfg.sample_rate
            value = 0j
            for tgt in targets:
                # Amplitude follows the radar equation: P_r ~ RCS / R^4.
                amplitude = math.sqrt(tgt.rcs) / max(tgt.range_m, 1.0) ** 2 * 1000.0
                f_beat = 2.0 * tgt.range_m * cfg.sweep_slope / SPEED_OF_LIGHT
                f_doppler = 2.0 * tgt.velocity_mps / cfg.wavelength
                phase = 2.0 * math.pi * (f_beat * t + f_doppler * chirp_time)
                value += amplitude * cmath.exp(1j * phase)
            # Thermal noise, complex circular Gaussian.
            value += complex(rng.gauss(0.0, noise_sigma), rng.gauss(0.0, noise_sigma))
            row.append(value)
        frame.append(row)
    return frame
