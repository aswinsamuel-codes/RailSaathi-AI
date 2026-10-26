/*
 * RailSaathi AI - in-browser inference.
 * A faithful JavaScript port of the Python pipeline: text normalisation,
 * scikit-learn TfidfVectorizer (word + char_wb, sublinear tf, l2 norm),
 * multinomial logistic regression, the minimum-expected-cost severity rule,
 * confidence-aware routing and regex entity extraction.
 */
(function (root) {
  "use strict";

  function normalise(text, lex) {
    let t = String(text || "").toLowerCase();
    t = t.replace(/@\w+/g, " ");
    t = t.replace(/\b\d{10}\b/g, " pnrnum ");
    t = t.replace(/\b\d{5}\b/g, " trainnum ");
    const toks = t.match(/[a-z]+|\d+/g) || [];
    return toks.map((w) => (lex[w] !== undefined ? lex[w] : w)).join(" ");
  }

  function fuseDocument(text, ocr, tags, lex) {
    let doc = normalise(text, lex);
    const o = normalise(ocr || "", lex);
    if (o) doc += " " + o.split(" ").map((w) => "ocr_" + w).join(" ");
    if (tags && tags.length) doc += " " + tags.map((g) => "img_" + g.replace(/ /g, "_")).join(" ");
    return doc.trim();
  }

  // --- scikit-learn analyzers ------------------------------------------------
  function wordNgrams(doc, lo, hi) {
    const toks = doc.match(/\b\w\w+\b/g) || [];
    const out = [];
    for (let n = lo; n <= hi; n++) {
      for (let i = 0; i + n <= toks.length; i++) out.push(toks.slice(i, i + n).join(" "));
    }
    return out;
  }

  function charWbNgrams(doc, lo, hi) {
    const text = doc.replace(/\s\s+/g, " ");
    const out = [];
    for (const raw of text.split(/\s+/)) {
      if (!raw) continue;
      const w = " " + raw + " ";
      const L = w.length;
      for (let n = lo; n <= hi; n++) {
        let off = 0;
        out.push(w.slice(off, off + n));
        while (off + n < L) {
          off += 1;
          out.push(w.slice(off, off + n));
        }
        if (off === 0) break;
      }
    }
    return out;
  }

  class Vectorizer {
    constructor(p) {
      this.idf = p.idf;
      this.lo = p.ngram[0];
      this.hi = p.ngram[1];
      this.isChar = p.analyzer === "char_wb";
      this.index = new Map(p.vocab.map((v, i) => [v, i]));
    }
    transform(doc) {
      const grams = this.isChar ? charWbNgrams(doc, this.lo, this.hi) : wordNgrams(doc, this.lo, this.hi);
      const tf = new Map();
      for (const g of grams) {
        const j = this.index.get(g);
        if (j !== undefined) tf.set(j, (tf.get(j) || 0) + 1);
      }
      let norm = 0;
      const vec = [];
      for (const [j, c] of tf) {
        const v = (1 + Math.log(c)) * this.idf[j];
        vec.push([j, v]);
        norm += v * v;
      }
      norm = Math.sqrt(norm) || 1;
      return vec.map(([j, v]) => [j, v / norm]);
    }
  }

  function softmax(z) {
    const m = Math.max(...z);
    const e = z.map((v) => Math.exp(v - m));
    const s = e.reduce((a, b) => a + b, 0);
    return e.map((v) => v / s);
  }

  // --- entity extraction (same patterns as extraction_dedup.py) ----------------
  const TRAIN_RE = /\b(?:train|trn|tr)\s*(?:no\.?|number)?\s*(\d{5})\b|\b(\d{5})\b/i;
  const COACH_RE = /\b(?:coach|coch)\s*([A-Z]{1,3}\d{0,2})\b|\b([SBAHCDE]\d{1,2})\b(?=\s*(?:\/|\d{5}))/i;
  const PNR_RE = /\b(\d{10})\b/;
  const firstGroup = (m) => (m ? m.slice(1).find((g) => g) || null : null);

  function extractEntities(text) {
    const coach = firstGroup(text.match(COACH_RE));
    return {
      train_no: firstGroup(text.match(TRAIN_RE)),
      coach: coach ? coach.toUpperCase() : null,
      pnr: firstGroup(text.match(PNR_RE)),
    };
  }

  class RailSaathi {
    constructor(data) {
      this.d = data;
      this.word = new Vectorizer(data.word);
      this.char = new Vectorizer(data.char);
      this.nWord = data.word.vocab.length;
    }
    features(doc) {
      const w = this.word.transform(doc);
      const c = this.char.transform(doc).map(([j, v]) => [j + this.nWord, v]);
      return w.concat(c);
    }
    linear(x, head) {
      const k = head.b.length;
      const z = head.b.slice();
      const s = this.d.scale;
      for (const [j, v] of x) {
        const row = head.W[j];
        for (let c = 0; c < k; c++) z[c] += (row[c] / s) * v;
      }
      return softmax(z);
    }
    predict(text, ocr, tags) {
      const doc = fuseDocument(text, ocr, tags, this.d.lexicon);
      const x = this.features(doc);
      const pc = this.linear(x, this.d.cat);
      const ps = this.linear(x, this.d.sev);
      const cats = this.d.cat.classes.map((c, i) => ({ label: c, p: pc[i] })).sort((a, b) => b.p - a.p);
      // minimum expected cost: argmin_k sum_j p(j) * C[j][k]
      const C = this.d.cost;
      const exp = C[0].map((_, k) => ps.reduce((acc, p, j) => acc + p * C[j][k], 0));
      const sevIdx = exp.indexOf(Math.min(...exp));
      const argmaxSev = ps.indexOf(Math.max(...ps));
      const top = cats[0];
      return {
        doc,
        nFeatures: x.length,
        category: top.label,
        confidence: top.p,
        department: this.d.dept_of[top.label],
        categories: cats,
        severity: this.d.sev.classes[sevIdx],
        severityArgmax: this.d.sev.classes[argmaxSev],
        severityProba: this.d.sev.classes.map((s, i) => ({ label: s, p: ps[i] })),
        expectedCost: exp,
        route: top.p >= this.d.route_threshold ? "auto" : "human",
        entities: extractEntities(text + " " + (ocr || "")),
      };
    }
  }

  const api = { RailSaathi, normalise, fuseDocument, wordNgrams, charWbNgrams, extractEntities };
  root.RailSaathiAI = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
