import unittest
import json
from cli.rust_bindings import calibrate_session

class TestCalibration(unittest.TestCase):
    def test_basic_calibration(self):
        watts = [210.0, 215.0, 212.0, 205.0, 220.0]
        speed_ms = [7.8, 8.0, 7.9, 7.7, 8.1]
        altitude_m = [100.0, 100.5, 101.0, 100.7, 100.2]

        profile = {
            "total_weight": 85.0,
            "bike_type": "road",
            "crr": None,
            "cda": None,
            "calibrated": False,
            "calibration_mae": None,
            "estimat": True,
        }
        weather = {
            "wind_ms": 0.0,
            "wind_dir_deg": 0.0,
            "air_temp_c": 15.0,
            "air_pressure_hpa": 1013.0,
        }

        out = calibrate_session(watts, speed_ms, altitude_m, profile, weather)

        self.assertIsInstance(out, dict)
        for k in ("cda", "crr", "mae", "calibrated", "profile"):
            self.assertIn(k, out)

        self.assertIsInstance(out["cda"], (int, float))
        self.assertIsInstance(out["crr"], (int, float))
        self.assertGreater(out["cda"], 0)
        self.assertLess(out["cda"], 1.0)
        self.assertGreater(out["crr"], 0)
        self.assertLess(out["crr"], 0.02)
        self.assertGreaterEqual(out["mae"], 0)

        json.loads(out["profile"])

if __name__ == "__main__":
    unittest.main()