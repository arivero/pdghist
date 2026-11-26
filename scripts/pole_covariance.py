#!/usr/bin/env python3
"""Reproduce the 2025 and 2026 W/Z pole comparison from the PDG display values."""
from math import hypot, sqrt
from pathlib import Path

import yaml

from extract_db import parse_value_text


DATA = Path(__file__).resolve().parents[1] / "data"


def display_measurement(record):
    measurement = parse_value_text(record["value_text"])
    if record["unit"] != "GeV" or record.get("limit_type") or measurement is None:
        raise ValueError(f"Expected a mass or width in GeV: {record}")
    value, upper, lower = measurement
    if value <= 0 or upper is None or upper != lower or upper < 0:
        raise ValueError(f"Expected a positive measurement with symmetric errors: {record}")
    return value, upper


def pole_comparison(w_mass, z_mass, w_width, z_width):
    """Return S, independent error and the sharp first-order correlation envelope."""
    mw, dmw = w_mass
    mz, dmz = z_mass
    gw, dgw = w_width
    gz, dgz = z_width
    tw = gw**2 / (mw**2 + gw**2)
    tz = gz**2 / (mz**2 + gz**2)
    ratio_sq = ((mw / mz) * hypot(1, gz / mz) / hypot(1, gw / mw))**2
    contributions = (
        2 * ratio_sq * (1 + tw) * dmw / mw,
        2 * ratio_sq * (1 + tz) * dmz / mz,
        2 * ratio_sq * gw * dgw / (mw**2 + gw**2),
        2 * ratio_sq * gz * dgz / (mz**2 + gz**2),
    )
    largest = sum(contributions)
    smallest = max(0.0, 2 * max(contributions) - largest)
    return 1 - ratio_sq, hypot(*contributions), smallest, largest


def main():
    def positive_branch(j):
        return (sqrt(j*j + 4*j) - j) / 2

    reference = 1 - positive_branch(0.75) / positive_branch(2)
    print("edition  pole angle   independent   minimum     maximum     residual/error range")
    for year in (2025, 2026):
        records = yaml.safe_load((DATA / str(year) / "summary.yaml").read_text())["quantities"]
        inputs = [display_measurement(records[key])
                  for key in ("W_mass", "Z_mass", "W_width", "Z_width")]
        value, independent, smallest, largest = pole_comparison(*inputs)
        residual = abs(value - reference)
        high_pull = f"{residual / smallest:.2f}" if smallest else "unbounded"
        print(f"{year}     {value:.8f}   {independent:.8f}    "
              f"{smallest:.8f}  {largest:.8f}  {residual / largest:.2f}–{high_pull}")


if __name__ == "__main__":
    main()
