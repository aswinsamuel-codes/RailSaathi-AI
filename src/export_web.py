"""
Exports everything the RailSaathi AI website (docs/) needs:

* a compact browser model: word + character TF-IDF with multinomial
  logistic regression for category and severity (weights stored as
  integers to keep the file small), run in JavaScript for the live demo
* a 3-D t-SNE map of test complaints for the WebGL "complaint galaxy"
* the headline results of every module
* parity test cases so the JavaScript port can be checked against Python
"""
import json
import shutil

import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.manifold import TSNE
from sklearn.metrics import accuracy_score, f1_score

from common import FIG, HINGLISH_LEXICON, RES, ROOT, SEVERITIES, SMS_LEXICON, load_data, multimodal_text
from generate_dataset import ALL_TAGS
from urgency import COST

WEB = ROOT / "docs"
JS = WEB / "js"
SCALE = 1000  # weights are stored as round(w * SCALE)


def vec_payload(v):
    vocab = sorted(v.vocabulary_, key=v.vocabulary_.get)
    return {"vocab": vocab, "idf": np.round(v.idf_, 4).tolist(), "ngram": list(v.ngram_range), "analyzer": v.analyzer}


def write_js(name, var, obj):
    JS.mkdir(parents=True, exist_ok=True)
    (JS / name).write_text(f"window.{var} = " + json.dumps(obj, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"{name}: {(JS / name).stat().st_size / 1e6:.2f} MB")


def main():
    df = load_data()
    tr, te = df[df["split"] == "train"], df[df["split"] == "test"]
    dtr, dte = multimodal_text(tr), multimodal_text(te)

    word = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, max_features=8000)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=3, sublinear_tf=True, max_features=12000)
    Xtr = hstack([word.fit_transform(dtr), char.fit_transform(dtr)]).tocsr()
    Xte = hstack([word.transform(dte), char.transform(dte)]).tocsr()

    cat = LogisticRegression(C=8, max_iter=3000, class_weight="balanced").fit(Xtr, tr["category"])
    sev = LogisticRegression(C=6, max_iter=3000, class_weight="balanced").fit(Xtr, tr["severity"])
    sev_order = [list(sev.classes_).index(s) for s in SEVERITIES]

    # evaluate the compact model exactly as the browser will use it
    p_cat = cat.predict(Xte)
    p_sev_proba = sev.predict_proba(Xte)[:, sev_order]
    p_sev = np.array(SEVERITIES)[(p_sev_proba @ COST).argmin(1)]
    idx = {s: i for i, s in enumerate(SEVERITIES)}
    t_i = te["severity"].map(idx).values
    s_i = np.array([idx[s] for s in p_sev])
    web_metrics = {
        "category_accuracy": accuracy_score(te["category"], p_cat),
        "category_macro_f1": f1_score(te["category"], p_cat, average="macro"),
        "critical_recall": float(np.mean(s_i[t_i == 0] == 0)),
        "under_triage": float(np.mean(s_i > t_i)),
    }
    print("Browser model:", {k: round(v, 4) for k, v in web_metrics.items()})

    dept_of = df.groupby("category")["department"].agg(lambda s: s.mode()[0]).to_dict()
    model = {
        "word": vec_payload(word), "char": vec_payload(char),
        "scale": SCALE,
        "cat": {"classes": list(cat.classes_), "W": np.round(cat.coef_.T * SCALE).astype(int).tolist(),
                "b": np.round(cat.intercept_, 5).tolist()},
        "sev": {"classes": SEVERITIES, "W": np.round(sev.coef_[sev_order].T * SCALE).astype(int).tolist(),
                "b": np.round(sev.intercept_[sev_order], 5).tolist()},
        "cost": COST.tolist(),
        "dept_of": dept_of,
        "lexicon": {**SMS_LEXICON, **HINGLISH_LEXICON},
        "vision_tags": ALL_TAGS,
        "route_threshold": 0.5,
        "metrics": web_metrics,
    }
    write_js("model-data.js", "RS_MODEL", model)

    # ---------------- parity cases for the JS port ---------------------------
    sample = te.sample(300, random_state=1)
    ds = multimodal_text(sample)
    Xs = hstack([word.transform(ds), char.transform(ds)]).tocsr()
    parity = [{"doc": d, "cat": c, "p": float(p)} for d, c, p in
              zip(ds, cat.predict(Xs), cat.predict_proba(Xs).max(1))]
    (ROOT / "data" / "processed" / "web_parity_cases.json").write_text(json.dumps(parity))

    # ---------------- 3-D complaint galaxy ----------------------------------
    gal = te.sample(2600, random_state=7)
    Xg = Xte[[te.index.get_loc(i) for i in gal.index]]
    emb = TSNE(n_components=3, perplexity=40, init="pca", learning_rate="auto", random_state=0).fit_transform(
        cat.decision_function(Xg))
    emb = (emb - emb.mean(0)) / np.abs(emb).max() * 11
    pred_g = cat.predict(Xg)
    points = [{
        "x": round(float(e[0]), 3), "y": round(float(e[1]), 3), "z": round(float(e[2]), 3),
        "c": r.category, "pc": pc, "s": r.severity, "m": r.media_type, "t": r.complaint_text[:150],
        "tn": r.train_no, "tt": r.train_type,
    } for e, pc, r in zip(emb, pred_g, gal.itertuples())]
    write_js("galaxy-data.js", "RS_GALAXY", {"points": points})

    # ---------------- headline results -------------------------------------
    rd = lambda n: pd.read_csv(RES / n, index_col=0)  # noqa: E731
    rj = lambda n: json.loads((RES / f"{n}.json").read_text())  # noqa: E731
    ov = rd("dataset_overview.csv")["value"]
    q = pd.read_csv(RES / "queue_simulation.csv").pivot(index="Severity", columns="Policy", values="Mean wait (min)")
    dup = pd.read_csv(RES / "duplicate_grouping.csv")
    dup_best = dup[dup["method"] == "text + coach"].sort_values("pair_F1").iloc[-1]
    results = {
        "overview": {k: (float(v) if k not in ("period",) else v) for k, v in ov.items()},
        "categories": df["category"].value_counts().to_dict(),
        "category_models": rd("categorisation_model_comparison.csv")[["Accuracy", "Macro-F1"]].round(4).to_dict("index"),
        "ablation": rd("categorisation_ablation.csv").round(4).to_dict("index"),
        "routing": rj("routing_summary"),
        "urgency": rd("urgency_results.csv")[["Accuracy", "Critical recall", "Under-triage rate", "Mean cost"]].round(4).to_dict("index"),
        "queue": {p: q.loc[SEVERITIES, p].round(1).tolist() for p in q.columns},
        "maintenance": rd("maintenance_forecast.csv").round(3).to_dict("index"),
        "hotspot": rj("hotspot_detection"),
        "duplicates": {"pair_f1": dup_best["pair_F1"], "before": int(dup_best["tickets_before"]),
                       "after": int(dup_best["tickets_after_grouping"]), "true": int(dup_best["true_incidents"])},
        "sentiment": rj("sentiment_results"),
        "sla": rd("sla_breach_model.csv")["ROC-AUC"].round(3).to_dict(),
        "dept": dept_of,
    }
    write_js("results-data.js", "RS_RESULTS", results)

    # figures for the gallery
    (WEB / "assets").mkdir(parents=True, exist_ok=True)
    for f in FIG.glob("*.png"):
        shutil.copy(f, WEB / "assets" / f.name)


if __name__ == "__main__":
    main()
