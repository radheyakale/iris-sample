from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path

from geoalchemy2.elements import WKTElement
from pyproj import Transformer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.paths import DataPaths
from app.database.models.signal_ingest import SignalIngest
from app.scrapers.hearings.hearings_filter import HearingsFilter


# Germany, axis order x/y. A point outside this box is rejected.
# Longitude/latitude are not swapped to force a fit.
BOUNDS = {
    4326: (5.8, 47.2, 15.1, 55.1),
    25832: (280000, 5230000, 920000, 6100000),
}

_TO_25832 = Transformer.from_crs(
    4326,
    25832,
    always_xy=True,
)


class SignalIngestLoader:
    """
    Loads relevant hearings into iris_staging.signal_ingest.

    The loader is idempotent:

    - Existing rows are identified by source system and source id.
    - An unchanged content hash is left as it is.
    - A changed content hash updates the existing row.
    - New source ids are inserted.

    DataPaths controls the input workspace so each
    pipeline execution can load its own isolated data.
    """

    def __init__(
        self,
        session: Session,
        paths: DataPaths | None = None,
    ):

        self.session = session

        self.paths = paths or DataPaths()

        # --------------------------------------------------
        # Input files
        # --------------------------------------------------

        self.source_file = (
            self.paths.hearings_raw
            / "merged.json"
        )

    # ======================================================
    # MAIN
    # ======================================================

    def execute(self):

        print("--------------------------------")
        print(
            "Loading Signal Ingest"
        )

        records, problem = self._load_json(
            self.source_file
        )

        report = self._blank_report()

        if problem == "malformed":

            report["malformed_file"] = True

            self._merge_parse_stats(report)

            self._write_quality(report)

            print(
                "Malformed hearings JSON. "
                "Nothing loaded."
            )

            return report

        print(
            f"Hearings : "
            f"{len(records)}"
        )

        try:

            report.update(
                self._load_records(
                    records
                )
            )

            self.session.commit()

        except Exception:

            self.session.rollback()

            raise

        report["empty_response"] = problem in {
            "missing",
            "empty",
        }

        report["rows_loaded"] = (
            report["inserted"]
            + report["updated"]
            + report["unchanged"]
        )

        self._merge_parse_stats(report)

        self._write_quality(report)

        print("--------------------------------")

        print(
            f"Inserted  : "
            f"{report['inserted']}"
        )

        print(
            f"Updated   : "
            f"{report['updated']}"
        )

        print(
            f"Unchanged : "
            f"{report['unchanged']}"
        )

        print(
            f"Duplicates skipped : "
            f"{report['duplicates_skipped']}"
        )

        print(
            f"Dropped missing    : "
            f"{report['dropped_missing_fields']}"
        )

        print(
            f"Ambiguous : "
            f"{report['ambiguous']}"
        )

        print(
            f"Unresolved: "
            f"{report['unresolved']}"
        )

        print("--------------------------------")

        print(
            "Signal Ingest "
            "Loaded Successfully"
        )

        return report

    # ======================================================
    # JSON
    # ======================================================

    @staticmethod
    def _load_json(
        file: Path,
    ) -> tuple[list, str | None]:

        if not file.exists():

            return [], "missing"

        try:

            with file.open(
                "r",
                encoding="utf-8",
            ) as handle:

                data = json.load(handle)

        except json.JSONDecodeError:

            return [], "malformed"

        if data is None or data == []:

            return [], "empty"

        if not isinstance(
            data,
            list,
        ):

            return [], "malformed"

        return data, None

    # ======================================================
    # RECORDS
    # ======================================================

    def _load_records(
        self,
        records: list,
    ) -> tuple[int, int, int]:

        inserted = 0
        updated = 0
        unchanged = 0
        duplicates_skipped = 0
        dropped_missing_fields = 0
        dropped_not_relevant = 0
        malformed_records = 0
        resolved = 0
        ambiguous = 0
        unresolved = 0

        seen = set()

        for record in records:

            if not isinstance(record, dict):

                malformed_records += 1

                continue

            source_id = str(
                record.get("source_id") or ""
            ).strip()

            title = str(
                record.get("title") or ""
            ).strip()

            source_url = str(
                record.get("source_url") or ""
            ).strip()

            if (
                not source_id
                or not title
                or not source_url
            ):

                dropped_missing_fields += 1

                continue

            if source_id in seen:

                duplicates_skipped += 1

                continue

            if record.get("relevant") is not True:

                dropped_not_relevant += 1

                continue

            seen.add(source_id)

            text = (
                f"{title} "
                f"{record.get('place_text') or ''}"
            ).casefold()

            if HearingsFilter.REGIONAL_PLAN.search(text):

                signal_type = "regional_plan_amendment"

            elif (
                HearingsFilter.EQUIPMENT.search(text)
                and HearingsFilter.EXPANSION.search(text)
            ):

                signal_type = "substation_expansion_hearing"

            else:

                dropped_not_relevant += 1

                continue

            # --------------------------------------------------
            # Location
            # --------------------------------------------------

            place = str(
                record.get("place_text") or ""
            ).strip() or None

            point = self._coordinate(record)

            geom = None

            if point == "malformed":

                location_status = "unresolved"

                location_note = (
                    "rejected coordinate: "
                    "value is not numeric"
                )

            elif point is None and place:

                location_status = "ambiguous"

                location_note = (
                    "place name only; "
                    "source has no coordinate"
                )

            elif point is None:

                location_status = "unresolved"

                location_note = "source has no location"

            else:

                x, y, crs = point

                bounds = BOUNDS.get(crs)

                if (
                    not math.isfinite(x)
                    or not math.isfinite(y)
                ):

                    location_note = (
                        "rejected coordinate: "
                        "value is not finite"
                    )

                elif x == 0 and y == 0:

                    location_note = (
                        "rejected coordinate: "
                        "point is (0, 0)"
                    )

                elif bounds is None:

                    location_note = (
                        "rejected coordinate: "
                        f"CRS EPSG:{crs} is unknown"
                    )

                elif not (
                    bounds[0] <= x <= bounds[2]
                    and bounds[1] <= y <= bounds[3]
                ):

                    location_note = (
                        "rejected coordinate: "
                        "outside the Germany bounds "
                        f"for EPSG:{crs}"
                    )

                else:

                    location_note = None

                    if crs == 4326:

                        x, y = _TO_25832.transform(
                            x,
                            y,
                        )

                    geom = WKTElement(
                        f"POINT({x} {y})",
                        srid=25832,
                    )

                location_status = (
                    "resolved"
                    if geom is not None
                    else "unresolved"
                )

            if location_status == "resolved":

                resolved += 1

            elif location_status == "ambiguous":

                ambiguous += 1

            else:

                unresolved += 1

            dates = {}

            for key in (
                "published_at",
                "participation_start",
                "participation_end",
            ):

                raw_date = record.get(key)

                parsed = None

                if raw_date:

                    try:

                        parsed = datetime.strptime(
                            str(raw_date).strip()[:10],
                            "%Y-%m-%d",
                        ).date()

                    except ValueError:

                        parsed = None

                dates[key] = parsed

            row = {
                "source_system": "beteiligung_bw",
                "source_id": source_id,
                "signal_type": signal_type,
                "title": title,
                "published_at": dates["published_at"],
                "participation_start": dates[
                    "participation_start"
                ],
                "participation_end": dates[
                    "participation_end"
                ],
                "source_url": source_url,
                "place_text": place,
                "geom": geom,
                "location_status": location_status,
                "location_note": location_note,
                "raw_payload": record,
            }

            raw = json.dumps(
                {
                    **row,
                    "geom": (
                        None
                        if geom is None
                        else str(geom)
                    ),
                },
                sort_keys=True,
                default=str,
            )

            row["content_hash"] = hashlib.sha256(
                raw.encode()
            ).hexdigest()

            action = self._upsert(row)

            if action == "inserted":

                inserted += 1

            elif action == "updated":

                updated += 1

            else:

                unchanged += 1

        return {
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
            "rows_loaded": (
                inserted + updated + unchanged
            ),
            "duplicates_skipped": duplicates_skipped,
            "dropped_missing_fields": (
                dropped_missing_fields
            ),
            "dropped_not_relevant": (
                dropped_not_relevant
            ),
            "malformed_records": malformed_records,
            "resolved": resolved,
            "ambiguous": ambiguous,
            "unresolved": unresolved,
        }

    # ======================================================
    # COORDINATES AND QUALITY
    # ======================================================

    @staticmethod
    def _coordinate(
        record: dict,
    ):

        candidates = (
            ("longitude", "latitude", 4326),
            ("lon", "lat", 4326),
            ("easting", "northing", 25832),
        )

        for x_key, y_key, default_crs in candidates:

            if (
                record.get(x_key) is None
                or record.get(y_key) is None
            ):

                continue

            return SignalIngestLoader._as_point(
                record.get(x_key),
                record.get(y_key),
                record.get("crs")
                or record.get("srid")
                or default_crs,
            )

        if (
            record.get("x") is None
            or record.get("y") is None
            or not (
                record.get("crs")
                or record.get("srid")
            )
        ):

            return None

        return SignalIngestLoader._as_point(
            record.get("x"),
            record.get("y"),
            record.get("crs") or record.get("srid"),
        )

    @staticmethod
    def _as_point(x_value, y_value, crs_value):

        try:

            return (
                float(x_value),
                float(y_value),
                int(crs_value),
            )

        except (TypeError, ValueError):

            return "malformed"

    @staticmethod
    def _blank_report() -> dict:

        return {
            "rows_loaded": 0,
            "inserted": 0,
            "updated": 0,
            "unchanged": 0,
            "duplicates_skipped": 0,
            "empty_pages": 0,
            "empty_response": False,
            "ambiguous": 0,
            "unresolved": 0,
            "resolved": 0,
            "dropped_missing_fields": 0,
            "dropped_not_relevant": 0,
            "malformed_records": 0,
            "malformed_file": False,
        }

    def _merge_parse_stats(
        self,
        report: dict,
    ):

        path = (
            self.paths.hearings_raw
            / "parse_quality.json"
        )

        if not path.exists():

            return

        try:

            stats = json.loads(
                path.read_text(encoding="utf-8")
            )

        except json.JSONDecodeError:

            return

        if not isinstance(stats, dict):

            return

        report["empty_pages"] = int(
            stats.get("empty_pages") or 0
        )

        report["duplicates_skipped"] += int(
            stats.get("duplicates_skipped") or 0
        )

        report["dropped_missing_fields"] += int(
            stats.get("dropped_missing_fields") or 0
        )

    def _write_quality(
        self,
        report: dict,
    ):

        path = (
            self.paths.hearings_raw
            / "quality_report.json"
        )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        path.write_text(
            json.dumps(
                report,
                indent=2,
            ),
            encoding="utf-8",
        )

    # ======================================================
    # UPSERT
    # ======================================================

    def _upsert(
        self,
        row: dict,
    ) -> str:

        existing = self.session.scalar(
            select(SignalIngest)
            .where(
                SignalIngest.source_system
                == row["source_system"],
                SignalIngest.source_id
                == row["source_id"],
            )
        )

        # --------------------------------------------------
        # New source id
        # --------------------------------------------------

        if existing is None:

            self.session.add(
                SignalIngest(**row)
            )

            return "inserted"

        # --------------------------------------------------
        # Same content
        # --------------------------------------------------

        if existing.content_hash == row["content_hash"]:

            return "unchanged"

        # --------------------------------------------------
        # Changed content
        # --------------------------------------------------

        for key, value in row.items():

            setattr(
                existing,
                key,
                value,
            )

        return "updated"
