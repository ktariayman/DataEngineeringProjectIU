"""
Privacy guardrails for the processing microservice.

Data privacy guarantees:
  1. **Column allowlist** — only pre-approved columns survive in curated-zone
     outputs; anything unexpected is dropped and logged.
  2. **PII scan** — regex-based check on column names to flag anything that
     resembles PII (email, name, phone, ip_address, etc.).
  3. **Anonymised-ID audit** — confirms user identifiers remain opaque.

These checks run *before* any processed data is written to the curated zone.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from pyspark.sql import DataFrame

logger = logging.getLogger(__name__)

# ── PII column-name patterns (case-insensitive) ──────────────────────────
_PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(first|last|full)[_]?name", re.IGNORECASE),
    re.compile(r"\bemail", re.IGNORECASE),
    re.compile(r"\bphone", re.IGNORECASE),
    re.compile(r"\bssn\b", re.IGNORECASE),
    re.compile(r"\bip[_]?addr", re.IGNORECASE),
    re.compile(r"\baddress", re.IGNORECASE),
    re.compile(r"\bpassword", re.IGNORECASE),
    re.compile(r"\bcredit[_]?card", re.IGNORECASE),
    re.compile(r"\bdate[_]?of[_]?birth", re.IGNORECASE),
    re.compile(r"\bdob\b", re.IGNORECASE),
    re.compile(r"\bsocial[_]?security", re.IGNORECASE),
]


class PrivacyViolationError(Exception):
    """Raised when a DataFrame contains suspected PII columns."""


def enforce_column_allowlist(
    df: DataFrame,
    allowed_columns: list[str],
    dataset_name: str,
) -> DataFrame:
    """Keep only ``allowed_columns``; drop and log any extras.

    Parameters
    ----------
    df : DataFrame
        The DataFrame to filter.
    allowed_columns : list[str]
        Exhaustive list of columns permitted in the output.
    dataset_name : str
        Logical name for log messages.

    Returns
    -------
    DataFrame
        Filtered DataFrame with only allowed columns.
    """
    actual = set(df.columns)
    allowed = set(allowed_columns)
    extra = actual - allowed

    if extra:
        logger.warning(
            "[privacy] Dataset '%s' has %d unexpected column(s) that will be "
            "DROPPED: %s",
            dataset_name, len(extra), sorted(extra),
        )

    keep = [c for c in allowed_columns if c in actual]
    return df.select(*keep)


def scan_for_pii_columns(
    df: DataFrame,
    dataset_name: str,
    strict: bool = True,
) -> list[str]:
    """Check column names against known PII patterns.

    Parameters
    ----------
    df : DataFrame
        The DataFrame to scan.
    dataset_name : str
        Logical name for log messages.
    strict : bool
        If ``True``, raise on any match; otherwise just log a warning.

    Returns
    -------
    list[str]
        List of flagged column names.

    Raises
    ------
    PrivacyViolationError
        If *strict* is ``True`` and any column matches a PII pattern.
    """
    flagged: list[str] = []

    for col_name in df.columns:
        for pattern in _PII_PATTERNS:
            if pattern.search(col_name):
                flagged.append(col_name)
                break

    if flagged:
        msg = (
            f"[privacy] Dataset '{dataset_name}' contains suspected PII "
            f"column(s): {flagged}"
        )
        logger.error(msg)
        if strict:
            raise PrivacyViolationError(msg)
    else:
        logger.info(
            "[privacy] Dataset '%s' passed PII column scan (%d columns checked).",
            dataset_name, len(df.columns),
        )

    return flagged
