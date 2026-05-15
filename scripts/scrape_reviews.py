#!/usr/bin/env python3
"""Scrape the weak mixing angle sin^2(theta_W) from the PDG "Electroweak Model
and Constraints on New Physics" review, which is NOT carried in PDG's
machine-readable database.

For each edition with a Standard Model review PDF, this downloads the PDF,
converts it to text with `pdftotext`, extracts the on-shell and effective
sin^2(theta_W) values from the schemes table, and writes:

  data/<year>/src/electroweak_review.md  - the extracted values + provenance
  data/<year>/electroweak.yaml           - the parsed numbers for the pipeline

The PDF itself is never stored: it is copyrighted. Only the extracted numeric
values (facts, not copyrightable) and a small quoted excerpt are kept, as
markdown, so the source stays traceable. See README.

Requires: pdftotext (poppler-utils).
"""
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# Standard Model review PDFs exist from the 2008 edition onward.
YEARS = [2008, 2010, 2012, 2014, 2016, 2018, 2020, 2022, 2023, 2024, 2025, 2026]
URL = "https://pdg.lbl.gov/{y}/reviews/rpp{y}-rev-standard-model.pdf"

# schemes-table rows: a label, then a notation token, then 0.22xxx / 0.231xx,
# then an optional +-uncertainty. The "Effective angle" label is sometimes
# split by the pdftotext ligature for "ff".
ON_SHELL = re.compile(r"On-shell\b.*?(0\.22\d+)\s*(?:[±+]-?\s*(0\.0\d+))?")
EFFECTIVE = re.compile(
    r"Effective\s+angle\b.*?(0\.23\d+)\s*(?:[±+]-?\s*(0\.0\d+))?")

# fit-table rows in the EW review. Format varies edition to edition:
#   "MW [GeV]   <direct val>±<err>   <SM-pred val>±<err>   <pull>"          2008-2024
#   "MW [GeV]   <direct val>±<err>   <SM-fit val>±<err>   <indirect>±<err>" 2025+
# Always pick the 2nd value/error pair, which is the SM-constrained value.
FIT_MW = re.compile(r"^\s*MW\s*\[GeV\]")
FIT_MZ = re.compile(r"^\s*MZ\s*\[GeV\]")
VALERR = re.compile(r"(\d{2,3}\.\d{3,5})\s*[±+\-]\s*(0\.\d{3,5})")


def extract_fit_mass(text, line_rx):
    for line in text.splitlines():
        if not line_rx.match(line):
            continue
        pairs = VALERR.findall(line)
        if len(pairs) >= 2:
            v, e = pairs[1]
            return {"value": float(v), "error": float(e), "line": line.strip()}
    return None


def fetch_text(year):
    url = URL.format(y=year)
    with tempfile.TemporaryDirectory() as tmp:
        pdf = os.path.join(tmp, "rev.pdf")
        try:
            urllib.request.urlretrieve(url, pdf)
        except Exception as exc:
            print(f"  {year}: download failed ({exc})")
            return None, url
        txt = os.path.join(tmp, "rev.txt")
        try:
            subprocess.run(["pdftotext", "-layout", pdf, txt],
                           check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"  {year}: pdftotext failed ({exc})")
            return None, url
        with open(txt, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        # pdftotext keeps typographic ligatures (e.g. "Eﬀective"); fold them
        for lig, plain in (("ﬀ", "ff"), ("ﬁ", "fi"),
                           ("ﬂ", "fl"), ("ﬃ", "ffi"),
                           ("ﬄ", "ffl")):
            text = text.replace(lig, plain)
        return text, url


def extract(text):
    """Pull schemes-table values plus W/Z fit-table values from review text."""
    out = {}
    for name, rx in (("sin2_theta_W", ON_SHELL),
                     ("sin2_theta_eff", EFFECTIVE)):
        out[name] = None
        for line in text.splitlines():
            m = rx.search(line)
            if not m:
                continue
            val = float(m.group(1))
            err = float(m.group(2)) if m.group(2) else None
            out[name] = {"value": val, "error": err, "line": line.strip()}
            break
    out["W_mass_ew_fit"] = extract_fit_mass(text, FIT_MW)
    out["Z_mass_ew_fit"] = extract_fit_mass(text, FIT_MZ)
    return out


MD = """# Electroweak review — sin²(theta_W), PDG {year} edition

The weak mixing angle is not carried in PDG's machine-readable database; it
lives only in the narrative *Electroweak Model and Constraints on New Physics*
review. These values were extracted from that review's "schemes" table.

- Source: PDG *Review of Particle Physics* {year}, review "Electroweak Model and
  Constraints on New Physics".
- Downloaded from {url}
  on {date}.
- The PDF is copyrighted and is **not** stored in this repository; only the
  extracted numeric values and the quoted lines below are kept.

| scheme | sin²(theta_W) | uncertainty |
|---|---|---|
| on-shell (s²_W) | {osv} | {ose} |
| effective angle (s²_l) | {efv} | {efe} |

Extracted lines from the review text:

```
{oline}
{eline}
```
"""


def main():
    if not subprocess.run(["which", "pdftotext"],
                          capture_output=True).stdout.strip():
        sys.exit("pdftotext not found - install poppler-utils.")
    date = time.strftime("%Y-%m-%d")
    n_ok = 0
    for year in YEARS:
        print(f"electroweak review {year} ...")
        text, url = fetch_text(year)
        if text is None:
            continue
        vals = extract(text)
        os_, eff = vals["sin2_theta_W"], vals["sin2_theta_eff"]
        if not os_ and not eff:
            print(f"  {year}: no sin2thetaW values found")
            continue

        ydir = os.path.join(DATA, str(year))
        os.makedirs(os.path.join(ydir, "src"), exist_ok=True)
        with open(os.path.join(ydir, "src", "electroweak_review.md"),
                  "w", encoding="utf-8") as fh:
            fh.write(MD.format(
                year=year, url=url, date=date,
                osv=os_["value"] if os_ else "—",
                ose=("±" + str(os_["error"])) if os_ and os_["error"]
                    else "—",
                efv=eff["value"] if eff else "—",
                efe=("±" + str(eff["error"])) if eff and eff["error"]
                    else "—",
                oline=os_["line"] if os_ else "(on-shell value not found)",
                eline=eff["line"] if eff else "(effective value not found)"))

        # preserve any manually-added quantities (e.g. 2026 direct W/Z values
        # added before the official mass_width file / SQLite were released)
        SCRAPER_KEYS = {"sin2_theta_W", "sin2_theta_eff",
                        "W_mass_ew_fit", "Z_mass_ew_fit"}
        preserved = {}
        existing_path = os.path.join(ydir, "electroweak.yaml")
        if os.path.exists(existing_path):
            try:
                old = yaml.safe_load(open(existing_path)) or {}
                for k, v in (old.get("quantities") or {}).items():
                    if k not in SCRAPER_KEYS:
                        preserved[k] = v
            except Exception:
                pass

        doc = {
            "edition": year,
            "source": "PDG Review of Particle Physics - Electroweak Model "
                      "and Constraints on New Physics review",
            "source_url": url,
            "note": "Extracted from the review's schemes table; the PDF is "
                    "copyrighted and not stored, see src/electroweak_review.md",
            "quantities": dict(preserved),
        }
        if os_:
            doc["quantities"]["sin2_theta_W"] = {
                "value": os_["value"], "error_positive": os_["error"],
                "error_negative": os_["error"], "unit": "",
                "scheme": "on-shell",
            }
        if eff:
            doc["quantities"]["sin2_theta_eff"] = {
                "value": eff["value"], "error_positive": eff["error"],
                "error_negative": eff["error"], "unit": "",
                "scheme": "effective leptonic",
            }
        # SM-constrained fit values for W and Z masses (the "second column" of
        # the EW review's big fit table - more precise than the direct
        # measurement for m_W, equally precise for m_Z)
        for key, mass in (("W_mass_ew_fit", vals.get("W_mass_ew_fit")),
                          ("Z_mass_ew_fit", vals.get("Z_mass_ew_fit"))):
            if mass:
                doc["quantities"][key] = {
                    "value": mass["value"],
                    "error_positive": mass["error"],
                    "error_negative": mass["error"],
                    "unit": "GeV",
                    "source_column": "EW review fit table, 2nd value column "
                                     "(SM-constrained value)",
                }
        with open(os.path.join(ydir, "electroweak.yaml"), "w") as fh:
            yaml.safe_dump(doc, fh, sort_keys=False, allow_unicode=True)
        n_ok += 1
        osv = os_["value"] if os_ else "?"
        efv = eff["value"] if eff else "?"
        mw = vals.get("W_mass_ew_fit")
        mz = vals.get("Z_mass_ew_fit")
        print(f"  {year}: on-shell={osv}  effective={efv}  "
              f"mW_fit={mw['value'] if mw else '?'}  "
              f"mZ_fit={mz['value'] if mz else '?'}")
        time.sleep(0.5)

    print(f"done: {n_ok}/{len(YEARS)} editions")


if __name__ == "__main__":
    main()
