from app.config.paths import DataPaths

from app.scrapers.hearings.hearings_scraper import (
    HearingsScraper,
)

from app.scrapers.hearings.hearings_parser import (
    HearingsParser,
)


def run(
    paths: DataPaths | None = None,
):
    """
    Run the Hearings acquisition and parsing pipeline.

    When called from `all`, the current RunContext-specific
    DataPaths are provided.

    When called independently, the default data/
    workspace is used.
    """

    paths = paths or DataPaths()

    # =====================================================
    # SCRAPER
    # =====================================================

    scraper = HearingsScraper(
        paths=paths,
    )

    scraper.scrape()

    # =====================================================
    # PARSER
    # =====================================================

    parser = HearingsParser(
        paths=paths,
    )

    return parser.parse()