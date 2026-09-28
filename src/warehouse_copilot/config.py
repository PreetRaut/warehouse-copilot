"""Typed configuration loaded from environment variables (.env supported).

Nothing here connects to Snowflake at import time - connections are created
lazily inside functions so unit tests and CI can import the package without
any credentials.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Snowflake connection + project settings.

    Values are read from environment variables (see .env.example).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- Snowflake connection ---
    snowflake_account: str = Field(default="", alias="SNOWFLAKE_ACCOUNT")
    snowflake_user: str = Field(default="", alias="SNOWFLAKE_USER")
    snowflake_password: str = Field(default="", alias="SNOWFLAKE_PASSWORD")
    # Key-pair auth (recommended; required when the account enforces MFA).
    snowflake_private_key_path: str = Field(default="", alias="SNOWFLAKE_PRIVATE_KEY_PATH")
    snowflake_private_key_passphrase: str = Field(
        default="", alias="SNOWFLAKE_PRIVATE_KEY_PASSPHRASE"
    )
    snowflake_role: str = Field(default="WAREHOUSE_COPILOT_RW", alias="SNOWFLAKE_ROLE")
    snowflake_warehouse: str = Field(default="WH_XS", alias="SNOWFLAKE_WAREHOUSE")
    snowflake_database: str = Field(default="WAREHOUSE_COPILOT", alias="SNOWFLAKE_DATABASE")
    snowflake_schema_raw: str = Field(default="RAW", alias="SNOWFLAKE_SCHEMA_RAW")
    snowflake_schema_analytics: str = Field(
        default="ANALYTICS", alias="SNOWFLAKE_SCHEMA_ANALYTICS"
    )

    # --- MCP server safety knobs ---
    mcp_row_limit: int = Field(default=100, alias="MCP_ROW_LIMIT")
    mcp_statement_timeout_seconds: int = Field(default=30, alias="MCP_STATEMENT_TIMEOUT_SECONDS")

    def connection_kwargs(self) -> dict:
        """Keyword arguments for snowflake.connector.connect().

        Prefers key-pair auth (SNOWFLAKE_JWT) when a private key path is set -
        this is required for MFA-enforced accounts and is the recommended path
        for programmatic access. Falls back to password auth otherwise.
        """
        kwargs = {
            "account": self.snowflake_account,
            "user": self.snowflake_user,
            "role": self.snowflake_role,
            "warehouse": self.snowflake_warehouse,
            "database": self.snowflake_database,
            "schema": self.snowflake_schema_raw,
            "client_session_keep_alive": False,
        }
        if self.snowflake_private_key_path:
            kwargs["private_key_file"] = self.snowflake_private_key_path
            if self.snowflake_private_key_passphrase:
                kwargs["private_key_file_pwd"] = self.snowflake_private_key_passphrase
        else:
            kwargs["password"] = self.snowflake_password
        return kwargs


@lru_cache
def get_settings() -> Settings:
    return Settings()
