// Checks that the JavaScript model reproduces the Python model's predictions.
// Usage: node docs/js/parity_test.js
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const here = __dirname;
const ctx = { window: {} };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(here, "model-data.js"), "utf8"), ctx);
const { RailSaathi } = require("./model.js");
const model = new RailSaathi(ctx.window.RS_MODEL);

const cases = JSON.parse(fs.readFileSync(path.join(here, "..", "..", "data", "processed", "web_parity_cases.json"), "utf8"));
let agree = 0;
let maxDiff = 0;
for (const c of cases) {
  // the parity docs are already fused, so feed them straight to the linear head
  const x = model.features(c.doc);
  const p = model.linear(x, model.d.cat);
  const best = p.indexOf(Math.max(...p));
  if (model.d.cat.classes[best] === c.cat) agree++;
  maxDiff = Math.max(maxDiff, Math.abs(p[best] - c.p));
}
console.log(`Category agreement: ${agree}/${cases.length}  max |p_js - p_py| = ${maxDiff.toFixed(4)}`);
process.exit(agree === cases.length ? 0 : 1);
