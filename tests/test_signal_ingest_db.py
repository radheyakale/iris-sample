import json
import os
import unittest
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import bindparam
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import ProgrammingError

load_dotenv()

FIXTURES = (
    Path(__file__).parent
    / "fixtures"
    / "hearings"
)

SOURCE_IDS = (
    "regionalplanung-stuttgart",
    "umspannwerk-karlsruhe",
    "umspannwerk-bad-coordinate",
)


def _database_ready() -> bool:
    if not os.getenv("DATABASE_URL"):
        return False
    try:
        from app.database.session import SessionLocal

        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))
            session.execute(
                text(
                    "SELECT 1 FROM iris_staging.signal_ingest LIMIT 1"
                )
            )
            return True
        finally:
            session.rollback()
            session.close()
    except (OperationalError, ProgrammingError):
        return False


@unittest.skipUnless(
    _database_ready(),
    "PostgreSQL with iris_staging.signal_ingest is not reachable",
)
class SignalIngestDatabaseTests(unittest.TestCase):
    """
    Loads tests/fixtures/hearings/signals.json into PostGIS.

    The transaction is rolled back, so the fixture rows are
    not left in the database.
    """

    def setUp(self):
        from app.database.session import SessionLocal

        self.session = SessionLocal()

    def tearDown(self):
        self.session.rollback()
        self.session.close()

    def test_fixture_ingest_on_postgis(self):
        from app.loaders.signal_ingest_loader import (
            SignalIngestLoader,
        )

        version = self.session.scalar(
            text("SHOW server_version")
        )
        postgis = self.session.scalar(
            text("SELECT postgis_version()")
        )
        self.assertTrue(str(version).startswith("16"))
        self.assertTrue(str(postgis).startswith("3.4"))

        delete = text(
            """
            DELETE FROM iris_staging.signal_ingest
            WHERE source_system = 'beteiligung_bw'
              AND source_id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True))
        self.session.execute(
            delete,
            {"ids": list(SOURCE_IDS)},
        )

        records = json.loads(
            (FIXTURES / "signals.json").read_text(
                encoding="utf-8"
            )
        )
        loader = SignalIngestLoader.__new__(
            SignalIngestLoader
        )
        loader.session = self.session

        first = loader._load_records(records)
        self.session.flush()
        self.assertEqual(first["inserted"], 3)
        self.assertEqual(first["duplicates_skipped"], 1)

        select = text(
            """
            SELECT
                source_id,
                signal_type,
                location_status,
                ST_SRID(geom) AS srid,
                geom IS NULL AS geom_is_null,
                count(*) OVER (PARTITION BY source_id) AS copies
            FROM iris_staging.signal_ingest
            WHERE source_system = 'beteiligung_bw'
              AND source_id IN :ids
            """
        ).bindparams(bindparam("ids", expanding=True))
        rows = self.session.execute(
            select,
            {"ids": list(SOURCE_IDS)},
        ).mappings().all()
        by_id = {row["source_id"]: row for row in rows}

        self.assertEqual(set(by_id), set(SOURCE_IDS))
        regional = by_id["regionalplanung-stuttgart"]
        self.assertEqual(
            regional["signal_type"],
            "regional_plan_amendment",
        )
        self.assertEqual(
            regional["location_status"],
            "ambiguous",
        )
        self.assertTrue(regional["geom_is_null"])
        self.assertEqual(regional["copies"], 1)

        substation = by_id["umspannwerk-karlsruhe"]
        self.assertEqual(
            substation["signal_type"],
            "substation_expansion_hearing",
        )
        self.assertEqual(
            substation["location_status"],
            "resolved",
        )
        self.assertEqual(substation["srid"], 25832)
        self.assertFalse(substation["geom_is_null"])
        self.assertEqual(substation["copies"], 1)

        rejected = by_id["umspannwerk-bad-coordinate"]
        self.assertEqual(
            rejected["location_status"],
            "unresolved",
        )
        self.assertTrue(rejected["geom_is_null"])

        second = loader._load_records(records)
        self.session.flush()
        self.assertEqual(second["inserted"], 0)
        self.assertEqual(second["unchanged"], 3)


if __name__ == "__main__":
    unittest.main()
