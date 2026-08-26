"""Reusable helpers for working with large CSV files (e.g. the Companies House
sample, ~418MB / ~850k rows) via pandas, without loading more than needed.
"""

from __future__ import annotations

from collections.abc import Iterator

import pandas as pd


def get_header(path: str) -> list[str]:
    """Return a CSV file's column names without loading any rows."""
    return list(pd.read_csv(path, nrows=0).columns)


def load_columns(path: str, columns: list[str], dtype: str = "string") -> pd.DataFrame:
    """Load only the given columns of a CSV file into a DataFrame.

    Prefer this over a full read_csv() for large files when only a handful
    of fields are needed (e.g. join-key columns for the sample CSV).
    """
    return pd.read_csv(path, usecols=columns, dtype=dtype)


def iter_chunks(
    path: str, columns: list[str], chunksize: int = 100_000, dtype: str = "string"
) -> Iterator[pd.DataFrame]:
    """Yield successive DataFrame chunks containing only the given columns.

    Useful when processing row-by-row (e.g. streaming a join against another
    source) is more natural than materializing the full selected columns.
    """
    yield from pd.read_csv(path, usecols=columns, dtype=dtype, chunksize=chunksize)
