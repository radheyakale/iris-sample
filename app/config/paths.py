from pathlib import Path


class DataPaths:
    """
    Centralized data paths for an IRIS pipeline run.

    The root can represent:

        data/
        data/runs/<run_id>/
        data/current/

    All ETL components should use this class instead
    of hard-coding data/raw or data/processed paths.
    """

    def __init__(
        self,
        root: Path | str = "data",
    ):
        self.root = Path(root)

    # =====================================================
    # ROOTS
    # =====================================================

    @property
    def raw(self) -> Path:
        return self.root / "raw"

    @property
    def processed(self) -> Path:
        return self.root / "processed"

    # =====================================================
    # DATACENTERMAP
    # =====================================================

    @property
    def datacentermap_raw(self) -> Path:
        return (
            self.raw
            / "datacentermap"
        )

    @property
    def datacentermap_processed(self) -> Path:
        return (
            self.processed
            / "datacentermap"
        )

    @property
    def datacentermap_facilities_raw(self) -> Path:
        return (
            self.datacentermap_raw
            / "facilities"
        )

    # =====================================================
    # OVERPASS
    # =====================================================

    @property
    def overpass_raw(self) -> Path:
        return (
            self.raw
            / "overpass"
        )

    @property
    def overpass_processed(self) -> Path:
        return (
            self.processed
            / "overpass"
        )

    # =====================================================
    # HEARINGS
    # =====================================================

    @property
    def hearings_raw(self) -> Path:
        return (
            self.raw
            / "hearings"
        )

    # =====================================================
    # MASTR
    # =====================================================

    @property
    def mastr_raw(self) -> Path:
        return (
            self.raw
            / "mastr"
        )

    @property
    def mastr_processed(self) -> Path:
        return (
            self.processed
            / "mastr"
        )

    # =====================================================
    # BORIS
    # =====================================================

    @property
    def boris_raw(self) -> Path:
        return (
            self.raw
            / "boris"
        )

    @property
    def boris_processed(self) -> Path:
        return (
            self.processed
            / "boris"
        )

    # =====================================================
    # ENRICHED
    # =====================================================

    @property
    def enriched(self) -> Path:
        return (
            self.processed
            / "enriched"
        )

    # =====================================================
    # INTELLIGENCE
    # =====================================================

    @property
    def intelligence(self) -> Path:
        return (
            self.processed
            / "intelligence"
        )

    # =====================================================
    # NEWS
    # =====================================================

    @property
    def news_raw(self) -> Path:
        return (
            self.raw
            / "news"
        )

    @property
    def news_processed(self) -> Path:
        return (
            self.processed
            / "news"
        )

    # =====================================================
    # FACILITIES
    # =====================================================

    @property
    def facilities_processed(self) -> Path:
        return (
            self.processed
            / "facilities"
        )

    # =====================================================
    # CREATE DIRECTORIES
    # =====================================================

    def create_directories(self) -> None:
        """
        Create the complete directory structure
        required by an ETL run.
        """

        directories = (
            self.raw,
            self.processed,

            # DataCenterMap
            self.datacentermap_raw,
            self.datacentermap_processed,
            self.datacentermap_facilities_raw,

            # Overpass
            self.overpass_raw,
            self.overpass_processed,

            # MaStR
            self.mastr_raw,
            self.mastr_processed,

            # BORIS
            self.boris_raw,
            self.boris_processed,

            # Derived data
            self.enriched,
            self.intelligence,

            # News
            self.news_raw,
            self.news_processed,

            # Facilities
            self.facilities_processed,
        )

        for directory in directories:

            directory.mkdir(
                parents=True,
                exist_ok=True,
            )