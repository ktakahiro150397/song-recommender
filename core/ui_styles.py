"""
UI styling helpers for DataFrames.
"""

import pandas as pd


def style_distance_value(val: str) -> str:
    """Return CSS style string for distance values."""
    if val == "-":
        return "background-color: #f7f7f7; color: #444; font-weight: bold"
    try:
        distance = float(val)
        ratio = min(distance / 0.01, 1.0)
        if ratio < 0.5:
            r = int(255 * (ratio * 2))
            g = 255
        else:
            r = 255
            g = int(255 * (1 - (ratio - 0.5) * 2))
        b = 0
        # Use colored background but keep dark text for contrast.
        bg_r = int(r * 0.18 + 255 * 0.82)
        bg_g = int(g * 0.18 + 255 * 0.82)
        bg_b = int(b * 0.18 + 255 * 0.82)
        return (
            f"background-color: #{bg_r:02x}{bg_g:02x}{bg_b:02x}; "
            "color: #1f1f1f; font-weight: 600"
        )
    except ValueError:
        return ""


def style_distance_column(
    df: pd.DataFrame, column_names: list[str] | None = None
) -> pd.DataFrame:
    """Apply distance styling to a distance column if present."""

    def color_distance(val: str) -> str:
        return style_distance_value(val)

    if column_names is None:
        column_names = ["距離", "コサイン距離"]

    for column in column_names:
        if column in df.columns:
            return df.style.map(color_distance, subset=[column])

    return df.style
