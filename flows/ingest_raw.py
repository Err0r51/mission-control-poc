"""Phase 1 scaffold for the raw-ingestion flow."""

from prefect import flow


@flow(name="ingest_raw")
def ingest_raw() -> None:
    """Placeholder flow body added in later implementation phases."""
    return None
