import unittest
from pathlib import Path
from urllib.robotparser import RobotFileParser

ROBOTS = (
    Path(__file__).parent
    / "fixtures"
    / "hearings"
    / "robots.txt"
)


class HearingsRobotsTests(unittest.TestCase):
    def setUp(self):
        self.robots = RobotFileParser()
        self.robots.parse(
            ROBOTS.read_text(encoding="utf-8").splitlines()
        )

    def test_search_page_is_excluded(self):
        url = (
            "https://beteiligungsportal.baden-wuerttemberg.de"
            "/de/system/suchergebnisseite?tx_solr[q]=regionalplanung"
        )
        self.assertFalse(
            self.robots.can_fetch("*", url)
        )

    def test_public_procedure_page_is_allowed(self):
        url = (
            "https://beteiligungsportal.baden-wuerttemberg.de"
            "/de/mitmachen/lp-17/planungsoffensive-windkraft-und-photovoltaik"
            "/themenlandkarte/kriterien-der-regionalplanung"
        )
        self.assertTrue(
            self.robots.can_fetch("*", url)
        )


if __name__ == "__main__":
    unittest.main()
