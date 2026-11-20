"""Load the raw CSV into DuckDB, run the SQL quality checks and expose tidy tables."""
from __future__ import annotations

import re

import duckdb
import pandas as pd

from src import config


class DataQualityError(RuntimeError):
    """Raised when a hard data-quality rule fails."""


def split_statements(sql: str) -> list[str]:
    """Split a SQL script on semicolons after removing -- comments."""
    no_comments = re.sub(r"--[^\n]*", "", sql)
    return [stmt.strip() for stmt in no_comments.split(";") if stmt.strip()]


def run_sql(con: duckdb.DuckDBPyConnection, filename: str, **params: str) -> pd.DataFrame | None:
    """Run every statement in sql/<filename>; return the last result as a DataFrame."""
    sql = (config.SQL_DIR / filename).read_text()
    for key, value in params.items():
        sql = sql.replace("{" + key + "}", value)
    result = None
    for statement in split_statements(sql):
        result = con.execute(statement)
    try:
        return result.df() if result is not None else None
    except duckdb.Error:
        return None


def connect() -> duckdb.DuckDBPyConnection:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(config.DB_PATH))


def build_database() -> pd.DataFrame:
    """Create the campaign table and return the quality-check report."""
    if not config.RAW_CSV.exists():
        raise FileNotFoundError(f"{config.RAW_CSV} not found. Run `python -m src.download_data` first.")
    raw = config.RAW_CSV.as_posix()
    with connect() as con:
        run_sql(con, "01_load_campaign.sql", raw_csv=raw)
        checks = run_sql(con, "02_quality_checks.sql", raw_csv=raw)
    failed_hard = checks[(checks.severity == "hard") & (checks.failures > 0)]
    if not failed_hard.empty:
        raise DataQualityError("Hard data-quality rules failed:\n" + failed_hard.to_string(index=False))
    return checks


def load_campaign() -> pd.DataFrame:
    with connect() as con:
        df = con.execute("SELECT * FROM campaign").df()
    df.insert(0, "customer_id", range(1, len(df) + 1))
    return df


def query(filename: str) -> pd.DataFrame:
    with connect() as con:
        return run_sql(con, filename)
