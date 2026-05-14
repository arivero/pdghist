# pdghist

**The history of PDG values for the fundamental parameters of the Standard Model.**

The [Particle Data Group](https://pdg.lbl.gov/) (PDG) publishes the *Review of
Particle Physics* every year, with the world's best estimate for each particle
mass, width and mixing parameter. Those estimates *change* as new measurements
come in. `pdghist` plots that history: for every quantity, **x = PDG edition
year**, **y = the value with its error bars**.

🌐 **Live site:** https://&lt;your-github-username&gt;.github.io/pdghist/
*(served from the [`docs/`](docs/) folder via GitHub Pages — see repo Settings → Pages)*

Each plot overlays **two independent PDG sources** as a sanity cross-check:

| series | source |
|---|---|
| **PDG database** | the all-editions `pdgall` SQLite database (headline value per edition, back to 1958) |
| **mass_width file** | the yearly `mass_width` machine-readable files (2004–present) |

## What's tracked

Fundamental Standard Model parameters only — quark masses, lepton masses,
W/Z/Higgs masses and widths, the effective weak mixing angle, and the neutrino
mixing angles and mass-squared differences. The full catalogue, with PDG
Identifiers, is in [`data/quantities.yaml`](data/quantities.yaml).

## Repository layout

```
data/
  quantities.yaml      catalogue of tracked quantities + their PDG Identifiers
  <year>/
    summary.yaml       SM parameter values for that PDG edition  (from the database)
    masses.yaml        particle masses/widths parsed from that year's mass_width file
    src/
      mass_width.<ext> the raw mass_width file as downloaded from pdg.lbl.gov
  _sqlite/             the pdgall SQLite database — git-ignored (binary, 60+ MB)
scripts/
  fetch.sh             download all raw PDG sources
  parse.py             mass_width files  -> data/<year>/masses.yaml
  extract_db.py        pdgall SQLite     -> data/<year>/summary.yaml + quantities.yaml
  build_site.py        all YAML          -> docs/data.json
docs/                  the GitHub Pages site (index.html, app.js, style.css, data.json)
```

**On sources and traceability.** Every raw *text* source is committed
(`data/<year>/src/`). The PDG SQLite database is binary and large, so it is
**not** committed — instead, the YAML it produces (`summary.yaml`,
`quantities.yaml`) is the traceable, diff-able source kept in the repo, and
`scripts/fetch.sh` records exactly where the database came from. No PDFs are
kept as sources.

## Building locally

```sh
pip install -r requirements.txt
./scripts/fetch.sh                  # download raw PDG sources
python3 scripts/parse.py            # mass_width files -> masses.yaml
python3 scripts/extract_db.py       # SQLite database  -> summary.yaml
python3 scripts/build_site.py       # everything       -> docs/data.json
python3 -m http.server -d docs 8000 # preview at http://localhost:8000
```

## Updating each year

**Keep this repository alive — the PDG publishes a new edition every year, and
`pdghist` is only interesting if it keeps up.** When the new edition appears
(typically mid-year for the `mass_width` file, late in the year for the
database), do this:

1. **Add the new `mass_width` file.** Edit `scripts/fetch.sh` and extend the
   year range so the new year is included (e.g. `seq 2010 2026`). Check the
   exact filename/extension on `https://pdg.lbl.gov/<year>/mcdata/`.
2. **Point at the new database.** On `https://pdg.lbl.gov/<year>/api/` find the
   new `pdgall-<year>-vX.Y.Z.sqlite` file and update `SQLITE_URL` in
   `scripts/fetch.sh`. (`extract_db.py` automatically picks the newest
   `pdgall-*.sqlite` in `data/_sqlite/`.)
3. **Re-run the pipeline:**
   ```sh
   ./scripts/fetch.sh
   python3 scripts/parse.py
   python3 scripts/extract_db.py
   python3 scripts/build_site.py
   ```
   This creates the new `data/<year>/` directory and refreshes every
   `summary.yaml` (older editions can change too — the PDG sometimes revises
   past values in the database).
4. **Review the diff.** `git diff data/` should show the new year plus any
   genuine revisions. If a value looks wildly off compared to neighbouring
   years, cross-check it against the live data on https://pdg.lbl.gov/ before
   committing — the two source series exist precisely to catch this.
5. **Commit** the new/changed YAML and `docs/data.json`.

If a brand-new quantity should be tracked, add it to the `QUANTITIES` list in
`scripts/extract_db.py` (you need its PDG Identifier — find it via
[pdgLive](https://pdglive.lbl.gov/)).

## Known gaps / future work

- **CKM matrix elements, α_s(M_Z), and the on-shell weak mixing angle** are not
  carried in PDG's machine-readable database — they live only in the narrative
  Reviews. They are intentionally skipped for now; adding them would mean
  parsing the per-year Review HTML pages.
- **Light-quark masses (u, d, s)** have no machine-readable value in the
  database for editions 2012–2023 (blank rows), so those years are missing from
  those three plots.

## License & attribution

Code: [MIT](LICENSE). Data: derived from the PDG *Review of Particle Physics*,
CC BY 4.0 — cite S. Navas *et al.* (Particle Data Group),
Phys. Rev. D **110**, 030001 (2024) and yearly updates.
