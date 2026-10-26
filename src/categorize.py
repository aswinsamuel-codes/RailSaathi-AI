"""
Automated categorisation and smart routing.

* Compares classical text classifiers on TF-IDF (word + character n-grams).
* Ablation: plain text -> + Hinglish/SMS normalisation -> + OCR -> + vision tags
  (multimodal fusion), to measure what every input stream contributes.
* Confidence-aware routing: complaints with a low predicted probability are
  sent to a human desk; the rest are auto-routed to the department.
* Robustness on hard sub-groups and inference speed.
"""
import time

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.naive_bayes import ComplementNB
from sklearn.svm import LinearSVC

from common import PROC, RES, load_data, multimodal_text, save_json, savefig

class TextFeaturiser:
    """Word 1-2 grams + character 2-5 grams (robust to typos and Hinglish spellings)."""

    def __init__(self, use_char: bool = True):
        self.use_char = use_char
        self.word = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
        self.char = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True, max_features=60000)

    def fit_transform(self, docs):
        if not self.use_char:
            return self.word.fit_transform(docs)
        return hstack([self.word.fit_transform(docs), self.char.fit_transform(docs)]).tocsr()

    def transform(self, docs):
        if not self.use_char:
            return self.word.transform(docs)
        return hstack([self.word.transform(docs), self.char.transform(docs)]).tocsr()


def get_models():
    return {
        "Complement Naive Bayes": ComplementNB(alpha=0.3),
        "Logistic Regression": LogisticRegression(C=8, max_iter=2000, class_weight="balanced"),
        "Linear SVM (calibrated)": CalibratedClassifierCV(LinearSVC(C=0.5, class_weight="balanced"), cv=3),
        "Random Forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=1, n_jobs=-1, random_state=0,
                                                class_weight="balanced_subsample"),
    }


def evaluate(y, p, dept_of):
    return {
        "Accuracy": accuracy_score(y, p),
        "Macro-F1": f1_score(y, p, average="macro"),
        "Weighted-F1": f1_score(y, p, average="weighted"),
        "Dept. routing acc.": np.mean(pd.Series(y).map(dept_of).values == pd.Series(p).map(dept_of).values),
    }


def main():
    df = load_data()
    dept_of = df.groupby("category")["department"].agg(lambda s: s.mode()[0]).to_dict()
    tr, te = df[df["split"] == "train"], df[df["split"] == "test"]

    # ---------------- 1. model comparison on full multimodal input --------
    feat = TextFeaturiser()
    Xtr = feat.fit_transform(multimodal_text(tr))
    Xte = feat.transform(multimodal_text(te))
    rows, fitted = [], {}
    for name, model in get_models().items():
        t0 = time.perf_counter()
        model.fit(Xtr, tr["category"])
        fit_s = time.perf_counter() - t0
        t0 = time.perf_counter()
        pred = model.predict(Xte)
        lat_ms = 1000 * (time.perf_counter() - t0) / len(te)
        r = evaluate(te["category"].values, pred, dept_of)
        r.update({"Model": name, "Train time (s)": fit_s, "Latency (ms/complaint)": lat_ms})
        rows.append(r)
        fitted[name] = model
        print(name, {k: round(v, 4) for k, v in r.items() if k != "Model"})
    comp = pd.DataFrame(rows).set_index("Model")
    comp.round(4).to_csv(RES / "categorisation_model_comparison.csv")
    best_name = comp["Macro-F1"].idxmax()
    best = fitted[best_name]

    # ---------------- 2. ablation of input streams ---------------------------
    settings = [
        ("Word n-grams, raw text", dict(use_lexicon=False, use_ocr=False, use_vision=False, use_char=False)),
        ("Word n-grams + Hinglish/SMS lexicon", dict(use_lexicon=True, use_ocr=False, use_vision=False, use_char=False)),
        ("+ Character n-grams", dict(use_lexicon=True, use_ocr=False, use_vision=False)),
        ("+ OCR text", dict(use_lexicon=True, use_ocr=True, use_vision=False)),
        ("+ Vision tags (full fusion)", dict(use_lexicon=True, use_ocr=True, use_vision=True)),
    ]
    abl = []
    media_mask = te["media_type"].isin(["photo", "video"]).values
    hing_mask = te["is_hinglish"].values == 1
    for label, kw in settings:
        f = TextFeaturiser(use_char=kw.pop("use_char", True))
        a = f.fit_transform(multimodal_text(tr, **kw))
        b = f.transform(multimodal_text(te, **kw))
        m = LinearSVC(C=0.5, class_weight="balanced").fit(a, tr["category"])
        p = m.predict(b)
        abl.append({"Input": label, "Macro-F1 (all)": f1_score(te["category"], p, average="macro"),
                    "Accuracy (all)": accuracy_score(te["category"], p),
                    "Accuracy (photo/video)": accuracy_score(te["category"][media_mask], p[media_mask]),
                    "Accuracy (Hinglish)": accuracy_score(te["category"][hing_mask], p[hing_mask])})
    abl = pd.DataFrame(abl).set_index("Input")
    abl.round(4).to_csv(RES / "categorisation_ablation.csv")
    print(abl.round(4).to_string())

    # ---------------- 3. per-class performance and confusion matrix ---------
    proba = best.predict_proba(Xte)
    classes = best.classes_
    pred = classes[proba.argmax(1)]
    conf = proba.max(1)
    per_class = pd.DataFrame({
        "F1": f1_score(te["category"], pred, average=None, labels=classes),
        "Support": te["category"].value_counts().reindex(classes).values}, index=classes)
    per_class.round(3).to_csv(RES / "categorisation_per_class.csv")

    cm = confusion_matrix(te["category"], pred, labels=classes, normalize="true")
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    im = ax.imshow(cm, cmap="Blues", vmin=0, vmax=1)
    short = [c.replace(" & ", "/").replace("Equipment", "Equip.").replace("Facilities", "Fac.")
             .replace("Assistance", "Assist.").replace("Maintenance", "Maint.").replace("Availability", "Avail.")
             .replace("Cleanliness", "Clean.").replace("Behaviour", "Behav.") for c in classes]
    ax.set_xticks(range(len(classes)))
    ax.set_xticklabels(short, rotation=55, ha="right", fontsize=9)
    ax.set_yticks(range(len(classes)))
    ax.set_yticklabels(short, fontsize=9)
    for i in range(len(classes)):
        for j in range(len(classes)):
            if cm[i, j] >= 0.01:
                ax.text(j, i, f"{cm[i, j]:.2f}", ha="center", va="center", fontsize=7,
                        color="white" if cm[i, j] > 0.5 else "black")
    ax.set_xlabel("Predicted category")
    ax.set_ylabel("True category")
    ax.grid(False)
    ax.set_title(f"Normalised confusion matrix - {best_name}")
    fig.colorbar(im, ax=ax, fraction=0.046)
    savefig(fig, "fig06_confusion_matrix")

    # ---------------- 4. confidence-aware routing ---------------------------
    correct = pred == te["category"].values
    thr = np.linspace(0, 0.95, 96)
    cov = np.array([np.mean(conf >= t) for t in thr])
    acc = np.array([correct[conf >= t].mean() if np.any(conf >= t) else np.nan for t in thr])
    target = 0.97
    ok = np.where(acc >= target)[0]
    t_star = thr[ok[0]] if len(ok) else thr[-1]
    routing = {
        "best_model": best_name, "target_auto_accuracy": target, "threshold": t_star,
        "auto_routed_share": np.mean(conf >= t_star), "auto_routed_accuracy": correct[conf >= t_star].mean(),
        "human_review_share": np.mean(conf < t_star), "accuracy_without_abstention": correct.mean(),
        "human_review_accuracy_of_model": correct[conf < t_star].mean(),
    }
    # vague complaints are where the model should defer
    save_json(routing, "routing_summary")
    print(routing)

    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.plot(cov * 100, acc * 100, color="#1f4e79", lw=2)
    ax.scatter([routing["auto_routed_share"] * 100], [routing["auto_routed_accuracy"] * 100], color="#c0504d", zorder=3,
               label=f"Threshold {t_star:.2f}: {routing['auto_routed_share'] * 100:.1f}% auto-routed "
                     f"at {routing['auto_routed_accuracy'] * 100:.1f}% accuracy")
    ax.axhline(target * 100, ls="--", color="grey", lw=0.8)
    ax.set_xlabel("Share of complaints routed automatically (%)")
    ax.set_ylabel("Accuracy of auto-routed complaints (%)")
    ax.set_title("Coverage-accuracy trade-off of confidence-aware routing")
    ax.legend(loc="lower left")
    savefig(fig, "fig07_routing_tradeoff")

    # ---------------- 5. robustness on hard sub-groups ---------------------
    groups = {
        "All test complaints": np.ones(len(te), bool),
        "Typed text": (te["media_type"] == "text").values,
        "Photo/video": media_mask,
        "Audio (ASR transcript)": (te["media_type"] == "audio").values,
        "Hinglish": hing_mask,
        "Mixed (contains 'also')": te["complaint_text"].str.contains(" also ", case=False).values,
    }
    rob = pd.DataFrame({g: {"n": m.sum(), "Accuracy": correct[m].mean(), "Mean confidence": conf[m].mean()}
                        for g, m in groups.items()}).T
    rob.round(4).to_csv(RES / "categorisation_robustness.csv")
    print(rob.round(3).to_string())

    # save predictions for later modules
    out = te[["complaint_id"]].copy()
    out["pred_category"] = pred
    out["pred_confidence"] = conf
    for i, c in enumerate(classes):
        out[f"p_{c}"] = proba[:, i]
    out.to_csv(PROC / "test_category_predictions.csv", index=False)

    # ---------------- 6. model comparison figure ----------------------------
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    x = np.arange(len(comp))
    ax.bar(x - 0.2, comp["Accuracy"] * 100, 0.4, label="Accuracy")
    ax.bar(x + 0.2, comp["Macro-F1"] * 100, 0.4, label="Macro-F1")
    for i, (a, f) in enumerate(zip(comp["Accuracy"], comp["Macro-F1"])):
        ax.text(i - 0.2, a * 100 + 0.5, f"{a * 100:.1f}", ha="center", fontsize=8)
        ax.text(i + 0.2, f * 100 + 0.5, f"{f * 100:.1f}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(comp.index, fontsize=9)
    ax.set_ylim(comp[["Accuracy", "Macro-F1"]].min().min() * 100 - 8, 100)
    ax.set_ylabel("Score (%)")
    ax.set_title("Complaint categorisation: model comparison (test set)")
    ax.legend(loc="lower right")
    savefig(fig, "fig08_model_comparison")


if __name__ == "__main__":
    main()
