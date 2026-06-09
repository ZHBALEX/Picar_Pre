from __future__ import annotations

from dataclasses import dataclass


AXIS_KEYS = {
    "x": {
        "length": "Lx",
        "center": "x_center_dense",
        "dense_length": "Lx_dense",
        "dense_count": "Nx_dense",
        "left_length": "len_left",
        "right_length": "len_right",
        "left_stretch": "n_left_stretch",
        "left_uniform": "n_left_uniform",
        "right_uniform": "n_right_uniform",
        "right_stretch": "n_right_stretch",
    },
    "y": {
        "length": "Ly",
        "center": "y_center_dense",
        "dense_length": "Ly_dense",
        "dense_count": "Ny_dense",
        "left_length": "len_bottom",
        "right_length": "len_top",
        "left_stretch": "n_bottom_stretch",
        "left_uniform": "n_bottom_uniform",
        "right_uniform": "n_top_uniform",
        "right_stretch": "n_top_stretch",
    },
    "z": {
        "length": "Lz",
        "center": "z_center_dense",
        "dense_length": "Lz_dense",
        "dense_count": "Nz_dense",
        "left_length": "len_front",
        "right_length": "len_back",
        "left_stretch": "n_front_stretch",
        "left_uniform": "n_front_uniform",
        "right_uniform": "n_back_uniform",
        "right_stretch": "n_back_stretch",
    },
}


@dataclass(frozen=True)
class CountQuality:
    """Divisibility-by-two quality for a positive interval count."""

    count: int
    odd_remainder: int
    factor_twos: int


@dataclass(frozen=True)
class AxisOptimization:
    """Optimization result for one mesh axis."""

    axis: str
    dense_spacing: float
    old_dense_count: int
    new_dense_count: int
    old_dense_length: float
    new_dense_length: float
    old_total_count: int
    new_total_count: int
    old_dense_quality: CountQuality
    new_dense_quality: CountQuality
    old_total_quality: CountQuality
    new_total_quality: CountQuality
    method: str = "search"

    @property
    def changed(self) -> bool:
        return self.old_dense_count != self.new_dense_count


def count_quality(count: int) -> CountQuality:
    """Return odd remainder and factor-of-two count."""
    count = int(count)
    if count <= 0:
        raise ValueError("Count must be positive")
    factor_twos = (count & -count).bit_length() - 1
    return CountQuality(count=count, odd_remainder=count >> factor_twos, factor_twos=factor_twos)


def optimize_mesh_params(
    params: dict[str, object],
    axes: tuple[str, ...] = ("x", "y", "z"),
    search_window: int | None = None,
    max_relative_dense_change: float = 0.25,
    priority: str = "dense",
    method: str = "search",
    ideal_deltas: dict[str, float] | None = None,
) -> tuple[dict[str, object], list[AxisOptimization]]:
    """Optimize dense interval counts independently for multigrid-friendly axes.

    Dense spacing is preserved. The optimizer changes each dense interval count
    and therefore its dense-region length, while keeping the dense center fixed.
    """
    result = dict(params)
    reports: list[AxisOptimization] = []
    for axis in axes:
        result, report = optimize_axis_params(
            result,
            axis,
            search_window=search_window,
            max_relative_dense_change=max_relative_dense_change,
            priority=priority,
            method=method,
            ideal_delta=None if ideal_deltas is None else ideal_deltas.get(axis),
        )
        reports.append(report)
    return result, reports


def optimize_axis_params(
    params: dict[str, object],
    axis: str,
    search_window: int | None = None,
    max_relative_dense_change: float = 0.25,
    priority: str = "dense",
    method: str = "search",
    ideal_delta: float | None = None,
) -> tuple[dict[str, object], AxisOptimization]:
    """Optimize one axis while preserving dense spacing."""
    keys = AXIS_KEYS[axis]
    old_dense_count = int(params[keys["dense_count"]])
    old_dense_length = float(params[keys["dense_length"]])
    if old_dense_count <= 0:
        raise ValueError(f"{axis}: dense interval count must be positive")

    spacing = old_dense_length / old_dense_count
    total_side_count = _side_interval_count(params, keys)
    old_total_count = total_side_count + old_dense_count
    if method == "table":
        target_spacing = float(ideal_delta) if ideal_delta is not None else spacing
        target_count = old_dense_length / target_spacing
        candidates = []
        for count in preferred_count_candidates(max_count=max(old_dense_count * 4, int(target_count * 2) + 1024)):
            new_dense_length = target_spacing * count
            if not _dense_change_allowed(old_dense_length, new_dense_length, max_relative_dense_change):
                continue
            if not _axis_geometry_is_valid(params, keys, new_dense_length):
                continue
            total_count = total_side_count + count
            candidates.append(
                (
                    count,
                    new_dense_length,
                    total_count,
                    (
                        abs(count - target_count),
                        count_quality(count).odd_remainder,
                        count_quality(total_count).odd_remainder,
                        -count_quality(count).factor_twos,
                    ),
                )
            )
    else:
        if method != "search":
            raise ValueError("method must be 'search' or 'table'")
        window = search_window if search_window is not None else max(32, old_dense_count // 2)
        low = max(1, old_dense_count - int(window))
        high = old_dense_count + int(window)

        candidates = []
        for count in range(low, high + 1):
            new_dense_length = spacing * count
            if not _dense_change_allowed(old_dense_length, new_dense_length, max_relative_dense_change):
                continue
            if not _axis_geometry_is_valid(params, keys, new_dense_length):
                continue
            total_count = total_side_count + count
            candidates.append(
                (count, new_dense_length, total_count, _score_counts(count, total_count, old_dense_count, priority))
            )

    if not candidates:
        raise ValueError(f"{axis}: no valid multigrid optimization candidate found")

    new_dense_count, new_dense_length, new_total_count, _ = min(candidates, key=lambda item: item[3])

    new_params = dict(params)
    new_params[keys["dense_count"]] = int(new_dense_count)
    new_params[keys["dense_length"]] = float(new_dense_length)

    report = AxisOptimization(
        axis=axis,
        dense_spacing=spacing,
        old_dense_count=old_dense_count,
        new_dense_count=int(new_dense_count),
        old_dense_length=old_dense_length,
        new_dense_length=float(new_dense_length),
        old_total_count=old_total_count,
        new_total_count=int(new_total_count),
        old_dense_quality=count_quality(old_dense_count),
        new_dense_quality=count_quality(new_dense_count),
        old_total_quality=count_quality(old_total_count),
        new_total_quality=count_quality(new_total_count),
        method=method,
    )
    return new_params, report


def format_optimization_report(reports: list[AxisOptimization]) -> str:
    """Format multigrid optimization results."""
    if not reports:
        return "No optimization report."
    header = (
        f"{'Axis':>4}  {'Dense':>13}  {'Dense odd':>11}  {'Total':>13}  "
        f"{'Total odd':>11}  {'dx':>12}  {'L_dense':>18}"
    )
    line = "-" * len(header)
    rows = ["Multigrid Count Optimization", "============================", header, line]
    for item in reports:
        rows.append(
            f"{item.axis:>4}  "
            f"{item.old_dense_count:>5}->{item.new_dense_count:<5}  "
            f"{item.old_dense_quality.odd_remainder:>5}->{item.new_dense_quality.odd_remainder:<5}  "
            f"{item.old_total_count:>5}->{item.new_total_count:<5}  "
            f"{item.old_total_quality.odd_remainder:>5}->{item.new_total_quality.odd_remainder:<5}  "
            f"{item.dense_spacing:>12.6g}  "
            f"{item.old_dense_length:>8.6g}->{item.new_dense_length:<8.6g}"
        )
    return "\n".join(rows)


def format_count_quality_report(params: dict[str, object]) -> str:
    """Format dense and total count quality for current parameters."""
    reports = []
    for axis in ("x", "y", "z"):
        keys = AXIS_KEYS[axis]
        dense_count = int(params[keys["dense_count"]])
        total_count = dense_count + _side_interval_count(params, keys)
        reports.append(
            (
                axis,
                count_quality(dense_count),
                count_quality(total_count),
            )
        )

    header = f"{'Axis':>4}  {'Dense':>8}  {'Dense odd':>11}  {'Dense /2':>9}  {'Total':>8}  {'Total odd':>11}  {'Total /2':>9}"
    line = "-" * len(header)
    rows = ["Multigrid Count Quality", "=======================", header, line]
    for axis, dense, total in reports:
        rows.append(
            f"{axis:>4}  {dense.count:>8}  {dense.odd_remainder:>11}  {dense.factor_twos:>9}  "
            f"{total.count:>8}  {total.odd_remainder:>11}  {total.factor_twos:>9}"
        )
    return "\n".join(rows)


def preferred_count_candidates(max_count: int, odd_remainders: tuple[int, ...] = tuple(range(1, 22, 2))) -> list[int]:
    """Return FSRG-style preferred counts, odd remainder times powers of two."""
    max_count = int(max_count)
    values: set[int] = set()
    power = 1
    while power <= max_count:
        for odd in odd_remainders:
            value = odd * power
            if 0 < value <= max_count:
                values.add(value)
        power *= 2
    return sorted(values)


def preferred_count_near(target: float, max_count: int | None = None) -> int:
    """Return the preferred count closest to target."""
    if max_count is None:
        max_count = max(64, int(target * 2) + 1024)
    candidates = preferred_count_candidates(max_count)
    return min(candidates, key=lambda count: (abs(count - target), count_quality(count).odd_remainder, -count_quality(count).factor_twos))


def _score_counts(
    dense_count: int,
    total_count: int,
    original_dense_count: int,
    priority: str,
) -> tuple[int, int, int, int, int]:
    dense = count_quality(dense_count)
    total = count_quality(total_count)
    if priority == "balanced":
        return (
            dense.odd_remainder + total.odd_remainder,
            max(dense.odd_remainder, total.odd_remainder),
            dense.odd_remainder,
            total.odd_remainder,
            abs(dense_count - original_dense_count),
        )
    if priority != "dense":
        raise ValueError("priority must be 'dense' or 'balanced'")
    return (
        dense.odd_remainder,
        total.odd_remainder,
        max(dense.odd_remainder, total.odd_remainder),
        dense.factor_twos * -1,
        abs(dense_count - original_dense_count),
    )


def _dense_change_allowed(old_dense_length: float, new_dense_length: float, max_relative_dense_change: float) -> bool:
    max_delta = abs(old_dense_length) * float(max_relative_dense_change)
    return abs(new_dense_length - old_dense_length) <= max_delta + 1e-12


def _side_interval_count(params: dict[str, object], keys: dict[str, str]) -> int:
    return (
        int(params[keys["left_stretch"]])
        + int(params[keys["left_uniform"]])
        + int(params[keys["right_uniform"]])
        + int(params[keys["right_stretch"]])
    )


def _axis_geometry_is_valid(params: dict[str, object], keys: dict[str, str], dense_length: float) -> bool:
    length = float(params[keys["length"]])
    center = float(params[keys["center"]])
    left_total = center - 0.5 * dense_length
    right_total = length - center - 0.5 * dense_length
    if left_total <= 0.0 or right_total <= 0.0:
        return False
    if int(params[keys["left_stretch"]]) > 0 and float(params[keys["left_length"]]) >= left_total:
        return False
    if int(params[keys["right_stretch"]]) > 0 and float(params[keys["right_length"]]) >= right_total:
        return False
    return True
