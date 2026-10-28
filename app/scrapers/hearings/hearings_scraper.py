from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from app.config.data_sources import get_data_source
from app.config.paths import DataPaths
from app.scrapers.base.http_client import HttpClient


class HearingsScraper:
    """
    Scrapes public Hearings data.

    Raw responses are stored in the workspace provided
    by DataPaths.

    Default:

        data/raw/hearings/

    Pipeline run:

        data/runs/<run_id>/raw/hearings/
    """

    def __init__(
        self,
        paths: DataPaths | None = None,
    ):

        self.paths = paths or DataPaths()

        self.client = HttpClient()

        self.source = get_data_source(
            "hearings"
        )

        # -------------------------------------------------
        # Run-specific output directory
        # -------------------------------------------------

        self.output_dir = (
            self.paths.hearings_raw
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # =====================================================
    # SCRAPE
    # =====================================================

    def scrape(self):

        if not self.source.urls:

            raise ValueError(
                "No URL configured for hearings data source."
            )

        url = self.source.urls[0]

        if not self._allowed(url):

            print(
                "Excluded by robots.txt: "
                f"{url}"
            )

            return {
                "fetched": 0,
                "empty_pages": 0,
                "excluded_by_robots": True,
            }

        # /de/mitmachen is one HTML page. It ignores
        # page and pageSize. The search results that
        # do paginate are disallowed by robots.txt.

        print(
            "Downloading hearings listing..."
        )

        response = self.client.get(url)

        for stale in self.output_dir.glob(
            "page_*.html"
        ):

            stale.unlink()

        output_file = (
            self.output_dir
            / "page_1.html"
        )

        body = response.text or ""

        output_file.write_text(
            body,
            encoding="utf-8",
        )

        empty_pages = (
            0 if body.strip() else 1
        )

        print(
            f"Saved {output_file}"
        )

        if empty_pages:

            print(
                "Empty hearings response."
            )

        print("--------------------------------")
        print(
            "hearings scraping completed."
        )

        print(
            f"Output Directory : "
            f"{self.output_dir}"
        )

        return {
            "fetched": 1,
            "empty_pages": empty_pages,
            "excluded_by_robots": False,
        }

    def _allowed(
        self,
        url: str,
    ) -> bool:

        origin = urlsplit(url)

        robots_url = (
            f"{origin.scheme}://{origin.netloc}"
            "/de/robots.txt"
        )

        response = self.client.get(robots_url)

        robots = RobotFileParser()

        robots.parse(
            (response.text or "").splitlines()
        )

        return robots.can_fetch("*", url)
