"""Tests for backup CLI."""

from __future__ import annotations

import tarfile

from typer.testing import CliRunner

from mymemex.cli.backup import app

runner = CliRunner()


def test_backup_create(tmp_path):
    """Test creating a tar.gz backup."""
    dest = tmp_path / "backups"

    result = runner.invoke(app, ["create", "-d", str(dest), "-n", "test_backup.tar.gz"])

    assert result.exit_code == 0
    assert "Backup created" in result.output

    backup_file = dest / "test_backup.tar.gz"
    assert backup_file.exists()

    # Validate it's a valid tar.gz with metadata.json
    with tarfile.open(str(backup_file), "r:gz") as tar:
        names = tar.getnames()
    assert any("metadata.json" in n for n in names)


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
    """Test restoring from invalid backup path."""
    result = runner.invoke(app, ["restore", str(tmp_path / "nonexistent.tar.gz")])

    assert result.exit_code != 0


def test_backup_create_and_restore(tmp_path):
    """Test full backup and restore cycle with tar.gz."""
    dest = tmp_path / "backups"

    # Create backup
    result = runner.invoke(app, ["create", "-d", str(dest), "-n", "full_test"])
    assert result.exit_code == 0

    # Find the created file
    backup_files = list(dest.glob("*.tar.gz"))
    assert len(backup_files) == 1

    # Restore (skip confirmation)
    result = runner.invoke(app, ["restore", str(backup_files[0]), "--yes"])
    assert result.exit_code == 0
    assert "Restore complete" in result.output
