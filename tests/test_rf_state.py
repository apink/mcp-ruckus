"""Tests for RF optimization state cache."""
from __future__ import annotations

from tools.rf_state import load_optimization, save_optimization


class TestRfState:
    def test_save_and_load(self):
        result = {"band": "5g", "aps_changed": 3}
        opt_id = save_optimization(result)
        assert opt_id.startswith("opt_")

        loaded = load_optimization(opt_id)
        assert loaded is not None
        assert loaded["band"] == "5g"
        assert loaded["aps_changed"] == 3

    def test_load_missing(self):
        loaded = load_optimization("opt_nonexistent")
        assert loaded is None
