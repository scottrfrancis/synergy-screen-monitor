"""Unit tests for config.py defaults"""

import pytest

from config import Config


@pytest.mark.unit
class TestSynergyLogPathDefault:
    """Synergy 3.8.4 moved its log from synergy.log to synergy.jsonl."""

    def test_default_log_path_is_jsonl(self):
        assert Config._get_default_synergy_log_path().endswith('synergy.jsonl')
