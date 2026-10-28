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

    def scrape(
        self,
        start_page: int = 1,
        max_pages: int = 5,
        page_size: int = 20,
    ):

        if not self.source.urls:

            raise ValueError(
                "No URL configured for hearings data source."
            )

        url = self.source.urls[0]

        robots = RobotFileParser()
        origin = urlsplit(url)
        robots.set_url(
            f"{origin.scheme}://{origin.netloc}/de/robots.txt"
        )
        robots.read()

        if not robots.can_fetch("*", url):

            print(
                "Excluded by robots.txt: "
                f"{url}"
            )

            return

        for page in range(
            start_page,
            start_page + max_pages,
        ):

            print(
                f"Downloading page {page}..."
            )

            response = self.client.get(
                url,
                params={
                    "page": page,
                    "pageSize": page_size,
                    "group": "",
                    "filter": "",
                },
            )

            output_file = (
                self.output_dir
                / f"page_{page}.html"
            )

            output_file.write_text(
                response.text,
                encoding="utf-8",
            )

            print(
                f"Saved {output_file}"
            )

        print("--------------------------------")
        print(
            "hearings scraping completed."
        )

        print(
            f"Output Directory : "
            f"{self.output_dir}"
        )
