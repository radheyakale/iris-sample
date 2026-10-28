from app.config.paths import DataPaths
from app.database.session import SessionLocal
from app.loaders.signal_ingest_loader import SignalIngestLoader


def run(
    paths: DataPaths | None = None,
):
    """
    Load merged hearings into iris_staging.signal_ingest.
    """

    paths = paths or DataPaths()
    session = SessionLocal()

    try:
        return SignalIngestLoader(
            session,
            paths=paths,
        ).execute()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
