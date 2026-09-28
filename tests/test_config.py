from warehouse_copilot.config import Settings


def test_settings_read_from_env(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "ab12345.eu-west-1")
    monkeypatch.setenv("SNOWFLAKE_USER", "preet")
    s = Settings(_env_file=None)
    assert s.snowflake_account == "ab12345.eu-west-1"
    assert s.connection_kwargs()["user"] == "preet"
    # sensible defaults
    assert s.snowflake_warehouse == "WH_XS"
    assert s.mcp_row_limit == 100
