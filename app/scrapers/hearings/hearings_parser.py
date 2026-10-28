import json

from app.config.data_sources import get_data_source
from app.config.paths import DataPaths
from app.scrapers.base.parser import HearingsHTMLDataParser
from app.scrapers.hearings.hearings_filter import HearingsFilter


class HearingsParser:
    """
    Parses and merges Hearings raw page responses.

    Input:
        <run>/raw/hearings/page_*.html

    Output:
        <run>/raw/hearings/merged.json

    The workspace is controlled by DataPaths so that
    each pipeline execution remains isolated.
    """

    def __init__(
        self,
        paths: DataPaths | None = None,
    ):

        self.paths = paths or DataPaths()

        # -------------------------------------------------
        # Run-specific paths
        # -------------------------------------------------

        self.input_dir = (
            self.paths.hearings_raw
        )

        self.output_file = (
            self.input_dir
            / "merged.json"
        )

        self.html_parser = HearingsHTMLDataParser()

        source = get_data_source("hearings")
        self.base_url = source.urls[0] if source.urls else None

    # =====================================================
    # PARSE
    # =====================================================

    def parse(self):

        if not self.input_dir.exists():

            raise FileNotFoundError(
                f"hearings raw directory not found: "
                f"{self.input_dir}"
            )

        merged_records = []
        empty_pages = 0
        dropped_missing_fields = 0

        page_files = sorted(
            self.input_dir.glob(
                "page_*.html"
            )
        )

        if not page_files:

            raise FileNotFoundError(
                "No hearings page files found "
                f"in {self.input_dir}."
            )

        print(
            f"Found {len(page_files)} "
            f"hearings page(s)."
        )

        for page_file in page_files:

            print(
                f"Reading "
                f"{page_file.name}"
            )

            html = page_file.read_text(
                encoding="utf-8",
            )

            records = self.html_parser.parse(
                html,
                base_url=self.base_url,
            )

            dropped_missing_fields += (
                self.html_parser.dropped_missing_fields
            )

            if not html.strip() or not records:

                empty_pages += 1

                print(
                    f"⚠ {page_file.name}: "
                    "no data available. "
                    "Skipping."
                )

                continue

            merged_records.extend(
                records
            )

        seen = set()
        unique_records = []
        duplicates_skipped = 0

        for record in merged_records:

            source_id = str(
                record.get("source_id") or ""
            ).strip()

            if source_id and source_id in seen:

                duplicates_skipped += 1

                continue

            if source_id:

                seen.add(source_id)

            unique_records.append(record)

        merged_records = HearingsFilter().apply(
            unique_records
        )

        quality = {
            "pages": len(page_files),
            "empty_pages": empty_pages,
            "records": len(merged_records),
            "duplicates_skipped": duplicates_skipped,
            "dropped_missing_fields": dropped_missing_fields,
        }

        quality_file = (
            self.input_dir
            / "parse_quality.json"
        )

        quality_file.write_text(
            json.dumps(
                quality,
                indent=2,
            ),
            encoding="utf-8",
        )

        with self.output_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                merged_records,
                file,
                ensure_ascii=False,
                indent=2,
            )

        print("--------------------------------")
        print(
            f"Total Records : "
            f"{len(merged_records)}"
        )

        print(
            f"Saved         : "
            f"{self.output_file}"
        )

        return merged_records