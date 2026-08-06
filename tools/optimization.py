"""WiFi RF channel optimization — DSATUR + Tabu Search hybrid.

Graph coloring adapted for wireless: edge weights = SNR (higher SNR =
stronger constraint), colors = channels, goal = minimize total weighted
co-channel + adjacent-channel interference.

Algorithm:
  1. DSATUR (greedy) — initial solution, fast baseline
  2. Tabu Search — local search refiner, escape local optima
  3. Power heuristic — adjust TX based on strongest neighbor SNR
"""

from __future__ import annotations

from collections import deque
from typing import Any
import logging
import random

logger = logging.getLogger(__name__)

# ── Channel Catalogue ──────────────────────────────────────

_5G_NON_DFS: list[int] = [36, 40, 44, 48, 149, 153, 157, 161, 165]
_5G_DFS: list[int] = [52, 56, 60, 64, 100, 104, 108, 112, 116, 120,
                       124, 128, 132, 136, 140, 144]
_24G_ALL: list[int] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]
_24G_NON_OVERLAP: list[int] = [1, 6, 11]

# Check that the DFS list includes channels 52-64 + 100-144
assert len(_5G_DFS) == 16, f"DFS channels expected 16, got {len(_5G_DFS)}"

_POWER_LEVELS: dict[str, int] = {"full": 0, "max": 0, "high": -3, "half": -6, "quarter": -9, "min": -12}
_POWER_LABELS: list[tuple[int, str]] = [(-12, "min"), (-9, "quarter"), (-6, "half"), (-3, "high"), (0, "max")]


_5G_ALL_FREQ_SORTED: list[int] = sorted(set(_5G_NON_DFS + _5G_DFS))


def _freq_5g(ch: int) -> int:
    return 5000 + ch * 5  # 5180 for ch36, 5745 for ch149


def _freq_24g(ch: int) -> int:
    return 2412 + (ch - 1) * 5


def _channel_index_5g(channels: list[int], ch: int) -> int:
    """Position of ch in the ordered 5GHz channel list (0-based)."""
    try:
        return channels.index(ch)
    except ValueError:
        return -1


def _secondary_channel(primary: int, width: int) -> int | None:
    """Derive 5GHz secondary (extension) channel for channel bonding.

    For width > 20MHz, two adjacent 20MHz blocks are bonded into a pair.
    The secondary is the partner channel:
    - Even index in freq-sorted list → secondary = next (upper bond)
    - Odd index → secondary = previous (lower bond)
    - Edge fallback: if no next channel (e.g. ch165), bond below.

    Examples:
        primary=36, width=40 → secondary=40   (36+40 bond)
        primary=44, width=40 → secondary=48   (44+48 bond)
        primary=149, width=80 → secondary=153 (149+153 sub-block)
        primary=165, width=40 → secondary=161 (edge: bond below)
        primary=36, width=20 → None           (no bonding)

    Returns None for 20MHz or if channel not in 5GHz catalogue.
    """
    if width <= 20:
        return None
    try:
        idx = _5G_ALL_FREQ_SORTED.index(primary)
    except ValueError:
        return None
    if idx % 2 == 0:
        # Prefer upper bond, fall back to lower at edge (e.g. ch165)
        if idx + 1 < len(_5G_ALL_FREQ_SORTED):
            return _5G_ALL_FREQ_SORTED[idx + 1]
        return _5G_ALL_FREQ_SORTED[idx - 1] if idx > 0 else None
    return _5G_ALL_FREQ_SORTED[idx - 1] if idx > 0 else None


# ── Interference Factor ────────────────────────────────────

def _interference_5g(ch_a: int, w_a: int, ch_b: int, w_b: int) -> float:
    """Interference factor 0.0–1.0 between two 5GHz assignments.

    1.0 = same channel (full co-channel)
    Falls off with channel separation and width.
    """
    if ch_a == ch_b:
        return 1.0
    full = _5G_NON_DFS + _5G_DFS
    if ch_a not in full or ch_b not in full:
        return 0.0
    f_a, f_b = _freq_5g(ch_a), _freq_5g(ch_b)
    sep = abs(f_a - f_b)
    half = (w_a + w_b) / 2.0
    if sep <= half:
        return 0.8  # bands overlap
    # adjacent guard band (extra 20 MHz)
    if sep <= half + 20:
        # scale: closer to half → higher, closer to half+20 → lower
        t = (sep - half) / 20.0  # 0..1
        return 0.5 * (1.0 - t)
    return 0.0


def _interference_24g(ch_a: int, w_a: int, ch_b: int, w_b: int) -> float:  # noqa: ARG001
    """Interference factor for 2.4GHz (22 MHz wide, 5 MHz spacing).

    Every channel overlaps with ±4 neighbors.
    """
    if ch_a == ch_b:
        return 1.0
    dist = abs(ch_a - ch_b)
    if dist == 1:
        return 0.7
    if dist <= 3:
        return 0.3
    if dist <= 4:
        return 0.1
    return 0.0


_INTERFERENCE = {"5g": _interference_5g, "2.4g": _interference_24g}

# ── Neighbor Graph Structure ────────────────────────────────

# Per-AP neighbor data: neighbors[ap_name] = list of tuples
#   (neighbor_name: str, snr: int | None, ch: int | None, width: int | None, anchor: bool)
Graph = dict[str, list[tuple[str, int, int, int, bool]]]
# Coloring: {ap_name: (channel: int, width: int)}
Coloring = dict[str, tuple[int, int]]


def build_graph(
    ap_neighbors_data: dict[str, dict[str, Any]],
    band: str,
    fallback_width: int,
    optimizable: set[str],
) -> tuple[Graph, list[int], set[str]]:
    """Build weighted interference graph from neighbor data.

    Args:
        ap_neighbors_data: {ap_name: {"neighbors": [...], "cur_ch_X": ..., "cur_width_X": ...}}
        band: "5g" or "2.4g"
        fallback_width: width to use when AP width is unknown.
        optimizable: set of AP names whose channel CAN be changed.

    Returns:
        graph: adjacency list with SNR, channel, width, anchor flag per edge.
        channel_set: available channels for this band.
        all_nodes: all AP names (optimizable + anchors).
    """
    # Map "2.4g" → "24g" for data key consistency (normalize_neighbor uses 24g)
    band_key = "24g" if band == "2.4g" else band
    ch_key = f"ch_{band_key}"       # e.g. "ch_5g", "ch_24g"
    w_key = f"width_{band_key}"     # e.g. "width_5g", "width_24g"
    snr_key = f"snr_{band_key}"     # e.g. "snr_5g", "snr_24g"

    if band == "5g":
        channel_set: list[int] = _5G_NON_DFS + _5G_DFS
    else:
        channel_set = _24G_ALL

    graph: Graph = {}
    all_nodes: set[str] = set()
    seen_pairs: set[tuple[str, str]] = set()

    for ap_name, data in ap_neighbors_data.items():
        if ap_name not in graph:
            graph[ap_name] = []

        ch = data.get(ch_key)
        if ch is None:
            continue
        width = data.get(w_key) or fallback_width

        for nb in data.get("neighbors", []):
            nb_name = nb.get("name", "")
            nb_ch = nb.get(ch_key)
            if nb_ch is None:
                continue
            nb_snr = nb.get(snr_key)
            if nb_snr is None or nb_snr <= 0:
                continue
            nb_width = nb.get(w_key) or fallback_width
            nb_anchor = nb_name not in optimizable

            # Deduplicate undirected edges (both APs may report each other)
            pair = tuple(sorted((ap_name, nb_name)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            # Add edge to both adjacency lists
            graph[ap_name].append((nb_name, nb_snr, nb_ch, nb_width, nb_anchor))
            if nb_name not in graph:
                graph[nb_name] = []
            graph[nb_name].append((ap_name, nb_snr, ch, width, False))

            all_nodes.add(ap_name)
            all_nodes.add(nb_name)

    # Remove nodes with no edges (isolated APs — skip)
    graph = {n: edges for n, edges in graph.items() if edges}

    return graph, channel_set, all_nodes


# ── Score Functions ─────────────────────────────────────────

def _ap_score(
    ap: str,
    ch: int,
    width: int,
    band: str,
    current: Coloring,
    graph: Graph,
) -> float:
    """Total interference for one AP given current coloring of neighbors."""
    total = 0.0
    interfer = _INTERFERENCE[band]
    for nb_name, snr, nb_ch, nb_width, _ in graph.get(ap, []):
        if nb_name in current:
            nb_color, nb_w = current[nb_name]
            factor = interfer(ch, width, nb_color, nb_w)
            total += snr * factor
    return total


def total_interference(graph: Graph, coloring: Coloring, band: str) -> float:
    """Sum of interference across all edges (each edge counted once)."""
    seen: set[tuple[str, str]] = set()
    total = 0.0
    interfer = _INTERFERENCE[band]
    for ap in graph:
        if ap not in coloring:
            continue
        ch_a, w_a = coloring[ap]
        for nb_name, snr, _, _, _ in graph[ap]:
            if nb_name not in coloring:
                continue
            pair = tuple(sorted((ap, nb_name)))
            if pair in seen:
                continue
            seen.add(pair)
            ch_b, w_b = coloring[nb_name]
            total += snr * interfer(ch_a, w_a, ch_b, w_b)
    return total


# ── KPI Computation ────────────────────────────────────────

def _interference_pairs(
    graph: Graph, coloring: Coloring, band: str,
) -> tuple[int, int, float]:
    """Count co-channel and adjacent-channel interfering pairs + max per-AP.

    Returns:
        (co_channel_pairs, adjacent_pairs, max_interference_per_ap).
    """
    seen: set[tuple[str, str]] = set()
    interfer = _INTERFERENCE[band]
    co = 0
    adj = 0
    per_ap: dict[str, float] = {}

    for ap in graph:
        if ap not in coloring:
            continue
        ch_a, w_a = coloring[ap]
        for nb_name, snr, _, _, _ in graph[ap]:
            if nb_name not in coloring:
                continue
            pair = tuple(sorted((ap, nb_name)))
            if pair in seen:
                continue
            seen.add(pair)
            ch_b, w_b = coloring[nb_name]
            factor = interfer(ch_a, w_a, ch_b, w_b)
            if factor <= 0:
                continue
            contribution = snr * factor
            per_ap[ap] = per_ap.get(ap, 0) + contribution
            per_ap[nb_name] = per_ap.get(nb_name, 0) + contribution
            if factor >= 0.8:
                co += 1
            elif factor >= 0.3:
                adj += 1

    max_ap = max(per_ap.values()) if per_ap else 0.0
    return co, adj, round(max_ap, 1)


def _channel_distribution(
    coloring: Coloring, optimizable: set[str],
) -> dict[str, int]:
    """Count APs per channel (only optimizable APs)."""
    dist: dict[int, int] = {}
    for ap, (ch, _) in coloring.items():
        if ap in optimizable:
            dist[ch] = dist.get(ch, 0) + 1
    return {str(k): v for k, v in sorted(dist.items())}


def _compute_kpis(
    graph: Graph,
    current: Coloring,
    final: Coloring,
    band: str,
    recommendations: list[dict[str, Any]],
    optimizable: set[str],
    total_channels: int,
) -> dict[str, Any]:
    """Compute before/after KPIs across interference, channel reuse, SNR, power."""
    co_before, adj_before, max_before = _interference_pairs(graph, current, band)
    co_after, adj_after, max_after = _interference_pairs(graph, final, band)

    dist_before = _channel_distribution(current, optimizable)
    dist_after = _channel_distribution(final, optimizable)

    max_ch_before = max(dist_before.values()) if dist_before else 0
    max_ch_after = max(dist_after.values()) if dist_after else 0
    used_before = len(dist_before)
    used_after = len(dist_after)

    # Reuse efficiency: channels used / theoretical max channels needed
    total_aps = len(optimizable)
    ideal_channels = min(total_aps, total_channels)
    reuse_before = round(used_before / ideal_channels * 100) if ideal_channels else 0
    reuse_after = round(used_after / ideal_channels * 100) if ideal_channels else 0

    # SNR quality — physical, same before/after
    all_snrs = [snr for edges in graph.values() for _, snr, _, _, _ in edges]
    avg_snr = round(sum(all_snrs) / len(all_snrs), 1) if all_snrs else 0
    strong = sum(1 for s in all_snrs if s > 25)
    strong_pct = round(strong / len(all_snrs) * 100) if all_snrs else 0

    # Power
    power_recs = [r.get("rec_power", "max") for r in recommendations]
    power_changes = sum(1 for p in power_recs if p != "max")
    coverage_risk = sum(1 for p in power_recs if p in ("min", "quarter"))
    deltas = [_POWER_LEVELS.get(p, 0) for p in power_recs if p != "max"]
    avg_delta = round(sum(deltas) / len(deltas), 1) if deltas else 0.0

    # Isolated APs (optimizable but no neighbors in graph)
    isolated = total_aps - sum(1 for ap in optimizable if ap in graph)

    return {
        "interference": {
            "total": {"before": round(_total_raw(graph, current, band), 1),
                      "after": round(_total_raw(graph, final, band), 1)},
            "co_channel_pairs": {"before": co_before, "after": co_after},
            "adjacent_pairs": {"before": adj_before, "after": adj_after},
            "max_per_ap": {"before": max_before, "after": max_after},
        },
        "channel_reuse": {
            "before": dist_before,
            "after": dist_after,
            "max_per_channel": {"before": max_ch_before, "after": max_ch_after},
            "channels_used": {"before": used_before, "after": used_after},
            "reuse_efficiency_pct": {"before": reuse_before, "after": reuse_after},
        },
        "snr_quality": {
            "avg_neighbor_snr": avg_snr,
            "strong_overlap_pct": strong_pct,
            "isolated_aps": isolated,
        },
        "power": {
            "avg_delta_db": avg_delta,
            "changes": power_changes,
            "coverage_risk_aps": coverage_risk,
        },
    }


def _total_raw(graph: Graph, coloring: Coloring, band: str) -> float:
    """Raw total interference (unrounded, for KPI nesting)."""
    return total_interference(graph, coloring, band)


def _compute_verdict(kpi: dict[str, Any]) -> tuple[str, str]:
    """Auto-generate verdict from KPI snapshot.

    Returns:
        (verdict_label, reason_string).
    """
    inter = kpi["interference"]
    power = kpi["power"]
    snr = kpi["snr_quality"]
    reuse = kpi["channel_reuse"]

    co_after = inter["co_channel_pairs"]["after"]
    isolated = snr["isolated_aps"]
    risk = power["coverage_risk_aps"]
    eff_after = reuse["reuse_efficiency_pct"]["after"]

    total_before = inter["total"]["before"]
    total_after = inter["total"]["after"]
    improvement = ((total_before - total_after) / total_before * 100) if total_before > 0 else 0

    if isolated > 0:
        return "warning", f"{isolated} AP(s) have no audible neighbors — potential coverage hole"
    if co_after == 0 and risk == 0:
        return "excellent", "Co-channel interference eliminated, no coverage risks"
    if co_after == 0 and risk > 0:
        return "good", "Co-channel eliminated, but check coverage risk on reduced-power APs"
    if improvement >= 50 and risk == 0:
        return "good", f"{improvement:.0f}% interference reduction, no coverage risks"
    if improvement >= 20:
        return "fair", f"{improvement:.0f}% reduction — some residual interference ({co_after} co-channel pairs)"
    if eff_after < 30:
        return "warning", "Low channel reuse efficiency — consider DFS or width downgrade"
    return "fair", f"{improvement:.0f}% reduction — review residual interference"


# ── DSATUR — Initial Solution ───────────────────────────────

def _saturation_order(graph: Graph, coloring: Coloring) -> list[str]:
    """Order uncolored APs by DSATUR priority: most constrained first.

    Saturation degree = number of distinct neighbor channels.
    Tiebreaker = total SNR from already-colored neighbors.
    """

    def _priority(ap: str) -> tuple[int, float]:
        colors_seen: set[int] = set()
        total_snr = 0.0
        for nb_name, snr, _, _, _ in graph.get(ap, []):
            if nb_name in coloring:
                nb_ch = coloring[nb_name][0]
                colors_seen.add(nb_ch)
                total_snr += snr
        return -len(colors_seen), -total_snr  # negate for ascending sort

    uncolored = [ap for ap in graph if ap not in coloring and not _is_anchor(ap, graph)]
    random.shuffle(uncolored)  # deterministic tie-break with shuffle
    return sorted(uncolored, key=_priority)


def _is_anchor(ap: str, graph: Graph) -> bool:
    """Check if ALL edges to this node point to anchors (meaning this node
    itself is a pure anchor that can't be changed)."""
    for _, _, _, _, anchor in graph.get(ap, []):
        if not anchor:
            return False
    return True  # no optimizable neighbor → no reason to optimize this AP


def _best_channel(
    ap: str,
    channels: list[int],
    width: int,
    band: str,
    coloring: Coloring,
    graph: Graph,
) -> int:
    """Pick channel with minimum interference from already-colored neighbors."""
    best_ch = channels[0]
    best_score = float("inf")
    for ch in channels:
        score = _ap_score(ap, ch, width, band, coloring, graph)
        if score < best_score:
            best_score = score
            best_ch = ch
    return best_ch


def dsatur_assign(
    graph: Graph,
    channels: list[int],
    width: int,
    band: str,
    anchor_colors: Coloring,
) -> tuple[Coloring, float]:
    """DSATUR greedy graph coloring for WiFi channel assignment.

    Returns:
        coloring: {ap_name: (channel, width)}
        score: total interference (lower = better).
    """
    coloring: Coloring = dict(anchor_colors)
    while True:
        order = _saturation_order(graph, coloring)
        if not order:
            break
        ap = order[0]
        ch = _best_channel(ap, channels, width, band, coloring, graph)
        coloring[ap] = (ch, width)
    score = total_interference(graph, coloring, band)
    logger.info("DSATUR score: %.1f", score)
    return coloring, score


# ── Tabu Search — Refinement ─────────────────────────────────

def tabu_refine(
    graph: Graph,
    initial: Coloring,
    channels: list[int],
    width: int,
    band: str,
    iterations: int = 500,
    tabu_size: int = 15,
) -> tuple[Coloring, float]:
    """Tabu Search refinement over DSATUR initial solution.

    Neighborhood: change 1 AP's channel (move).
    Tabu list: prevents cycling by remembering recent (ap, channel) pairs.
    Aspiration: accept tabu move if it beats the global best.

    Returns:
        best_coloring, best_score (float).
    """
    optimizable = {ap for ap in initial if not _is_anchor(ap, graph)}
    if not optimizable:
        return dict(initial), total_interference(graph, initial, band)

    current = dict(initial)
    best = dict(initial)
    current_score = total_interference(graph, current, band)
    best_score = current_score
    tabu: deque[tuple[str, int]] = deque(maxlen=tabu_size)

    for iteration in range(iterations):
        best_move_score = float("inf")
        best_move: tuple[str, int] | None = None

        for ap in optimizable:
            if ap not in current:
                continue
            old_ch = current[ap][0]
            for ch in channels:
                if ch == old_ch:
                    continue

                # Evaluate this move via delta score
                current[ap] = (ch, width)
                new_score = total_interference(graph, current, band)
                current[ap] = (old_ch, width)  # undo

                if new_score < best_move_score:
                    tabu_hit = (ap, ch) in tabu
                    # Aspiration: accept tabu move if it beats global best
                    if not tabu_hit or new_score < best_score:
                        best_move_score = new_score
                        best_move = (ap, ch)

        if best_move is None:
            break  # no improving moves available

        ap, ch = best_move  # type: ignore[assignment]
        current[ap] = (ch, width)
        current_score = best_move_score
        tabu.append((ap, ch))

        if current_score < best_score:
            best = dict(current)
            best_score = current_score

    logger.info(
        "Tabu: %d iterations done, score %.1f → %.1f",
        iteration + 1, total_interference(graph, initial, band), best_score,
    )
    return best, best_score


# ── Power Optimization — SNR-based Heuristic ─────────────────

def _power_recommendation(
    ap: str,
    coloring: Coloring,
    graph: Graph,
    band: str,
    current_power: str,
) -> tuple[str, str]:
    """Recommend TX power based on strongest co-channel / adjacent neighbor SNR.

    If a neighbor has very high SNR (>30dB) the cell is oversized → reduce.
    If no strong neighbors exist → keep max.

    Returns:
        (recommended_power_label, reason_string).
    """
    if ap not in coloring:
        return current_power, "not in graph"

    ch_a, w_a = coloring[ap]
    interfer = _INTERFERENCE[band]
    max_snr = 0
    max_nb = ""

    for nb_name, snr, nb_ch, nb_width, _ in graph.get(ap, []):
        if nb_name not in coloring:
            continue
        nb_color, nb_w = coloring[nb_name]
        # Only consider neighbors with actual interference potential
        if interfer(ch_a, w_a, nb_color, nb_w) > 0 and snr > max_snr:
            max_snr = snr
            max_nb = nb_name

    # Map SNR to power recommendation
    if max_snr > 35:
        label, reason = "min", f"very strong neighbor {max_nb} ({max_snr}dB)"
    elif max_snr > 30:
        label, reason = "quarter", f"strong neighbor {max_nb} ({max_snr}dB)"
    elif max_snr > 25:
        label, reason = "half", f"moderate neighbor {max_nb} ({max_snr}dB)"
    elif max_snr > 15:
        label, reason = "high", f"weak neighbor {max_nb} ({max_snr}dB)"
    else:
        label, reason = "max", "no close neighbor — coverage priority"

    return label, reason


# ── Main Entry Point ─────────────────────────────────────────

def optimize(
    ap_neighbors_data: dict[str, dict[str, Any]],
    band: str,
    channel_width: int,
    allow_dfs: bool,
    optimizable: set[str],
    channels: list[int] | None = None,
) -> dict[str, Any]:
    """Run full channel + power optimization.

    Args:
        ap_neighbors_data: output of per-AP neighbor collection.
        band: "5g" or "2.4g".
        channel_width: MHz (e.g. 20, 40, 80). 0 = auto from AP config.
        allow_dfs: include DFS channels (52-64, 100-144). Ignored if
            channels is set.
        optimizable: set of AP names that can be changed.
        channels: Custom channel pool (overrides allow_dfs). Filters to
            valid channels for the band. e.g. [36, 40, 44, 48] for
            UNII-1 only, or [149, 153, 157, 161] for UNII-3 (no 165).

    Returns:
        dict with before/after scores, per-AP recommendations, and summary.
    """
    # Channel set
    if channels:
        _valid = set(_5G_NON_DFS + _5G_DFS) if band == "5g" else set(_24G_ALL)
        full_channels = [c for c in channels if c in _valid]
        if not full_channels:
            return {"error": "no_valid_channels", "detail": f"none of {channels} are valid for band={band}"}
    elif band == "5g":
        full_channels = _5G_NON_DFS + (list(_5G_DFS) if allow_dfs else [])
    else:
        full_channels = _24G_ALL

    # Resolve channel width — auto-detect from AP data
    band_key = "24g" if band == "2.4g" else band
    if channel_width == 0:
        widths: list[int] = []
        for d in ap_neighbors_data.values():
            w = d.get(f"width_{band_key}")
            if w:
                widths.append(w)
        channel_width = max(set(widths)) if widths else (80 if band == "5g" else 20)

    # Build graph
    graph, channels_available, all_nodes = build_graph(
        ap_neighbors_data, band, channel_width, optimizable,
    )

    if not graph:
        return {"error": "no_interference_graph", "detail": "no APs with audible neighbors"}

    # Anchor colors: current channels of non-optimizable APs
    anchor_colors: Coloring = {}
    for name, data in ap_neighbors_data.items():
        if name not in optimizable:
            ch = data.get(f"ch_{band_key}")
            if ch is not None:
                anchor_colors[name] = (ch, data.get(f"width_{band_key}") or channel_width)

    # Use only channels in our catalogue
    channels = [c for c in full_channels if c in full_channels]
    if not channels:
        return {"error": "no_channels_available", "band": band, "allow_dfs": allow_dfs}

    # Baseline: current interference
    current_coloring: Coloring = {}
    for name, data in ap_neighbors_data.items():
        ch = data.get(f"ch_{band_key}")
        if ch is not None:
            current_coloring[name] = (ch, data.get(f"width_{band_key}") or channel_width)
    score_before = total_interference(graph, current_coloring, band)

    # DSATUR
    dsat_coloring, dsat_score = dsatur_assign(graph, channels, channel_width, band, anchor_colors)

    # Tabu Search
    final_coloring, final_score = tabu_refine(graph, dsat_coloring, channels, channel_width, band)

    # Per-AP recommendations
    recommendations: list[dict[str, Any]] = []
    aps_changed = 0
    aps_unchanged = 0

    for ap in optimizable:
        if ap not in current_coloring:
            continue
        old_ch, old_w = current_coloring[ap]
        new_ch = final_coloring.get(ap, (old_ch, old_w))[0]
        new_w = channel_width

        changed = old_ch != new_ch
        if changed:
            aps_changed += 1
        else:
            aps_unchanged += 1

        # Power recommendation
        power_label, power_reason = _power_recommendation(
            ap, final_coloring, graph, band, "max",
        )

        rec: dict[str, Any] = {
            "ap": ap,
            "cur_ch": old_ch,
            "cur_width": old_w,
            "rec_ch": new_ch,
            "rec_width": new_w,
            "changed": changed,
            "rec_power": power_label,
            "power_reason": power_reason,
        }
        if band == "5g":
            rec["cur_secondary"] = _secondary_channel(old_ch, old_w)
            rec["rec_secondary"] = _secondary_channel(new_ch, new_w)
        if changed:
            rec["reason_ch"] = _change_reason(ap, old_ch, new_ch, current_coloring, graph, band)

        recommendations.append(rec)

    improvements_pct = ((score_before - final_score) / score_before * 100) if score_before > 0 else 0

    # KPI computation
    kpi = _compute_kpis(
        graph, current_coloring, final_coloring, band,
        recommendations, optimizable, len(channels),
    )
    verdict, verdict_reason = _compute_verdict(kpi)

    return {
        "band": band,
        "channel_width": channel_width,
        "allow_dfs": allow_dfs,
        "channels_available": len(channels),
        "graphs_nodes": len(graph),
        "score_before": round(score_before, 1),
        "score_after": round(final_score, 1),
        "score_dsatur_only": round(dsat_score, 1),
        "improvement_pct": round(improvements_pct, 1),
        "aps_total": len(optimizable),
        "aps_changed": aps_changed,
        "aps_unchanged": aps_unchanged,
        "kpi": kpi,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "recommendations": sorted(recommendations, key=lambda r: r["changed"], reverse=True),
    }


def _change_reason(
    ap: str,
    old_ch: int,
    new_ch: int,
    current: Coloring,
    graph: Graph,
    band: str,
) -> str:
    """Human-readable reason for a channel change."""
    interfer = _INTERFERENCE[band]
    co_neighbors: list[str] = []
    adj_neighbors: list[str] = []
    for nb, snr, nb_ch, nb_width, _ in graph.get(ap, []):
        if nb in current:
            nb_col = current[nb][0]
            nb_w = current[nb][1]
            f = interfer(old_ch, 20, nb_col, nb_w)
            if f >= 0.8:
                co_neighbors.append(f"{nb}({snr}dB)")
            elif f >= 0.3:
                adj_neighbors.append(f"{nb}({snr}dB)")

    parts: list[str] = []
    if co_neighbors:
        parts.append(f"{len(co_neighbors)} co-channel: {', '.join(co_neighbors[:3])}" + (
            " ..." if len(co_neighbors) > 3 else ""))
    if adj_neighbors:
        parts.append(f"{len(adj_neighbors)} adjacent: {', '.join(adj_neighbors[:3])}" + (
            " ..." if len(adj_neighbors) > 3 else ""))
    if not parts:
        parts.append("no strong interference on current channel")
    return f"ch{old_ch} → ch{new_ch}: {'; '.join(parts)}"
