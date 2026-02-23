"""Tests for :mod:`microservices.ingestion.src.checksum`."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path for direct execution
_project_root = str(Path(__file__).resolve().parents[3])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from microservices.ingestion.src.checksum import (
    ChecksumMismatchError,
    compute_checksums,
    load_manifest,
    save_manifest,
    sha256_file,
    verify_checksums,
)


@pytest.fixture()
def sample_dir(tmp_path: Path) -> Path:
    """Create a temp directory with a few small files."""
    (tmp_path / "a.csv").write_text("id,name\n1,Alice\n", encoding="utf-8")
    (tmp_path / "b.csv").write_text("id,name\n2,Bob\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.csv").write_text("id,name\n3,Charlie\n", encoding="utf-8")
    return tmp_path


class TestSha256File:
    def test_deterministic(self, sample_dir: Path) -> None:
        print("\n[TEST] SHA256 deterministic hashing")
        h1 = sha256_file(sample_dir / "a.csv")
        h2 = sha256_file(sample_dir / "a.csv")
        print(f"  Hash 1: {h1[:16]}...")
        print(f"  Hash 2: {h2[:16]}...")
        print(f"  ✓ Hashes match: {h1 == h2}")
        assert h1 == h2

    def test_different_files_differ(self, sample_dir: Path) -> None:
        print("\n[TEST] Different files produce different hashes")
        h1 = sha256_file(sample_dir / "a.csv")
        h2 = sha256_file(sample_dir / "b.csv")
        print(f"  File a.csv: {h1[:16]}...")
        print(f"  File b.csv: {h2[:16]}...")
        print(f"  ✓ Hashes differ: {h1 != h2}")
        assert sha256_file(sample_dir / "a.csv") != sha256_file(sample_dir / "b.csv")


class TestComputeChecksums:
    def test_finds_all_files(self, sample_dir: Path) -> None:
        print("\n[TEST] Compute checksums for all files")
        manifest = compute_checksums(str(sample_dir))
        print(f"  Directory: {sample_dir}")
        print(f"  Files found: {len(manifest)}")
        for filepath in manifest.keys():
            print(f"    - {filepath}")
        print(f"  ✓ Expected 3 files (a.csv, b.csv, sub/c.csv)")
        assert len(manifest) == 3  # a.csv, b.csv, sub/c.csv

    def test_glob_filter(self, sample_dir: Path) -> None:
        print("\n[TEST] Glob pattern filtering")
        manifest = compute_checksums(str(sample_dir), glob_pattern="*.csv")
        print(f"  Pattern: *.csv")
        print(f"  Files matched: {len(manifest)}")
        print(f"  ✓ All CSV files found")
        # rglob("*.csv") matches csv files in all subdirectories
        assert len(manifest) == 3

    def test_missing_dir_raises(self) -> None:
        print("\n[TEST] Missing directory raises error")
        print("  Attempting to compute checksums for non-existent path...")
        with pytest.raises(FileNotFoundError):
            compute_checksums("/nonexistent/path")
        print("  ✓ FileNotFoundError raised as expected")


class TestManifestPersistence:
    def test_round_trip(self, sample_dir: Path, tmp_path: Path) -> None:
        print("\n[TEST] Manifest save/load round-trip")
        manifest = compute_checksums(str(sample_dir))
        manifest_path = tmp_path / "manifest.json"
        print(f"  Computing checksums for {len(manifest)} files...")
        save_manifest(manifest, manifest_path)
        print(f"  Saved manifest to: {manifest_path}")
        loaded = load_manifest(manifest_path)
        print(f"  Loaded manifest: {len(loaded)} entries")
        print(f"  ✓ Original and loaded manifests match")
        assert loaded == manifest


class TestVerifyChecksums:
    def test_pass_when_unchanged(self, sample_dir: Path, tmp_path: Path) -> None:
        print("\n[TEST] Verification passes for unchanged files")
        manifest = compute_checksums(str(sample_dir))
        manifest_path = tmp_path / "manifest.json"
        save_manifest(manifest, manifest_path)
        print(f"  Created baseline manifest with {len(manifest)} files")

        mismatches = verify_checksums(str(sample_dir), manifest_path)
        print(f"  Verification result: {len(mismatches)} mismatches")
        print(f"  ✓ All files verified successfully")
        assert mismatches == []

    def test_fail_on_modification(self, sample_dir: Path, tmp_path: Path) -> None:
        print("\n[TEST] Verification fails on file modification")
        manifest = compute_checksums(str(sample_dir))
        manifest_path = tmp_path / "manifest.json"
        save_manifest(manifest, manifest_path)
        print(f"  Created baseline manifest")

        # Tamper with one file
        print("  Tampering with a.csv...")
        (sample_dir / "a.csv").write_text("TAMPERED CONTENT", encoding="utf-8")

        print("  Verifying checksums (strict mode)...")
        with pytest.raises(ChecksumMismatchError):
            verify_checksums(str(sample_dir), manifest_path, strict=True)
        print("  ✓ ChecksumMismatchError raised as expected")

    def test_non_strict_collects_all(self, sample_dir: Path, tmp_path: Path) -> None:
        print("\n[TEST] Non-strict mode collects all mismatches")
        manifest = compute_checksums(str(sample_dir))
        manifest_path = tmp_path / "manifest.json"
        save_manifest(manifest, manifest_path)
        print(f"  Created baseline manifest")

        print("  Tampering with a.csv and b.csv...")
        (sample_dir / "a.csv").write_text("TAMPERED", encoding="utf-8")
        (sample_dir / "b.csv").write_text("ALSO TAMPERED", encoding="utf-8")

        print("  Verifying checksums (non-strict mode)...")
        mismatches = verify_checksums(
            str(sample_dir), manifest_path, strict=False
        )
        print(f"  Mismatches found: {len(mismatches)}")
        for mismatch in mismatches:
            print(f"    - {mismatch}")
        print(f"  ✓ Both tampered files detected")
        assert len(mismatches) == 2

    def test_fail_on_missing_file(self, sample_dir: Path, tmp_path: Path) -> None:
        print("\n[TEST] Verification fails on missing file")
        manifest = compute_checksums(str(sample_dir))
        manifest_path = tmp_path / "manifest.json"
        save_manifest(manifest, manifest_path)
        print(f"  Created baseline manifest with {len(manifest)} files")

        print("  Deleting a.csv...")
        (sample_dir / "a.csv").unlink()

        print("  Verifying checksums (strict mode)...")
        with pytest.raises(ChecksumMismatchError):
            verify_checksums(str(sample_dir), manifest_path, strict=True)
        print("  ✓ ChecksumMismatchError raised for missing file")
