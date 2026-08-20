#!/usr/bin/env python3
"""
SafeVision end-to-end demo.

Drives the complete pipeline on a simulated highway scene:

    synthetic 24 GHz beat signal -> range-Doppler -> CFAR detection
                                 -> time-to-contact -> driver warning

Run it with no arguments:

    python3 demo.py

Or describe your own scene:

    python3 demo.py --speed 90 --targets "pothole:38:0.5,stopped car:120:9.0"
"""

from __future__ import annotations

import argparse
from typing import List

from safevision import RadarConfig, Target, assess, braking_distance, detect, simulate_frame
from safevision.hazard import WARNING_HORIZON_S
from safevision.v2v import HazardMap, relay_frame

KMH_TO_MPS = 1.0 / 3.6


def parse_targets(spec: str) -> List[Target]:
    """Parse ``label:range_m:rcs[,...]`` into targets."""
    targets: List[Target] = []
    for chunk in spec.split(","):
        parts = [p.strip() for p in chunk.split(":")]
        if len(parts) != 3:
            raise argparse.ArgumentTypeError(
                f"expected 'label:range_m:rcs', got {chunk!r}"
            )
        label, range_m, rcs = parts
        targets.append(Target(range_m=float(range_m), velocity_mps=0.0, rcs=float(rcs), label=label))
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description="SafeVision hazard-detection demo")
    parser.add_argument("--speed", type=float, default=80.0, help="ego vehicle speed in km/h")
    parser.add_argument(
        "--targets",
        type=parse_targets,
        default=parse_targets("pothole:28:0.6,stalled vehicle:62:9.0"),
        help="scene as 'label:range_m:rcs' entries separated by commas",
    )
    parser.add_argument("--seed", type=int, default=7, help="noise seed for reproducibility")
    args = parser.parse_args()

    cfg = RadarConfig()
    ego_speed = args.speed * KMH_TO_MPS

    print("SafeVision - 24 GHz mmWave road-hazard detection")
    print("=" * 62)
    print(f"Sensor          : {cfg.center_frequency / 1e9:.3f} GHz, {cfg.bandwidth / 1e6:.0f} MHz sweep")
    print(f"Range resolution: {cfg.range_resolution:.2f} m   (max {cfg.max_range:.0f} m)")
    print(f"Speed resolution: {cfg.velocity_resolution:.2f} m/s (max +/-{cfg.max_velocity:.0f} m/s)")
    print(f"Ego speed       : {args.speed:.0f} km/h ({ego_speed:.1f} m/s)")
    print(f"Braking distance: {braking_distance(ego_speed):.0f} m dry / "
          f"{braking_distance(ego_speed, friction=0.4):.0f} m wet")
    print()

    # Static road hazards are closed on at the ego speed.
    scene = [
        Target(t.range_m, -ego_speed, t.rcs, t.label) for t in args.targets
    ]
    print("Scene:")
    for t in scene:
        print(f"  - {t.label:<12} {t.range_m:5.1f} m, RCS {t.rcs:.1f} m^2")
    print()

    frame = simulate_frame(scene, cfg, seed=args.seed)
    detections = detect(frame, cfg)

    print(f"Detections ({len(detections)}):")
    for d in detections:
        print(f"  {d}")
    print()

    hazards = assess(detections, ego_speed)
    print("Driver warnings:")
    if not hazards:
        print("  Road clear")
    for h in hazards:
        print(f"  [{str(h.level):<8}] {h.message}  (TTC {h.time_to_contact_s:.1f} s, "
              f"confidence {h.confidence:.0%})")
    print()

    # The fleet layer: what this car just saw is broadcast, so the car behind is
    # warned long before its own radar can see the same hazard.
    hazard_map = HazardMap()
    position = 2000.0
    stats = relay_frame(hazard_map, position, hazards)
    print(f"Shared hazard map: {stats['published']} hazard(s) broadcast, "
          f"{stats['map_size']} on the map")

    nearest = min((h.position_m for h in hazard_map.hazards), default=position)
    follower = nearest - ego_speed * WARNING_HORIZON_S
    upcoming = hazard_map.ahead_of(follower, ego_speed)
    print(f"Following vehicle, still {nearest - follower:.0f} m short of the hazard "
          f"(its own radar horizon is only {cfg.max_range:.0f} m):")
    if not upcoming:
        print("  nothing relayed")
    for entry in upcoming:
        lead_time = (entry.position_m - follower) / ego_speed
        print(f"  [{str(entry.level):<8}] hazard in {entry.position_m - follower:.0f} m "
              f"- {lead_time:.0f} s of warning, confidence {entry.confidence:.0%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
