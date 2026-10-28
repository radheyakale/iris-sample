from datetime import date
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Identity
from sqlalchemy import Index
from sqlalchemy import Text
from sqlalchemy import UniqueConstraint
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from app.database.base import Base


class SignalIngest(Base):
    """
    Staging row for one public hearing.

    Identity is (source_system, source_id), the same idea
    as facilities.source_id. The point is EPSG:25832, as
    on land_values, and is null unless location_status
    is resolved.
    """

    __tablename__ = "signal_ingest"

    __table_args__ = (
        UniqueConstraint(
            "source_system",
            "source_id",
            name="uq_signal_ingest_source",
        ),
        Index(
            "idx_signal_ingest_geom",
            "geom",
            postgresql_using="gist",
        ),
        {"schema": "iris_staging"},
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    source_system: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(Text)
    signal_type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    published_at: Mapped[date | None] = mapped_column(Date)
    participation_start: Mapped[date | None] = mapped_column(Date)
    participation_end: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str] = mapped_column(Text)
    place_text: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[str | None] = mapped_column(
        Geometry(
            geometry_type="POINT",
            srid=25832,
            spatial_index=False,
        )
    )
    location_status: Mapped[str] = mapped_column(Text)
    location_note: Mapped[str | None] = mapped_column(Text)
    raw_payload: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(Text)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
