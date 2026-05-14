#!/usr/bin/env python3
"""Parse PDG mass_width machine-readable files into per-year masses.yaml.

Handles the two FORTRAN fixed-width layouts PDG has used:
  old (2004-2012):  (BN, A1, 4I8, 1X, E15.0, 2(1X, E8.0), 1X, A21)
  new (2013-):      (BN, 4I8, 2(1X,E18.0, 1X,E8.0, 1X,E8.0), 1X,A21)
"""
import glob
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def num(s):
    s = s.strip()
    if not s:
        return None
    return float(s)


def chunks(s):
    """Split the 32-char id region into up to 4 ints."""
    out = []
    for i in range(0, 32, 8):
        v = s[i:i + 8].strip()
        if v:
            out.append(int(v))
    return out


def split_name(field):
    """A21 field: name left-justified, charge right-justified."""
    field = field.rstrip()
    toks = field.split()
    if not toks:
        return "", ""
    if len(toks) == 1:
        return toks[0], ""
    return " ".join(toks[:-1]), toks[-1]


def parse_old(lines):
    """One line per M or W; merge by id tuple + name."""
    rec = {}
    order = []
    for ln in lines:
        kind = ln[0:1]
        if kind not in ("M", "W"):
            continue
        ids = tuple(chunks(ln[1:33]))
        value = num(ln[34:49])
        errp = num(ln[50:58])
        errn = num(ln[59:67])
        name, charge = split_name(ln[68:])
        key = (ids, name, charge)
        if key not in rec:
            rec[key] = {"mc_ids": list(ids), "name": name, "charge": charge}
            order.append(key)
        field = "mass" if kind == "M" else "width"
        rec[key][field] = {"value": value, "error_pos": errp, "error_neg": errn}
    return [rec[k] for k in order]


def parse_new(lines):
    out = []
    for ln in lines:
        if not ln.strip() or ln.startswith("*"):
            continue
        ids = chunks(ln[0:32])
        if not ids:
            continue
        mass_v, mass_p, mass_n = num(ln[33:51]), num(ln[52:60]), num(ln[61:69])
        wid_v, wid_p, wid_n = num(ln[70:88]), num(ln[89:97]), num(ln[98:106])
        name, charge = split_name(ln[107:])
        entry = {"mc_ids": ids, "name": name, "charge": charge}
        if mass_v is not None:
            entry["mass"] = {"value": mass_v, "error_pos": mass_p,
                             "error_neg": mass_n}
        if wid_v is not None:
            entry["width"] = {"value": wid_v, "error_pos": wid_p,
                              "error_neg": wid_n}
        out.append(entry)
    return out


def parse_file(path):
    with open(path, encoding="latin-1") as fh:
        raw = fh.read().splitlines()
    header = [l for l in raw if l.startswith("*")]
    data = [l for l in raw if l and not l.startswith("*")]

    generated = None
    for l in header:
        m = re.search(r"generated on (\S+)", l)
        if m:
            generated = m.group(1)
            break

    fmt = next((l for l in header if "FORMAT" in l.upper()), "")
    old = "A1, 4I8" in fmt.replace(" ", " ")
    # robust fallback: detect by first data char
    if data and data[0][0:1] in ("M", "W"):
        old = True
    particles = parse_old(data) if old else parse_new(data)
    return generated, particles


def main():
    years = sorted(d for d in os.listdir(DATA)
                   if os.path.isdir(os.path.join(DATA, d)) and d.isdigit())
    for year in years:
        src = glob.glob(os.path.join(DATA, year, "src", "mass_width.*"))
        if not src:
            print(f"{year}: no raw file", file=sys.stderr)
            continue
        path = src[0]
        ext = os.path.splitext(path)[1].lstrip(".")
        generated, particles = parse_file(path)
        doc = {
            "edition": int(year),
            "source": f"https://pdg.lbl.gov/{year}/mcdata/"
                      f"mass_width_{year}.{ext}",
            "generated": generated,
            "unit": "GeV",
            "n_particles": len(particles),
            "particles": particles,
        }
        out = os.path.join(DATA, year, "masses.yaml")
        with open(out, "w") as fh:
            yaml.safe_dump(doc, fh, sort_keys=False, default_flow_style=False,
                           allow_unicode=True)
        print(f"{year}: {len(particles)} particles -> {out}")


if __name__ == "__main__":
    main()
