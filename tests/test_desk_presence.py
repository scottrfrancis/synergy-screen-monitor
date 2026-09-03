"""Unit tests for desk_presence.py — HID-idle based at-desk heartbeat"""

import json
import pytest
from unittest.mock import Mock, patch

from desk_presence import (
    parse_hid_idle_ns,
    idle_seconds,
    build_message,
    is_at_desk,
    IOREG_COMMAND,
)


IOREG_SAMPLE = """
+-o IOHIDSystem  <class IOHIDSystem, id 0x100000abc, registered, matched, active>
    | | |   {
    | | |     "IOClass" = "IOHIDSystem"
    | | |     "HIDIdleTime" = 55277777625
    | | |     "HIDPointerAcceleration" = 45056
    | | |   }
"""

# Real ioreg output lists several nested entries; only the first HIDIdleTime matters.
IOREG_MULTI = """
    | | |   "HIDIdleTime" = 1200000000
    | | |   "HIDIdleTime" = 99999999999
"""


class TestParseHidIdleNs:
    """parse_hid_idle_ns turns raw ioreg text into nanoseconds"""

    def test_parses_value(self):
        assert parse_hid_idle_ns(IOREG_SAMPLE) == 55277777625

    def test_takes_first_match_when_several(self):
        assert parse_hid_idle_ns(IOREG_MULTI) == 1200000000

    def test_returns_none_when_absent(self):
        assert parse_hid_idle_ns("no such key here") is None

    def test_returns_none_on_empty(self):
        assert parse_hid_idle_ns("") is None

    def test_ignores_malformed_value(self):
        assert parse_hid_idle_ns('"HIDIdleTime" = notanumber') is None


class TestIdleSeconds:
    """idle_seconds converts nanoseconds to seconds"""

    def test_converts(self):
        assert idle_seconds(55_277_777_625) == pytest.approx(55.277, abs=0.01)

    def test_zero(self):
        assert idle_seconds(0) == 0.0

    def test_none_is_none(self):
        assert idle_seconds(None) is None


class TestIsAtDesk:
    """is_at_desk applies the idle threshold"""

    def test_active_is_at_desk(self):
        assert is_at_desk(5.0, threshold=900) is True

    def test_just_under_threshold(self):
        assert is_at_desk(899.9, threshold=900) is True

    def test_at_threshold_is_away(self):
        assert is_at_desk(900.0, threshold=900) is False

    def test_long_idle_is_away(self):
        assert is_at_desk(4000.0, threshold=900) is False

    def test_unknown_idle_is_away(self):
        """A failed read must not assert presence."""
        assert is_at_desk(None, threshold=900) is False


class TestBuildMessage:
    """build_message produces the MQTT payload"""

    def test_shape(self):
        m = json.loads(build_message("studio", 12.5, threshold=900, now="2026-09-03T12:00:00"))
        assert m["host"] == "studio"
        assert m["idle_seconds"] == 12.5
        assert m["at_desk"] is True
        assert m["timestamp"] == "2026-09-03T12:00:00"

    def test_away_when_idle(self):
        m = json.loads(build_message("studio", 1800.0, threshold=900, now="t"))
        assert m["at_desk"] is False

    def test_unknown_idle_reports_away_and_null(self):
        m = json.loads(build_message("studio", None, threshold=900, now="t"))
        assert m["at_desk"] is False
        assert m["idle_seconds"] is None

    def test_is_valid_json(self):
        json.loads(build_message("h", 1.0, threshold=900, now="t"))


class TestIoregCommand:
    """The probe must query IOHIDSystem"""

    def test_command_shape(self):
        assert IOREG_COMMAND[0] == "ioreg"
        assert "IOHIDSystem" in IOREG_COMMAND
