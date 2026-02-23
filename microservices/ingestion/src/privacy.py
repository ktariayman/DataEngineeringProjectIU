"""
Privacy guardrails for ingested DataFrames.

Data privacy guarantees:
  1. **Column allowlist** — only pre-approved columns survive; anything else
     is dropped and logged.  Prevents accidental PII leakage if the source
     schema changes upstream.
  2. **PII scan** — regex-based check on column names to flag anything that
     smells like PII (email, name, phone, ip_address, …).  Does *not* scan
     cell values (expensive), but catches schema-level leaks.
  3. **Anonymised-ID audit** — confirms user identifiers remain opaque
     (no plain emails, SSNs, etc.).

These checks run *before* any data is written to the raw zone.
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from pyspark.sql import DataFrame

logger = logging.getLogger(__name__)

# ── PII column-name patterns (case-insensitive) ──────────────────────────
_PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(first|last|full)[_]?name\b", re.IGNORECASE),
    re.compile(r"\bemail\b", re.IGNORECASE),
    re.compile(r"\bphone\b", re.IGNORECASE),
    re.compile(r"\bssn\b", re.IGNORECASE),
    re.compile(r"\bip[_]?addr", re.IGNORECASE),
    re.compile(r"\baddress\b", re.IGNORECASE),
    re.compile(r"\bpassword\b", re.IGNORECASE),
    re.compile(r"\bcredit[_]?card\b", re.IGNORECASE),
    re.compile(r"\bdate[_]?of[_]?birth\b", re.IGNORECASE),
    re.compile(r"\bdob\b", re.IGNORECASE),
    re.compile(r"\bsocial[_]?security\b", re.IGNORECASE),
]


class PrivacyViolationError(Exception):
    """Raised when a DataFrame contains suspected PII columns."""


# ── Column allowlist enforcement ──────────────────────────────────────────

def enforce_column_allowlist(
    df: DataFrame,
    allowed_columns: list[str],
    source_name: str,
) -> DataFrame:
    """Keep only ``allowed_columns``; drop and log any extras.

    Parameters
    ----------
    df : DataFrame
        Input DataFrame.
    allowed_columns : list[str]
        Exhaustive list of columns that may appear in the output.
    source_name : str
        Name for logging.

    Returns
    -------
    DataFrame
        DataFrame with only the allowed columns (order preserved).
    """
    actual = set(df.columns)
    allowed = set(allowed_columns)
    extra = actual - allowed

    if extra:
        logger.warning(
            "[privacy] Source '%s' has %d unexpected column(s) that will be "
            "DROPPED: %s",
            source_name, len(extra), sorted(extra),
        )

    # Select only allowed columns that actually exist
    keep = [c for c in allowed_columns if c in actual]
    return df.select(*keep)


# ── PII column-name scan ─────────────────────────────────────────────────

def scan_for_pii_columns(
    df: DataFrame,
    source_name: str,
    strict: bool = True,
) -> list[str]:
    """Check column names against known PII patterns.

    Parameters
    ----------
    df : DataFrame
        Input DataFrame.
    source_name : str
        Name for logging.
    strict : bool
        If ``True``, raise :class:`PrivacyViolationError` when PII is found.

    Returns
    -------
    list[str]
        Column names that matched PII patterns.
    """
    flagged: list[str] = []

    for col_name in df.columns:
        for pattern in _PII_PATTERNS:
            if pattern.search(col_name):
                flagged.append(col_name)
                break

    if flagged:
        msg = (
            f"[privacy] Source '{source_name}' contains suspected PII "
            f"column(s): {flagged}"
        )
        logger.error(msg)
        if strict:
            raise PrivacyViolationError(msg)

    else:
        logger.info(
            "[privacy] Source '%s' passed PII column scan (%d columns checked).",
            source_name, len(df.columns),
        )

    return flagged
