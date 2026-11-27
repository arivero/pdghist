# Innovations for Opus

Proposed by a Fable subagent review of this repo.

## 1. Track CKM matrix elements and α_s(M_Z) via review scraping

The README's "Known gaps / future work" section names these explicitly: CKM elements and α_s(M_Z) are absent from PDG's machine-readable database, exactly like sin²θ_W, and the repo already has the proven pattern for this in `scripts/scrape_reviews.py` (download review PDF → pdftotext → regex extraction → `data/<year>/electroweak.yaml` + committed markdown provenance). Opus would extend that scraper (or add a sibling) for the *CKM Quark-Mixing Matrix* review (Wolfenstein parameters λ, A, ρ̄, η̄ and/or |V_us|, |V_cb|, |V_ub|) and the *QCD* review's α_s(M_Z) world average, then wire the new keys through `quantities.yaml`, `build_site.py`, and the site's category rendering. The tricky part is that the fit-table/regex formats drift edition to edition (2008–2026), which the existing `FIT_MW`/`VALERR` regexes already show how to handle.

**Size:** medium

## 2. Automated yearly-update watcher via GitHub Actions

The README opens its update section with "Keep this repository alive — pdghist is only interesting if it keeps up," yet the update is a fully manual 6-step checklist (edit year ranges in `fetch.sh`, find the new sqlite filename, extend `YEARS` in `scrape_reviews.py`, re-run 4 scripts, eyeball the diff). A scheduled workflow would probe `pdg.lbl.gov/<year>/mcdata/` and `/api/` for new `mass_width` files, `pdgall-*.sqlite`, and review PDFs, auto-extend the year lists, run the whole pipeline, and open a PR with the regenerated YAML/`data.json` — including an automated version of README step 5's sanity check (flag any value that jumps more than N sigma from its neighboring editions, using the cross-check series the repo already builds for exactly this purpose). Scope: one workflow file plus a small `scripts/check_sanity.py` and making the hardcoded year lists data-driven.

**Size:** medium

## 3. A "precision & consistency" analytics page (how PDG values converge — and when they were wrong)

The repo already holds a unique dataset: 21 quantities × up to 68 years of values with errors, in `docs/data.json`. A third page (alongside `index.html` and `predictions.html`) would plot relative uncertainty vs. year on a log scale (the "error half-life" of each parameter), and compute edition-to-edition pulls — how often the new PDG value landed outside the previous edition's error bars, the classic signature of underestimated systematics that PDG itself famously documents. This reuses the existing plotting machinery in `docs/app.js` (niceTicks/logTicks/card infrastructure) and needs only a derived-series computation in `build_site.py` plus one new page; the s-quark and light-quark mass histories (backfilled 2012–2023 in the last commit) would make striking examples.

**Size:** small-to-medium
