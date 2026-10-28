import tempfile
import unittest
from pathlib import Path

from app.config.paths import DataPaths
from app.scrapers.hearings.hearings_scraper import (
    HearingsScraper,
)


class _Response:

    def __init__(self, text):
        self.text = text


class HearingsScraperTests(unittest.TestCase):
    def test_listing_is_fetched_once_and_stale_pages_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw" / "hearings"
            raw.mkdir(parents=True)
            (raw / "page_2.html").write_text(
                "stale",
                encoding="utf-8",
            )
            (raw / "page_5.html").write_text(
                "stale",
                encoding="utf-8",
            )

            scraper = HearingsScraper(
                paths=DataPaths(tmp)
            )
            calls = []

            def get(url):
                calls.append(url)
                if url.endswith("/de/robots.txt"):
                    return _Response(
                        "User-agent: *\nAllow: /\n"
                    )
                return _Response("<html>listing</html>")

            scraper.client.get = get
            result = scraper.scrape()

            self.assertEqual(
                calls,
                [
                    "https://beteiligungsportal.baden-wuerttemberg.de/de/robots.txt",
                    "https://beteiligungsportal.baden-wuerttemberg.de/de/mitmachen",
                ],
            )
            self.assertEqual(result["fetched"], 1)
            self.assertEqual(result["empty_pages"], 0)
            self.assertEqual(
                (raw / "page_1.html").read_text(
                    encoding="utf-8"
                ),
                "<html>listing</html>",
            )
            self.assertFalse((raw / "page_2.html").exists())
            self.assertFalse((raw / "page_5.html").exists())

    def test_empty_response_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            scraper = HearingsScraper(
                paths=DataPaths(tmp)
            )

            def get(url):
                if url.endswith("/de/robots.txt"):
                    return _Response(
                        "User-agent: *\nAllow: /\n"
                    )
                return _Response("   ")

            scraper.client.get = get
            result = scraper.scrape()

            self.assertEqual(result["empty_pages"], 1)
            self.assertEqual(result["fetched"], 1)


if __name__ == "__main__":
    unittest.main()
