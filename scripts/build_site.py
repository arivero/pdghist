#!/usr/bin/env python3
"""Consolidate the per-edition YAML files into docs/data.json for the website.

For every tracked quantity it builds a time series from two independent PDG
sources, so the site can cross-check them visually:
  * pdg_database  - PDG headline value per edition (data/<year>/summary.yaml)
  * mass_width    - value from that year's mass_width file (data/<year>/masses.yaml)
"""
import glob
import json
import math
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

    summaries, masswidth, electroweak = {}, {}, {}
    for y in years:
        sp = os.path.join(DATA, y, "summary.yaml")
        mp = os.path.join(DATA, y, "masses.yaml")
        ep = os.path.join(DATA, y, "electroweak.yaml")
        if os.path.exists(sp):
            summaries[int(y)] = load_yaml(sp)
        if os.path.exists(mp):
            doc = load_yaml(mp)
            by_id = {}
            for p in doc.get("particles", []):
                for mid in p.get("mc_ids", []):
                    by_id.setdefault(mid, p)
            masswidth[int(y)] = by_id
        if os.path.exists(ep):
            electroweak[int(y)] = load_yaml(ep)

    def review_series(qkey):
        """Time series scraped from the Electroweak review PDFs."""
        out = []
        for year, doc in sorted(electroweak.items()):
            e = doc.get("quantities", {}).get(qkey)
            if not e:
                continue
            out.append({
                "year": year,
                "value": e.get("value"),
                "error_positive": e.get("error_positive"),
                "error_negative": e.get("error_negative"),
                "unit": e.get("unit", ""),
                "scheme": e.get("scheme"),
            })
        return out

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

        series = {
            "pdg_database": db_series,
            "mass_width_file": mw_series,
        }
        # the effective weak mixing angle has a long history in the
        # Electroweak review even though the database only carries one edition
        if key == "sin2_theta_eff":
            series["review_pdf"] = review_series("sin2_theta_eff")
        # for W and Z masses the review carries the world average too -
        # useful as a third cross-check and the only source for editions
        # whose pdgall SQLite has not yet been released (e.g. 2026 preview).
        if key in ("W_mass", "Z_mass"):
            rs = review_series(key)
            if rs:
                series["review_pdf"] = rs
            # the EW fit's SM-constrained value: ~2x more precise than direct
            # for W (5-15 MeV vs 13-40 MeV), about the same for Z
            fs = review_series(key + "_ew_fit")
            if fs:
                series["ew_fit"] = fs

        quantities.append({
            "key": key,
            "name": q["name"],
            "symbol": q["symbol"],
            "category": q["category"],
            "pdgid": q["pdgid"],
            "unit": unit,
            "series": series,
        })

    # on-shell sin^2(theta_W) is not in the database at all - it comes only
    # from the Electroweak review PDFs (see scripts/scrape_reviews.py).
    # We also compute it directly: 1 - (m_W/m_Z)^2 from the headline masses
    # and from the EW fit values. The three series give different stories:
    #   * review_pdf     - the schemes-table value the review prints
    #   * derived_direct - 1 - (m_W/m_Z)^2 from the experimental world averages
    #   * derived_fit    - 1 - (m_W/m_Z)^2 from the EW review's fit table
    sw_series = review_series("sin2_theta_W")

    def headline_mass(qkey):
        q = next((q for q in quantities if q["key"] == qkey), None)
        if not q:
            return {}
        by_year = {}
        # mass_width is machine-generated from the database headline and
        # tracks value_text more faithfully than the SQLite numeric column
        for sk in ("mass_width_file", "pdg_database", "review_pdf"):
            for p in q["series"].get(sk, []):
                y = p["year"]
                if y in by_year or p.get("value") is None:
                    continue
                ep = p.get("error_positive") or 0
                en = p.get("error_negative") or 0
                by_year[y] = (p["value"], max(ep, en))
        return by_year

    def fit_mass(qkey):
        q = next((q for q in quantities if q["key"] == qkey), None)
        if not q:
            return {}
        by_year = {}
        for p in q["series"].get("ew_fit", []):
            if p.get("value") is None:
                continue
            ep = p.get("error_positive") or 0
            en = p.get("error_negative") or 0
            by_year[p["year"]] = (p["value"], max(ep, en))
        return by_year

    def derived_swsq(mw_by, mz_by):
        out = []
        for y in sorted(set(mw_by) & set(mz_by)):
            mw, ew = mw_by[y]
            mz, ez = mz_by[y]
            if mw <= 0 or mz <= 0:
                continue
            r = mw / mz
            sr = r * math.sqrt((ew / mw) ** 2 + (ez / mz) ** 2)
            r2 = r * r
            sr2 = 2 * r * sr
            out.append({
                "year": y,
                "value": 1.0 - r2,
                "error_positive": sr2,
                "error_negative": sr2,
                "unit": "",
            })
        return out

    dd = derived_swsq(headline_mass("W_mass"), headline_mass("Z_mass"))
    df = derived_swsq(fit_mass("W_mass"), fit_mass("Z_mass"))

    if sw_series or dd or df:
        quantities.append({
            "key": "sin2_theta_W",
            "name": "Weak mixing angle (on-shell)",
            "symbol": "sin^2(theta_W)",
            "category": "electroweak mixing",
            "pdgid": "(review + derived)",
            "unit": "",
            "series": {
                "pdg_database": [],
                "mass_width_file": [],
                "review_pdf": sw_series,
                "derived_direct": dd,
                "derived_fit": df,
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
            "review_pdf": "PDG Electroweak review (values extracted from the "
                          "review text; see scripts/scrape_reviews.py)",
            "ew_fit": "SM-constrained best-fit value from the EW review's fit "
                      "table (2nd column); ~2x more precise than direct m_W",
        },
        "categories": sorted({q["category"] for q in quantities}),
        "quantities": quantities,
    }
    with open(os.path.join(DOCS, "data.json"), "w") as fh:
        json.dump(out, fh, indent=1)

    npts = sum(len(s) for q in quantities for s in q["series"].values())
    print(f"docs/data.json: {len(quantities)} quantities, {npts} points")


if __name__ == "__main__":
    main()
