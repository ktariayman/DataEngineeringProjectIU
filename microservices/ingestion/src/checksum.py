"""
Source-file checksum verification.

Computes and validates SHA-256 digests of input CSV/TSV files to detect
corruption or tampering before processing.  Implements the "Checksum
verification" requirement from the non-functional / security layer.

Usage
-----
1. **First run (initial load):** Call :func:`compute_checksums` to generate
   a manifest of ``{filename: sha256hex}`` and persist it alongside data.
2. **Subsequent runs (daily):** Call :func:`verify_checksums` to compare
   current file digests against the stored manifest.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 8 * 1024 * 1024  # 8 MB read chunks


# ── core helpers ───────────────────────────────────────────────────────────

def sha256_file(filepath: str | Path) -> str:
    """Return the hex-encoded SHA-256 digest of a single file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while chunk := fh.read(_CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def compute_checksums(source_dir: str, glob_pattern: str = "*") -> dict[str, str]:
    """Walk *source_dir*, hash every file matching *glob_pattern*.

    Parameters
    ----------
    source_dir : str
        Root directory of source files (local path only).
    glob_pattern : str
        Glob to filter files (default: ``*`` = all files).

    Returns
    -------
    dict[str, str]
        ``{relative_filename: sha256_hex}``
    """
    base = Path(source_dir)
    if not base.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    manifest: dict[str, str] = {}
    for fp in sorted(base.rglob(glob_pattern)):
        if fp.is_file():
            rel = str(fp.relative_to(base))
            digest = sha256_file(fp)
            manifest[rel] = digest
            logger.debug("SHA-256 %-64s  %s", digest, rel)

    logger.info(
        "Computed checksums for %d file(s) in '%s'.", len(manifest), source_dir
    )
    return manifest


# ── manifest persistence ──────────────────────────────────────────────────

def save_manifest(manifest: dict[str, str], output_path: str | Path) -> None:
    """Persist a checksum manifest as JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
    logger.info("Checksum manifest saved → %s", path)


def load_manifest(manifest_path: str | Path) -> dict[str, str]:
    """Load a previously saved checksum manifest."""
    with open(manifest_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ── verification ──────────────────────────────────────────────────────────

class ChecksumMismatchError(Exception):
    """Raised when one or more files fail checksum verification."""


def verify_checksums(
    source_dir: str,
    manifest_path: str | Path,
    glob_pattern: str = "*",
    strict: bool = True,
) -> list[str]:
    """Verify current files against a stored checksum manifest.

    Parameters
    ----------
    source_dir : str
        Directory of source files to verify.
    manifest_path : str | Path
        Path to the JSON manifest produced by :func:`save_manifest`.
    glob_pattern : str
        Glob pattern to filter files.
    strict : bool
        If ``True``, raise :class:`ChecksumMismatchError` on the first
        mismatch.  If ``False``, collect all mismatches and return them.

    Returns
    -------
    list[str]
        List of filenames that failed verification (empty on success).

    Raises
    ------
    ChecksumMismatchError
        If *strict* is ``True`` and any file fails verification.
    """
    expected = load_manifest(manifest_path)
    current = compute_checksums(source_dir, glob_pattern)

    mismatches: list[str] = []

    for filename, expected_hash in expected.items():
        actual_hash = current.get(filename)
        if actual_hash is None:
            msg = f"File missing: {filename}"
            logger.error(msg)
            mismatches.append(filename)
            if strict:
                raise ChecksumMismatchError(msg)
        elif actual_hash != expected_hash:
            msg = (
                f"Checksum mismatch: {filename}  "
                f"expected={expected_hash[:16]}…  actual={actual_hash[:16]}…"
            )
            logger.error(msg)
            mismatches.append(filename)
            if strict:
                raise ChecksumMismatchError(msg)

    if not mismatches:
        logger.info("All %d file(s) passed checksum verification.", len(expected))

    return mismatches
