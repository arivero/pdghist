// Smoke test: run docs/app.js against docs/data.json with a minimal DOM stub
// and render every card. Usage: node tests/site_smoke.js [--strip-diagnostics]
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.join(__dirname, "..");
const data = JSON.parse(fs.readFileSync(path.join(root, "docs", "data.json"), "utf8"));
const strip = process.argv.includes("--strip-diagnostics");
if (strip) for (const q of data.quantities) {
  delete q.history_diagnostics;
  for (const sk in q.series) for (const p of q.series[sk]) {
    delete p.error_envelope; delete p.uncertainty_model; delete p.inputs;
    delete p.provenance_notes;
  }
}

let nodes = 0;
function makeNode(tag) {
  nodes++;
  return {
    tag, children: [], attrs: {}, style: {}, listeners: {},
    textContent: "", innerHTML: "", className: "", id: "",
    appendChild(c) { this.children.push(c); return c; },
    setAttribute(k, v) { this.attrs[k] = v; },
    addEventListener(t, f) { this.listeners[t] = f; },
  };
}
const byId = {};
const document = {
  createElement: makeNode,
  createElementNS: (_ns, tag) => makeNode(tag),
  getElementById: id => (byId[id] = byId[id] || makeNode("div")),
  body: makeNode("body"),
};
let done;
const finished = new Promise(r => { done = r; });
const ctx = {
  document, console, URL, URLSearchParams, Math, JSON, Number, String, Object,
  Set, Array, parseInt, isFinite,
  location: { search: "", href: "http://localhost/index.html", pathname: "/index.html" },
  localStorage: { getItem: () => null, setItem: () => {} },
  fetch: () => Promise.resolve({ json: () => Promise.resolve(data) }),
};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(root, "docs", "app.js"), "utf8"), ctx);
setTimeout(() => done(), 50);
finished.then(() => {
  const plots = byId.plots;
  if (!plots || /Failed/.test(plots.innerHTML)) {
    console.error("render failed:", plots && plots.innerHTML);
    process.exit(1);
  }
  let cards = 0, diags = 0, tips = 0;
  const walk = n => {
    if (n.className === "card") cards++;
    if (n.className === "diagnostics") diags++;
    if (n.listeners && n.listeners.mousemove) {
      n.listeners.mousemove({ clientX: 0, clientY: 0 }); tips++;
    }
    (n.children || []).forEach(walk);
  };
  walk(plots);
  console.log(`cards=${cards} diagnostics=${diags} tooltips=${tips} nodes=${nodes}`);
  if (cards !== data.quantities.length) process.exit(1);
});
