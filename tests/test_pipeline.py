"""End-to-end tests for the SafeVision detection pipeline."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from safevision import RadarConfig, Target, assess, braking_distance, detect, simulate_frame
from safevision.hazard import WarningLevel, classify, time_to_contact
from safevision.radar import Detection
from safevision.v2v import HazardMap, relay_frame

CFG = RadarConfig()
EGO_SPEED = 22.2  # m/s, about 80 km/h


class TestRadarConfig(unittest.TestCase):
    def test_resolutions_match_the_datasheet(self):
        self.assertAlmostEqual(CFG.range_resolution, 0.6, places=1)
        self.assertGreater(CFG.max_range, 70.0)
        # Must stay unambiguous well past motorway speed.
        self.assertGreater(CFG.max_velocity, 40.0)

    def test_wavelength_is_about_12_millimetres(self):
        self.assertAlmostEqual(CFG.wavelength * 1000, 12.4, places=1)


class TestDetection(unittest.TestCase):
    def test_detects_a_pothole_and_a_stalled_vehicle(self):
        scene = [
            Target(28.0, -EGO_SPEED, rcs=0.6, label="pothole"),
            Target(62.0, -EGO_SPEED, rcs=9.0, label="stalled vehicle"),
        ]
        detections = detect(simulate_frame(scene, CFG, seed=7), CFG)

        self.assertEqual(len(detections), 2)
        for detected, expected in zip(detections, scene):
            # Range must land inside one range gate.
            self.assertLess(abs(detected.range_m - expected.range_m), CFG.range_resolution)
            # Closing speed must land inside two Doppler bins.
            self.assertLess(
                abs(detected.velocity_mps - expected.velocity_mps),
                2 * CFG.velocity_resolution,
            )

    def test_empty_road_produces_no_detections(self):
        self.assertEqual(detect(simulate_frame([], CFG, seed=3), CFG), [])

    def test_result_is_deterministic_for_a_fixed_seed(self):
        scene = [Target(35.0, -EGO_SPEED, rcs=1.0)]
        first = detect(simulate_frame(scene, CFG, seed=11), CFG)
        second = detect(simulate_frame(scene, CFG, seed=11), CFG)
        self.assertEqual(first, second)


class TestHazardLogic(unittest.TestCase):
    def test_time_to_contact(self):
        self.assertAlmostEqual(time_to_contact(50.0, 25.0), 2.0)
        # A gap that is not closing can never be reached.
        self.assertEqual(time_to_contact(50.0, 0.0), math.inf)
        self.assertEqual(time_to_contact(50.0, -5.0), math.inf)

    def test_braking_distance_grows_on_a_wet_road(self):
        dry = braking_distance(EGO_SPEED, friction=0.7)
        wet = braking_distance(EGO_SPEED, friction=0.4)
        self.assertGreater(wet, dry)
        self.assertGreater(dry, EGO_SPEED)  # reaction distance alone

    def test_close_hazard_is_critical(self):
        hazard = classify(Detection(20.0, -EGO_SPEED, snr_db=40.0), EGO_SPEED)
        self.assertIsNotNone(hazard)
        self.assertIs(hazard.level, WarningLevel.CRITICAL)
        self.assertIn("Brake now", hazard.message)

    def test_receding_target_is_not_a_hazard(self):
        self.assertIsNone(classify(Detection(40.0, +18.0, snr_db=40.0), EGO_SPEED))

    def test_weak_detection_is_discarded(self):
        self.assertIsNone(classify(Detection(40.0, -EGO_SPEED, snr_db=9.0), EGO_SPEED))

    def test_hazards_are_ranked_most_urgent_first(self):
        detections = [
            Detection(70.0, -EGO_SPEED, snr_db=30.0),
            Detection(15.0, -EGO_SPEED, snr_db=30.0),
            Detection(40.0, -EGO_SPEED, snr_db=30.0),
        ]
        ttcs = [h.time_to_contact_s for h in assess(detections, EGO_SPEED)]
        self.assertEqual(ttcs, sorted(ttcs))


class TestVehicleToVehicleRelay(unittest.TestCase):
    def test_repeated_reports_reinforce_confidence(self):
        hazard_map = HazardMap()
        hazard = classify(Detection(30.0, -EGO_SPEED, snr_db=18.0), EGO_SPEED)
        first = hazard_map.report(1000.0, hazard)
        second = hazard_map.report(1005.0, hazard)  # same spot, another car

        self.assertIs(first, second)
        self.assertEqual(second.reports, 2)
        self.assertGreater(second.confidence, hazard.confidence)
        self.assertLess(second.confidence, 1.0)
        self.assertEqual(len(hazard_map.hazards), 1)

    def test_relay_gives_a_following_car_a_15_second_warning(self):
        hazard_map = HazardMap()
        scene = [Target(40.0, -EGO_SPEED, rcs=9.0, label="stalled vehicle")]
        detections = detect(simulate_frame(scene, CFG, seed=5), CFG)
        stats = relay_frame(hazard_map, vehicle_position_m=2000.0, hazards=assess(detections, EGO_SPEED))
        self.assertEqual(stats["published"], 1)

        # A second car is 300 m behind - far beyond its own radar horizon.
        upcoming = hazard_map.ahead_of(position_m=1740.0, speed_mps=EGO_SPEED)
        self.assertEqual(len(upcoming), 1)
        lead_time = (upcoming[0].position_m - 1740.0) / EGO_SPEED
        self.assertGreater(lead_time, 12.0)
        self.assertGreater(upcoming[0].position_m - 1740.0, CFG.max_range)

    def test_hazards_behind_the_vehicle_are_ignored(self):
        hazard_map = HazardMap()
        hazard_map.hazards.append(
            hazard_map.report(500.0, classify(Detection(30.0, -EGO_SPEED, snr_db=30.0), EGO_SPEED))
        )
        self.assertEqual(hazard_map.ahead_of(position_m=900.0, speed_mps=EGO_SPEED), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
