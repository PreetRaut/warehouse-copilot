"""MCP server: let any MCP client (Claude Desktop, VS Code, ...) query the
Snowflake warehouse in natural language, safely.

Built on FastMCP (bundled with the official `mcp` Python SDK). Exposes:
  - resource  schema://tables            -> catalogue of analytics tables
  - tool      list_tables()              -> table names in the ANALYTICS schema
  - tool      describe_table(table)      -> column names + types
  - tool      run_query(sql)             -> read-only SELECT, auto-LIMITed
  - tool      top_movers(days, limit)    -> convenience over the metrics mart

All queries pass through the read-only guard in sql_guard.py and run under a
statement timeout, ideally with a dedicated read-only Snowflake role.
"""

from __future__ import annotations

from typing import Any

import snowflake.connector
from mcp.server.fastmcp import FastMCP

from warehouse_copilot.config import get_settings
from warehouse_copilot.mcp_server.sql_guard import apply_row_limit, assert_read_only
from warehouse_copilot.utils.logging import get_logger

log = get_logger("wc-mcp")
mcp = FastMCP("warehouse-copilot")


def _connect():
    settings = get_settings()
    if not settings.snowflake_account:
        raise RuntimeError("Snowflake is not configured. See .env.example.")
    kwargs = settings.connection_kwargs()
    kwargs["schema"] = settings.snowflake_schema_analytics
    conn = snowflake.connector.connect(**kwargs)
    conn.cursor().execute(
        f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = {settings.mcp_statement_timeout_seconds}"
    )
    return conn


def _run(sql: str) -> list[dict[str, Any]]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
    finally:
        conn.close()


@mcp.resource("schema://tables")
def schema_catalogue() -> str:
    """A human-readable catalogue of tables in the ANALYTICS schema."""
    settings = get_settings()
    rows = _run(
        f"""
        SELECT table_name, row_count, comment
        FROM {settings.snowflake_database}.INFORMATION_SCHEMA.TABLES
        WHERE table_schema = '{settings.snowflake_schema_analytics}'
        ORDER BY table_name
        """
    )
    if not rows:
        return "No tables found. Have you run `dbt build`?"
    lines = [f"- {r['TABLE_NAME']} ({r['ROW_COUNT']} rows): {r['COMMENT'] or 'n/a'}" for r in rows]
    return "Analytics tables:\n" + "\n".join(lines)


@mcp.tool()
def list_tables() -> list[str]:
    """List table and view names available in the analytics schema."""
    settings = get_settings()
    rows = _run(
        f"""
        SELECT table_name
        FROM {settings.snowflake_database}.INFORMATION_SCHEMA.TABLES
        WHERE table_schema = '{settings.snowflake_schema_analytics}'
        ORDER BY table_name
        """
    )
    return [r["TABLE_NAME"] for r in rows]


@mcp.tool()
def describe_table(table: str) -> list[dict[str, Any]]:
    """Return column names and data types for a table in the analytics schema."""
    safe = assert_read_only(f"DESCRIBE TABLE {table}")  # validates identifier shape
    settings = get_settings()
    return _run(
        f"""
        SELECT column_name, data_type, is_nullable
        FROM {settings.snowflake_database}.INFORMATION_SCHEMA.COLUMNS
        WHERE table_schema = '{settings.snowflake_schema_analytics}'
          AND table_name = UPPER('{table}')
        ORDER BY ordinal_position
        """
    ) or [{"note": f"No such table: {table}", "checked": safe}]


@mcp.tool()
def run_query(sql: str) -> list[dict[str, Any]]:
    """Run a read-only SELECT against the warehouse.

    Only a single SELECT/WITH statement is permitted; a LIMIT is applied
    automatically. DML/DDL is rejected before it reaches Snowflake.
    """
    settings = get_settings()
    safe = assert_read_only(sql)
    safe = apply_row_limit(safe, settings.mcp_row_limit)
    log.info("run_query: %s", safe.replace("\n", " ")[:200])
    return _run(safe)


@mcp.tool()
def top_movers(days: int = 7, limit: int = 10) -> list[dict[str, Any]]:
    """Currencies with the largest recent move, from MART_FX_DAILY_METRICS."""
    settings = get_settings()
    fqtn = (
        f"{settings.snowflake_database}."
        f"{settings.snowflake_schema_analytics}.MART_FX_DAILY_METRICS"
    )
    sql = f"""
        SELECT quote_currency, rate_date, rate, daily_return, volatility_30
        FROM {fqtn}
        WHERE rate_date >= DATEADD('day', -{int(days)}, CURRENT_DATE())
        ORDER BY ABS(daily_return) DESC NULLS LAST
        LIMIT {int(limit)}
    """
    return _run(sql)


def main() -> None:
    """Entry point for `wc-mcp` and `python -m warehouse_copilot.mcp_server.server`."""
    mcp.run()


if __name__ == "__main__":
    main()
