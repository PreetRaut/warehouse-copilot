"""Data sources for the ELT pipeline.

Primary source: daily FX reference rates from the Frankfurter API (published by
the European Central Bank). It needs no API key, which keeps the whole project
free to run.

A deterministic synthetic generator is included as a fallback so the pipeline
(and the test suite) always runs, even offline.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from warehouse_copilot.utils.logging import get_logger

log = get_logger(__name__)

# Frankfurter is mirrored on two hosts; we try the newer one first.
_FRANKFURTER_HOSTS = ["https://api.frankfurter.dev/v1", "https://api.frankfurter.app"]

DEFAULT_BASE = "EUR"
DEFAULT_SYMBOLS = ["USD", "GBP", "JPY", "CHF", "AUD", "CAD"]

_RAW_COLUMNS = ["RATE_DATE", "BASE_CURRENCY", "QUOTE_CURRENCY", "RATE"]


def _parse_frankfurter(payload: dict, base: str) -> pd.DataFrame:
    """Turn the nested Frankfurter time-series payload into a tidy long DataFrame."""
    rows: list[dict] = []
    for day, quotes in payload.get("rates", {}).items():
        for quote_ccy, rate in quotes.items():
            rows.append(
                {
                    "RATE_DATE": day,
                    "BASE_CURRENCY": base,
                    "QUOTE_CURRENCY": quote_ccy,
                    "RATE": float(rate),
                }
            )
    df = pd.DataFrame(rows, columns=_RAW_COLUMNS)
    if not df.empty:
        df["RATE_DATE"] = pd.to_datetime(df["RATE_DATE"]).dt.date
    return df.sort_values(["RATE_DATE", "QUOTE_CURRENCY"]).reset_index(drop=True)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _get(url: str, params: dict) -> dict:
    resp = httpx.get(url, params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def fetch_fx_rates(
    start: date,
    end: date,
    base: str = DEFAULT_BASE,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """Fetch daily FX rates for a date range from Frankfurter.

    Returns a long DataFrame with columns:
    RATE_DATE, BASE_CURRENCY, QUOTE_CURRENCY, RATE.
    """
    symbols = symbols or DEFAULT_SYMBOLS
    params = {"base": base, "symbols": ",".join(symbols)}
    path = f"/{start.isoformat()}..{end.isoformat()}"

    last_error: Exception | None = None
    for host in _FRANKFURTER_HOSTS:
        try:
            log.info("Fetching FX rates %s from %s", path, host)
            payload = _get(host + path, params)
            return _parse_frankfurter(payload, base)
        except Exception as exc:  # noqa: BLE001 - try the next mirror
            last_error = exc
            log.warning("Host %s failed: %s", host, exc)
    raise RuntimeError(f"All Frankfurter hosts failed: {last_error}")


def generate_synthetic_fx(
    start: date,
    end: date,
    base: str = DEFAULT_BASE,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """Deterministic offline fallback that mimics the shape of real FX data."""
    symbols = symbols or DEFAULT_SYMBOLS
    seeds = {"USD": 1.08, "GBP": 0.85, "JPY": 161.0, "CHF": 0.95, "AUD": 1.63, "CAD": 1.47}
    rows: list[dict] = []
    day = start
    t = 0
    while day <= end:
        for ccy in symbols:
            base_rate = seeds.get(ccy, 1.0)
            drift = 1 + 0.02 * math.sin((t + hash(ccy) % 7) / 6.0)
            rows.append(
                {
                    "RATE_DATE": day,
                    "BASE_CURRENCY": base,
                    "QUOTE_CURRENCY": ccy,
                    "RATE": round(base_rate * drift, 6),
                }
            )
        day += timedelta(days=1)
        t += 1
    return pd.DataFrame(rows, columns=_RAW_COLUMNS)


def load_fx_dataframe(
    start: date,
    end: date,
    base: str = DEFAULT_BASE,
    symbols: list[str] | None = None,
    synthetic: bool = False,
) -> pd.DataFrame:
    """Convenience wrapper used by the CLI: live source with synthetic fallback."""
    if synthetic:
        return generate_synthetic_fx(start, end, base, symbols)
    try:
        return fetch_fx_rates(start, end, base, symbols)
    except Exception as exc:  # noqa: BLE001
        log.warning("Live fetch failed (%s); falling back to synthetic data.", exc)
        return generate_synthetic_fx(start, end, base, symbols)


def default_date_range(days_back: int = 90) -> tuple[date, date]:
    end = datetime.utcnow().date()
    return end - timedelta(days=days_back), end
