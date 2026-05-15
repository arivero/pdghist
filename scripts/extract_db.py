#!/usr/bin/env python3
"""Extract the history of fundamental Standard Model parameters from the PDG
all-editions SQLite database into per-edition YAML files.

Input : data/_sqlite/pdgall-*.sqlite   (PDG "pdgall" database, all editions)
Output: data/<year>/summary.yaml       (one PDG edition per directory)
        data/quantities.yaml           (catalogue of tracked quantities)

The PDG database is binary and not committed; the YAML it produces is the
traceable, diff-able source kept in the repo. Re-run after dropping a new
pdgall-*.sqlite in place (see README).
"""
import glob
import os
import re
import sqlite3
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# key, PDG Identifier(s), display name, symbol, category
# The Identifier may be a list: PDG renamed the light-quark masses, so the
# history is split across the current id and a legacy id. Editions are merged,
# preferring the id listed first when both carry a value for the same edition.
QUANTITIES = [
    ("d_quark_mass",   ["Q001M", "Q123DM"], "Down quark mass",    "m_d", "quark mass"),
    ("u_quark_mass",   ["Q002M", "Q123UM"], "Up quark mass",      "m_u", "quark mass"),
    ("s_quark_mass",   ["Q003M", "Q123SM"], "Strange quark mass", "m_s", "quark mass"),
    ("c_quark_mass",   "Q004M",   "Charm quark mass",   "m_c",    "quark mass"),
    ("b_quark_mass",   "Q005M",   "Bottom quark mass",  "m_b",    "quark mass"),
    ("t_quark_mass",   "Q007TP",  "Top quark mass",     "m_t",    "quark mass"),
    ("electron_mass",  "S003M",   "Electron mass",      "m_e",    "lepton mass"),
    ("muon_mass",      "S004M",   "Muon mass",          "m_mu",   "lepton mass"),
    ("tau_mass",       "S035M",   "Tau mass",           "m_tau",  "lepton mass"),
    ("W_mass",         "S043M",   "W boson mass",       "m_W",    "boson mass"),
    ("Z_mass",         "S044M",   "Z boson mass",       "m_Z",    "boson mass"),
    ("H_mass",         "S126M",   "Higgs boson mass",   "m_H",    "boson mass"),
    ("W_width",        "S043W",   "W boson width",      "Gamma_W", "boson width"),
    ("Z_width",        "S044W",   "Z boson width",      "Gamma_Z", "boson width"),
    ("H_width",        "S126W",   "Higgs boson width",  "Gamma_H", "boson width"),
    ("sin2_theta_eff", "S044SEF", "Effective weak mixing angle",
     "sin^2(theta_eff)", "electroweak mixing"),
    ("sin2_theta_12",  "S067P12", "Neutrino mixing sin^2(theta_12)",
     "sin^2(theta_12)", "neutrino mixing"),
    ("sin2_theta_13",  "S067P13", "Neutrino mixing sin^2(theta_13)",
     "sin^2(theta_13)", "neutrino mixing"),
    ("sin2_theta_23",  "S067P23", "Neutrino mixing sin^2(theta_23)",
     "sin^2(theta_23)", "neutrino mixing"),
    ("dm2_21",         "S067DM3", "Neutrino mass-squared difference "
     "Delta(m^2_21)", "Delta(m^2_21)", "neutrino mass-squared difference"),
    ("dm2_32",         "S067DM1", "Neutrino mass-squared difference "
     "Delta(m^2_32)", "Delta(m^2_32)", "neutrino mass-squared difference"),
]

# preference order when one edition has several summary-table rows
VALUE_TYPE_RANK = {"V": 0, "FC": 1, "AC": 2, "DR": 3, "E": 4}


def parse_value_text(t):
    """Recover (value, err_pos, err_neg) when the numeric `value` column is
    NULL but a textual value is given, e.g. '1.27+0.07-0.09 (1.18 -- 1.34)'."""
    if not t:
        return None
    s = t.strip()
    expo = 0
    m = re.match(r"^\((.*)\)\s*[eE]\s*([+-]?\d+)\s*$", s)
    if m:
        s, expo = m.group(1).strip(), int(m.group(2))
    s = re.sub(r"\s*\([^()]*\)\s*$", "", s).strip()
    scale = 10.0 ** expo

    m = re.match(r"^([-\d.]+)\s+to\s+([-\d.]+)$", s)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        e = abs(b - a) / 2
        return (a + b) / 2 * scale, e * scale, e * scale
    m = re.match(r"^([+-]?[\d.]+)\s*\+-\s*([\d.]+)$", s)
    if m:
        v, e = float(m.group(1)), float(m.group(2))
        return v * scale, e * scale, e * scale
    m = re.match(r"^([+-]?[\d.]+)\s*\+\s*([\d.]+)\s*-\s*([\d.]+)$", s)
    if m:
        return (float(m.group(1)) * scale, float(m.group(2)) * scale,
                float(m.group(3)) * scale)
    m = re.match(r"^([+-]?[\d.]+)$", s)
    if m:
        return float(m.group(1)) * scale, None, None
    return None


def norm_unit(u):
    if not u:
        return ""
    return {"mev": "MeV", "gev": "GeV", "kev": "keV",
            "ev": "eV", "ev**2": "eV^2"}.get(u.strip().lower(), u.strip())


def find_db():
    cands = sorted(glob.glob(os.path.join(DATA, "_sqlite", "pdgall-*.sqlite")))
    if not cands:
        sys.exit("No pdgall-*.sqlite found in data/_sqlite/ (see README).")
    return cands[-1]


def main():
    db_path = find_db()
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    db_version = os.path.basename(db_path)

    # editions[year][key] = value dict
    editions = {}
    catalogue = []

    for key, pdgid, name, symbol, category in QUANTITIES:
        pdgids = [pdgid] if isinstance(pdgid, str) else list(pdgid)
        placeholders = ",".join("?" * len(pdgids))
        rows = con.execute(
            f"SELECT pdgid, edition, value_type, limit_type, value, value_text, "
            f"error_positive, error_negative, unit_text "
            f"FROM pdgdata WHERE pdgid IN ({placeholders}) "
            f"AND in_summary_table = 1 ORDER BY edition", pdgids).fetchall()

        # pick the best usable row per edition: prefer the id listed first,
        # then the value_type rank. Rows with no recoverable value are skipped.
        best = {}
        for r in rows:
            value = r["value"]
            err_p, err_n = r["error_positive"], r["error_negative"]
            if value is None:
                parsed = parse_value_text(r["value_text"])
                if parsed is None:
                    continue
                value, err_p, err_n = parsed
            sort_key = (pdgids.index(r["pdgid"]),
                        VALUE_TYPE_RANK.get(r["value_type"], 9))
            if r["edition"] in best and best[r["edition"]][0] <= sort_key:
                continue
            entry = {
                "value": value,
                "error_positive": err_p,
                "error_negative": err_n,
                "unit": norm_unit(r["unit_text"]),
                "value_text": r["value_text"],
                "value_type": r["value_type"],
            }
            if r["limit_type"]:
                entry["limit_type"] = r["limit_type"]
            best[r["edition"]] = (sort_key, entry)

        valid_years = []
        for ed, (_, entry) in best.items():
            valid_years.append(int(ed))
            editions.setdefault(ed, {})[key] = entry

        valid_years.sort()
        catalogue.append({
            "key": key, "pdgid": pdgids[0], "name": name, "symbol": symbol,
            "category": category,
            "editions": valid_years,
            "n_editions": len(valid_years),
        })

    # write one summary.yaml per edition
    for ed, quantities in sorted(editions.items()):
        ydir = os.path.join(DATA, str(ed))
        os.makedirs(ydir, exist_ok=True)
        doc = {
            "edition": int(ed),
            "source": "PDG Review of Particle Physics database",
            "source_file": db_version,
            "source_api": "https://pdgapi.lbl.gov/",
            "quantities": {k: quantities[k] for k in
                           (q[0] for q in QUANTITIES) if k in quantities},
        }
        with open(os.path.join(ydir, "summary.yaml"), "w") as fh:
            yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)

    # write the catalogue
    with open(os.path.join(DATA, "quantities.yaml"), "w") as fh:
        yaml.safe_dump({
            "description": "Fundamental Standard Model parameters tracked by "
                           "pdghist, with their PDG Identifiers.",
            "source_file": db_version,
            "quantities": catalogue,
        }, fh, sort_keys=False, allow_unicode=True)

    con.close()
    print(f"db: {db_version}")
    print(f"editions written: {len(editions)} "
          f"({min(editions)}-{max(editions)})")
    print(f"quantities: {len(catalogue)}")


if __name__ == "__main__":
    main()
