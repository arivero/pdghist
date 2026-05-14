#!/usr/bin/env python3
"""Consolidate the per-edition YAML files into docs/data.json for the website.

For every tracked quantity it builds a time series from two independent PDG
sources, so the site can cross-check them visually:
  * pdg_database  - PDG headline value per edition (data/<year>/summary.yaml)
  * mass_width    - value from that year's mass_width file (data/<year>/masses.yaml)
"""
import glob
import json
import os
import time
from collections import Counter

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")

# quantity key -> PDG Monte Carlo id + which mass_width field to read
MASS_WIDTH_MAP = {
    "d_quark_mass": (1, "mass"), "u_quark_mass": (2, "mass"),
    "s_quark_mass": (3, "mass"), "c_quark_mass": (4, "mass"),
    "b_quark_mass": (5, "mass"), "t_quark_mass": (6, "mass"),
    "electron_mass": (11, "mass"), "muon_mass": (13, "mass"),
    "tau_mass": (15, "mass"),
    "W_mass": (24, "mass"), "Z_mass": (23, "mass"), "H_mass": (25, "mass"),
    "W_width": (24, "width"), "Z_width": (23, "width"),
    "H_width": (25, "width"),
}

UNIT_TO_GEV = {"GeV": 1.0, "MeV": 1e-3, "keV": 1e-6, "eV": 1e-9}


def load_yaml(path):
    with open(path) as fh:
        return yaml.safe_load(fh)


def normalise_units(points):
    """Convert every point (across all series of one quantity) to a single
    common energy unit, so the two series share a y-axis."""
    units = [p["unit"] for p in points if p.get("unit") in UNIT_TO_GEV]
    if not units:
        return points[0].get("unit", "") if points else ""
    target = Counter(units).most_common(1)[0][0]
    factor_target = UNIT_TO_GEV[target]
    for p in points:
        u = p.get("unit")
        if u in UNIT_TO_GEV and u != target:
            scale = UNIT_TO_GEV[u] / factor_target
            for f in ("value", "error_positive", "error_negative"):
                if p.get(f) is not None:
                    p[f] = p[f] * scale
            p["unit"] = target
    return target


def main():
    catalogue = load_yaml(os.path.join(DATA, "quantities.yaml"))
    years = sorted(d for d in os.listdir(DATA)
                   if d.isdigit() and os.path.isdir(os.path.join(DATA, d)))

    summaries, masswidth = {}, {}
    for y in years:
        sp = os.path.join(DATA, y, "summary.yaml")
        mp = os.path.join(DATA, y, "masses.yaml")
        if os.path.exists(sp):
            summaries[int(y)] = load_yaml(sp)
        if os.path.exists(mp):
            doc = load_yaml(mp)
            by_id = {}
            for p in doc.get("particles", []):
                for mid in p.get("mc_ids", []):
                    by_id.setdefault(mid, p)
            masswidth[int(y)] = by_id

    quantities = []
    for q in catalogue["quantities"]:
        key = q["key"]

        db_series = []
        for year, doc in sorted(summaries.items()):
            e = doc.get("quantities", {}).get(key)
            if not e:
                continue
            db_series.append({
                "year": year,
                "value": e.get("value"),
                "error_positive": e.get("error_positive"),
                "error_negative": e.get("error_negative"),
                "unit": e.get("unit", ""),
                "value_text": e.get("value_text"),
                "value_type": e.get("value_type"),
                "limit_type": e.get("limit_type"),
            })

        mw_series = []
        if key in MASS_WIDTH_MAP:
            mcid, field = MASS_WIDTH_MAP[key]
            for year, by_id in sorted(masswidth.items()):
                p = by_id.get(mcid)
                if not p or field not in p:
                    continue
                fv = p[field]
                if fv.get("value") is None:
                    continue
                mw_series.append({
                    "year": year,
                    "value": fv.get("value"),
                    "error_positive": fv.get("error_pos"),
                    "error_negative": abs(fv["error_neg"])
                    if fv.get("error_neg") is not None else None,
                    "unit": "GeV",
                })

        unit = normalise_units(db_series + mw_series)

        quantities.append({
            "key": key,
            "name": q["name"],
            "symbol": q["symbol"],
            "category": q["category"],
            "pdgid": q["pdgid"],
            "unit": unit,
            "series": {
                "pdg_database": db_series,
                "mass_width_file": mw_series,
            },
        })

    os.makedirs(DOCS, exist_ok=True)
    out = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "about": "History of PDG values for fundamental Standard Model "
                 "parameters. x = PDG edition year, y = value with errors.",
        "sources": {
            "pdg_database": "PDG pdgall SQLite database (all editions)",
            "mass_width_file": "PDG yearly mass_width machine-readable files",
        },
        "categories": sorted({q["category"] for q in quantities}),
        "quantities": quantities,
    }
    with open(os.path.join(DOCS, "data.json"), "w") as fh:
        json.dump(out, fh, indent=1)

    npts = sum(len(q["series"]["pdg_database"]) +
               len(q["series"]["mass_width_file"]) for q in quantities)
    print(f"docs/data.json: {len(quantities)} quantities, {npts} points")


if __name__ == "__main__":
    main()
