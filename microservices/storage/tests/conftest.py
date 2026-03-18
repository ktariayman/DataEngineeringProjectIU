"""
Shared test fixtures for the storage microservice.

No PySpark dependency — all storage tests use pure Python.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── Ensure project root is on sys.path for direct ``pytest`` execution ──
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
