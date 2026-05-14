#!/usr/bin/env bash
# Download the raw PDG sources pdghist is built from.
# Run this, then: python3 scripts/parse.py && python3 scripts/extract_db.py
#
# To add a new edition, see the "Updating each year" section of README.md.
set -euo pipefail
cd "$(dirname "$0")/.."

# --- 1. Yearly mass_width machine-readable files (independent cross-check) ----
# extension differs per era: .mc (2004-2008), .mcd (2010+)
declare -A EXT=( [2004]=mc [2006]=mc [2008]=mc )
for y in $(seq 2010 2025); do EXT[$y]=mcd; done

for y in "${!EXT[@]}"; do
  ext=${EXT[$y]}
  url="https://pdg.lbl.gov/$y/mcdata/mass_width_$y.$ext"
  mkdir -p "data/$y/src"
  echo "mass_width $y  <-  $url"
  curl -fsS "$url" -o "data/$y/src/mass_width.$ext"
done

# --- 2. All-editions SQLite database (primary source) ------------------------
# Binary, not committed to git; the YAML it produces is the traceable source.
# Find the current URL under https://pdg.lbl.gov/<year>/api/
SQLITE_URL="https://pdg.lbl.gov/2025/api/pdgall-2025-v0.2.2.sqlite"
mkdir -p data/_sqlite
echo "pdgall db   <-  $SQLITE_URL"
curl -fsS "$SQLITE_URL" -o "data/_sqlite/$(basename "$SQLITE_URL")"

echo "done. next: python3 scripts/parse.py && python3 scripts/extract_db.py && python3 scripts/build_site.py"
