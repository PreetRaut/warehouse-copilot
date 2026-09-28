"""Dagster orchestration: ingestion -> dbt build, on a daily schedule.

The dbt source (raw.fx_rates) is mapped to the Python ingestion asset so Dagster
understands the full lineage: raw_fx_rates -> staging -> marts. Run locally with:

    pip install -e ".[orchestration]"
    dbt deps --project-dir dbt/warehouse_copilot
    dagster dev -f orchestration/warehouse_copilot_dagster/definitions.py
"""

from __future__ import annotations

from pathlib import Path

from dagster import (
    AssetExecutionContext,
    AssetKey,
    Definitions,
    ScheduleDefinition,
    asset,
    define_asset_job,
)
from dagster_dbt import (
    DagsterDbtTranslator,
    DbtCliResource,
    DbtProject,
    dbt_assets,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DBT_DIR = _REPO_ROOT / "dbt" / "warehouse_copilot"

dbt_project = DbtProject(project_dir=_DBT_DIR)
dbt_project.prepare_if_dev()

_INGEST_KEY = AssetKey(["raw_fx_rates"])


class _Translator(DagsterDbtTranslator):
    """Point the dbt `raw.fx_rates` source at the Python ingestion asset."""

    def get_asset_key(self, dbt_resource_props: dict) -> AssetKey:
        if dbt_resource_props.get("resource_type") == "source":
            return _INGEST_KEY
        return super().get_asset_key(dbt_resource_props)


@asset(key=_INGEST_KEY, compute_kind="python", group_name="ingestion")
def raw_fx_rates(context: AssetExecutionContext) -> None:
    """Fetch FX rates and load them into Snowflake RAW.FX_RATES."""
    from warehouse_copilot.ingest.run import main

    context.log.info("Running FX ingestion for the last 90 days.")
    main([])  # live source with synthetic fallback; see run.py for flags


@dbt_assets(manifest=dbt_project.manifest_path, dagster_dbt_translator=_Translator())
def dbt_models(context: AssetExecutionContext, dbt: DbtCliResource):
    """Build all dbt models, seeds and tests."""
    yield from dbt.cli(["build"], context=context).stream()


daily_job = define_asset_job("daily_refresh", selection="*")
daily_schedule = ScheduleDefinition(
    job=daily_job,
    cron_schedule="0 6 * * *",  # 06:00 every day
)

defs = Definitions(
    assets=[raw_fx_rates, dbt_models],
    jobs=[daily_job],
    schedules=[daily_schedule],
    resources={"dbt": DbtCliResource(project_dir=dbt_project)},
)
