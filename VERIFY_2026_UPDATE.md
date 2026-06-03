# Verification Steps for PDG 2026 Official Update

## Background

The 2026 preview was created on 2026-05-15 using:
- Electroweak review PDFs from https://pdg.lbl.gov/2026/reviews/
- **Manual W/Z mass values from pdgLive** (staging server `pdgprod.lbl.gov`):
  - W mass: 80.3625 ± 0.0077 GeV (from S043M node)
  - Z mass: 91.1879 ± 0.0020 GeV (from S044M node)

Now that PDG has officially published the 2026 edition, we need to:
1. Fetch the official `mass_width_2026.mcd` file
2. Fetch the official `pdgall-2026-vX.Y.Z.sqlite` database
3. Re-run the pipeline
4. **Compare preview values with official values** to check for discrepancies

## Updated Files

I've updated `scripts/fetch.sh` to:
1. Include 2026 in the mass_width download loop (changed `seq 2010 2025` to `seq 2010 2026`)
2. Point to the 2026 SQLite database URL

**Note:** The exact SQLite database version (v0.1.0, v0.2.0, etc.) needs to be verified at:
https://pdg.lbl.gov/2026/api/

## Steps to Run

### 1. Verify the SQLite database version

Check https://pdg.lbl.gov/2026/api/ for the actual filename, which should be something like:
- `pdgall-2026-v0.1.0.sqlite`
- `pdgall-2026-v0.2.0.sqlite`

Update line 25 in `scripts/fetch.sh` if the version differs from v0.1.0.

### 2. Run the pipeline

```bash
# Ensure dependencies are installed
pip install -r requirements.txt
sudo apt-get install poppler-utils  # if not already installed

# Download all sources (including the new 2026 data)
./scripts/fetch.sh

# Parse the mass_width file -> data/2026/masses.yaml
python3 scripts/parse.py

# Extract from SQLite database -> data/2026/summary.yaml
python3 scripts/extract_db.py

# Clean up the preview electroweak.yaml (remove manual W/Z entries)
python3 scripts/cleanup_2026_preview.py

# Re-scrape electroweak reviews (updates sin²θ_W and EW fit values)
python3 scripts/scrape_reviews.py

# Build the site -> docs/data.json
python3 scripts/build_site.py
```

### 3. Review the Changes

Check what changed with:
```bash
git status
git diff data/2026/
```

**Critical values to verify:**

#### From `data/2026/masses.yaml` (now from official mass_width file):
- W boson mass (S043M)
- Z boson mass (S044M)
- Higgs mass (S126M)
- Top quark mass (Q007M)

#### From `data/2026/summary.yaml` (now from official SQLite database):
- All quark masses (u, d, s, c, b, t)
- All lepton masses (e, μ, τ)
- W, Z, H masses and widths

#### From `data/2026/electroweak.yaml`:
The scraper script is designed to preserve manual entries like `W_mass` and `Z_mass` that were added before the official files were available (see lines 167-180 in `scripts/scrape_reviews.py`).

**However**, after the official database is published, these manual `W_mass` and `Z_mass` entries should be **removed** from `electroweak.yaml` because they will now come from:
- `data/2026/summary.yaml` (from the SQLite database)
- `data/2026/masses.yaml` (from the mass_width file)

The note field in `electroweak.yaml` currently says "The 2026 pdgall SQLite DB and mass_width file are not yet published" - this should be updated to match the format used in previous years (see `data/2025/electroweak.yaml` for reference).

### 4. Compare Preview vs Official Values

Pay special attention to these values that were manually entered:

| Quantity | Preview Value (pdgLive 2026-05-15) | Official Value (to check) |
|----------|-------------------------------------|---------------------------|
| W mass   | 80.3625 ± 0.0077 GeV               | ? |
| Z mass   | 91.1879 ± 0.0020 GeV               | ? |
| W mass (EW fit) | 80.359 ± 0.006 GeV        | ? |
| Z mass (EW fit) | 91.1883 ± 0.002 GeV       | ? |
| sin²θ_W (on-shell) | 0.22342 ± 0.00009      | (already from review PDF) |
| sin²θ_W (effective) | 0.23154 ± 0.00006     | (already from review PDF) |

**Expected behavior:**
- The official mass_width file and SQLite database should contain W/Z masses very close to the preview values
- Small differences (< 0.0001 GeV) are acceptable if PDG updated their evaluation between May 15 and the official release
- Large differences would be unexpected and should be investigated

### 5. Check for Issues

Look for:
- Values that differ significantly from 2025 without explanation
- Unexpected jumps or discontinuities in the plots
- Missing values that were present in 2025

The overlaid source series (database, mass_width file, electroweak review) are specifically designed to catch transcription errors or formatting issues.

### 6. Commit Changes

Once verified:
```bash
git add data/2026/masses.yaml data/2026/summary.yaml
git add data/2026/electroweak.yaml  # if changed
git add docs/data.json
git add scripts/fetch.sh

git commit -m "Update to official PDG 2026 data

- Add 2026 mass_width file (official release)
- Add 2026 SQLite database values (official release)
- Replace preview W/Z values with official database values
- Verify W mass: 80.3625 ± 0.0077 GeV (preview) vs [official] GeV
- Verify Z mass: 91.1879 ± 0.0020 GeV (preview) vs [official] GeV"

git push
```

## Notes

- The `data/2026/src/` directory will gain a new `mass_width.mcd` file
- The manual documentation files in `data/2026/src/` (pdglive_w_z_evaluation.md, etc.) can remain as historical record of how the preview was created
- The `cleanup_2026_preview.py` script removes the manual W/Z entries from `electroweak.yaml` so they come from the official sources instead

## Key Files to Review

Before committing, check these files have been properly updated:
- `data/2026/masses.yaml` - should now exist with ~2700+ entries from mass_width file
- `data/2026/summary.yaml` - should now exist with values from SQLite database
- `data/2026/electroweak.yaml` - should NOT contain manual `W_mass`/`Z_mass` entries anymore
- `data/2026/src/mass_width.mcd` - the official 2026 mass_width file
- `docs/data.json` - should be regenerated with the new 2026 data

## Troubleshooting

If the official values differ significantly from the preview:
1. Check the PDG website directly for the latest values
2. Cross-reference with pdgLive viewer (https://pdglive.lbl.gov/)
3. Check if PDG published errata or updates between the preview and official release
