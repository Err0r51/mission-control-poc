"""Parent Prefect flow that runs the SOC metrics pipeline end to end."""

from prefect import flow, get_run_logger

from flows.build_analytics import build_analytics
from flows.ingest_raw import ingest_raw


@flow(name="soc_metrics_pipeline")
def soc_metrics_pipeline() -> None:
    """Run raw ingestion and analytics rebuild in sequence."""
    logger = get_run_logger()

    logger.info("Starting raw ingestion flow.")
    ingest_raw()

    logger.info("Starting analytics rebuild flow.")
    build_analytics()

    logger.info("Completed SOC metrics pipeline.")
