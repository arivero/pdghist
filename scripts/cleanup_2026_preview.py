#!/usr/bin/env python3
"""Clean up the 2026 preview electroweak.yaml file after official data is available.

This script removes the manual W_mass and Z_mass entries that were added from pdgLive
before the official database was published. These values should now come from the
official sources (summary.yaml from SQLite database and masses.yaml from mass_width file).

Run this after:
1. ./scripts/fetch.sh
2. python3 scripts/parse.py
3. python3 scripts/extract_db.py

This will ensure the manual preview values are replaced with official database values.
"""
import os
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
YAML_PATH = os.path.join(ROOT, "data", "2026", "electroweak.yaml")

def main():
    if not os.path.exists(YAML_PATH):
        print(f"Error: {YAML_PATH} not found")
        return 1

    with open(YAML_PATH, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    quantities = data.get("quantities", {})
    removed = []

    # Remove manual W_mass and Z_mass entries
    for key in ["W_mass", "Z_mass"]:
        if key in quantities:
            source = quantities[key].get("source", "")
            # Only remove if it's from pdgLive (the manual preview entry)
            if "pdgprod.lbl.gov" in source or "pdgLive" in source:
                removed.append(f"{key} = {quantities[key]['value']} ± {quantities[key]['error_positive']}")
                del quantities[key]

    # Update the note to remove the "not yet published" text
    if "note" in data:
        data["note"] = "Extracted from the review's schemes table; the PDF is copyrighted and not stored, see src/electroweak_review.md"

    # Update the source to match previous years
    data["source"] = "PDG Review of Particle Physics - Electroweak Model and Constraints on New Physics review"

    if removed:
        with open(YAML_PATH, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

        print(f"✓ Cleaned up {YAML_PATH}")
        print(f"  Removed manual preview entries:")
        for item in removed:
            print(f"    - {item}")
        print(f"\n  These values now come from:")
        print(f"    - data/2026/summary.yaml (SQLite database)")
        print(f"    - data/2026/masses.yaml (mass_width file)")
        return 0
    else:
        print(f"ℹ No manual preview entries found in {YAML_PATH}")
        print(f"  (Already cleaned up or never had them)")
        return 0

if __name__ == "__main__":
    exit(main())
