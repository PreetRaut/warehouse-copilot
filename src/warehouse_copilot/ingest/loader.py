"""Load raw FX rates into Snowflake idempotently.

Strategy: write the batch to a transient staging table with write_pandas, then
MERGE into RAW.FX_RATES on the natural key (date, base, quote). Re-running the
same range is safe - it updates in place rather than duplicating rows.

The database and schemas are created once by scripts/bootstrap_snowflake.sql
(run as ACCOUNTADMIN). This loader only *uses* them and creates its table, so
it can run under a least-privilege role that has no CREATE DATABASE right.
"""

from __future__ import annotations

import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas

from warehouse_copilot.config import Settings, get_settings
from warehouse_copilot.utils.logging import get_logger

log = get_logger(__name__)

_TARGET_TABLE = "FX_RATES"
_STAGING_TABLE = "FX_RATES_STAGING"


def _ensure_objects(cur, settings: Settings) -> None:
    # The database and schema are provisioned by bootstrap_snowflake.sql. We only
    # select them here (USE), then ensure the target table exists - both of which
    # the WAREHOUSE_COPILOT_RW role is granted, without needing account-level
    # CREATE DATABASE / CREATE SCHEMA privileges.
    cur.execute(f"USE DATABASE {settings.snowflake_database}")
    cur.execute(f"USE SCHEMA {settings.snowflake_schema_raw}")
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {_TARGET_TABLE} (
            RATE_DATE      DATE           NOT NULL,
            BASE_CURRENCY  STRING         NOT NULL,
            QUOTE_CURRENCY STRING         NOT NULL,
            RATE           FLOAT          NOT NULL,
            LOADED_AT      TIMESTAMP_NTZ  DEFAULT CURRENT_TIMESTAMP(),
            CONSTRAINT PK_FX_RATES PRIMARY KEY (RATE_DATE, BASE_CURRENCY, QUOTE_CURRENCY)
        )
        """
    )


def _merge_from_staging(cur) -> int:
    cur.execute(
        f"""
        MERGE INTO {_TARGET_TABLE} AS t
        USING {_STAGING_TABLE} AS s
          ON  t.RATE_DATE = s.RATE_DATE
          AND t.BASE_CURRENCY = s.BASE_CURRENCY
          AND t.QUOTE_CURRENCY = s.QUOTE_CURRENCY
        WHEN MATCHED THEN UPDATE SET
            t.RATE = s.RATE,
            t.LOADED_AT = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT
            (RATE_DATE, BASE_CURRENCY, QUOTE_CURRENCY, RATE, LOADED_AT)
        VALUES
            (s.RATE_DATE, s.BASE_CURRENCY, s.QUOTE_CURRENCY, s.RATE, CURRENT_TIMESTAMP())
        """
    )
    # rowcount reflects inserted + updated rows for MERGE.
    return cur.rowcount or 0


def load_to_snowflake(df: pd.DataFrame, settings: Settings | None = None) -> int:
    """Load a tidy FX DataFrame into RAW.FX_RATES. Returns rows affected."""
    if df.empty:
        log.warning("Nothing to load - DataFrame is empty.")
        return 0

    settings = settings or get_settings()
    if not settings.snowflake_account:
        raise RuntimeError(
            "Snowflake is not configured. Copy .env.example to .env and fill it in."
        )

    conn = snowflake.connector.connect(**settings.connection_kwargs())
    try:
        cur = conn.cursor()
        _ensure_objects(cur, settings)

        write_pandas(
            conn,
            df,
            table_name=_STAGING_TABLE,
            auto_create_table=True,
            overwrite=True,
            quote_identifiers=False,
        )
        affected = _merge_from_staging(cur)
        cur.execute(f"DROP TABLE IF EXISTS {_STAGING_TABLE}")
        conn.commit()
        log.info(
            "Loaded %s rows into %s.%s.%s",
            affected,
            settings.snowflake_database,
            settings.snowflake_schema_raw,
            _TARGET_TABLE,
        )
        return affected
    finally:
        conn.close()