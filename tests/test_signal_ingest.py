import json
import tempfile
import unittest
from pathlib import Path

from app.config.paths import DataPaths
from app.loaders.signal_ingest_loader import SignalIngestLoader


FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "hearings"
)


def _hearing(**overrides):
    record = {
        "source_id": "1",
        "title": (
            "Öffentlichkeitsbeteiligung zur "
            "Änderung der Regionalplanung"
        ),
        "source_url": "https://example.test/1",
        "place_text": "Stuttgart",
        "relevant": True,
        "published_at": "2026-10-13",
    }
    record.update(overrides)
    return record


class _Session:

    def __init__(self, existing=None):
        self.existing = existing
        self.added = []

    def scalar(self, _statement):
        return self.existing

    def add(self, row):
        self.added.append(row)

    def commit(self):
        return None

    def rollback(self):
        return None


def _load(records, existing=None):
    session = _Session(existing)
    loader = SignalIngestLoader.__new__(
        SignalIngestLoader
    )
    loader.session = session
    counts = loader._load_records(records)
    return session.added, counts


class SignalIngestTests(unittest.TestCase):
    def test_place_name_without_coordinate_is_ambiguous(self):
        added, counts = _load([_hearing()])

        self.assertEqual(counts["inserted"], 1)
        self.assertEqual(
            added[0].location_status,
            "ambiguous",
        )
        self.assertIsNone(added[0].geom)
        self.assertEqual(
            added[0].signal_type,
            "regional_plan_amendment",
        )

    def test_valid_lon_lat_becomes_epsg_25832(self):
        added, _counts = _load(
            [
                _hearing(
                    longitude=9.18,
                    latitude=48.78,
                )
            ]
        )

        self.assertEqual(
            added[0].location_status,
            "resolved",
        )
        self.assertIn(
            "POINT(",
            str(added[0].geom),
        )

    def test_bad_coordinate_is_not_stored(self):
        added, _counts = _load(
            [
                _hearing(
                    longitude=1.0,
                    latitude=48.78,
                )
            ]
        )

        self.assertIsNone(added[0].geom)
        self.assertEqual(
            added[0].location_status,
            "unresolved",
        )

    def test_origin_is_rejected(self):
        added, _counts = _load(
            [_hearing(longitude=0, latitude=0)]
        )

        self.assertIsNone(added[0].geom)
        self.assertIn(
            "(0, 0)",
            added[0].location_note,
        )

    def test_non_numeric_coordinate_is_unresolved(self):
        added, counts = _load(
            [
                _hearing(
                    longitude="not-a-number",
                    latitude=48.78,
                )
            ]
        )

        self.assertEqual(len(added), 1)
        self.assertIsNone(added[0].geom)
        self.assertEqual(
            added[0].location_status,
            "unresolved",
        )
        self.assertIn(
            "not numeric",
            added[0].location_note,
        )
        self.assertEqual(counts["unresolved"], 1)
        self.assertEqual(counts["inserted"], 1)

    def test_duplicate_missing_and_empty(self):
        added, counts = _load(
            [
                _hearing(),
                _hearing(),
                _hearing(source_id="2", title="  "),
                "not-a-record",
            ]
        )

        self.assertEqual(len(added), 1)
        self.assertEqual(counts["duplicates_skipped"], 1)
        self.assertEqual(counts["dropped_missing_fields"], 1)
        self.assertEqual(counts["malformed_records"], 1)

        empty, counts = _load([])
        self.assertEqual(empty, [])
        self.assertEqual(counts["inserted"], 0)
        self.assertEqual(counts["updated"], 0)
        self.assertEqual(counts["unchanged"], 0)

    def test_second_load_does_not_insert(self):
        added, _counts = _load([_hearing()])

        again, counts = _load(
            [_hearing()],
            existing=added[0],
        )

        self.assertEqual(again, [])
        self.assertEqual(counts["inserted"], 0)
        self.assertEqual(counts["unchanged"], 1)

    def test_fixture_rows_and_malformed_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / "raw" / "hearings"
            raw.mkdir(parents=True)
            (raw / "merged.json").write_text(
                (FIXTURES / "signals.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            (raw / "parse_quality.json").write_text(
                json.dumps(
                    {
                        "empty_pages": 1,
                        "duplicates_skipped": 0,
                        "dropped_missing_fields": 1,
                    }
                ),
                encoding="utf-8",
            )

            session = _Session()
            report = SignalIngestLoader(
                session,
                paths=DataPaths(tmp),
            ).execute()

            self.assertEqual(report["rows_loaded"], 3)
            self.assertEqual(report["inserted"], 3)
            self.assertEqual(
                report["duplicates_skipped"],
                1,
            )
            self.assertEqual(report["empty_pages"], 1)
            self.assertEqual(report["ambiguous"], 1)
            self.assertEqual(report["resolved"], 1)
            self.assertEqual(report["unresolved"], 1)
            self.assertEqual(
                report["dropped_missing_fields"],
                2,
            )
            self.assertEqual(
                report["malformed_records"],
                1,
            )
            by_id = {
                row.source_id: row
                for row in session.added
            }
            self.assertEqual(
                by_id[
                    "regionalplanung-stuttgart"
                ].signal_type,
                "regional_plan_amendment",
            )
            self.assertEqual(
                by_id[
                    "regionalplanung-stuttgart"
                ].location_status,
                "ambiguous",
            )
            self.assertEqual(
                by_id[
                    "umspannwerk-karlsruhe"
                ].signal_type,
                "substation_expansion_hearing",
            )
            self.assertEqual(
                by_id[
                    "umspannwerk-karlsruhe"
                ].location_status,
                "resolved",
            )
            self.assertIsNone(
                by_id[
                    "umspannwerk-bad-coordinate"
                ].geom
            )

            again = SignalIngestLoader(
                _Session(
                    existing=by_id[
                        "regionalplanung-stuttgart"
                    ]
                ),
                paths=DataPaths(tmp),
            ).execute()
            self.assertEqual(again["inserted"], 0)

            (raw / "merged.json").write_text(
                "{",
                encoding="utf-8",
            )
            malformed = SignalIngestLoader(
                _Session(),
                paths=DataPaths(tmp),
            ).execute()
            self.assertTrue(malformed["malformed_file"])
            self.assertEqual(malformed["inserted"], 0)


if __name__ == "__main__":
    unittest.main()
