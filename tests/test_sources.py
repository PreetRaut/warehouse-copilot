from datetime import date

from warehouse_copilot.ingest.sources import (
    _parse_frankfurter,
    generate_synthetic_fx,
)


def test_parse_frankfurter_shape():
    payload = {
        "base": "EUR",
        "rates": {
            "2024-01-01": {"USD": 1.10, "GBP": 0.86},
            "2024-01-02": {"USD": 1.11, "GBP": 0.87},
        },
    }
    df = _parse_frankfurter(payload, "EUR")
    assert list(df.columns) == ["RATE_DATE", "BASE_CURRENCY", "QUOTE_CURRENCY", "RATE"]
    assert len(df) == 4
    assert set(df["QUOTE_CURRENCY"]) == {"USD", "GBP"}
    assert (df["BASE_CURRENCY"] == "EUR").all()


def test_synthetic_is_deterministic_and_complete():
    start, end = date(2024, 1, 1), date(2024, 1, 3)
    a = generate_synthetic_fx(start, end, symbols=["USD", "GBP"])
    b = generate_synthetic_fx(start, end, symbols=["USD", "GBP"])
    assert a.equals(b)               # deterministic
    assert len(a) == 3 * 2           # 3 days x 2 currencies
    assert (a["RATE"] > 0).all()
