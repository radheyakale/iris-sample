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

        records = self._load_json(
            self.source_file
        )

        print(
            f"Hearings : "
            f"{len(records)}"
        )

        try:

            inserted, updated, unchanged = (
                self._load_records(
                    records
                )
            )

            self.session.commit()

        except Exception:

            self.session.rollback()

            raise

        print("--------------------------------")

        print(
            f"Inserted  : "
            f"{inserted}"
        )

        print(
            f"Updated   : "
            f"{updated}"
        )

        print(
            f"Unchanged : "
            f"{unchanged}"
        )

        print("--------------------------------")

        print(
            "Signal Ingest "
            "Loaded Successfully"
        )

        return {
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
        }

    # ======================================================
    # JSON
    # ======================================================

    @staticmethod
    def _load_json(
        file: Path,
    ) -> list:

        if not file.exists():

            return []

        with file.open(
            "r",
            encoding="utf-8",
        ) as handle:

            data = json.load(handle)

        if data is None:

            return []

        if not isinstance(
            data,
            list,
        ):

            raise ValueError(
                f"Expected a JSON list in {file}"
            )

        return data

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

        seen = set()

        for record in records:

            if not isinstance(record, dict):

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
                or source_id in seen
                or record.get("relevant") is not True
            ):

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

                continue

            # --------------------------------------------------
            # Location
            # --------------------------------------------------

            place = str(
                record.get("place_text") or ""
            ).strip() or None

            point = None

            for x_key, y_key, default_crs in (
                ("longitude", "latitude", 4326),
                ("lon", "lat", 4326),
                ("easting", "northing", 25832),
            ):

                if (
                    record.get(x_key) is None
                    or record.get(y_key) is None
                ):

                    continue

                point = (
                    float(record[x_key]),
                    float(record[y_key]),
                    int(
                        record.get("crs")
                        or record.get("srid")
                        or default_crs
                    ),
                )

                break

            if (
                point is None
                and record.get("x") is not None
                and record.get("y") is not None
                and (
                    record.get("crs")
                    or record.get("srid")
                )
            ):

                point = (
                    float(record["x"]),
                    float(record["y"]),
                    int(
                        record.get("crs")
                        or record.get("srid")
                    ),
                )

            geom = None

            if point is None and place:

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

        return inserted, updated, unchanged

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
