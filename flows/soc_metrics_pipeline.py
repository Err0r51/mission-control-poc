"""Phase 1 scaffold for the parent SOC metrics pipeline flow."""

from prefect import flow


@flow(name="soc_metrics_pipeline")
def soc_metrics_pipeline() -> None:
    """Placeholder parent flow body added in later implementation phases."""
    return None
