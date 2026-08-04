import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VercelRoutingTests(unittest.TestCase):
    def test_root_entrypoint_exports_the_fews_app(self):
        from index import app

        route_paths = {route.path for route in app.routes}

        for path in ("/", "/login", "/dashboard", "/alerts", "/reports", "/branch-inputs", "/archives", "/health"):
            self.assertIn(path, route_paths)

    def test_vercel_config_preserves_original_request_paths(self):
        config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))

        self.assertNotIn("rewrites", config)
        self.assertEqual(config["regions"], ["hnd1"])


if __name__ == "__main__":
    unittest.main()
