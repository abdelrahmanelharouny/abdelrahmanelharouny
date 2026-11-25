import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.generate_profile_metrics import build_svg, format_number


class ProfileMetricsRenderingTests(unittest.TestCase):
    def test_dashboard_renders_live_account_totals(self):
        profile = {"followers": 12, "public_repos": 3}
        repositories = [
            {"stargazers_count": 6, "forks_count": 2},
            {"stargazers_count": 9, "forks_count": 3},
        ]
        languages = Counter({"Python": 800, "TypeScript": 200})

        svg = build_svg(profile, repositories, languages)

        self.assertIn(">12</text>", svg)
        self.assertIn(">3</text>", svg)
        self.assertIn(">15</text>", svg)
        self.assertIn(">5</text>", svg)
        self.assertIn("80.0%", svg)
        self.assertIn("20.0%", svg)
        self.assertIn("LANGUAGE FOOTPRINT", svg)
        self.assertIn("AUTO-UPDATED EVERY 6 HOURS", svg)

    def test_language_labels_are_xml_escaped(self):
        svg = build_svg(
            {"followers": 0, "public_repos": 0},
            [],
            Counter({"<script>alert(1)</script>": 100}),
        )

        self.assertIn("&lt;script&gt;", svg)
        self.assertNotIn("<script>alert(1)</script>", svg)

    def test_empty_language_data_has_a_safe_fallback(self):
        svg = build_svg({"followers": 1, "public_repos": 1}, [], Counter())

        self.assertIn("Language data is not available yet.", svg)
        self.assertIn('fill="#34464A"', svg)

    def test_large_numbers_are_formatted_readably(self):
        self.assertEqual(format_number(1234567), "1,234,567")
        self.assertEqual(format_number(0), "0")


if __name__ == "__main__":
    unittest.main()
