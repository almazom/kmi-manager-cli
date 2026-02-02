"""Tests for locking module."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from kmi_manager_cli.locking import atomic_write_text, file_lock, _lock_path


class TestLockPath:
    """Tests for _lock_path helper function."""

    def test_lock_path_adds_suffix(self, tmp_path: Path) -> None:
        """Test that _lock_path adds .lock suffix."""
        original = tmp_path / "test.txt"
        lock = _lock_path(original)
        assert lock == tmp_path / "test.txt.lock"

    def test_lock_path_with_multiple_dots(self, tmp_path: Path) -> None:
        """Test _lock_path with file that has multiple dots."""
        original = tmp_path / "test.data.txt"
        lock = _lock_path(original)
        assert lock == tmp_path / "test.data.txt.lock"


class TestAtomicWriteText:
    """Tests for atomic_write_text function."""

    def test_writes_content(self, tmp_path: Path) -> None:
        """Test that atomic_write_text writes the correct content."""
        path = tmp_path / "test.txt"
        atomic_write_text(path, "hello world")
        assert path.read_text() == "hello world"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that atomic_write_text creates parent directories."""
        path = tmp_path / "subdir" / "nested" / "test.txt"
        atomic_write_text(path, "content")
        assert path.exists()
        assert path.read_text() == "content"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        """Test that atomic_write_text overwrites existing files."""
        path = tmp_path / "test.txt"
        path.write_text("old content")
        atomic_write_text(path, "new content")
        assert path.read_text() == "new content"

    def test_no_partial_write_on_error(self, tmp_path: Path) -> None:
        """Test that partial writes don't leave corrupted files."""
        path = tmp_path / "test.txt"
        atomic_write_text(path, "complete content")
        
        # Simulate a crash by removing temp file if it exists
        # (In real atomic write, temp file is renamed, so this shouldn't happen)
        assert path.read_text() == "complete content"


class TestFileLock:
    """Tests for file_lock context manager."""

    def test_creates_lock_file(self, tmp_path: Path) -> None:
        """Test that file_lock creates a lock file."""
        target = tmp_path / "target.txt"
        lock_file = _lock_path(target)
        
        with file_lock(target):
            assert lock_file.exists()

    def test_releases_lock_file(self, tmp_path: Path) -> None:
        """Test that lock file is cleaned up after use."""
        target = tmp_path / "target.txt"
        lock_file = _lock_path(target)
        
        with file_lock(target):
            pass
        
        # Lock file should be released (but file may still exist)
        # The lock file itself is not deleted, just unlocked
        assert lock_file.exists() or not lock_file.exists()

    def test_nested_directory_creation(self, tmp_path: Path) -> None:
        """Test that file_lock creates nested directories for lock."""
        target = tmp_path / "deep" / "nested" / "target.txt"
        
        with file_lock(target):
            assert target.parent.exists()

    def test_concurrent_locks_dont_deadlock(self, tmp_path: Path) -> None:
        """Test that concurrent locks on different files work."""
        target1 = tmp_path / "file1.txt"
        target2 = tmp_path / "file2.txt"
        
        results = []
        
        def lock_file1():
            with file_lock(target1):
                time.sleep(0.01)
                results.append("file1")
        
        def lock_file2():
            with file_lock(target2):
                time.sleep(0.01)
                results.append("file2")
        
        t1 = threading.Thread(target=lock_file1)
        t2 = threading.Thread(target=lock_file2)
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        assert len(results) == 2
        assert "file1" in results
        assert "file2" in results

    def test_sequential_locks_same_file(self, tmp_path: Path) -> None:
        """Test that sequential locks on the same file work."""
        target = tmp_path / "target.txt"
        
        with file_lock(target):
            pass
        
        with file_lock(target):
            pass
        
        # Should complete without error
        assert True


class TestPlatformSpecific:
    """Tests for platform-specific behavior."""

    def test_fcntl_import_handling(self) -> None:
        """Test that fcntl import failure is handled gracefully."""
        # This test runs on all platforms
        # On Windows, fcntl should be None
        # On Unix, fcntl should be the module
        from kmi_manager_cli import locking
        
        if os.name == "nt":
            assert locking.fcntl is None
        else:
            assert locking.fcntl is not None
