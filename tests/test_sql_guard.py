import pytest

from warehouse_copilot.mcp_server.sql_guard import (
    UnsafeSQLError,
    apply_row_limit,
    assert_read_only,
)


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM mart_fx_daily_metrics",
        "with x as (select 1 as a) select a from x",
        "SELECT rate FROM fct_fx_rate; ",  # single trailing semicolon is fine
        "DESCRIBE TABLE dim_currency",
    ],
)
def test_allows_read_only(sql):
    assert assert_read_only(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE fct_fx_rate",
        "DELETE FROM fct_fx_rate",
        "INSERT INTO fct_fx_rate VALUES (1)",
        "UPDATE fct_fx_rate SET rate = 0",
        "SELECT 1; DROP TABLE fct_fx_rate",  # stacked statements
        "MERGE INTO t USING s ON t.id = s.id",
        "",
    ],
)
def test_rejects_writes(sql):
    with pytest.raises(UnsafeSQLError):
        assert_read_only(sql)


def test_apply_row_limit_adds_limit():
    out = apply_row_limit("select * from t", 50)
    assert out.strip().endswith("LIMIT 50")


def test_apply_row_limit_respects_existing_limit():
    sql = "select * from t limit 5"
    assert apply_row_limit(sql, 50) == sql
