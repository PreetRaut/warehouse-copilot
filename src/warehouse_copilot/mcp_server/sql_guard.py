"""Read-only SQL guard for the MCP server.

The MCP server exposes a natural-language query surface to an LLM, so the SQL it
runs must be strictly read-only. This module is pure (no DB, no network) and is
the most heavily unit-tested part of the project.
"""

from __future__ import annotations

import re

_ALLOWED_STARTS = ("select", "with", "show", "describe", "desc", "explain")

_FORBIDDEN = {
    "insert", "update", "delete", "merge", "truncate", "drop", "create", "alter",
    "grant", "revoke", "copy", "put", "remove", "call", "use", "begin", "commit",
    "rollback", "unload", "execute",
}


class UnsafeSQLError(ValueError):
    """Raised when a statement is not a safe, single, read-only query."""


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    sql = re.sub(r"--[^\n]*", " ", sql)
    return sql.strip()


def assert_read_only(sql: str) -> str:
    """Validate a single read-only statement. Returns the cleaned SQL or raises."""
    cleaned = _strip_comments(sql)
    if not cleaned:
        raise UnsafeSQLError("Empty statement.")

    # Reject multiple statements (allow a single trailing semicolon).
    body = cleaned.rstrip(";")
    if ";" in body:
        raise UnsafeSQLError("Multiple statements are not allowed.")

    first = body.lstrip("( ").split(None, 1)[0].lower()
    if first not in _ALLOWED_STARTS:
        raise UnsafeSQLError(f"Only read-only queries are allowed (got '{first}').")

    tokens = set(re.findall(r"[a-zA-Z_]+", body.lower()))
    hits = tokens & _FORBIDDEN
    if hits:
        raise UnsafeSQLError(f"Forbidden keyword(s) present: {', '.join(sorted(hits))}.")

    return body


def apply_row_limit(sql: str, limit: int) -> str:
    """Append a LIMIT if the query is a SELECT/WITH without one."""
    lowered = sql.lower()
    if lowered.startswith(("select", "with")) and " limit " not in f" {lowered} ":
        return f"{sql}\nLIMIT {int(limit)}"
    return sql
