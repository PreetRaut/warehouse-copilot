# Architecture

```mermaid
flowchart LR
    subgraph Ingest["Ingestion (Python)"]
        A["Frankfurter API<br/>(ECB FX rates, no key)"] --> B["httpx + tenacity<br/>retry / fallback"]
        B --> C["write_pandas + MERGE<br/>idempotent load"]
    end

    C --> D[("Snowflake<br/>RAW.FX_RATES")]

    subgraph Transform["Transformation (dbt)"]
        D --> E["staging<br/>stg_fx_rates (view)"]
        E --> F["intermediate<br/>int_fx_rates_enriched (ephemeral)"]
        F --> G["fct_fx_rate<br/>(incremental / merge)"]
        G --> H["mart_fx_daily_metrics<br/>returns, MA, volatility"]
        H -. optional .-> I["mart_market_commentary<br/>Snowflake Cortex LLM"]
    end

    subgraph Serve["AI interface (MCP)"]
        H --> J["FastMCP server<br/>read-only SQL guard"]
        J --> K["Claude Desktop / VS Code<br/>chat with the warehouse"]
    end

    subgraph Ops["Orchestration & CI"]
        L["Dagster<br/>ingest -> dbt lineage + schedule"]
        M["GitHub Actions<br/>ruff + pytest + dbt parse"]
        N["Docker"]
    end

    L --- Ingest
    L --- Transform
```

## Layers

| Layer | Tool | What it shows |
|-------|------|---------------|
| Ingestion | Python, httpx, tenacity, `write_pandas` + `MERGE` | REST ingestion, retries, idempotent loads |
| Warehouse | Snowflake | Cloud data warehouse, roles, cost-safe warehouse |
| Transformation | dbt (staging -> intermediate -> marts) | Analytics engineering, incremental models, tests, lineage |
| Analytics | Snowflake SQL window functions | Returns, moving averages, rolling volatility |
| AI (optional) | Snowflake Cortex `COMPLETE` | Native in-warehouse LLM enrichment |
| AI interface | MCP (FastMCP) | Natural-language, read-only access for LLM clients |
| Orchestration | Dagster + dagster-dbt | Scheduling and end-to-end asset lineage |
| Quality/CI | ruff, pytest, sqlfluff, GitHub Actions | Testing, linting, automation |
| Packaging | Docker | Reproducible runtime |

## Design decisions

- **Read-only by construction.** The MCP server routes every query through a
  pure SQL guard (single statement, `SELECT`/`WITH` only, forbidden-keyword
  scan, auto-`LIMIT`) *and* is meant to run under a dedicated read-only
  Snowflake role. Two independent layers of protection for LLM-driven queries.
- **Idempotent ingestion.** Loads MERGE on the natural key, so re-running any
  date range never duplicates rows.
- **Trial-safe cost.** An `XSMALL` warehouse with `AUTO_SUSPEND = 60s` keeps
  usage far inside the $400 / 30-day free trial.
- **Always runnable.** A deterministic synthetic data source means the pipeline
  and tests work with no API key and no internet.
