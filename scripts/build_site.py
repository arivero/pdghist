#!/usr/bin/env python3
"""Consolidate the per-edition YAML files into docs/data.json for the website.

For every tracked quantity it builds a time series from two independent PDG
sources, so the site can cross-check them visually:
  * pdg_database  - PDG headline value per edition (data/<year>/summary.yaml)
  * mass_width    - value from that year's mass_width file (data/<year>/masses.yaml)

It also attaches covariance-aware history diagnostics (issue #3): for listed
histories every adjacent pair of editions is classified as known-covariance,
certified nested average, or unknown covariance (data/history_covariance.yaml),
and the derived weak-angle series carry their W/Z covariance model.
"""
import glob
import json
import math
import os
import time
from collections import Counter

import yaml

from extract_db import parse_value_text

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


# ----- covariance-aware history diagnostics (issue #3) ----------------------
#
# Nested-average theorem. Independent X_j ~ N(theta, s_j^2), weights
# w_j = s_j^-2, release average over a nested input set I_t with variance
# v_t = 1/sum w_j. For I_t subset of I_u, Cov(theta_t, theta_u) = v_u, so the
# innovation (theta_u - theta_t)/sqrt(v_t - v_u) is N(0,1) and innovations of
# one nested chain are independent.

COVARIANCE_FILE = os.path.join(DATA, "history_covariance.yaml")
AVERAGING_METHODS = ("single_input", "inverse_variance_independent")
MODEL_TEXT = {
    "known": "declared covariance: Var(Δ) = v₁ + v₂ − 2c",
    "nested": "certified nested inverse-variance average: Var(Δ) = v₁ − v₂",
    "identical": "same declared inputs in both editions: no innovation",
    "unknown": "covariance unknown: Var(Δ) ∈ [(σ₁−σ₂)², (σ₁+σ₂)²]",
}


def load_covariance_config(path=COVARIANCE_FILE):
    if not os.path.exists(path):
        return {}
    return load_yaml(path) or {}


def measurement_error(rec):
    if rec.get("error") is not None:
        return float(rec["error"])
    return math.hypot(float(rec.get("stat", 0.0)), float(rec.get("syst", 0.0)))


def inverse_variance_average(records):
    """Return (mean, variance) of independent Gaussian inputs."""
    weights = [measurement_error(r) ** -2 for r in records]
    total = sum(weights)
    mean = sum(w * float(r["value"]) for w, r in zip(weights, records)) / total
    return mean, 1.0 / total


def innovation_known(delta, v_t, v_u, c):
    var = v_t + v_u - 2.0 * c
    if var <= 0:
        raise ValueError("declared covariance gives a non-positive variance")
    return math.sqrt(var), delta / math.sqrt(var)


def innovation_nested(delta, v_t, v_u):
    """Exact N(0,1) innovation for a certified nested pair (v_t > v_u)."""
    if not v_t > v_u:
        raise ValueError("nested innovation needs a strict variance decrease")
    sigma = math.sqrt(v_t - v_u)
    return sigma, delta / sigma


def innovation_envelope(delta, s_t, s_u):
    """Range of sd(Δ) and |Δ|/sd(Δ) over all correlations in [-1, 1]."""
    lo, hi = abs(s_t - s_u), s_t + s_u
    z_lo = abs(delta) / hi if hi > 0 else (0.0 if delta == 0 else math.inf)
    if delta == 0:
        z_hi = 0.0
    else:
        z_hi = abs(delta) / lo if lo > 0 else math.inf
    return (lo, hi), (z_lo, z_hi)


def chi2_sf(x, k):
    """Survival function of the chi-square distribution (regularized Q)."""
    a, x = k / 2.0, x / 2.0
    if x <= 0:
        return 1.0
    if x < a + 1:  # series for P
        term = total = 1.0 / a
        n = a
        for _ in range(500):
            n += 1
            term *= x / n
            total += term
            if abs(term) < abs(total) * 1e-15:
                break
        return 1.0 - total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b = x + 1 - a  # continued fraction for Q
    c, d = 1e300, 1.0 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        h *= d * c
        if abs(d * c - 1) < 1e-15:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def _decimals(x):
    s = repr(float(x))
    if "e" in s:
        mant, exp = s.split("e")
        dec = len(mant.split(".")[1]) if "." in mant else 0
        return max(0, dec - int(exp))
    return len(s.split(".")[1].rstrip("0")) if "." in s else 0


def edition_value(p):
    """(value, sigma, note) for one history point; the display text wins when
    the numeric column disagrees with it beyond display rounding."""
    v, ep, en = p.get("value"), p.get("error_positive"), p.get("error_negative")
    sigma = max(ep or 0.0, en or 0.0)
    shown = parse_value_text(p.get("value_text")) if p.get("value_text") else None
    if shown and shown[1] is not None:
        dv, dep, den = shown
        dsig = max(dep or 0.0, den or 0.0)
        half = 0.5 * 10 ** -max(_decimals(dv), _decimals(dsig))
        if v is None or abs(v - dv) > half * 1.0001 or abs(sigma - dsig) > half * 1.0001:
            return dv, dsig, "display text (numeric column disagrees)"
    return v, sigma, "numeric column"


def classify_pair(t, u, pt, pu, hist, measurements):
    th_t, s_t, src_t = edition_value(pt)
    th_u, s_u, src_u = edition_value(pu)
    delta = th_u - th_t
    out = {"from": t, "to": u, "delta": delta, "sigma_from": s_t,
           "sigma_to": s_u, "value_source": src_u if src_u == src_t
           else f"{t}: {src_t}; {u}: {src_u}"}
    eds = hist.get("editions", {}) or {}
    et, eu = eds.get(t), eds.get(u)
    key = f"{t}-{u}"
    note = (hist.get("pair_notes", {}) or {}).get(key)
    known = (hist.get("pair_covariance", {}) or {}).get(key)
    reason = None
    if known is not None:
        sigma, z = innovation_known(delta, s_t ** 2, s_u ** 2, float(known["c"]))
        out.update(mode="known", sigma=sigma, z=z,
                   covariance_source=known.get("source", "declared"))
    elif et and eu:
        it, iu = set(et["inputs"]), set(eu["inputs"])
        tol = max(1e-9, 1e-9 * abs(th_u))
        if "display" in out["value_source"]:
            tol = 0.5 * 10 ** -_decimals(th_u)
        if it == iu:
            if abs(delta) <= tol and abs(s_t - s_u) <= tol:
                out.update(mode="identical", sigma=0.0, z=None,
                           covariance_source=f"declared inputs {sorted(iu)}")
            else:
                reason = "same declared inputs but a changed value: model change"
        elif (it < iu and et.get("method") in AVERAGING_METHODS
              and eu.get("method") in AVERAGING_METHODS):
            mt, vt = inverse_variance_average([measurements[k] for k in sorted(it)])
            mu, vu = inverse_variance_average([measurements[k] for k in sorted(iu)])
            ok = (abs(mt - th_t) <= tol and abs(mu - th_u) <= tol
                  and abs(math.sqrt(vt) - s_t) <= max(tol, 1e-12)
                  and abs(math.sqrt(vu) - s_u) <= max(tol, 1e-12))
            if ok:
                sigma, z = innovation_nested(mu - mt, vt, vu)
                added = sorted(iu - it)
                out.update(mode="nested", sigma=sigma, z=z,
                           covariance_source="nested inputs " + ", ".join(sorted(it))
                           + " + " + ", ".join(added) + "; " + eu.get("evidence", ""),
                           added_inputs=added, inputs=sorted(iu))
            else:
                reason = "declared nested inputs do not reproduce the published values"
        else:
            reason = note or "declared inputs are not nested inverse-variance averages"
    else:
        reason = note or hist.get("default_note") or "no provenance record for this pair"
    if "mode" not in out:
        (lo, hi), (zlo, zhi) = innovation_envelope(delta, s_t, s_u)
        flags = []
        if s_u > s_t:
            flags.append("variance increased: outside the nested theorem")
        elif s_u == s_t and delta != 0:
            flags.append("changed mean with unchanged variance: model change")
        out.update(mode="unknown", sigma_range=[lo, hi],
                   z_range=[zlo, zhi if math.isfinite(zhi) else None],
                   covariance_source=reason, flags=flags)
    out["model"] = MODEL_TEXT[out["mode"]]
    return out


def history_diagnostics(points, hist, measurements):
    """Classify every adjacent pair and combine innovations of nested chains."""
    pts = sorted((p for p in points if p.get("value") is not None
                  and not p.get("limit_type")), key=lambda p: p["year"])
    pairs = [classify_pair(a["year"], b["year"], a, b, hist, measurements)
             for a, b in zip(pts, pts[1:])]
    chains, run = [], []
    for pr in pairs + [None]:
        if pr is not None and pr["mode"] in ("nested", "identical"):
            run.append(pr)
            continue
        zs = [q["z"] for q in run if q["mode"] == "nested"]
        if zs:
            x = sum(z * z for z in zs)
            chains.append({"from": run[0]["from"], "to": run[-1]["to"],
                           "chi2": x, "dof": len(zs), "p_value": chi2_sf(x, len(zs)),
                           "justification": "innovations of one nested input chain "
                           "with fixed weights are independent N(0,1)"})
        run = []
    return {"estimand": hist.get("estimand"), "pairs": pairs, "chains": chains,
            "model_note": "Δ uses one value per edition; repeated formats of one "
                          "PDG average are not separate observations."}


def rho_interval_from_review(mw, ew, mz, ez, s_err, steps=20001):
    """Correlations rho in [-1, 1] compatible with a printed s2_W uncertainty.

    Each printed number is widened by half a unit in its last digit (value and
    uncertainty printed to the same decimal place)."""
    r2 = (mw / mz) ** 2
    hw = 0.5 * 10 ** -max(_decimals(mw), _decimals(ew))
    hz = 0.5 * 10 ** -max(_decimals(mz), _decimals(ez))
    hs = 0.5 * 10 ** -_decimals(s_err)
    a_lo, a_hi = 2 * r2 * (ew - hw) / mw, 2 * r2 * (ew + hw) / mw
    b_lo, b_hi = 2 * r2 * (ez - hz) / mz, 2 * r2 * (ez + hz) / mz
    s_lo, s_hi = (s_err - hs) ** 2, (s_err + hs) ** 2

    def g_range(rho):
        def g(a, b):
            return a * a + b * b - 2 * rho * a * b
        cand = [g(a, b) for a in (a_lo, a_hi) for b in (b_lo, b_hi)]
        for a in (a_lo, a_hi):  # edge minima of the convex quadratic
            b = rho * a
            if b_lo <= b <= b_hi:
                cand.append(g(a, b))
        for b in (b_lo, b_hi):
            a = rho * b
            if a_lo <= a <= a_hi:
                cand.append(g(a, b))
        return min(cand), max(cand)

    ok = []
    for i in range(steps):
        rho = -1.0 + 2.0 * i / (steps - 1)
        lo, hi = g_range(rho)
        if hi >= s_lo and lo <= s_hi:
            ok.append(rho)
    if not ok:
        return None
    return [round(ok[0], 4), round(ok[-1], 4)]


def swsq_with_covariance(mw, ew, mz, ez, cov=None, rho_interval=(-1.0, 1.0),
                         rho_declared=0.0):
    """q = 1 - (M_W/M_Z)^2 with first-order error
    sigma_q^2 = 4 r^4 [ew^2/mw^2 + ez^2/mz^2 - 2 cov/(mw mz)]."""
    r2 = (mw / mz) ** 2
    a, b = 2 * r2 * ew / mw, 2 * r2 * ez / mz

    def sig(rho):
        return math.sqrt(max(0.0, a * a + b * b - 2 * rho * a * b))
    if cov is not None:
        var = 4 * r2 * r2 * ((ew / mw) ** 2 + (ez / mz) ** 2 - 2 * cov / (mw * mz))
        sigma = math.sqrt(max(0.0, var))
    else:
        sigma = sig(rho_declared)
    lo, hi = rho_interval
    return 1.0 - r2, sigma, [sig(hi), sig(lo)]


def build(cov_config=None):
    """Assemble the site payload; cov_config defaults to the YAML file."""
    if cov_config is None:
        cov_config = load_covariance_config()
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
        # whose pdgall SQLite has not yet been released (e.g. a preview year).
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
                by_year[y] = (p["value"], max(ep, en), sk)
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
            by_year[p["year"]] = (p["value"], max(ep, en), "ew_fit")
        return by_year

    review_s2w_err = {p["year"]: p.get("error_positive") for p in sw_series}
    within = cov_config.get("within_edition", {}) or {}

    def display_disagreement(qkey, year):
        """Flag when the mass_width file and the database display text of one
        edition differ beyond display rounding (one average, two formats)."""
        q = next((q for q in quantities if q["key"] == qkey), None)
        db = next((p for p in q["series"].get("pdg_database", [])
                   if p["year"] == year), None) if q else None
        mwf = next((p for p in q["series"].get("mass_width_file", [])
                    if p["year"] == year), None) if q else None
        if not db or not mwf or not db.get("value_text"):
            return None
        shown = parse_value_text(db["value_text"])
        if not shown:
            return None
        # the coarser of the two printed precisions sets the rounding allowance
        half = 0.5 * 10 ** -min(_decimals(shown[0]), _decimals(mwf["value"]))
        if abs(shown[0] - mwf["value"]) > half * 1.0001:
            return (f"{qkey} {year}: mass_width file {mwf['value']} vs database "
                    f"display {db['value_text'].strip()}")
        return None

    def derived_swsq(mw_by, mz_by, kind):
        cfg = within.get(kind, {}) or {}
        out = []
        for y in sorted(set(mw_by) & set(mz_by)):
            mw, ew, sw = mw_by[y]
            mz, ez, sz = mz_by[y]
            if mw <= 0 or mz <= 0:
                continue
            cov = (cfg.get("covariance_by_year", {}) or {}).get(y)
            rho_int, rho_src = [-1.0, 1.0], "all correlations in [-1, 1]"
            if cov is None and cfg.get("rho_from_review") and review_s2w_err.get(y):
                r = rho_interval_from_review(mw, ew, mz, ez, review_s2w_err[y])
                if r:
                    rho_int = r
                    rho_src = ("correlations compatible with the review's printed "
                               f"s2_W uncertainty ±{review_s2w_err[y]} (rounding-widened)")
            rho_decl = float(cfg.get("rho_declared", 0.0))
            rho_used = min(max(rho_decl, rho_int[0]), rho_int[1])
            value, sigma, env = swsq_with_covariance(
                mw, ew, mz, ez, cov=cov, rho_interval=rho_int,
                rho_declared=rho_used)
            notes = [n for n in (display_disagreement("W_mass", y),
                                 display_disagreement("Z_mass", y))
                     if n and kind == "derived_direct"]
            out.append({
                "year": y,
                "value": value,
                "error_positive": sigma,
                "error_negative": sigma,
                "unit": "",
                "covariance_mode": "known" if cov is not None else "unknown",
                "uncertainty_model": (
                    "first-order propagation with the declared W–Z covariance"
                    if cov is not None else
                    f"first-order propagation, plotted with ρ = {rho_used:.3g}"
                    + ("" if rho_used == rho_decl else
                       f" (declared ρ = {rho_decl:g} lies outside the compatible interval)")
                    + f"; envelope over {rho_src}"),
                "rho_interval": rho_int if cov is None else None,
                "error_envelope": env,
                "inputs": {"W": sw, "Z": sz},
                "provenance_notes": notes,
            })
        return out

    dd = derived_swsq(headline_mass("W_mass"), headline_mass("Z_mass"),
                      "derived_direct")
    df = derived_swsq(fit_mass("W_mass"), fit_mass("Z_mass"), "derived_fit")

    measurements = cov_config.get("measurements", {}) or {}
    for hkey, hist in (cov_config.get("histories", {}) or {}).items():
        qkey = hist.get("quantity", hkey)
        q = next((q for q in quantities if q["key"] == qkey), None)
        if not q:
            continue
        sk = hist.get("series", "pdg_database")
        pts = q["series"].get(sk, [])
        if len(pts) < 2:
            continue
        q.setdefault("history_diagnostics", {})[sk] = history_diagnostics(
            pts, hist, measurements)

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
            "history_covariance": "data/history_covariance.yaml (edition "
                                  "inputs, covariance modes, W-Z covariance)",
        },
        "covariance_models": MODEL_TEXT,
        "categories": sorted({q["category"] for q in quantities}),
        "quantities": quantities,
    }
    return out


def main():
    out = build()
    with open(os.path.join(DOCS, "data.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    quantities = out["quantities"]
    npts = sum(len(s) for q in quantities for s in q["series"].values())
    print(f"docs/data.json: {len(quantities)} quantities, {npts} points")
    for q in quantities:
        for sk, diag in q.get("history_diagnostics", {}).items():
            modes = Counter(p["mode"] for p in diag["pairs"])
            chains = "; ".join(f"chi2_{c['dof']}={c['chi2']:.3f} (p={c['p_value']:.3f}, "
                               f"{c['from']}-{c['to']})" for c in diag["chains"])
            print(f"  {q['key']}/{sk}: {dict(modes)}" + (f"; {chains}" if chains else ""))


if __name__ == "__main__":
    main()
