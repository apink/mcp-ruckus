"""Tests for RF optimization algorithm."""
from __future__ import annotations

from tools.optimization import _interference_5g, _interference_24g, _secondary_channel, _POWER_LEVELS


class TestInterference5g:
    def test_same_channel(self):
        assert _interference_5g(36, 20, 36, 20) == 1.0

    def test_different_channel(self):
        factor = _interference_5g(36, 20, 40, 20)
        assert 0 < factor < 1.0

    def test_far_apart(self):
        assert _interference_5g(36, 20, 149, 20) == 0.0

    def test_unknown_channel(self):
        assert _interference_5g(99, 20, 36, 20) == 0.0


class TestInterference24g:
    def test_same_channel(self):
        assert _interference_24g(1, 20, 1, 20) == 1.0

    def test_adjacent(self):
        assert _interference_24g(1, 20, 2, 20) == 0.7

    def test_overlap(self):
        assert _interference_24g(1, 20, 4, 20) == 0.3

    def test_non_overlap(self):
        assert _interference_24g(1, 20, 11, 20) == 0.0


class TestSecondaryChannel:
    def test_20mhz_no_secondary(self):
        assert _secondary_channel(36, 20) is None

    def test_40mhz_pair(self):
        assert _secondary_channel(36, 40) == 40

    def test_40mhz_lower(self):
        assert _secondary_channel(44, 40) == 48

    def test_80mhz(self):
        assert _secondary_channel(149, 80) == 153

    def test_edge_channel_165(self):
        result = _secondary_channel(165, 40)
        assert result == 161


class TestPowerLevels:
    def test_levels_map(self):
        assert _POWER_LEVELS["max"] == 0
        assert _POWER_LEVELS["half"] == -6
        assert _POWER_LEVELS["quarter"] == -9
        assert _POWER_LEVELS["min"] == -12


class TestDsatur:
    def test_build_graph_with_neighbors(self):
        from tools.optimization import build_graph
        ap_data = {
            "AP1": {
                "neighbors": [
                    {"name": "AP2", "snr_5g": 30, "ch_5g": 149, "width_5g": 80},
                ],
                "ch_5g": 36,
                "width_5g": 80,
            },
            "AP2": {
                "neighbors": [
                    {"name": "AP1", "snr_5g": 30, "ch_5g": 36, "width_5g": 80},
                ],
                "ch_5g": 149,
                "width_5g": 80,
            },
        }
        graph, channels, nodes = build_graph(ap_data, "5g", 80, {"AP1", "AP2"})
        assert len(graph) == 2
        assert len(channels) == 25  # 9 non-DFS + 16 DFS
        assert "AP1" in graph


class TestOptimizeFull:
    def test_two_ap_no_neighbors(self):
        from tools.optimization import optimize
        ap_data = {
            "AP1": {"neighbors": [], "ch_5g": 36, "width_5g": 80},
            "AP2": {"neighbors": [], "ch_5g": 36, "width_5g": 80},
        }
        result = optimize(ap_data, "5g", 80, False, {"AP1", "AP2"})
        assert "error" in result
        assert result["error"] == "no_interference_graph"

    def test_two_ap_with_neighbors(self):
        from tools.optimization import optimize
        ap_data = {
            "AP1": {
                "neighbors": [
                    {"name": "AP2", "snr_5g": 35, "ch_5g": 36, "width_5g": 80},
                ],
                "ch_5g": 36,
                "width_5g": 80,
            },
            "AP2": {
                "neighbors": [
                    {"name": "AP1", "snr_5g": 35, "ch_5g": 36, "width_5g": 80},
                ],
                "ch_5g": 36,
                "width_5g": 80,
            },
        }
        result = optimize(ap_data, "5g", 80, False, {"AP1", "AP2"})
        assert "error" not in result
        assert result["band"] == "5g"
        assert result["aps_total"] == 2
        assert "score_before" in result
        assert "score_after" in result
        assert "recommendations" in result
        assert "kpi" in result
        assert "verdict" in result

    def test_dfs_disabled(self):
        from tools.optimization import optimize
        ap_data = {
            "AP1": {
                "neighbors": [{"name": "AP2", "snr_5g": 30, "ch_5g": 36, "width_5g": 40}],
                "ch_5g": 36,
                "width_5g": 40,
            },
            "AP2": {
                "neighbors": [{"name": "AP1", "snr_5g": 30, "ch_5g": 36, "width_5g": 40}],
                "ch_5g": 36,
                "width_5g": 40,
            },
        }
        result = optimize(ap_data, "5g", 40, False, {"AP1", "AP2"})
        assert result["allow_dfs"] is False

    def test_custom_channels(self):
        from tools.optimization import optimize
        ap_data = {
            "AP1": {
                "neighbors": [{"name": "AP2", "snr_5g": 25, "ch_5g": 149, "width_5g": 20}],
                "ch_5g": 149,
                "width_5g": 20,
            },
            "AP2": {
                "neighbors": [{"name": "AP1", "snr_5g": 25, "ch_5g": 149, "width_5g": 20}],
                "ch_5g": 149,
                "width_5g": 20,
            },
        }
        result = optimize(ap_data, "5g", 20, False, {"AP1", "AP2"}, channels=[149, 153, 157, 161])
        assert "error" not in result
