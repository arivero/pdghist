"use strict";

// Each `part` is one of:
//   { mass: "<quantity_key>", sign: +1 | -1 }       a single mass with a sign
//   { zero: true }                                  contributes m = 0, √m = 0
//   { sum_sqrts: ["k1", "k2"], sign: +1 }           charge √m = √m1 + √m2
const TUPLES = [
  { name: "(e, μ, τ)",
    parts: [{ mass: "electron_mass", sign: +1 },
            { mass: "muon_mass", sign: +1 },
            { mass: "tau_mass", sign: +1 }],
    inverse: false,
    note: "the original Koide formula, exact",
    predicted: { year: 1983, ref: "Koide, PLB 120 (1983) 161" } },
  { name: "(d, s, b)",
    parts: [{ mass: "d_quark_mass", sign: +1 },
            { mass: "s_quark_mass", sign: +1 },
            { mass: "b_quark_mass", sign: +1 }],
    inverse: true,
    note: "inverse Koide K⁻¹ = 2/3; the main result of the 2026 PLB paper",
    predicted: { year: 2026, ref: "Rivero, PLB 877 (2026) 140510" } },
  { name: "(t, b, c)",
    parts: [{ mass: "t_quark_mass", sign: +1 },
            { mass: "b_quark_mass", sign: +1 },
            { mass: "c_quark_mass", sign: +1 }],
    inverse: false,
    note: "Rodejohann-Zhang tuple, ~0.6% off 2/3",
    predicted: { year: 2011,
      ref: "PF \"waterfall\" thread / Rodejohann–Zhang, PLB 698 (2011) 152" } },
  { name: "(−s, c, b)",
    parts: [{ mass: "s_quark_mass", sign: -1 },
            { mass: "c_quark_mass", sign: +1 },
            { mass: "b_quark_mass", sign: +1 }],
    inverse: false,
    note: "Rivero's 'new tuple'; uses the negative square root of m_s",
    predicted: { year: 2007,
      ref: "Rivero, Physics Forums posts (approximate)" } },
  { name: "(c, s, u)",
    parts: [{ mass: "c_quark_mass", sign: +1 },
            { mass: "s_quark_mass", sign: +1 },
            { mass: "u_quark_mass", sign: +1 }],
    inverse: false,
    note: "fails by ~6%; the u → 0 substitution rescues it",
    predicted: { year: 2011, ref: "PF \"waterfall\" thread (approximate)" } },
  { name: "(c, s, 0)",
    parts: [{ mass: "c_quark_mass", sign: +1 },
            { mass: "s_quark_mass", sign: +1 },
            { zero: true }],
    inverse: false,
    note: "u → 0 substitution applied to (c, s, u) — Harari trick on a different generation",
    predicted: { year: 2011,
      ref: "PF \"waterfall\" thread / Harari-style u → 0 (approximate)" } },
  { name: "(s, u, d)",
    parts: [{ mass: "s_quark_mass", sign: +1 },
            { mass: "u_quark_mass", sign: +1 },
            { mass: "d_quark_mass", sign: +1 }],
    inverse: false,
    note: "fails by ~15%; needs the d → u̅+d̄ substitution",
    predicted: { year: 2011, ref: "PF \"waterfall\" thread (approximate)" } },
  { name: "(d, s, 0)",
    parts: [{ mass: "d_quark_mass", sign: +1 },
            { mass: "s_quark_mass", sign: +1 },
            { zero: true }],
    inverse: false,
    note: "the original Harari–Haut–Weyers s,d,u set with u → 0; tied to the Cabibbo angle tan²θ_C ≈ m_d/m_s",
    predicted: { year: 1978,
      ref: "Harari, Haut, Weyers, PLB 78 (1978) 459 — \"sdu set\", first Koide-like tuple ever" } },
  { name: "(s, 0, u+d)",
    parts: [{ mass: "s_quark_mass", sign: +1 },
            { zero: true },
            { sum_masses: ["u_quark_mass", "d_quark_mass"], sign: +1 }],
    inverse: false,
    note: "ChPT-inspired d → u̅+d̄ replacement; composite mass m_u+m_d",
    predicted: { year: 2026,
      ref: "discussed in Rivero, PLB 877 (2026) 140510" } },
];
const TARGET = 2 / 3;

const UNIT_TO_GEV = { GeV: 1, MeV: 1e-3, keV: 1e-6, eV: 1e-9 };

function bestMassPerYear(q) {
  const out = {};
  const f = UNIT_TO_GEV[q.unit] || 1;
  for (const sk of ["mass_width_file", "pdg_database", "review_pdf"]) {
    for (const p of (q.series[sk] || [])) {
      const limit = p.value_text && /^\s*[<>]/.test(p.value_text);
      if (p.value != null && !limit && !(p.year in out)) {
        const ep = (p.error_positive || 0) * f;
        const en = (p.error_negative || 0) * f;
        // store symmetric proxy = max of the two-sided errors
        out[p.year] = { v: p.value * f, e: Math.max(ep, en) };
      }
    }
  }
  return out;
}

// reduce one part at a given year to (m, q) where m is the effective mass
// and q is the signed √-charge that goes into the Koide denominator
function partValues(part, maps, year) {
  if (part.zero) return { m: 0, q: 0, hasMass: false };
  if (part.sum_masses) {
    // u+d composite as a single "particle" with mass = m_u + m_d and
    // charge = √(m_u + m_d). This is the convention the PLB paper's
    // table uses for the (s, 0, u+d) tuple (gives K = 0.664831).
    let m = 0;
    for (const k of part.sum_masses) {
      const v = maps[k] && maps[k][year];
      if (!v || v.v <= 0) return null;
      m += v.v;
    }
    const sgn = part.sign || 1;
    return { m, q: sgn * Math.sqrt(m), hasMass: true };
  }
  if (part.sum_sqrts) {
    let q = 0;
    for (const k of part.sum_sqrts) {
      const m = maps[k] && maps[k][year];
      if (!m || m.v <= 0) return null;
      q += Math.sqrt(m.v);
    }
    const sgn = part.sign || 1;
    return { m: q * q, q: sgn * q, hasMass: true };
  }
  const m = maps[part.mass] && maps[part.mass][year];
  if (!m || m.v <= 0) return null;
  return { m: m.v, q: (part.sign || 1) * Math.sqrt(m.v), hasMass: true };
}

function koideFromParts(parts_values, inverse) {
  let sumA = 0, sumB = 0;
  for (const pv of parts_values) {
    if (inverse) {
      if (pv.m === 0 || pv.q === 0) return NaN;
      sumA += 1 / pv.m;
      sumB += 1 / pv.q;
    } else {
      sumA += pv.m;
      sumB += pv.q;
    }
  }
  return sumA / (sumB * sumB);
}

function tupleSeries(tuple, quantities) {
  // collect every quantity_key that any part references
  const keys = new Set();
  for (const part of tuple.parts) {
    if (part.mass) keys.add(part.mass);
    if (part.sum_sqrts) for (const k of part.sum_sqrts) keys.add(k);
    if (part.sum_masses) for (const k of part.sum_masses) keys.add(k);
  }
  const maps = {};
  for (const k of keys) {
    const q = quantities.find(qu => qu.key === k);
    if (!q) return [];
    maps[k] = bestMassPerYear(q);
  }
  // common years where all referenced masses exist
  const ksArr = [...keys];
  const sets = ksArr.map(k => new Set(Object.keys(maps[k]).map(y => +y)));
  const common = sets.length
    ? [...sets[0]].filter(y => sets.every(s => s.has(y))).sort((a, b) => a - b)
    : [];

  const out = [];
  for (const y of common) {
    const vals = tuple.parts.map(p => partValues(p, maps, y));
    if (vals.some(v => v === null)) continue;
    const K0 = koideFromParts(vals, tuple.inverse);
    if (!Number.isFinite(K0)) continue;
    // numerical Jacobian over each underlying mass
    let varK = 0;
    for (const k of keys) {
      const m = maps[k][y];
      if (!m || !m.e) continue;
      const h = Math.max(m.e * 0.01, 1e-9);
      const mapsP = { ...maps, [k]: { ...maps[k],
                       [y]: { v: m.v + h, e: m.e } } };
      const valsP = tuple.parts.map(p => partValues(p, mapsP, y));
      if (valsP.some(v => v === null)) continue;
      const Kp = koideFromParts(valsP, tuple.inverse);
      varK += ((Kp - K0) / h * m.e) ** 2;
    }
    out.push({ year: y, K: K0, sigma: Math.sqrt(varK) });
  }
  return out;
}

const SVGNS = "http://www.w3.org/2000/svg";
function el(name, attrs, parent) {
  const n = document.createElementNS(SVGNS, name);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
function niceTicks(min, max, target) {
  if (min === max) { min -= 1; max += 1; }
  const raw = (max - min) / target;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  let step = mag;
  if (norm >= 5) step = 10 * mag;
  else if (norm >= 2) step = 5 * mag;
  else if (norm >= 1) step = 2 * mag;
  const ticks = [];
  for (let v = Math.ceil(min / step) * step; v <= max + step * 1e-6; v += step)
    ticks.push(v);
  return ticks;
}

function renderKoidePlot(tuple, series) {
  const inverse = tuple.inverse;
  const W = 460, H = 240;
  const m = { l: 60, r: 16, t: 16, b: 38 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
  if (!series.length && !tuple.predicted) {
    el("text", { x: W / 2, y: H / 2, "text-anchor": "middle",
      class: "tick-label" }, svg).textContent = "no overlap of inputs";
    return svg;
  }
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  for (const p of series) {
    xmin = Math.min(xmin, p.year); xmax = Math.max(xmax, p.year);
    const s = p.sigma || 0;
    ymin = Math.min(ymin, p.K - s); ymax = Math.max(ymax, p.K + s);
  }
  // include the postdiction year so the line is on-plot
  if (tuple.predicted) {
    xmin = Math.min(xmin, tuple.predicted.year);
    xmax = Math.max(xmax, tuple.predicted.year);
  }
  if (!Number.isFinite(ymin)) { ymin = TARGET - 0.01; ymax = TARGET + 0.01; }
  ymin = Math.min(ymin, TARGET); ymax = Math.max(ymax, TARGET);
  const xpad = (xmax - xmin) * 0.04 || 1;
  xmin -= xpad; xmax += xpad;
  const ypad = (ymax - ymin) * 0.1 || 0.01;
  ymin -= ypad; ymax += ypad;
  const X = v => m.l + (v - xmin) / (xmax - xmin) * iw;
  const Y = v => m.t + ih - (v - ymin) / (ymax - ymin) * ih;

  for (const t of niceTicks(ymin, ymax, 5)) {
    const y = Y(t);
    if (y < m.t - 1 || y > m.t + ih + 1) continue;
    el("line", { x1: m.l, y1: y, x2: m.l + iw, y2: y, class: "grid-line" }, svg);
    el("text", { x: m.l - 6, y: y + 3, "text-anchor": "end",
      class: "tick-label" }, svg).textContent = t.toFixed(4);
  }
  for (const t of niceTicks(xmin, xmax, 6)) {
    const yr = Math.round(t);
    if (yr < xmin || yr > xmax) continue;
    const x = X(yr);
    el("line", { x1: x, y1: m.t, x2: x, y2: m.t + ih, class: "grid-line" }, svg);
    el("text", { x: x, y: m.t + ih + 14, "text-anchor": "middle",
      class: "tick-label" }, svg).textContent = yr;
  }
  el("line", { x1: m.l, y1: m.t, x2: m.l, y2: m.t + ih, class: "axis" }, svg);
  el("line", { x1: m.l, y1: m.t + ih, x2: m.l + iw, y2: m.t + ih,
    class: "axis" }, svg);

  // target line at 2/3
  const yT = Y(TARGET);
  el("line", { x1: m.l, y1: yT, x2: m.l + iw, y2: yT,
    stroke: "#bf3989", "stroke-dasharray": "5 3",
    "stroke-width": 1.2, opacity: 0.85 }, svg);
  el("text", { x: m.l + iw - 4, y: yT - 3, "text-anchor": "end",
    class: "annotation-label", fill: "#bf3989" }, svg).textContent =
    (inverse ? "K⁻¹ = 2/3" : "K = 2/3");

  // connecting line
  const d = series.map((p, i) =>
    (i ? "L" : "M") + X(p.year) + " " + Y(p.K)).join(" ");
  el("path", { d, fill: "none", stroke: "#0969da",
    "stroke-width": 1.3, opacity: 0.55 }, svg);
  // error bars + markers
  for (const p of series) {
    const cx = X(p.year), cy = Y(p.K);
    if (p.sigma > 0) {
      const yHi = Y(p.K + p.sigma), yLo = Y(p.K - p.sigma);
      el("line", { x1: cx, y1: yHi, x2: cx, y2: yLo,
        stroke: "#0969da", "stroke-width": 1.2 }, svg);
      for (const yy of [yHi, yLo])
        el("line", { x1: cx - 3, y1: yy, x2: cx + 3, y2: yy,
          stroke: "#0969da", "stroke-width": 1.2 }, svg);
    }
    el("circle", { cx, cy, r: 2.6, fill: "#0969da" }, svg);
  }
  el("text", { x: m.l + iw / 2, y: H - 3, "text-anchor": "middle",
    class: "axis-title" }, svg).textContent = "PDG edition year";
  el("text", { x: 12, y: m.t + ih / 2, "text-anchor": "middle",
    class: "axis-title",
    transform: `rotate(-90 12 ${m.t + ih / 2})` }, svg).textContent =
    inverse ? "K⁻¹" : "K";

  // postdiction year - vertical dashed line + label
  if (tuple.predicted) {
    const xp = X(tuple.predicted.year);
    if (xp >= m.l - 0.5 && xp <= m.l + iw + 0.5) {
      el("line", { x1: xp, y1: m.t, x2: xp, y2: m.t + ih,
        stroke: "#bc4c00", "stroke-dasharray": "4 3",
        "stroke-width": 1.3, opacity: 0.85 }, svg);
      const lbl = `postdicted ${tuple.predicted.year}`;
      // place label vertically along the line, just to its right
      el("text", { x: xp + 4, y: m.t + 10,
        fill: "#bc4c00", class: "annotation-label" }, svg).textContent = lbl;
    }
  }
  return svg;
}

function renderKoideTable(tuples, quantities) {
  const tbody = document.getElementById("koide-tbody");
  tbody.innerHTML = "";
  for (const t of tuples) {
    const series = tupleSeries(t, quantities);
    const last = series.length ? series[series.length - 1] : null;
    const dev = last ? ((last.K - TARGET) / TARGET * 100) : null;
    const devStr = dev != null
      ? `${dev > 0 ? "+" : ""}${dev.toFixed(3)}%` : "—";
    const yr = t.predicted ? t.predicted.year : "—";
    const ref = t.predicted ? t.predicted.ref : "";
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${t.name}</td>` +
      `<td>${t.inverse ? "K⁻¹" : "K"} = 2/3</td>` +
      `<td class="num">0.66667</td>` +
      `<td class="num">${last ? last.K.toFixed(6) : "—"}</td>` +
      `<td class="num">${devStr}</td>` +
      `<td>${yr}</td>` +
      `<td><span title="${ref}">${t.note}</span></td>`;
    tbody.appendChild(tr);
  }
}

function renderKoidePlots(tuples, quantities) {
  const wrap = document.getElementById("koide-plots");
  wrap.innerHTML = "";
  for (const t of tuples) {
    const series = tupleSeries(t, quantities);
    const card = document.createElement("div");
    card.className = "card";
    const h = document.createElement("h3");
    h.textContent = (t.inverse ? "K⁻¹ " : "K ") + t.name;
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `${series.length} editions &middot; postdicted ` +
      (t.predicted ? `<strong>${t.predicted.year}</strong>` : "—") +
      (t.predicted ? ` <span class="hint">(${t.predicted.ref})</span>` : "");
    card.appendChild(h);
    card.appendChild(meta);
    card.appendChild(renderKoidePlot(t, series));
    wrap.appendChild(card);
  }
}

// Poincare-Casimir quartic slots (a, b, c, d label them)
const CASIMIR_SLOTS = [
  { slot: "(1, +)", label: "M_Z",   r: 1.0,        sign: 0, name: "Z_mass" },
  { slot: "(½, +)", label: "M_W",   r: 0.881419,   sign: 0, name: "W_mass" },
  { slot: "(1, −)", label: "v/√2",  r: 1.931852,   sign: -1, name: "v/√2" },
  { slot: "(½, −)", label: "m_H",   r: 1.342173,   sign: +1, name: "H_mass" },
];

function latest(byYear) {
  const ys = Object.keys(byYear).map(Number).sort((a, b) => b - a);
  return ys.length ? byYear[ys[0]] : null;
}

function renderCasimirTable(quantities) {
  const W = latest(bestMassPerYear(quantities.find(q => q.key === "W_mass")));
  const Z = latest(bestMassPerYear(quantities.find(q => q.key === "Z_mass")));
  const H = latest(bestMassPerYear(quantities.find(q => q.key === "H_mass")));
  // v/sqrt(2): from PDG G_F = 1.1663788e-5 GeV^-2 -> v = 246.21965 GeV
  const V = { v: 246.21965 / Math.SQRT2, e: 0.00015 };
  const mZ = Z.v, mW = W.v;
  const eps = (3 / 8) * (mZ * mZ - mW * mW);   // GeV^2
  const measured = { Z_mass: Z, W_mass: W, "v/√2": V, H_mass: H };

  const tbody = document.getElementById("casimir-tbody");
  tbody.innerHTML = "";
  for (const slot of CASIMIR_SLOTS) {
    const tree = slot.r * mZ;
    let withCorr = tree;
    if (slot.sign !== 0) {
      const sq = tree * tree + slot.sign * eps;
      withCorr = sq > 0 ? Math.sqrt(sq) : NaN;
    }
    const m = measured[slot.name];
    const meas = m && m.v != null ? m.v : null;
    const mErr = m && m.e != null ? m.e : null;
    const dev = meas != null ?
      ((withCorr - meas) / meas * 100).toFixed(3) + "%" : null;
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${slot.slot}</td>` +
      `<td>${slot.label}</td>` +
      `<td class="num">${slot.r.toFixed(6)}</td>` +
      `<td class="num">${tree.toFixed(4)}</td>` +
      `<td class="num">${Number.isFinite(withCorr) ? withCorr.toFixed(4)
          + (slot.sign !== 0 && dev ? `  (Δ ${dev})` : "") : "—"}</td>` +
      `<td class="num">${meas != null ?
          meas.toFixed(4) + " ± " + (mErr || 0).toFixed(4) : "—"}</td>`;
    tbody.appendChild(tr);
  }
}

fetch("data.json", { cache: "no-store" })
  .then(r => r.json())
  .then(data => {
    renderKoideTable(TUPLES, data.quantities);
    renderKoidePlots(TUPLES, data.quantities);
    renderCasimirTable(data.quantities);
  })
  .catch(err => {
    document.body.insertAdjacentHTML("beforeend",
      `<p class="loading">Failed to load data.json: ${err}</p>`);
  });
