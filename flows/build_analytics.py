"""Phase 1 scaffold for the analytics-build flow."""

from prefect import flow


@flow(name="build_analytics")
def build_analytics() -> None:
    """Placeholder flow body added in later implementation phases."""
    return None
