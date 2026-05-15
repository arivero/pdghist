# pdghist

**The history of PDG values for the fundamental parameters of the Standard Model.**

The [Particle Data Group](https://pdg.lbl.gov/) (PDG) publishes the *Review of
Particle Physics* every year, with the world's best estimate for each particle
mass, width and mixing parameter. Those estimates *change* as new measurements
come in. `pdghist` plots that history: for every quantity, **x = PDG edition
year**, **y = the value with its error bars**.

🌐 **Live site:** https://arivero.github.io/pdghist/
*(served from the [`docs/`](docs/) folder via GitHub Pages — see repo Settings → Pages)*

Each plot overlays the **independent PDG sources** that carry the quantity, as a
sanity cross-check:

| series | source |
|---|---|
| **PDG database** | the all-editions `pdgall` SQLite database (headline value per edition, back to 1958) |
| **mass_width file** | the yearly `mass_width` machine-readable files (2004–present) |
| **Electroweak review** | values extracted from the PDG *Electroweak Model* review (the weak mixing angle is not in the database) |
| **EW fit (constrained)** | the SM-constrained best-fit `m_W` and `m_Z` from the EW review's fit table (~2× more precise than direct `m_W`) |

## The site

- **All masses together** — one high-resolution figure at the top with every
  Standard Model mass on a single logarithmic axis; the line is the PDG value
  and the shaded band is its uncertainty.
- **Per-quantity plots** — one card per quantity, grouped by category.
- **Vertical zoom** — modern error bars are tiny next to the huge 1980s ones,
  so on the full-range axis they collapse to nothing. Append `?recent=N` to the
  URL (or use the zoom bar) to show only the last `N` editions of every plot;
  the y-axis rescales and the shrinking error bars become visible. It is a URL
  parameter on purpose — the state survives bookmarking and **printing**.
  Examples: `?recent=10`, `?recent=5`.
- **Reference lines** — selected plots show horizontal dashed lines for
  notable theoretical predictions (e.g. the de Vries numerological prediction
  `sin²θ_W = 0.22310132` on the on-shell weak mixing angle plot). Toggle them
  on/off with the "Show reference lines" checkbox; the preference is saved in
  `localStorage`. Defined in the `ANNOTATIONS` map in `docs/app.js`.

## What's tracked

Fundamental Standard Model parameters only — quark masses, lepton masses,
W/Z/Higgs masses and widths, the weak mixing angle (on-shell and effective),
and the neutrino mixing angles and mass-squared differences. The full
catalogue, with PDG Identifiers, is in [`data/quantities.yaml`](data/quantities.yaml).

## Repository layout

```
data/
  quantities.yaml      catalogue of tracked quantities + their PDG Identifiers
  <year>/
    summary.yaml       SM parameter values for that PDG edition  (from the database)
    masses.yaml        particle masses/widths parsed from that year's mass_width file
    electroweak.yaml   weak mixing angle, extracted from the Electroweak review
    src/
      mass_width.<ext>        the raw mass_width file as downloaded from pdg.lbl.gov
      electroweak_review.md   the sin^2(theta_W) values extracted from the review PDF
  _sqlite/             the pdgall SQLite database — git-ignored (binary, 60+ MB)
scripts/
  fetch.sh             download all raw PDG sources
  parse.py             mass_width files  -> data/<year>/masses.yaml
  extract_db.py        pdgall SQLite     -> data/<year>/summary.yaml + quantities.yaml
  scrape_reviews.py    Electroweak review PDFs -> data/<year>/electroweak.yaml
  build_site.py        all YAML          -> docs/data.json
docs/                  the GitHub Pages site (index.html, app.js, style.css, data.json)
```

**On sources and traceability.** Every raw *text* source is committed
(`data/<year>/src/`). Two kinds of source are deliberately **not** committed:

- the PDG SQLite database is binary and large — instead, the YAML it produces
  (`summary.yaml`, `quantities.yaml`) is the traceable, diff-able source kept in
  the repo;
- the Electroweak review **PDFs are copyrighted** — they are downloaded, parsed,
  and discarded. Only the extracted numeric values (facts, not copyrightable)
  and a short quoted excerpt are kept, as markdown, in
  `data/<year>/src/electroweak_review.md`.

`scripts/fetch.sh` and `scripts/scrape_reviews.py` record exactly where every
source came from.

## Building locally

```sh
pip install -r requirements.txt
sudo apt-get install poppler-utils      # provides pdftotext, used by scrape_reviews.py
./scripts/fetch.sh                       # download raw PDG sources
python3 scripts/parse.py                 # mass_width files -> masses.yaml
python3 scripts/extract_db.py            # SQLite database  -> summary.yaml
python3 scripts/scrape_reviews.py        # Electroweak review PDFs -> electroweak.yaml
python3 scripts/build_site.py            # everything       -> docs/data.json
python3 -m http.server -d docs 8000      # preview at http://localhost:8000
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
3. **Add the new Electroweak review.** Add the new year to the `YEARS` list in
   `scripts/scrape_reviews.py` (only editions with a `rev-standard-model.pdf`,
   i.e. 2008 onward).
4. **Re-run the pipeline:**
   ```sh
   ./scripts/fetch.sh
   python3 scripts/parse.py
   python3 scripts/extract_db.py
   python3 scripts/scrape_reviews.py
   python3 scripts/build_site.py
   ```
   This creates the new `data/<year>/` directory and refreshes every
   `summary.yaml` (older editions can change too — the PDG sometimes revises
   past values in the database).
5. **Review the diff.** `git diff data/` should show the new year plus any
   genuine revisions. If a value looks wildly off compared to neighbouring
   years, cross-check it against the live data on https://pdg.lbl.gov/ before
   committing — the overlaid source series exist precisely to catch this.
6. **Commit** the new/changed YAML, the new `src/` files, and `docs/data.json`
   (see below).

If a brand-new quantity should be tracked, add it to the `QUANTITIES` list in
`scripts/extract_db.py` (you need its PDG Identifier — find it via
[pdgLive](https://pdglive.lbl.gov/)). PDG occasionally *renames* Identifiers;
when that happens, an entry's `pdgid` can be a list (current id first, legacy
id second) and the editions are merged automatically.

## Committing changes

This repo has no automated deploy — committing the regenerated files *is* the
update. After re-running the pipeline:

```sh
# review what changed first
git status
git diff --stat data/ docs/data.json

# stage the regenerated data, sources, and site payload
git add data/ docs/data.json
git add scripts/ docs/*.html docs/*.js docs/*.css   # only if you changed code

git commit -m "Update to PDG <year> edition"
git push
```

Notes:
- **Never** `git add data/_sqlite/` — the binary database is git-ignored on
  purpose. Never commit a review PDF either; only the extracted markdown.
- `docs/data.json` is a build artefact but **is** committed, because GitHub
  Pages serves the site straight from `docs/` with no build step.
- Keep one commit per PDG edition update so the history is easy to bisect.

## Known gaps / future work

- **The weak mixing angle** is taken from the *Electroweak Model* review, which
  only exists as a PDF from the 2008 edition onward — so `sin^2(theta_W)`
  history starts at 2008, not 1958.
- **CKM matrix elements and α_s(M_Z)** are likewise not in the machine-readable
  database; they could be added with the same review-scraping approach used for
  the weak mixing angle (`scripts/scrape_reviews.py`).

## License & attribution

Code: [MIT](LICENSE). Data: derived from the PDG *Review of Particle Physics*,
CC BY 4.0 — cite S. Navas *et al.* (Particle Data Group),
Phys. Rev. D **110**, 030001 (2024) and yearly updates.
