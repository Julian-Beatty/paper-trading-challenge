"""Plots module for the paper-trading challenge.

This file keeps its responsibilities focused so the trading workflow remains easy to follow and test.
"""

# Responsibility: render portfolio trajectories and optional execution annotations.

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import matplotlib

# FastAPI may run without a desktop/display (CI, Docker, remote server).
matplotlib.use("Agg")

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, PercentFormatter


@dataclass(frozen=True)
class PortfolioPoint:
    timestamp: datetime
    value: Decimal


@dataclass(frozen=True)
class PortfolioSeries:
    label: str
    starting_value: Decimal
    points: tuple[PortfolioPoint, ...]


@dataclass(frozen=True)
class TradeMarker:
    """One grouped order execution marker displayed on a participant chart."""

    timestamp: datetime
    side: str
    symbol: str
    quantity: int
    average_price: Decimal
    fill_count: int = 1


def _as_float(value: Decimal) -> float:
    return float(value)


def _money_formatter(value: float, _position: int) -> str:
    return f"${value:,.0f}"


def _style_time_axis(ax) -> None:
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.margins(x=0.02)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.22, linewidth=0.8)
    ax.grid(axis="x", alpha=0.10, linewidth=0.6)


def _style_metric_axis(ax, metric: str) -> None:
    if metric == "return":
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=100, decimals=2))
        ax.axhline(0, linewidth=1.0, linestyle="--", alpha=0.65)
        ax.set_ylabel("Cumulative return")
    else:
        ax.yaxis.set_major_formatter(FuncFormatter(_money_formatter))
        ax.set_ylabel("Portfolio value")


def _render_figure(fig) -> bytes:
    buffer = BytesIO()
    try:
        fig.tight_layout()
        fig.savefig(
            buffer,
            format="png",
            dpi=175,
            bbox_inches="tight",
            facecolor="white",
        )
        return buffer.getvalue()
    finally:
        plt.close(fig)
        buffer.close()


def _marker_y_value(
    marker: TradeMarker,
    times: list[datetime],
    y_values: list[float],
) -> float:
    """Return the first portfolio observation at or after an execution timestamp."""
    for timestamp, y_value in zip(times, y_values):
        if timestamp >= marker.timestamp:
            return y_value
    return y_values[-1]


def _annotate_trades(ax, markers, times, y_values) -> None:
    """Annotate grouped buy/sell executions without changing the portfolio series."""
    markers = tuple(markers)
    for index, marker in enumerate(markers):
        y_value = _marker_y_value(marker, times, y_values)
        is_buy = marker.side.upper() == "BUY"
        marker_shape = "^" if is_buy else "v"
        vertical_offset = 18 if is_buy else -32
        # Alternate horizontal offsets to reduce collisions when trades occur close together.
        horizontal_offset = 9 if index % 2 == 0 else -72
        ax.scatter(
            marker.timestamp,
            y_value,
            marker=marker_shape,
            s=62,
            zorder=6,
        )
        fill_note = f" · {marker.fill_count} fills" if marker.fill_count > 1 else ""
        label = (
            f"{marker.side.upper()} {marker.quantity} {marker.symbol}{fill_note}\n"
            f"avg ${float(marker.average_price):,.2f}"
        )
        ax.annotate(
            label,
            xy=(marker.timestamp, y_value),
            xytext=(horizontal_offset, vertical_offset),
            textcoords="offset points",
            fontsize=8,
            ha="left",
            va="bottom" if is_buy else "top",
            arrowprops={"arrowstyle": "->", "linewidth": 0.7, "alpha": 0.6},
            bbox={"boxstyle": "round,pad=0.3", "fc": "white", "alpha": 0.88, "lw": 0.6},
            zorder=7,
        )


def participant_portfolio_plot(
    *,
    participant_name: str,
    points: Iterable[PortfolioPoint],
    metric: str = "value",
    starting_value: Decimal | None = None,
    trade_markers: Iterable[TradeMarker] = (),
) -> bytes:
    points = tuple(points)
    if not points:
        raise ValueError("No portfolio history is available for this participant")

    times = [point.timestamp for point in points]
    values = [_as_float(point.value) for point in points]

    if metric == "return":
        initial = _as_float(starting_value) if starting_value is not None else values[0]
        if initial == 0:
            raise ValueError("Cannot calculate returns from a zero initial portfolio value")
        y_values = [(value / initial - 1.0) * 100.0 for value in values]
        title = f"{participant_name} — Cumulative portfolio return"
    elif metric == "value":
        y_values = values
        title = f"{participant_name} — Portfolio value trajectory"
    else:
        raise ValueError("metric must be either 'value' or 'return'")

    fig, ax = plt.subplots(figsize=(11.5, 6.5))
    ax.plot(times, y_values, linewidth=2.4)
    ax.scatter(times[-1], y_values[-1], s=38, zorder=4)

    if metric == "return":
        ax.fill_between(times, y_values, 0, alpha=0.08)

    markers = tuple(trade_markers)
    if markers:
        _annotate_trades(ax, markers, times, y_values)

    ax.set_title(title, pad=14, fontsize=15)
    ax.set_xlabel("Simulation time")
    _style_metric_axis(ax, metric)
    _style_time_axis(ax)

    latest_label = (
        f"{y_values[-1]:.2f}%"
        if metric == "return"
        else f"${y_values[-1]:,.2f}"
    )
    ax.annotate(
        latest_label,
        xy=(times[-1], y_values[-1]),
        xytext=(8, 8),
        textcoords="offset points",
        fontsize=9,
    )

    if markers:
        ax.text(
            0.01,
            0.01,
            "▲ BUY    ▼ SELL    (partial fills grouped by order)",
            transform=ax.transAxes,
            fontsize=8,
            alpha=0.75,
        )

    return _render_figure(fig)


def competition_portfolio_plot(
    *,
    competition_name: str,
    series: Iterable[PortfolioSeries],
    metric: str = "return",
) -> bytes:
    series = tuple(series)
    populated = [item for item in series if item.points]
    if not populated:
        raise ValueError("No portfolio history is available for this competition")

    if metric not in {"value", "return"}:
        raise ValueError("metric must be either 'value' or 'return'")

    fig, ax = plt.subplots(figsize=(12, 6.7))

    for item in populated:
        times = [point.timestamp for point in item.points]
        values = [_as_float(point.value) for point in item.points]

        if metric == "return":
            initial = _as_float(item.starting_value)
            if initial == 0:
                continue
            y_values = [(value / initial - 1.0) * 100.0 for value in values]
        else:
            y_values = values

        line = ax.plot(times, y_values, linewidth=2.0, label=item.label)[0]
        ax.scatter(
            times[-1],
            y_values[-1],
            s=28,
            color=line.get_color(),
            zorder=4,
        )

    metric_name = "Cumulative returns" if metric == "return" else "Portfolio values"
    ax.set_title(f"{competition_name} — {metric_name}", pad=14, fontsize=15)
    ax.set_xlabel("Simulation time")
    _style_metric_axis(ax, metric)
    _style_time_axis(ax)
    ax.legend(
        loc="upper left",
        frameon=False,
        ncol=min(3, max(1, len(populated))),
    )

    return _render_figure(fig)
