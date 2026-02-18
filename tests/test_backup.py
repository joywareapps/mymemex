"""Tests for backup CLI."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from librarian.cli.backup import app

runner = CliRunner()


def test_backup_create(tmp_path):
    """Test creating a backup."""
    dest = tmp_path / "backups"

    result = runner.invoke(app, ["create", "-d", str(dest), "-n", "test_backup"])

    assert result.exit_code == 0
    assert "Backup created" in result.output

    backup_dir = dest / "test_backup"
    assert backup_dir.exists()

    manifest = json.loads((backup_dir / "manifest.json").read_text())
    assert manifest["version"] == "1.0"
    assert "created_at" in manifest


def test_backup_list_empty(tmp_path):
    """Test listing when no backups exist."""
    result = runner.invoke(app, ["list", "-d", str(tmp_path / "nonexistent")])

    assert result.exit_code == 0
    assert "No backups found" in result.output


def test_backup_list_with_backups(tmp_path):
    """Test listing backups."""
    dest = tmp_path / "backups"

    # Create a backup first
    runner.invoke(app, ["create", "-d", str(dest), "-n", "backup_one"])

    result = runner.invoke(app, ["list", "-d", str(dest)])

    assert result.exit_code == 0
    assert "backup_one" in result.output


def test_backup_restore_invalid(tmp_path):
    """Test restoring from invalid backup."""
    result = runner.invoke(app, ["restore", str(tmp_path)])

    assert result.exit_code == 1
    assert "Invalid backup" in result.output


def test_backup_create_and_restore(tmp_path):
    """Test full backup and restore cycle."""
    dest = tmp_path / "backups"

    # Create backup
    result = runner.invoke(app, ["create", "-d", str(dest), "-n", "full_test"])
    assert result.exit_code == 0

    # Restore
    backup_dir = dest / "full_test"
    result = runner.invoke(app, ["restore", str(backup_dir)])
    assert result.exit_code == 0
    assert "Restore complete" in result.output
