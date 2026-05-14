"use strict";

const SERIES = {
  pdg_database:   { label: "PDG database",    color: "#4ea1ff", shape: "circle" },
  mass_width_file:{ label: "mass_width file", color: "#ff9d4e", shape: "square" },
};

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

const isLimit = p => !!p.value_text && /^\s*[<>]/.test(p.value_text);

const SVGNS = "http://www.w3.org/2000/svg";
function el(name, attrs, parent) {
  const n = document.createElementNS(SVGNS, name);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}

function renderPlot(q) {
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
  for (const t of yticks) {
    const y = Y(t);
    if (y < m.t - 1 || y > m.t + ih + 1) continue;
    el("line", { x1: m.l, y1: y, x2: m.l + iw, y2: y, class: "grid-line" }, svg);
    el("text", { x: m.l - 6, y: y + 3, "text-anchor": "end",
      class: "tick-label" }, svg).textContent = fmt(t);
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
        // upper/lower limit: hollow triangle pointing in the bound direction
        const up = /^\s*>/.test(p.value_text), dy = up ? -6 : 6;
        mark = el("path", { d: `M${cx - 4} ${cy} L${cx + 4} ${cy} ` +
          `L${cx} ${cy + dy} Z`, fill: "none", stroke: cfg.color,
          "stroke-width": 1.5 }, svg);
      } else if (cfg.shape === "circle") {
        mark = el("circle", { cx: cx, cy: cy, r: 3.4, fill: cfg.color }, svg);
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
  const n = (q.series.pdg_database || []).length;
  meta.innerHTML = `${q.symbol} &middot; PDG id <code>${q.pdgid}</code> ` +
    `&middot; ${n} editions`;
  c.appendChild(h);
  c.appendChild(meta);
  c.appendChild(renderPlot(q));
  return c;
}

fetch("data.json")
  .then(r => r.json())
  .then(data => {
    document.getElementById("generated").textContent =
      "Built " + data.generated + ".";
    const main = document.getElementById("plots");
    main.innerHTML = "";
    const nav = document.getElementById("nav");

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
  })
  .catch(err => {
    document.getElementById("plots").innerHTML =
      '<p class="loading">Failed to load data.json: ' + err + "</p>";
  });
