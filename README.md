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
  history_covariance.yaml  edition inputs, covariance modes and W-Z covariance for the history diagnostics
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
  pole_covariance.py   W/Z pole-angle comparison for 2025 and 2026
tests/                 pytest checks of the diagnostics + a node render smoke test
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
   year range so the new year is included (e.g. `seq 2010 2027`). Check the
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

## W/Z pole comparison in two editions

Run `python3 scripts/pole_covariance.py` to reproduce the comparison from the display strings in the 2025 and 2026 summary files. Both W listings use a mass-dependent-width Breit–Wigner parameter. Convert each mass with $\bar M=M/\sqrt{1+(\Gamma/M)^2}$ and compute $S=1-(\bar M_W/\bar M_Z)^2$. The direct and fitted on-shell histories on the site use their own conventions.

| Edition | $S$ | Independent-input standard error | Standard error over all input correlations |
|---|---:|---:|---:|
| 2025 | 0.22317850 | 0.00026081 | 0.00019640–0.00031818 |
| 2026 | 0.22330640 | 0.00015495 | 0.00008806–0.00020983 |

For the four marginal uncertainties let $u_i=|\partial_i S|\sigma_i$. In the linear approximation a correlation matrix is a Gram matrix of unit vectors, so the possible standard errors are the lengths of sums of four vectors of lengths $u_i$. Their maximum is $\sum u_i$ and their minimum is $\max(0,2\max u_i-\sum u_i)$. For the 2026 edition the offset from the de Vries value $0.22310132$ spans 0.98–2.33 standard errors on those assumptions. A statistic for the change *between* editions additionally needs their shared covariance.

The 2025 W record contains numeric $80.377\pm0.012$ GeV and display text $80.3692\pm0.0133$ GeV. The display agrees with the printed world average; the yearly mass-width file rounds it to 80.369 GeV. The script uses the same display convention for all four inputs and preserves the underlying source records. [2025 listing](https://pdg.lbl.gov/2025/listings/rpp2025-list-w-boson.pdf#page=1) · [2026 listing](https://pdg.lbl.gov/2026/listings/rpp2026-list-w-boson.pdf#page=1) · [Calculation](https://github.com/arivero/pdghist/issues/3#issuecomment-7192852130)

## Edition-to-edition changes and their covariance

Successive PDG averages reuse measurements, so the change between two editions
needs a covariance. `scripts/build_site.py` classifies every adjacent pair of
editions of the W and Z mass histories (database and EW-fit series) with the
records in [`data/history_covariance.yaml`](data/history_covariance.yaml) and
shows the decision in each card ("Edition-to-edition changes…") and in the
point tooltips.

- **Known covariance** $c$: $\mathrm{Var}(\Delta)=v_1+v_2-2c$.
- **Certified nested average.** If both editions are inverse-variance averages
  of independent Gaussian inputs with fixed errors, the earlier input set is
  contained in the later one, and the builder reproduces both published values
  from the listed inputs, then $\mathrm{Cov}(\hat\theta_1,\hat\theta_2)=v_2$ and
  $Z=\Delta/\sqrt{v_1-v_2}\sim N(0,1)$ exactly. Innovations along one nested
  chain are independent, and only such a chain is combined into a $\chi^2$.
- **Unknown covariance** (every pair without a record): the change is shown
  with $\sigma(\Delta)\in[|\sigma_1-\sigma_2|,\sigma_1+\sigma_2]$ and the
  corresponding range of $|\Delta|/\sigma(\Delta)$. A growing error and a
  changed mean with unchanged error are flagged as outside the nested model.

Two formats of one PDG average (database row, `mass_width` file, review table)
count as one observation; the diagnostic pairs editions within one series.

**Results from the 2022–2026 listings** (PDG W and Z listings, page 1, read on
2026-11-26; values and short quotes in the YAML file):

| Series | Pair | Decision | Statistic |
|---|---|---|---|
| Z mass | 2022→2023 | same input (LEP-SLC 06) | no innovation |
| Z mass | 2023→2024 | nested: LEP + CDF 22, "assuming no correlations" | $Z=+0.635$ |
| Z mass | 2024→2025 | same inputs | no innovation |
| Z mass | 2025→2026 | nested: + LHCb 25AH | $Z=-0.243$ |
| Z mass | chain 2022–2026 | one nested chain | $\chi^2_2=0.462$, $p=0.794$ |
| W mass | 2023→2024 | AMOROSO 24 recombination, CDF-II removed: not nested, error grows | $|\Delta|/\sigma\in[0.31,6.0]$ |
| W mass | 2025→2026 | new LHC-TeV combination with CMS, ATLAS update: not nested | $\Delta=-6.7$ MeV, $|\Delta|/\sigma\in[0.32,1.20]$ |
| EW fit $M_W$, $M_Z$ | all pairs | global fits with changing inputs | unknown-covariance ranges |

The builder reproduces the 2024 and 2026 database values of $M_Z$
(91.18797809… and 91.18787330… GeV) from the listed inputs to $10^{-14}$, and
each nested $Z$ equals the pull of the added measurement against the previous
average. The Z innovation therefore follows from the listing, through the YAML
record and `build_site.py`, to the table in the Z-mass card.

**Weak-angle series.** `derived_swsq` now takes the within-edition W–Z
covariance,
$\sigma_q^2=4r^4[\sigma_W^2/M_W^2+\sigma_Z^2/M_Z^2-2\,\mathrm{Cov}(M_W,M_Z)/(M_WM_Z)]$,
for both `derived_direct` and `derived_fit`. A common fractional scale error on
both masses cancels from the ratio. PDG prints no W–Z covariance, so each point
carries the declared $\rho$, a dashed envelope bar over the allowed
correlations, and the input source. For the fit series the review's printed
$s^2_W$ uncertainty, widened by half a unit in each last digit, restricts
$\rho$ to $[0.012,0.769]$ (2018), $[0.471,1]$ (2025) and $[-0.085,0.757]$
(2026); this assumes that the printed $s^2_W$ error is the same fit's
propagation. In 2018 and 2025 the declared $\rho=0$ lies outside that interval,
and the plotted error uses the nearest compatible $\rho$.

**Format checks recorded on the points.** The 2022 `mass_width` file prints
$M_W=80.379$ GeV while the listing and the database display give
$80.377\pm0.012$ GeV; the 2024 and 2025 database numeric columns keep
$80.377\pm0.012$ GeV while the display text and the listing give
$80.3692\pm0.0133$ GeV. The diagnostics use the display text in those cases.

Tests: `pip install pytest` and `python3 -m pytest -q tests` (the site smoke
test also needs `node`). They cover the two-measurement example
($Z=\sqrt2$ against the independent-release value $\sqrt{2/3}$), three nested
releases with zero cross-innovation covariance, an identical release, a changed
mean with unchanged variance, the common-scale cancellation, the real Z chain,
and a render of every card with and without the diagnostic fields.

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
