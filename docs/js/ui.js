/* RailSaathi AI - page interactions (demo, charts, counters, gallery, tilt). */
(function () {
  "use strict";

  const COLORS = {
    "Coach Cleanliness": "#34d399",
    "Electrical Equipment": "#facc15",
    "Water Availability": "#38bdf8",
    "Coach Maintenance": "#a78bfa",
    "Punctuality": "#94a3b8",
    "Catering & Vending": "#fb923c",
    "Bed Roll": "#f0abfc",
    "Security": "#f43f5e",
    "Staff Behaviour": "#e879f9",
    "Refund & Ticketing": "#5eead4",
    "Medical Assistance": "#ef4444",
    "Women Safety": "#ec4899",
    "Divyangjan Facilities": "#22d3ee",
  };
  window.RS_COLORS = COLORS;

  const $ = (s, r = document) => r.querySelector(s);
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const finePointer = window.matchMedia("(pointer: fine)").matches;
  const R = window.RS_RESULTS;
  const model = new window.RailSaathiAI.RailSaathi(window.RS_MODEL);
  const pct = (v, d = 1) => (100 * v).toFixed(d) + "%";

  // ---------------------------------------------------------------- demo ----
  const EXAMPLES = [
    ["AC failure", "AC not working since 5 hours in coach B3 of train 12951, it is very hot, please help"],
    ["Medical emergency", "my father is having severe chest pain in coach S4, need doctor immediately"],
    ["Hinglish", "toilet me pani nahi hai 6 ghante se, coach S2 pls help"],
    ["Bribe", "TTE asking Rs 500 without receipt for confirming berth"],
    ["Overcharging", "vendor charging more than MRP for water bottle", "MRP Rs 20 PACKAGED DRINKING WATER", ["water bottle", "bill"]],
    ["Vague (photo only)", "please look into this", "", ["garbage", "dirty floor"]],
    ["Women safety", "a man is harassing a girl travelling alone in coach B2, send help"],
  ];
  const exWrap = $("#examples");
  const tagWrap = $("#tags");
  const tagState = new Set();

  window.RS_MODEL.vision_tags.forEach((t) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = t;
    b.setAttribute("aria-pressed", "false");
    b.addEventListener("click", () => {
      tagState.has(t) ? tagState.delete(t) : tagState.add(t);
      b.setAttribute("aria-pressed", String(tagState.has(t)));
    });
    tagWrap.appendChild(b);
  });
  function setTags(list) {
    tagState.clear();
    (list || []).forEach((t) => tagState.add(t));
    tagWrap.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(tagState.has(b.textContent))));
  }

  EXAMPLES.forEach(([label, text, ocr, tags]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.addEventListener("click", () => {
      $("#complaint").value = text;
      $("#ocr").value = ocr || "";
      setTags(tags);
      if (ocr || (tags && tags.length)) $(".media").open = true;
      analyse();
    });
    exWrap.appendChild(b);
  });

  function analyse() {
    const text = $("#complaint").value.trim();
    const ocr = $("#ocr").value.trim();
    const tags = [...tagState];
    if (!text && !ocr && !tags.length) {
      $("#complaint").focus();
      return;
    }
    const t0 = performance.now();
    const r = model.predict(text, ocr, tags);
    const ms = performance.now() - t0;

    $("#result").hidden = false;
    $("#r-cat").textContent = r.category;
    $("#r-cat").style.color = COLORS[r.category];
    $("#r-dept").textContent = "Department: " + r.department;
    const sev = $("#r-sev");
    sev.textContent = r.severity;
    sev.className = "sev " + r.severity;
    $("#r-sev-note").textContent = r.severity !== r.severityArgmax
      ? `Raised from ${r.severityArgmax} by the cost-aware rule`
      : "Minimum expected cost";

    const route = $("#r-route");
    route.className = "route " + r.route;
    route.innerHTML = r.route === "auto"
      ? `<b>Auto-routed</b> to the ${r.department} department (confidence ${pct(r.confidence)}).`
      : `<b>Sent to the human review desk</b>: confidence is only ${pct(r.confidence)}, below the ${pct(window.RS_MODEL.route_threshold, 0)} threshold.`;

    const bars = $("#r-bars");
    bars.innerHTML = "";
    r.categories.slice(0, 5).forEach((c) => {
      const row = document.createElement("div");
      row.className = "bar";
      row.innerHTML = `<span>${c.label}</span><span class="track"><span class="fill" style="--c:${COLORS[c.label]}"></span></span><span class="pv">${pct(c.p)}</span>`;
      bars.appendChild(row);
      requestAnimationFrame(() => requestAnimationFrame(() => { row.querySelector(".fill").style.width = (100 * c.p).toFixed(1) + "%"; }));
    });

    const e = r.entities;
    $("#r-entities").innerHTML = [["Train", e.train_no], ["Coach", e.coach], ["PNR", e.pnr]]
      .map(([k, v]) => (v ? `<span>${k}: ${v}</span>` : `<span class="miss">${k}: not found</span>`)).join("");
    $("#r-meta").textContent = `Analysed in ${ms.toFixed(1)} ms in your browser · ${r.nFeatures} active TF-IDF features · nothing is sent to a server.`;

    window.dispatchEvent(new CustomEvent("rs:classified", { detail: r }));
  }
  $("#analyse").addEventListener("click", analyse);
  // shareable demo links: index.html?q=<complaint text>
  // add &shot=1 to show the demo at the top without scrolling (used for report screenshots)
  const params = new URLSearchParams(location.search);
  const q = params.get("q");
  if (params.get("shot")) document.body.classList.add("shot");
  if (q) {
    $("#complaint").value = q;
    analyse();
    if (!params.get("shot")) $("#demo").scrollIntoView({ behavior: "auto" });
  }
  $("#complaint").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) analyse();
  });

  // ------------------------------------------------------------- counters ----
  const counterIO = new IntersectionObserver((entries) => {
    entries.forEach((en) => {
      if (!en.isIntersecting) return;
      const el = en.target;
      counterIO.unobserve(el);
      const target = parseFloat(el.dataset.count);
      const dec = (el.dataset.count.split(".")[1] || "").length;
      const suf = el.dataset.suffix || "";
      if (reduceMotion) { el.textContent = target.toFixed(dec) + suf; return; }
      const t0 = performance.now();
      const step = (now) => {
        const k = Math.max(0, Math.min(1, (now - t0) / 1400));
        const v = target * (1 - Math.pow(1 - k, 3));
        el.textContent = v.toFixed(dec) + suf;
        if (k < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    });
  }, { threshold: 0.5 });

  // --------------------------------------------------------------- charts ----
  const NS = "http://www.w3.org/2000/svg";
  const el = (tag, attrs, parent) => {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  };
  const tween = (from, to, dur, fn) => {
    if (reduceMotion) return fn(to);
    const t0 = performance.now();
    const step = (now) => {
      const k = Math.max(0, Math.min(1, (now - t0) / dur));
      fn(from + (to - from) * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  };

  /** Horizontal grouped bar chart. rows: [{label, values:[...]}] */
  function hbars(container, rows, series, colors, { min = 0, max = 1, fmt = (v) => pct(v), labelW = 170 } = {}) {
    const W = 520, rowH = 16 * series.length + 18, top = 26;
    const H = top + rows.length * rowH;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
    series.forEach((s, i) => {
      el("rect", { x: labelW + i * 130, y: 4, width: 10, height: 10, rx: 2, fill: colors[i] }, svg);
      el("text", { x: labelW + 16 + i * 130, y: 13 }, svg).textContent = s;
    });
    const scale = (v) => ((Math.max(min, v) - min) / (max - min)) * (W - labelW - 56);
    rows.forEach((r, ri) => {
      const y0 = top + ri * rowH;
      el("text", { x: 0, y: y0 + (16 * series.length) / 2 + 4 }, svg).textContent = r.label;
      r.values.forEach((v, si) => {
        const y = y0 + si * 16;
        const rect = el("rect", { class: "b", x: labelW, y, height: 12, rx: 3, width: 0, fill: colors[si] }, svg);
        const t = el("text", { class: "val", x: labelW + 4, y: y + 10 }, svg);
        t.textContent = fmt(v);
        el("title", {}, rect).textContent = `${r.label} - ${series[si]}: ${fmt(v)}`;
        container._anim = container._anim || [];
        container._anim.push(() => tween(0, scale(v), 900, (w) => {
          rect.setAttribute("width", w);
          t.setAttribute("x", labelW + w + 6);
        }));
      });
    });
    container.appendChild(svg);
  }

  function animateOnView(container) {
    const io = new IntersectionObserver((ents) => {
      if (ents[0].isIntersecting) { io.disconnect(); (container._anim || []).forEach((f) => f()); }
    }, { threshold: 0.3 });
    io.observe(container);
  }

  // model comparison
  const cm = R.category_models;
  const cmBox = $("#chart-models");
  hbars(cmBox, Object.keys(cm).map((k) => ({ label: k, values: [cm[k]["Accuracy"], cm[k]["Macro-F1"]] })),
    ["Accuracy", "Macro-F1"], ["#22d3ee", "#f59e0b"], { min: 0.85, max: 0.97, fmt: (v) => pct(v), labelW: 180 });
  animateOnView(cmBox);

  // ablation (photo/video accuracy)
  const ab = R.ablation;
  const abBox = $("#chart-ablation");
  hbars(abBox, Object.keys(ab).map((k) => ({ label: k.replace("Word n-grams", "Words").replace(" (full fusion)", ""), values: [ab[k]["Accuracy (all)"], ab[k]["Accuracy (photo/video)"]] })),
    ["All complaints", "Photo/video"], ["#22d3ee", "#f59e0b"], { min: 0.9, max: 0.97, labelW: 210 });
  animateOnView(abBox);

  // urgency
  const ug = R.urgency;
  const uKeys = ["Logistic Regression (arg-max)", "LR + minimum expected cost (proposed)"];
  const ugBox = $("#chart-urgency");
  hbars(ugBox, [
    { label: "Accuracy", values: uKeys.map((k) => ug[k]["Accuracy"]) },
    { label: "Critical recall", values: uKeys.map((k) => ug[k]["Critical recall"]) },
    { label: "Under-triage rate", values: uKeys.map((k) => ug[k]["Under-triage rate"]) },
  ], ["Arg-max", "Cost-aware (proposed)"], ["#64748b", "#34d399"], { min: 0, max: 1, labelW: 150 });
  animateOnView(ugBox);

  // queue chart with policy switch
  const qBox = $("#chart-queue");
  const sevs = ["Critical", "High", "Medium", "Low"];
  const sevColors = ["#f43f5e", "#f59e0b", "#22d3ee", "#94a3b8"];
  const policies = Object.keys(R.queue);
  const qmax = Math.max(...policies.flatMap((p) => R.queue[p]));
  const QW = 520, QH = 240, base = 205;
  const qsvg = el("svg", { viewBox: `0 0 ${QW} ${QH}`, role: "img" });
  const qbars = sevs.map((s, i) => {
    const x = 40 + i * 120;
    const rect = el("rect", { x, y: base, width: 80, height: 0, rx: 6, fill: sevColors[i] }, qsvg);
    const val = el("text", { class: "val", x: x + 40, y: base - 6, "text-anchor": "middle" }, qsvg);
    el("text", { x: x + 40, y: base + 22, "text-anchor": "middle" }, qsvg).textContent = s;
    return { rect, val, h: 0 };
  });
  el("line", { x1: 20, x2: QW - 10, y1: base, y2: base, stroke: "rgba(148,178,220,.3)" }, qsvg);
  qBox.appendChild(qsvg);
  function showPolicy(p) {
    $("#queue-seg").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.p === p));
    R.queue[p].forEach((v, i) => {
      const b = qbars[i];
      const target = (v / qmax) * 175;
      tween(b.h, target, 700, (h) => {
        b.h = h;
        b.rect.setAttribute("y", base - h);
        b.rect.setAttribute("height", h);
        b.val.setAttribute("y", base - h - 6);
      });
      b.val.textContent = v.toFixed(0) + " min";
    });
  }
  const order = ["FIFO (current)", "AI priority (proposed)", "Oracle priority (upper bound)"].filter((p) => policies.includes(p));
  order.forEach((p) => {
    const b = document.createElement("button");
    b.type = "button";
    b.dataset.p = p;
    b.textContent = p.replace(" (upper bound)", "").replace(" (proposed)", "").replace(" (current)", "");
    b.addEventListener("click", () => showPolicy(p));
    $("#queue-seg").appendChild(b);
  });
  const qio = new IntersectionObserver((ents) => {
    if (ents[0].isIntersecting) {
      qio.disconnect();
      showPolicy(order[0]);
      if (!reduceMotion) setTimeout(() => showPolicy(order[1]), 1600);
    }
  }, { threshold: 0.4 });
  qio.observe(qBox);

  // stat row
  const mf = R.maintenance;
  const devCut = 1 - mf["Gradient Boosting (Poisson)"]["Poisson deviance"] / mf["Naive (last week)"]["Poisson deviance"];
  const stats = [
    [(100 * devCut).toFixed(0), "%", "lower forecast error than a naive weekly guess"],
    [(100 * R.hotspot.precision_at_k_deteriorating).toFixed(0), "%", `of flagged trains truly deteriorating (${(100 * R.hotspot.random_baseline).toFixed(0)}% by chance)`],
    [R.duplicates.pair_f1.toFixed(2), "", `duplicate-grouping F1: ${R.duplicates.before.toLocaleString()} reports to ${R.duplicates.after.toLocaleString()} tickets`],
    [(100 * R.sentiment.accuracy).toFixed(1), "%", "feedback sentiment accuracy"],
  ];
  $("#stat-row").innerHTML = stats.map(([n, s, t]) =>
    `<div class="glass stat"><span class="num" data-count="${n}" data-suffix="${s}">0</span><span>${t}</span></div>`).join("");
  document.querySelectorAll("[data-count]").forEach((n) => counterIO.observe(n));

  // -------------------------------------------------------------- gallery ----
  const FIGS = [
    ["fig01_architecture", "RailSaathi AI pipeline architecture"],
    ["fig02_category_severity", "Complaint volume by category and severity"],
    ["fig03_seasonality", "Seasonality of complaint categories"],
    ["fig06_confusion_matrix", "Confusion matrix of the calibrated linear SVM"],
    ["fig07_routing_tradeoff", "Coverage vs accuracy of confidence-aware routing"],
    ["fig09_urgency_queue", "Cost-aware urgency and queue simulation"],
    ["fig10_duplicate_grouping", "Duplicate-incident grouping"],
    ["fig11_maintenance_forecast", "Predictive maintenance forecasts"],
    ["fig12_sla_sentiment", "SLA-breach drivers and monitoring KPIs"],
    ["fig04_operations", "Resolution time and SLA breach by zone"],
    ["fig05_media_hour", "Complaint timing and media types"],
    ["fig08_model_comparison", "Categorisation model comparison"],
  ];
  const lb = $("#lightbox");
  $("#gallery").innerHTML = FIGS.map(([f, c]) =>
    `<button type="button" data-f="${f}" data-c="${c}" aria-label="Open figure: ${c}"><img loading="lazy" src="assets/${f}.png" alt="${c}"></button>`).join("");
  $("#gallery").addEventListener("click", (ev) => {
    const b = ev.target.closest("button");
    if (!b) return;
    lb.querySelector("img").src = `assets/${b.dataset.f}.png`;
    lb.querySelector("img").alt = b.dataset.c;
    lb.querySelector("p").textContent = b.dataset.c;
    lb.showModal();
  });
  $("#lb-close").addEventListener("click", () => lb.close());
  lb.addEventListener("click", (ev) => { if (ev.target === lb) lb.close(); });

  // ------------------------------------------------------------ 3D tilt ----
  if (finePointer && !reduceMotion) {
    document.querySelectorAll(".tilt").forEach((card) => {
      card.addEventListener("pointermove", (ev) => {
        const r = card.getBoundingClientRect();
        const x = (ev.clientX - r.left) / r.width, y = (ev.clientY - r.top) / r.height;
        card.style.transform = `rotateY(${(x - 0.5) * 14}deg) rotateX(${(0.5 - y) * 12}deg) translateZ(6px)`;
        card.style.setProperty("--mx", `${x * 100}%`);
        card.style.setProperty("--my", `${y * 100}%`);
      });
      card.addEventListener("pointerleave", () => { card.style.transform = ""; });
    });
  }
})();
