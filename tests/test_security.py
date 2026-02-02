"""Tests for security module."""

from __future__ import annotations

import os
import stat
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from kmi_manager_cli.security import (
    _secure_mode,
    ensure_secure_permissions,
    is_insecure_permissions,
    warn_if_insecure,
)


class TestSecureMode:
    """Tests for _secure_mode helper function."""

    def test_directory_mode(self) -> None:
        """Test that _secure_mode returns 0o700 for directories."""
        assert _secure_mode(is_dir=True) == 0o700

    def test_file_mode(self) -> None:
        """Test that _secure_mode returns 0o600 for files."""
        assert _secure_mode(is_dir=False) == 0o600


class TestIsInsecurePermissions:
    """Tests for is_insecure_permissions function."""

    def test_windows_always_secure(self, tmp_path: Path, monkeypatch) -> None:
        """Test that Windows is always considered secure."""
        monkeypatch.setattr(os, "name", "nt")
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        # Even with world-readable permissions, Windows returns False
        assert is_insecure_permissions(test_file) is False

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Test that nonexistent files are considered secure."""
        nonexistent = tmp_path / "does_not_exist.txt"
        assert is_insecure_permissions(nonexistent) is False

    def test_secure_permissions(self, tmp_path: Path, monkeypatch) -> None:
        """Test file with owner-only permissions is secure."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "secure.txt"
        test_file.write_text("content")
        test_file.chmod(0o600)
        
        assert is_insecure_permissions(test_file) is False

    def test_insecure_group_readable(self, tmp_path: Path, monkeypatch) -> None:
        """Test file with group-readable permissions is insecure."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o640)
        
        assert is_insecure_permissions(test_file) is True

    def test_insecure_other_readable(self, tmp_path: Path, monkeypatch) -> None:
        """Test file with other-readable permissions is insecure."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o604)
        
        assert is_insecure_permissions(test_file) is True

    def test_insecure_group_writable(self, tmp_path: Path, monkeypatch) -> None:
        """Test file with group-writable permissions is insecure."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o620)
        
        assert is_insecure_permissions(test_file) is True

    def test_insecure_group_executable(self, tmp_path: Path, monkeypatch) -> None:
        """Test file with group-executable permissions is insecure."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o610)
        
        assert is_insecure_permissions(test_file) is True


class TestWarnIfInsecure:
    """Tests for warn_if_insecure function."""

    def test_no_warning_for_secure_file(self, tmp_path: Path) -> None:
        """Test that secure files don't trigger warnings."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "secure.txt"
        test_file.write_text("content")
        test_file.chmod(0o600)
        
        mock_logger = MagicMock()
        warn_if_insecure(test_file, mock_logger, "test_label")
        
        mock_logger.warning.assert_not_called()

    def test_warning_for_insecure_file(self, tmp_path: Path) -> None:
        """Test that insecure files trigger warnings."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o644)
        
        mock_logger = MagicMock()
        warn_if_insecure(test_file, mock_logger, "test_label")
        
        mock_logger.warning.assert_called_once()

    def test_warning_fallback_format(self, tmp_path: Path) -> None:
        """Test warning fallback when extra fails."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o644)
        
        mock_logger = MagicMock()
        # First call raises, second succeeds
        mock_logger.warning.side_effect = [Exception("extra not supported"), None]
        
        warn_if_insecure(test_file, mock_logger, "test_label")
        
        assert mock_logger.warning.call_count == 2


class TestEnsureSecurePermissions:
    """Tests for ensure_secure_permissions function."""

    def test_no_op_when_not_enforced(self, tmp_path: Path) -> None:
        """Test that nothing happens when enforce=False."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        original_mode = test_file.stat().st_mode
        
        mock_logger = MagicMock()
        ensure_secure_permissions(test_file, mock_logger, "test", is_dir=False, enforce=False)
        
        assert test_file.stat().st_mode == original_mode

    def test_no_op_on_windows(self, tmp_path: Path, monkeypatch) -> None:
        """Test that Windows is skipped even with enforce=True."""
        monkeypatch.setattr(os, "name", "nt")
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")
        
        mock_logger = MagicMock()
        ensure_secure_permissions(test_file, mock_logger, "test", is_dir=False, enforce=True)
        
        # No exception, no changes
        assert test_file.exists()

    def test_no_op_for_nonexistent(self, tmp_path: Path) -> None:
        """Test that nonexistent files are skipped."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        nonexistent = tmp_path / "does_not_exist"
        mock_logger = MagicMock()
        
        ensure_secure_permissions(nonexistent, mock_logger, "test", is_dir=False, enforce=True)
        
        # Should not raise
        assert not nonexistent.exists()

    def test_no_op_for_already_secure(self, tmp_path: Path) -> None:
        """Test that already secure files are not modified."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "secure.txt"
        test_file.write_text("content")
        test_file.chmod(0o600)
        
        mock_logger = MagicMock()
        ensure_secure_permissions(test_file, mock_logger, "test", is_dir=False, enforce=True)
        
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()

    def test_hardens_insecure_file(self, tmp_path: Path) -> None:
        """Test that insecure files are hardened."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o644)
        
        mock_logger = MagicMock()
        ensure_secure_permissions(test_file, mock_logger, "test", is_dir=False, enforce=True)
        
        # Check mode was changed
        mode = stat.S_IMODE(test_file.stat().st_mode)
        assert mode == 0o600
        
        # Check logging
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "permissions_hardened"

    def test_hardens_directory(self, tmp_path: Path) -> None:
        """Test that insecure directories are hardened."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_dir = tmp_path / "insecure_dir"
        test_dir.mkdir()
        test_dir.chmod(0o755)
        
        mock_logger = MagicMock()
        ensure_secure_permissions(test_dir, mock_logger, "test", is_dir=True, enforce=True)
        
        # Check mode was changed
        mode = stat.S_IMODE(test_dir.stat().st_mode)
        assert mode == 0o700

    def test_handles_chmod_error(self, tmp_path: Path) -> None:
        """Test that chmod errors are handled gracefully."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o644)
        
        mock_logger = MagicMock()
        
        # Make chmod fail
        def failing_chmod(path, mode):
            raise PermissionError("Cannot change mode")
        
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(os, "chmod", failing_chmod)
        
        try:
            ensure_secure_permissions(test_file, mock_logger, "test", is_dir=False, enforce=True)
        finally:
            monkeypatch.undo()
        
        # Should log warning, not raise
        mock_logger.warning.assert_called()

    def test_warning_fallback_on_error(self, tmp_path: Path) -> None:
        """Test fallback warning format when extra fails."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")
        
        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o644)
        
        mock_logger = MagicMock()
        mock_logger.info.side_effect = Exception("extra not supported")
        
        # Make chmod succeed
        
        ensure_secure_permissions(test_file, mock_logger, "test", is_dir=False, enforce=True)
        
        # Should try info, fail, then try warning
        assert mock_logger.info.call_count >= 1

    def test_handles_stat_error(self, tmp_path: Path, monkeypatch) -> None:
        """Test that stat errors are handled gracefully."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")

        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o644)

        def failing_stat(_self):
            raise OSError("stat failed")

        monkeypatch.setattr(Path, "exists", lambda _self: True)
        monkeypatch.setattr(Path, "stat", failing_stat)

        mock_logger = MagicMock()
        ensure_secure_permissions(test_file, mock_logger, "test", is_dir=False, enforce=True)
        mock_logger.info.assert_not_called()
        mock_logger.warning.assert_not_called()

    def test_warning_fallback_on_chmod_failure(self, tmp_path: Path, monkeypatch) -> None:
        """Test fallback warning when warn with extra fails."""
        if os.name == "nt":
            pytest.skip("Permission tests don't apply on Windows")

        test_file = tmp_path / "insecure.txt"
        test_file.write_text("content")
        test_file.chmod(0o644)

        monkeypatch.setattr(os, "chmod", lambda *_a, **_k: (_ for _ in ()).throw(PermissionError("fail")))

        mock_logger = MagicMock()
        mock_logger.warning.side_effect = [Exception("extra"), None]

        ensure_secure_permissions(test_file, mock_logger, "test", is_dir=False, enforce=True)
        assert mock_logger.warning.call_count == 2
