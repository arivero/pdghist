"use strict";

const SERIES = {
  pdg_database:    { label: "PDG database",       color: "#0969da", shape: "circle" },
  mass_width_file: { label: "mass_width file",    color: "#bc4c00", shape: "square" },
  review_pdf:      { label: "Electroweak review", color: "#1a7f37", shape: "triangle" },
  ew_fit:          { label: "EW fit (constrained)", color: "#8250df", shape: "diamond" },
  derived_direct:  { label: "1−(m_W/m_Z)² direct",  color: "#cf222e", shape: "plus" },
  derived_fit:     { label: "1−(m_W/m_Z)² (EW fit)", color: "#9a6700", shape: "cross" },
};

// Horizontal reference lines drawn over selected plots. These come from the
// theoretical predictions catalogued on the /predictions.html page (Koide
// tuples and the Poincare-Casimir quartic construction by A. Rivero).
const ANNOTATIONS = {
  sin2_theta_W: [
    { value: 0.22310132, label: "Casimir-quartic s²_dV (0.22310132)",
      color: "#bf3989" },
  ],
  W_mass: [
    { value: 80.3724, label: "Casimir-quartic (80.3724 GeV)",
      color: "#bf3989" },
  ],
  H_mass: [
    { value: 122.3879, label: "Casimir-quartic (122.39 GeV)",
      color: "#bf3989" },
  ],
  b_quark_mass: [
    { value: 4.1845, label: "√mb = √3·√ms + √mc → 4.1845 GeV",
      color: "#bf3989" },
  ],
};
const ANN_STORAGE_KEY = "pdghist.annotations";
let annotationsEnabled =
  (localStorage.getItem(ANN_STORAGE_KEY) ?? "1") === "1";

// vertical-zoom: ?recent=N keeps only the last N editions of every plot, so
// the y-axis rescales and the (tiny) modern error bars become visible. It is
// a URL parameter on purpose: the state survives printing and bookmarking.
const RECENT = (() => {
  const v = parseInt(new URLSearchParams(location.search).get("recent"), 10);
  return Number.isFinite(v) && v > 0 ? v : 0;
})();

const tooltip = document.createElement("div");
tooltip.className = "tooltip";
document.body.appendChild(tooltip);
const showTip = (html, x, y) => {
  tooltip.innerHTML = html;
  tooltip.style.left = (x + 14) + "px";
  tooltip.style.top = (y + 14) + "px";
  tooltip.style.opacity = "1";
};
const hideTip = () => { tooltip.style.opacity = "0"; };

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

function logTicks(min, max) {
  const ticks = [];
  const lo = Math.floor(Math.log10(min)), hi = Math.ceil(Math.log10(max));
  const decades = hi - lo;
  const mults = decades <= 2 ? [1, 2, 5] : [1];
  for (let d = lo; d <= hi; d++)
    for (const mlt of mults) {
      const v = mlt * Math.pow(10, d);
      if (v >= min * 0.999 && v <= max * 1.001) ticks.push(v);
    }
  return ticks;
}

function fmt(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "?";
  if (v === 0) return "0";
  const a = Math.abs(v);
  if (a >= 1e4 || a < 1e-3) return v.toExponential(2);
  if (a >= 100) return v.toFixed(1);
  if (a >= 1) return v.toFixed(3);
  return v.toPrecision(3);
}

// choose enough decimal places that adjacent axis ticks render distinctly
function tickFormatter(ticks) {
  let mind = Infinity;
  for (let i = 1; i < ticks.length; i++)
    mind = Math.min(mind, Math.abs(ticks[i] - ticks[i - 1]));
  if (!Number.isFinite(mind) || mind === 0) return fmt;
  const dec = Math.min(8, Math.max(0, Math.ceil(-Math.log10(mind)) + 1));
  return v => {
    const a = Math.abs(v);
    if (a !== 0 && (a >= 1e5 || a < 1e-4)) return v.toExponential(1);
    return v.toFixed(dec);
  };
}

const isLimit = p => !!p.value_text && /^\s*[<>]/.test(p.value_text);

const SVGNS = "http://www.w3.org/2000/svg";
function el(name, attrs, parent) {
  const n = document.createElementNS(SVGNS, name);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}

// keep only the last RECENT editions across every series of one quantity
function applyRecent(q) {
  if (!RECENT) return q;
  const years = new Set();
  for (const sk in SERIES) (q.series[sk] || []).forEach(p => years.add(p.year));
  const keep = [...years].sort((a, b) => b - a).slice(0, RECENT);
  const cut = keep.length ? Math.min(...keep) : -Infinity;
  const series = {};
  for (const sk in SERIES)
    series[sk] = (q.series[sk] || []).filter(p => p.year >= cut);
  return Object.assign({}, q, { series });
}

function renderPlot(q0) {
  const q = applyRecent(q0);
  const W = 460, H = 300;
  const m = { l: 60, r: 16, t: 16, b: 38 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });

  const all = [];
  for (const sk in SERIES) (q.series[sk] || []).forEach(p => all.push(p));
  if (!all.length) {
    el("text", { x: W / 2, y: H / 2, "text-anchor": "middle",
      class: "tick-label" }, svg).textContent = "no data";
    return svg;
  }

  // x / y data extents
  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  let posMin = Infinity, anyNeg = false;
  for (const p of all) {
    xmin = Math.min(xmin, p.year); xmax = Math.max(xmax, p.year);
    const ep = p.error_positive || 0, en = isLimit(p) ? 0 : (p.error_negative || 0);
    const hi = p.value + ep, lo = p.value - en;
    ymin = Math.min(ymin, lo); ymax = Math.max(ymax, hi);
    if (lo <= 0) anyNeg = true;
    else posMin = Math.min(posMin, lo);
  }
  // extend y-extent to cover any annotation lines so they stay visible
  const anns = (annotationsEnabled && ANNOTATIONS[q0.key]) || [];
  for (const a of anns) {
    ymin = Math.min(ymin, a.value); ymax = Math.max(ymax, a.value);
    if (a.value > 0) posMin = Math.min(posMin, a.value);
  }
  if (xmin === xmax) { xmin -= 1; xmax += 1; }
  const xpad = Math.max(1, (xmax - xmin) * 0.04);
  xmin -= xpad; xmax += xpad;

  // log scale when the series spans a wide, strictly-positive range
  const useLog = !anyNeg && posMin > 0 && ymax / posMin > 80;
  let Y;
  if (useLog) {
    const l0 = Math.log10(posMin) - 0.15, l1 = Math.log10(ymax) + 0.15;
    Y = v => m.t + ih - (Math.log10(v) - l0) / (l1 - l0) * ih;
    var yticks = logTicks(Math.pow(10, l0), Math.pow(10, l1));
  } else {
    const pad = (ymax - ymin) * 0.08 || Math.abs(ymax) * 0.1 || 1;
    ymin -= pad; ymax += pad;
    Y = v => m.t + ih - (v - ymin) / (ymax - ymin) * ih;
    var yticks = niceTicks(ymin, ymax, 5);
  }
  const X = v => m.l + (v - xmin) / (xmax - xmin) * iw;

  // y grid + labels
  const yfmt = useLog ? fmt : tickFormatter(yticks);
  for (const t of yticks) {
    const y = Y(t);
    if (y < m.t - 1 || y > m.t + ih + 1) continue;
    el("line", { x1: m.l, y1: y, x2: m.l + iw, y2: y, class: "grid-line" }, svg);
    el("text", { x: m.l - 6, y: y + 3, "text-anchor": "end",
      class: "tick-label" }, svg).textContent = yfmt(t);
  }
  // x grid + labels (integer years)
  for (const t of niceTicks(xmin, xmax, 6)) {
    const yr = Math.round(t);
    if (yr < xmin || yr > xmax) continue;
    const x = X(yr);
    el("line", { x1: x, y1: m.t, x2: x, y2: m.t + ih, class: "grid-line" }, svg);
    el("text", { x: x, y: m.t + ih + 14, "text-anchor": "middle",
      class: "tick-label" }, svg).textContent = yr;
  }
  // annotation reference lines (drawn under the data points)
  for (const a of anns) {
    const y = Y(a.value);
    if (y < m.t - 1 || y > m.t + ih + 1) continue;
    el("line", { x1: m.l, y1: y, x2: m.l + iw, y2: y,
      stroke: a.color, "stroke-width": 1.2,
      "stroke-dasharray": "5 3", opacity: 0.85 }, svg);
    el("text", { x: m.l + iw - 4, y: y - 3, "text-anchor": "end",
      class: "annotation-label", fill: a.color }, svg).textContent = a.label;
  }

  // axes
  el("line", { x1: m.l, y1: m.t, x2: m.l, y2: m.t + ih, class: "axis" }, svg);
  el("line", { x1: m.l, y1: m.t + ih, x2: m.l + iw, y2: m.t + ih,
    class: "axis" }, svg);
  el("text", { x: m.l + iw / 2, y: H - 3, "text-anchor": "middle",
    class: "axis-title" }, svg).textContent = "PDG edition year";
  el("text", { x: 12, y: m.t + ih / 2, "text-anchor": "middle",
    class: "axis-title",
    transform: `rotate(-90 12 ${m.t + ih / 2})` }, svg).textContent =
    (q.unit ? `value (${q.unit})` : "value") + (useLog ? " — log" : "");

  // series
  for (const sk in SERIES) {
    const pts = (q.series[sk] || []).slice().sort((a, b) => a.year - b.year);
    if (!pts.length) continue;
    const cfg = SERIES[sk];

    const solid = pts.filter(p => !isLimit(p));
    if (solid.length > 1) {
      const d = solid.map((p, i) =>
        (i ? "L" : "M") + X(p.year) + " " + Y(p.value)).join(" ");
      el("path", { d: d, fill: "none", stroke: cfg.color,
        "stroke-width": 1.3, opacity: 0.5 }, svg);
    }

    for (const p of pts) {
      const cx = X(p.year), cy = Y(p.value);
      const limit = isLimit(p);
      const ep = p.error_positive || 0, en = p.error_negative || 0;

      if (!limit && (ep || en)) {
        const yHi = Y(p.value + ep), yLo = Y(p.value - en);
        el("line", { x1: cx, y1: yHi, x2: cx, y2: yLo,
          stroke: cfg.color, class: "errbar" }, svg);
        for (const yy of [yHi, yLo])
          el("line", { x1: cx - 3, y1: yy, x2: cx + 3, y2: yy,
            stroke: cfg.color, class: "errbar" }, svg);
      }

      let mark;
      if (limit) {
        const up = /^\s*>/.test(p.value_text), dy = up ? -6 : 6;
        mark = el("path", { d: `M${cx - 4} ${cy} L${cx + 4} ${cy} ` +
          `L${cx} ${cy + dy} Z`, fill: "none", stroke: cfg.color,
          "stroke-width": 1.5 }, svg);
      } else if (cfg.shape === "circle") {
        mark = el("circle", { cx: cx, cy: cy, r: 3.4, fill: cfg.color }, svg);
      } else if (cfg.shape === "triangle") {
        mark = el("path", { d: `M${cx} ${cy - 4} L${cx + 3.7} ${cy + 3} ` +
          `L${cx - 3.7} ${cy + 3} Z`, fill: cfg.color }, svg);
      } else if (cfg.shape === "diamond") {
        mark = el("path", { d: `M${cx} ${cy - 4} L${cx + 4} ${cy} ` +
          `L${cx} ${cy + 4} L${cx - 4} ${cy} Z`, fill: cfg.color }, svg);
      } else if (cfg.shape === "plus") {
        mark = el("path", { d: `M${cx - 4} ${cy} L${cx + 4} ${cy} ` +
          `M${cx} ${cy - 4} L${cx} ${cy + 4}`,
          stroke: cfg.color, "stroke-width": 1.8, fill: "none" }, svg);
      } else if (cfg.shape === "cross") {
        mark = el("path", { d: `M${cx - 3} ${cy - 3} L${cx + 3} ${cy + 3} ` +
          `M${cx - 3} ${cy + 3} L${cx + 3} ${cy - 3}`,
          stroke: cfg.color, "stroke-width": 1.8, fill: "none" }, svg);
      } else {
        mark = el("rect", { x: cx - 3.2, y: cy - 3.2, width: 6.4, height: 6.4,
          fill: "none", stroke: cfg.color, "stroke-width": 1.6 }, svg);
      }
      mark.style.cursor = "pointer";
      const txt = p.value_text ||
        (fmt(p.value) + (ep ? " ± " + fmt(ep) : ""));
      mark.addEventListener("mousemove", e => showTip(
        `<strong>${p.year}</strong> &middot; ${cfg.label}<br>` +
        `${q.symbol} = ${txt}${q.unit ? " " + q.unit : ""}` +
        (limit ? " <em>(limit)</em>" : ""), e.clientX, e.clientY));
      mark.addEventListener("mouseleave", hideTip);
    }
  }

  // legend
  let lx = m.l + 4;
  for (const sk in SERIES) {
    if (!(q.series[sk] || []).length) continue;
    const cfg = SERIES[sk];
    el("circle", { cx: lx + 4, cy: m.t + 4, r: 3.4, fill: cfg.color }, svg);
    el("text", { x: lx + 12, y: m.t + 7, class: "legend" }, svg)
      .textContent = cfg.label;
    lx += 22 + cfg.label.length * 5.6;
  }
  return svg;
}

function card(q) {
  const c = document.createElement("div");
  c.className = "card";
  c.id = "q-" + q.key;
  const h = document.createElement("h3");
  h.textContent = q.name;
  const meta = document.createElement("div");
  meta.className = "meta";
  let n = 0;
  for (const sk in SERIES) n = Math.max(n, (q.series[sk] || []).length);
  meta.innerHTML = `${q.symbol} &middot; PDG id <code>${q.pdgid}</code> ` +
    `&middot; ${n} editions`;
  c.appendChild(h);
  c.appendChild(meta);
  c.appendChild(renderPlot(q));
  return c;
}

// ----- the global all-masses figure (log y, shaded uncertainty bands) -------

const UNIT_TO_GEV = { GeV: 1, MeV: 1e-3, keV: 1e-6, eV: 1e-9 };
const MASS_COLORS = {
  d_quark_mass: "#d62728", u_quark_mass: "#ff7f0e", s_quark_mass: "#bcbd22",
  c_quark_mass: "#2ca02c", b_quark_mass: "#17becf", t_quark_mass: "#1f77b4",
  electron_mass: "#9467bd", muon_mass: "#8c564b", tau_mass: "#e377c2",
  W_mass: "#7f7f7f", Z_mass: "#393b79", H_mass: "#e7298a",
};

function massSeriesGeV(q) {
  // prefer the database series, fall back to the mass_width file
  const raw = (q.series.pdg_database && q.series.pdg_database.length)
    ? q.series.pdg_database : q.series.mass_width_file || [];
  const f = UNIT_TO_GEV[q.unit] || 1;
  return raw
    .filter(p => p.value != null && !isLimit(p))
    .map(p => ({
      year: p.year,
      v: p.value * f,
      hi: (p.value + (p.error_positive || 0)) * f,
      lo: (p.value - (p.error_negative || 0)) * f,
    }))
    .sort((a, b) => a.year - b.year);
}

function renderGlobalPlot(quantities) {
  const masses = quantities
    .filter(q => /mass$/.test(q.category) && MASS_COLORS[q.key])
    .map(q => ({ q, pts: massSeriesGeV(q) }))
    .filter(d => d.pts.length);
  if (!masses.length) return null;

  const W = 1180, H = 640;
  const m = { l: 66, r: 150, t: 18, b: 44 };
  const iw = W - m.l - m.r, ih = H - m.t - m.b;
  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });

  let xmin = Infinity, xmax = -Infinity, ymin = Infinity, ymax = -Infinity;
  const FLOOR = 1e-5; // GeV, keeps the log scale finite for huge old errors
  for (const d of masses)
    for (const p of d.pts) {
      xmin = Math.min(xmin, p.year); xmax = Math.max(xmax, p.year);
      ymax = Math.max(ymax, p.hi);
      ymin = Math.min(ymin, Math.max(FLOOR, p.lo, p.v * 0.2));
    }
  const xpad = (xmax - xmin) * 0.02;
  xmin -= xpad; xmax += xpad;
  const l0 = Math.log10(ymin) - 0.1, l1 = Math.log10(ymax) + 0.1;
  const X = v => m.l + (v - xmin) / (xmax - xmin) * iw;
  const Y = v => m.t + ih - (Math.log10(Math.max(FLOOR, v)) - l0) /
    (l1 - l0) * ih;

  for (const t of logTicks(Math.pow(10, l0), Math.pow(10, l1))) {
    const y = Y(t);
    el("line", { x1: m.l, y1: y, x2: m.l + iw, y2: y, class: "grid-line" }, svg);
    el("text", { x: m.l - 7, y: y + 3, "text-anchor": "end",
      class: "tick-label" }, svg).textContent = fmt(t);
  }
  for (const t of niceTicks(xmin, xmax, 9)) {
    const yr = Math.round(t);
    if (yr < xmin || yr > xmax) continue;
    const x = X(yr);
    el("line", { x1: x, y1: m.t, x2: x, y2: m.t + ih, class: "grid-line" }, svg);
    el("text", { x: x, y: m.t + ih + 15, "text-anchor": "middle",
      class: "tick-label" }, svg).textContent = yr;
  }
  el("line", { x1: m.l, y1: m.t, x2: m.l, y2: m.t + ih, class: "axis" }, svg);
  el("line", { x1: m.l, y1: m.t + ih, x2: m.l + iw, y2: m.t + ih,
    class: "axis" }, svg);
  el("text", { x: m.l + iw / 2, y: H - 6, "text-anchor": "middle",
    class: "axis-title" }, svg).textContent = "PDG edition year";
  el("text", { x: 13, y: m.t + ih / 2, "text-anchor": "middle",
    class: "axis-title", transform: `rotate(-90 13 ${m.t + ih / 2})` }, svg)
    .textContent = "mass (GeV) — log scale";

  for (const d of masses) {
    const col = MASS_COLORS[d.q.key];
    const pts = d.pts;
    // shaded uncertainty band
    const top = pts.map(p => `${X(p.year)} ${Y(p.hi)}`);
    const bot = pts.map(p => `${X(p.year)} ${Y(p.lo)}`).reverse();
    el("polygon", { points: top.concat(bot).join(" "),
      fill: col, "fill-opacity": 0.18, class: "global-band" }, svg);
    // central line
    el("path", { d: pts.map((p, i) =>
      (i ? "L" : "M") + X(p.year) + " " + Y(p.v)).join(" "),
      fill: "none", stroke: col, "stroke-width": 1.8 }, svg);
    // label at the right end
    const last = pts[pts.length - 1];
    el("text", { x: X(last.year) + 6, y: Y(last.v) + 3,
      fill: col, class: "global-label" }, svg).textContent = d.q.symbol;
  }
  return svg;
}

// ----- zoom-bar links -------------------------------------------------------

function buildZoomBar() {
  const box = document.getElementById("zoom-links");
  box.innerHTML = "";
  const opts = [["All editions", 0], ["Last 15", 15],
    ["Last 10", 10], ["Last 5", 5]];
  for (const [label, n] of opts) {
    const a = document.createElement("a");
    const u = new URL(location.href);
    if (n) u.searchParams.set("recent", n);
    else u.searchParams.delete("recent");
    u.hash = "";
    a.href = u.pathname + u.search;
    a.textContent = label;
    if (n === RECENT) a.className = "active";
    box.appendChild(a);
  }
}

function buildAnnotationToggle(rerender) {
  const box = document.getElementById("annotation-toggle");
  if (!box) return;
  box.innerHTML = "";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.id = "ann-cb";
  cb.checked = annotationsEnabled;
  cb.addEventListener("change", () => {
    annotationsEnabled = cb.checked;
    localStorage.setItem(ANN_STORAGE_KEY, annotationsEnabled ? "1" : "0");
    rerender();
  });
  const lbl = document.createElement("label");
  lbl.htmlFor = "ann-cb";
  lbl.textContent = " Show reference lines (de Vries prediction, …)";
  box.appendChild(cb);
  box.appendChild(lbl);
}

function renderEverything(data) {
  document.getElementById("generated").textContent =
    "Built " + data.generated + "." +
    (RECENT ? ` Showing the last ${RECENT} editions of each plot.` : "");

  const gWrap = document.getElementById("global");
  gWrap.innerHTML = "";
  const gPlot = renderGlobalPlot(data.quantities);
  if (gPlot) gWrap.appendChild(gPlot);
  else gWrap.textContent = "no mass data";

  const main = document.getElementById("plots");
  main.innerHTML = "";
  const nav = document.getElementById("nav");
  nav.innerHTML = "";
  const navTop = document.createElement("a");
  navTop.href = "#global-section";
  navTop.textContent = "all masses";
  nav.appendChild(navTop);

  for (const cat of data.categories) {
    const qs = data.quantities.filter(q => q.category === cat);
    if (!qs.length) continue;
    const slug = cat.replace(/[^a-z]+/gi, "-");

    const a = document.createElement("a");
    a.href = "#cat-" + slug;
    a.textContent = cat;
    nav.appendChild(a);

    const sec = document.createElement("section");
    sec.className = "category";
    sec.id = "cat-" + slug;
    const h2 = document.createElement("h2");
    h2.textContent = cat;
    sec.appendChild(h2);
    const grid = document.createElement("div");
    grid.className = "grid";
    qs.forEach(q => grid.appendChild(card(q)));
    sec.appendChild(grid);
    main.appendChild(sec);
  }
}

fetch("data.json", { cache: "no-store" })
  .then(r => r.json())
  .then(data => {
    buildZoomBar();
    buildAnnotationToggle(() => renderEverything(data));
    renderEverything(data);
  })
  .catch(err => {
    document.getElementById("plots").innerHTML =
      '<p class="loading">Failed to load data.json: ' + err + "</p>";
  });
