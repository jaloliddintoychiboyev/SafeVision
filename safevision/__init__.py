"""SafeVision - turning every car into a 24 GHz mmWave road-hazard sensor."""

from .hazard import Hazard, WarningLevel, assess, braking_distance, time_to_contact
from .radar import Detection, RadarConfig, detect, range_doppler_map
from .simulator import Target, simulate_frame

__version__ = "0.1.0"

__all__ = [
    "Detection",
    "Hazard",
    "RadarConfig",
    "Target",
    "WarningLevel",
    "assess",
    "braking_distance",
    "detect",
    "range_doppler_map",
    "simulate_frame",
    "time_to_contact",
]
