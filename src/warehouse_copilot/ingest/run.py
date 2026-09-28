"""CLI entrypoint for the ingestion step: fetch FX rates and load into Snowflake."""

from __future__ import annotations

import argparse
from datetime import date, datetime

from warehouse_copilot.ingest.sources import (
    DEFAULT_BASE,
    DEFAULT_SYMBOLS,
    default_date_range,
    load_fx_dataframe,
)
from warehouse_copilot.utils.logging import get_logger

log = get_logger("wc-ingest")


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def build_parser() -> argparse.ArgumentParser:
    default_start, default_end = default_date_range()
    p = argparse.ArgumentParser(description="Ingest FX rates into Snowflake RAW.FX_RATES.")
    p.add_argument("--start", type=_parse_date, default=default_start, help="YYYY-MM-DD")
    p.add_argument("--end", type=_parse_date, default=default_end, help="YYYY-MM-DD")
    p.add_argument("--base", default=DEFAULT_BASE, help="Base currency (default EUR)")
    p.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS, help="Quote currencies")
    p.add_argument("--synthetic", action="store_true", help="Use offline synthetic data")
    p.add_argument("--dry-run", action="store_true", help="Fetch only; skip Snowflake load")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    df = load_fx_dataframe(args.start, args.end, args.base, args.symbols, synthetic=args.synthetic)
    log.info("Prepared %s rows (%s -> %s)", len(df), args.start, args.end)
    if args.dry_run:
        log.info("Dry run - not loading. Sample:\n%s", df.head().to_string(index=False))
        return 0

    from warehouse_copilot.ingest.loader import load_to_snowflake  # lazy: needs snowflake

    load_to_snowflake(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
