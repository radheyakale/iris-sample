from app.config.paths import DataPaths
from app.scrapers.hearings.hearings_parser import HearingsParser


def run(
    paths: DataPaths | None = None,
):
    """
    Run the Hearings parser.

    When called from `all`, the current RunContext-specific
    DataPaths are provided.

    When called independently, the default data/
    workspace is used.
    """

    paths = paths or DataPaths()

    parser = HearingsParser(
        paths=paths,
    )

    return parser.parse()