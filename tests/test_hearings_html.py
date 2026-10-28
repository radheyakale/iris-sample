import json
import tempfile
import unittest
from pathlib import Path

from app.config.paths import DataPaths
from app.scrapers.base.parser import HearingsHTMLDataParser
from app.scrapers.hearings.hearings_filter import HearingsFilter
from app.scrapers.hearings.hearings_parser import HearingsParser


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "hearings"
)


class HearingsHtmlTests(unittest.TestCase):
    def test_listing_fixture_extracts_both_signal_types(self):
        html = (FIXTURES / "listing.html").read_text(
            encoding="utf-8"
        )
        parser = HearingsHTMLDataParser()
        records = HearingsFilter().apply(
            parser.parse(html)
        )

        self.assertEqual(parser.dropped_missing_fields, 1)
        by_id = {
            record["source_id"]: record
            for record in records
        }

        regional = by_id["regionalplanung-stuttgart"]
        self.assertTrue(regional["relevant"])
        self.assertEqual(
            regional["published_at"],
            "2026-10-03",
        )
        self.assertEqual(
            regional["participation_start"],
            "2026-10-13",
        )
        self.assertEqual(
            regional["participation_end"],
            "2026-11-13",
        )
        self.assertEqual(regional["place_text"], "Stuttgart")

        substation = by_id["umspannwerk-karlsruhe"]
        self.assertTrue(substation["relevant"])
        self.assertIsNone(substation["published_at"])
        self.assertEqual(
            substation["participation_start"],
            "2026-09-01",
        )
        self.assertEqual(
            substation["participation_end"],
            "2026-09-30",
        )
        self.assertEqual(
            substation["place_text"],
            "Karlsruhe",
        )
        self.assertFalse(by_id["haushalt"]["relevant"])

    def test_empty_page_is_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = (
                Path(tmp)
                / "raw"
                / "hearings"
            )
            raw.mkdir(parents=True)
            (raw / "page_1.html").write_text(
                (
                    FIXTURES / "empty.html"
                ).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (raw / "page_2.html").write_text(
                (
                    FIXTURES / "listing.html"
                ).read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            records = HearingsParser(
                paths=DataPaths(tmp)
            ).parse()

            relevant = [
                record["source_id"]
                for record in records
                if record["relevant"]
            ]
            self.assertEqual(
                relevant,
                [
                    "regionalplanung-stuttgart",
                    "umspannwerk-karlsruhe",
                ],
            )
            quality = json.loads(
                (raw / "parse_quality.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(quality["empty_pages"], 1)
            self.assertEqual(
                quality["dropped_missing_fields"],
                1,
            )
            self.assertEqual(quality["pages"], 2)


if __name__ == "__main__":
    unittest.main()
