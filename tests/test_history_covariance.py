"""Checks for the covariance-aware history diagnostics (issue #3).

Run with:  python3 -m pytest -q tests
"""
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import build_site as bs  # noqa: E402


def pt(year, value, err, text=None):
    return {"year": year, "value": value, "error_positive": err,
            "error_negative": err, "value_text": text}


def test_two_measurement_example():
    # first release 10 +- 1; adding an independent 12 +- 1 gives 11 +- 1/sqrt(2)
    meas = {"a": {"value": 10.0, "error": 1.0}, "b": {"value": 12.0, "error": 1.0}}
    mean, var = bs.inverse_variance_average([meas["a"], meas["b"]])
    assert mean == pytest.approx(11.0) and var == pytest.approx(0.5)
    sigma, z = bs.innovation_nested(1.0, 1.0, 0.5)
    assert z == pytest.approx(math.sqrt(2))
    # treating the releases as independent gives sqrt(2/3)
    assert 1.0 / math.sqrt(1.0 + 0.5) == pytest.approx(math.sqrt(2 / 3))
    hist = {"editions": {1: {"inputs": ["a"], "method": "single_input"},
                         2: {"inputs": ["a", "b"], "method": "inverse_variance_independent"}}}
    out = bs.classify_pair(1, 2, pt(1, 10.0, 1.0), pt(2, 11.0, math.sqrt(0.5)), hist, meas)
    assert out["mode"] == "nested" and out["z"] == pytest.approx(math.sqrt(2))


def test_three_nested_releases_have_zero_cross_innovation_covariance():
    sig = [1.0, 1.0, 2.0]
    w = [s ** -2 for s in sig]
    # weight vectors of the three release averages on the inputs
    rel = []
    for k in (1, 2, 3):
        tot = sum(w[:k])
        rel.append([w[j] / tot if j < k else 0.0 for j in range(3)])

    def cov(x, y):
        return sum(x[j] * y[j] * sig[j] ** 2 for j in range(3))
    d1 = [rel[1][j] - rel[0][j] for j in range(3)]
    d2 = [rel[2][j] - rel[1][j] for j in range(3)]
    assert cov(d1, d2) == pytest.approx(0.0, abs=1e-15)
    v = [1 / sum(w[:k]) for k in (1, 2, 3)]
    assert cov(d1, d1) == pytest.approx(v[0] - v[1])
    assert cov(d2, d2) == pytest.approx(v[1] - v[2])
    # the history diagnostic combines the two innovations into one chi2 chain
    meas = {"a": {"value": 10.0, "error": 1.0}, "b": {"value": 12.0, "error": 1.0},
            "c": {"value": 8.0, "error": 2.0}}
    hist = {"editions": {
        1: {"inputs": ["a"], "method": "single_input"},
        2: {"inputs": ["a", "b"], "method": "inverse_variance_independent"},
        3: {"inputs": ["a", "b", "c"], "method": "inverse_variance_independent"}}}
    m2, v2 = bs.inverse_variance_average([meas["a"], meas["b"]])
    m3, v3 = bs.inverse_variance_average(list(meas.values()))
    diag = bs.history_diagnostics(
        [pt(1, 10.0, 1.0), pt(2, m2, math.sqrt(v2)), pt(3, m3, math.sqrt(v3))], hist, meas)
    z = [p["z"] for p in diag["pairs"]]
    (chain,) = diag["chains"]
    assert chain["dof"] == 2 and chain["chi2"] == pytest.approx(z[0] ** 2 + z[1] ** 2)
    assert chain["p_value"] == pytest.approx(math.exp(-chain["chi2"] / 2))


def test_identical_release_and_unchanged_variance():
    meas = {"a": {"value": 10.0, "error": 1.0}}
    hist = {"editions": {1: {"inputs": ["a"], "method": "single_input"},
                         2: {"inputs": ["a"], "method": "single_input"}}}
    same = bs.classify_pair(1, 2, pt(1, 10.0, 1.0), pt(2, 10.0, 1.0), hist, meas)
    assert same["mode"] == "identical" and same["z"] is None
    moved = bs.classify_pair(1, 2, pt(1, 10.0, 1.0), pt(2, 10.5, 1.0), {}, meas)
    assert moved["mode"] == "unknown"
    assert any("unchanged variance" in f for f in moved["flags"])
    assert moved["z_range"] == [pytest.approx(0.25), None]  # sd(Δ) in [0, 2]
    grown = bs.classify_pair(1, 2, pt(1, 10.0, 1.0), pt(2, 10.5, 2.0), {}, meas)
    assert any("variance increased" in f for f in grown["flags"])
    assert grown["sigma_range"] == [pytest.approx(1.0), pytest.approx(3.0)]
    assert bs.history_diagnostics([pt(1, 10.0, 1.0), pt(2, 10.0, 1.0)], hist, meas)["chains"] == []


def test_known_covariance_mode():
    sigma, z = bs.innovation_known(0.3, 0.04, 0.01, 0.01)
    assert sigma == pytest.approx(math.sqrt(0.03)) and z == pytest.approx(0.3 / math.sqrt(0.03))


def test_common_scale_cancels_from_weak_angle():
    mw, mz, k = 80.36, 91.1876, 1e-4
    ew, ez = k * mw, k * mz
    q, sigma, env = bs.swsq_with_covariance(mw, ew, mz, ez, cov=k * k * mw * mz)
    assert q == pytest.approx(1 - (mw / mz) ** 2)
    assert sigma == pytest.approx(0.0, abs=1e-12)
    # independent inputs reproduce the previous builder formula
    _, s0, (lo, hi) = bs.swsq_with_covariance(mw, 0.012, mz, 0.0021)
    r = mw / mz
    assert s0 == pytest.approx(2 * r * r * math.hypot(0.012 / mw, 0.0021 / mz))
    a, b = 2 * r * r * 0.012 / mw, 2 * r * r * 0.0021 / mz
    assert (lo, hi) == (pytest.approx(abs(a - b)), pytest.approx(a + b))


def test_chi2_survival():
    assert bs.chi2_sf(0.0, 3) == 1.0
    assert bs.chi2_sf(2.0, 2) == pytest.approx(math.exp(-1.0))
    assert bs.chi2_sf(3.841458820694124, 1) == pytest.approx(0.05, rel=1e-9)
    # reference values from scipy.stats.chi2.sf
    assert bs.chi2_sf(30.0, 5) == pytest.approx(1.4748581038443073e-05, rel=1e-12)
    assert bs.chi2_sf(7.3, 3) == pytest.approx(0.06292623645904312, rel=1e-12)


def test_real_z_mass_chain_from_the_listings():
    out = bs.build()
    q = next(q for q in out["quantities"] if q["key"] == "Z_mass")
    diag = q["history_diagnostics"]["pdg_database"]
    by = {(p["from"], p["to"]): p for p in diag["pairs"]}
    assert by[(2022, 2023)]["mode"] == "identical"
    assert by[(2023, 2024)]["mode"] == "nested"
    assert by[(2023, 2024)]["z"] == pytest.approx((91.1923 - 91.1876) / math.hypot(0.0021, 0.0071))
    assert by[(2024, 2025)]["mode"] == "identical"
    assert by[(2025, 2026)]["mode"] == "nested"
    assert by[(2025, 2026)]["z"] == pytest.approx(-0.2426315, abs=1e-6)
    (chain,) = diag["chains"]
    assert chain["dof"] == 2 and chain["p_value"] == pytest.approx(0.7938, abs=1e-4)
    w = next(q for q in out["quantities"] if q["key"] == "W_mass")
    wby = {(p["from"], p["to"]): p for p in w["history_diagnostics"]["pdg_database"]["pairs"]}
    assert wby[(2023, 2024)]["mode"] == "unknown"
    assert wby[(2025, 2026)]["z_range"][0] == pytest.approx(0.0067 / 0.021)


def test_plots_survive_without_any_covariance_record():
    full = bs.build()
    bare = bs.build(cov_config={})
    for qf, qb in zip(full["quantities"], bare["quantities"]):
        assert qf["key"] == qb["key"]
        for sk, pts in qb["series"].items():
            assert [(p["year"], p["value"]) for p in pts] == \
                   [(p["year"], p["value"]) for p in qf["series"][sk]]
        assert "history_diagnostics" not in qb
    sw = next(q for q in bare["quantities"] if q["key"] == "sin2_theta_W")
    assert all(p["covariance_mode"] == "unknown" and p["rho_interval"] == [-1.0, 1.0]
               for p in sw["series"]["derived_direct"] + sw["series"]["derived_fit"])


@pytest.mark.parametrize("flag", [[], ["--strip-diagnostics"]])
def test_site_renders_with_and_without_diagnostics(flag):
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("node not installed")
    here = os.path.dirname(os.path.abspath(__file__))
    res = subprocess.run([node, os.path.join(here, "site_smoke.js"), *flag],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    assert "cards=" in res.stdout
