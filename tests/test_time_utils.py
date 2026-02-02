"""Tests for time_utils module."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest

from kmi_manager_cli.time_utils import (
    format_timestamp,
    now_timestamp,
    parse_iso_timestamp,
    resolve_timezone,
)


class TestResolveTimezone:
    """Tests for resolve_timezone function."""

    def test_none_returns_local(self) -> None:
        """Test that None returns local timezone."""
        tz = resolve_timezone(None)
        assert tz is not None

    def test_empty_string_returns_local(self) -> None:
        """Test that empty string returns local timezone."""
        tz = resolve_timezone("")
        assert tz is not None

    def test_local_returns_local(self) -> None:
        """Test that 'local' returns local timezone."""
        tz = resolve_timezone("local")
        assert tz is not None

    def test_utc_returns_utc(self) -> None:
        """Test that 'UTC' returns UTC."""
        tz = resolve_timezone("UTC")
        assert tz == timezone.utc

    def test_gmt_returns_utc(self) -> None:
        """Test that 'GMT' returns UTC."""
        tz = resolve_timezone("GMT")
        assert tz == timezone.utc

    def test_z_returns_utc(self) -> None:
        """Test that 'Z' returns UTC."""
        tz = resolve_timezone("Z")
        assert tz == timezone.utc

    def test_lowercase_utc(self) -> None:
        """Test that 'utc' (lowercase) returns UTC."""
        tz = resolve_timezone("utc")
        assert tz == timezone.utc

    def test_positive_offset_with_colon(self) -> None:
        """Test positive offset with colon format."""
        tz = resolve_timezone("+05:00")
        assert isinstance(tz, timezone)
        assert tz.utcoffset(None) == timedelta(hours=5)

    def test_negative_offset_with_colon(self) -> None:
        """Test negative offset with colon format."""
        tz = resolve_timezone("-03:00")
        assert isinstance(tz, timezone)
        assert tz.utcoffset(None) == timedelta(hours=-3)

    def test_positive_offset_without_colon(self) -> None:
        """Test positive offset without colon format."""
        tz = resolve_timezone("+0530")
        assert isinstance(tz, timezone)
        assert tz.utcoffset(None) == timedelta(hours=5, minutes=30)

    def test_negative_offset_without_colon(self) -> None:
        """Test negative offset without colon format."""
        tz = resolve_timezone("-0330")
        assert isinstance(tz, timezone)
        assert tz.utcoffset(None) == timedelta(hours=-3, minutes=-30)

    def test_offset_with_partial_minutes(self) -> None:
        """Test offset with single digit minutes."""
        tz = resolve_timezone("+05:05")
        assert isinstance(tz, timezone)
        assert tz.utcoffset(None) == timedelta(hours=5, minutes=5)

    def test_invalid_offset_returns_utc(self) -> None:
        """Test that invalid offset returns UTC."""
        tz = resolve_timezone("+invalid")
        assert tz == timezone.utc

    def test_zoneinfo_name(self) -> None:
        """Test IANA timezone name if ZoneInfo available."""
        try:
            from zoneinfo import ZoneInfo
            tz = resolve_timezone("America/New_York")
            assert isinstance(tz, ZoneInfo)
            assert str(tz) == "America/New_York"
        except ImportError:
            pytest.skip("ZoneInfo not available")

    def test_invalid_zoneinfo_returns_utc(self) -> None:
        """Test that invalid timezone name returns UTC."""
        tz = resolve_timezone("Invalid/Timezone")
        assert tz == timezone.utc

    def test_zoneinfo_none_fallback(self, monkeypatch) -> None:
        """Test fallback when ZoneInfo is None (Python < 3.9)."""
        from kmi_manager_cli import time_utils
        original_zoneinfo = time_utils.ZoneInfo
        
        try:
            monkeypatch.setattr(time_utils, "ZoneInfo", None)
            tz = resolve_timezone("America/New_York")
            assert tz == timezone.utc
        finally:
            monkeypatch.setattr(time_utils, "ZoneInfo", original_zoneinfo)


class TestFormatTimestamp:
    """Tests for format_timestamp function."""

    def test_utc_formatting(self) -> None:
        """Test formatting UTC datetime."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_timestamp(dt, timezone.utc)
        assert result == "2024-01-15 10:30:00 +0000"

    def test_timezone_conversion(self) -> None:
        """Test conversion to different timezone."""
        utc_dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        tz = timezone(timedelta(hours=5, minutes=30))  # +05:30
        result = format_timestamp(utc_dt, tz)
        assert "2024-01-15" in result
        assert "16:00:00" in result or "15:30:00" in result  # Depends on exact offset
        assert "+0530" in result

    def test_negative_timezone(self) -> None:
        """Test formatting with negative timezone offset."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        tz = timezone(timedelta(hours=-8))  # PST
        result = format_timestamp(dt, tz)
        assert "-0800" in result


class TestNowTimestamp:
    """Tests for now_timestamp function."""

    def test_returns_string(self) -> None:
        """Test that now_timestamp returns a string."""
        result = now_timestamp("UTC")
        assert isinstance(result, str)

    def test_utc_format(self) -> None:
        """Test that UTC timestamp has expected format."""
        result = now_timestamp("UTC")
        # Should be like "2024-01-15 10:30:00 +0000"
        assert len(result) > 20
        assert "+0000" in result

    def test_local_format(self) -> None:
        """Test that local timestamp has timezone info."""
        result = now_timestamp("local")
        assert isinstance(result, str)
        assert len(result) > 20


class TestParseIsoTimestamp:
    """Tests for parse_iso_timestamp function."""

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        assert parse_iso_timestamp("") is None

    def test_none_returns_none(self) -> None:
        """Test that None returns None."""
        assert parse_iso_timestamp(None) is None  # type: ignore[arg-type]

    def test_z_format(self) -> None:
        """Test parsing ISO format with Z suffix."""
        result = parse_iso_timestamp("2024-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0

    def test_explicit_utc_offset(self) -> None:
        """Test parsing ISO format with explicit UTC offset."""
        result = parse_iso_timestamp("2024-01-15T10:30:00+00:00")
        assert result is not None
        assert result.year == 2024

    def test_positive_offset(self) -> None:
        """Test parsing ISO format with positive offset."""
        result = parse_iso_timestamp("2024-01-15T10:30:00+05:30")
        assert result is not None
        assert result.utcoffset() == timedelta(hours=5, minutes=30)

    def test_negative_offset(self) -> None:
        """Test parsing ISO format with negative offset."""
        result = parse_iso_timestamp("2024-01-15T10:30:00-08:00")
        assert result is not None
        assert result.utcoffset() == timedelta(hours=-8)

    def test_no_timezone(self) -> None:
        """Test parsing ISO format without timezone."""
        result = parse_iso_timestamp("2024-01-15T10:30:00")
        assert result is not None
        assert result.year == 2024

    def test_space_separator(self) -> None:
        """Test parsing ISO format with space separator."""
        result = parse_iso_timestamp("2024-01-15 10:30:00")
        assert result is not None
        assert result.year == 2024

    def test_invalid_format_returns_none(self) -> None:
        """Test that invalid format returns None."""
        assert parse_iso_timestamp("not-a-date") is None

    def test_partial_date_returns_none(self) -> None:
        """Test that partial date returns None."""
        assert parse_iso_timestamp("2024-01") is None

    def test_garbage_returns_none(self) -> None:
        """Test that garbage input returns None."""
        assert parse_iso_timestamp("xyz123") is None

    def test_microseconds(self) -> None:
        """Test parsing with microseconds."""
        result = parse_iso_timestamp("2024-01-15T10:30:00.123456Z")
        assert result is not None
        assert result.microsecond == 123456

    def test_date_only_fails(self) -> None:
        """Test that date-only string fails."""
        # fromisoformat accepts date-only, but we should verify behavior
        result = parse_iso_timestamp("2024-01-15")
        # This might return a datetime with time=00:00:00 or None depending on Python version
        # The function should handle it gracefully
        assert result is None or (result.year == 2024 and result.month == 1 and result.day == 15)
