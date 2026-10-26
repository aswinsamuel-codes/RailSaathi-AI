"""
Urgency detection and prioritisation.

* Severity (Critical / High / Medium / Low) is predicted from the fused
  complaint text and metadata.
* Under-prioritising an emergency is far worse than over-prioritising a
  minor issue, so an asymmetric cost matrix is defined and the class with
  the minimum expected cost is chosen (Bayes decision rule) instead of the
  most probable class.
* A small safety lexicon is tested as an extra guard-rail that escalates
  life-safety keywords to Critical.
* A discrete-event queue simulation compares first-come-first-served
  handling with AI-prioritised handling.
"""
import heapq

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import cohen_kappa_score, f1_score, recall_score
from sklearn.preprocessing import OneHotEncoder
from sklearn.svm import LinearSVC

from common import PROC, RES, SEVERITIES, load_data, multimodal_text, save_json, savefig

# cost[true][pred]; rows/cols ordered Critical, High, Medium, Low
COST = np.array([
    [0, 4, 9, 16],
    [1, 0, 3, 6],
    [1, 1, 0, 2],
    [1, 1, 1, 0],
], dtype=float)

SAFETY_LEXICON = ["chest pain", "unconscious", "not responding", "fainted", "bleeding", "labour pain", "breathing",
                  "fits", "smoke", "sparks", "fire", "short circuit", "knife", "armed", "touched me", "harassing",
                  "stalked", "send help", "door is not closing", "fell on a passenger", "stone pelting"]


def features(tr, te):
    word = TfidfVectorizer(ngram_range=(1, 3), min_df=2, sublinear_tf=True)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=3, sublinear_tf=True, max_features=50000)
    meta_cols = ["media_type", "channel", "train_type", "is_night"]
    enc = OneHotEncoder(handle_unknown="ignore")
    dtr, dte = multimodal_text(tr), multimodal_text(te)
    Xtr = hstack([word.fit_transform(dtr), char.fit_transform(dtr), enc.fit_transform(tr[meta_cols].astype(str))]).tocsr()
    Xte = hstack([word.transform(dte), char.transform(dte), enc.transform(te[meta_cols].astype(str))]).tocsr()
    return Xtr, Xte


def score(y_true, y_pred, name):
    idx = {s: i for i, s in enumerate(SEVERITIES)}
    t = np.array([idx[s] for s in y_true])
    p = np.array([idx[s] for s in y_pred])
    return {
        "Method": name,
        "Accuracy": np.mean(t == p),
        "Macro-F1": f1_score(t, p, average="macro"),
        "Quadratic kappa": cohen_kappa_score(t, p, weights="quadratic"),
        "Critical recall": recall_score(t, p, labels=[0], average="macro"),
        "Critical+High recall": np.mean(p[t <= 1] <= 1),
        "Under-triage rate": np.mean(p > t),
        "Mean cost": COST[t, p].mean(),
    }


def safety_override(texts: pd.Series, pred: np.ndarray) -> np.ndarray:
    pattern = "|".join(SAFETY_LEXICON)
    hit = texts.str.lower().str.contains(pattern, regex=True).values
    out = pred.copy()
    out[hit] = "Critical"
    return out


def simulate_queue(arrivals, service, priority, servers=1):
    """Non-pre-emptive priority queue; returns waiting time (minutes) per job."""
    order = np.argsort(arrivals)
    free = [0.0] * servers  # time at which each server becomes free
    waiting = np.zeros(len(arrivals))
    queue, i, n = [], 0, len(arrivals)
    while i < n or queue:
        t = free[0] if queue else max(free[0], arrivals[order[i]])
        while i < n and arrivals[order[i]] <= t:  # everyone who has arrived joins the queue
            j = order[i]
            heapq.heappush(queue, (priority[j], arrivals[j], j))
            i += 1
        _, arr, j = heapq.heappop(queue)
        start = max(heapq.heappop(free), arr)
        waiting[j] = start - arr
        heapq.heappush(free, start + service[j])
    return waiting


def main():
    df = load_data()
    tr, te = df[df["split"] == "train"], df[df["split"] == "test"]
    Xtr, Xte = features(tr, te)
    ytr, yte = tr["severity"].values, te["severity"].values

    lr = LogisticRegression(C=6, max_iter=3000, class_weight="balanced").fit(Xtr, ytr)
    svm = LinearSVC(C=0.4, class_weight="balanced").fit(Xtr, ytr)
    proba = pd.DataFrame(lr.predict_proba(Xte), columns=lr.classes_)[SEVERITIES].values
    expected_cost = proba @ COST  # expected cost of predicting each class
    p_lr = np.array(SEVERITIES)[proba.argmax(1)]
    p_cost = np.array(SEVERITIES)[expected_cost.argmin(1)]
    p_hybrid = safety_override(te["complaint_text"], p_cost)
    p_lex = safety_override(te["complaint_text"], np.full(len(te), "Medium", dtype=object))

    rows = [
        score(yte, p_lex, "Keyword rules only"),
        score(yte, svm.predict(Xte), "Linear SVM"),
        score(yte, p_lr, "Logistic Regression (arg-max)"),
        score(yte, p_cost, "LR + minimum expected cost (proposed)"),
        score(yte, p_hybrid, "LR + min. cost + safety lexicon"),
    ]
    res = pd.DataFrame(rows).set_index("Method")
    res.round(4).to_csv(RES / "urgency_results.csv")
    print(res.round(3).to_string())

    # confusion of the proposed method
    cm = pd.crosstab(pd.Categorical(yte, SEVERITIES), pd.Categorical(p_cost, SEVERITIES),
                     rownames=["True"], colnames=["Predicted"], dropna=False)
    cm.to_csv(RES / "urgency_confusion.csv")

    # ---------------- queue simulation -----------------------------------
    rng = np.random.default_rng(7)
    arrivals = ((te["timestamp"] - te["timestamp"].min()).dt.total_seconds() / 60).values
    service = rng.exponential(30, len(te))  # 30-min average handling per complaint at a triage desk
    rank = {s: i for i, s in enumerate(SEVERITIES)}
    policies = {
        "FIFO (current)": np.zeros(len(te)),
        "AI priority (proposed)": np.array([rank[s] for s in p_cost]),
        "Oracle priority (upper bound)": np.array([rank[s] for s in yte]),
    }
    q = []
    for name, prio in policies.items():
        w = simulate_queue(arrivals, service, prio, servers=1)
        for s in SEVERITIES:
            m = yte == s
            q.append({"Policy": name, "Severity": s, "Mean wait (min)": w[m].mean(), "P90 wait (min)": np.percentile(w[m], 90)})
    q = pd.DataFrame(q)
    q.round(1).to_csv(RES / "queue_simulation.csv", index=False)
    print(q.pivot(index="Policy", columns="Severity", values="Mean wait (min)")[SEVERITIES].round(1).to_string())
    util = service.sum() / (arrivals.max() - arrivals.min())

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    show = res.loc[["Linear SVM", "Logistic Regression (arg-max)", "LR + minimum expected cost (proposed)"]]
    metrics = ["Accuracy", "Critical recall", "Critical+High recall", "Under-triage rate"]
    x = np.arange(len(metrics))
    axes[0].set_ylim(0, 118)
    for k, (name, r) in enumerate(show.iterrows()):
        axes[0].bar(x + (k - 1) * 0.27, r[metrics] * 100, 0.27,
                    label=name.replace("Logistic Regression", "LR").replace(" (proposed)", "*"))
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["Accuracy", "Critical\nrecall", "Critical+High\nrecall", "Under-triage\nrate"], fontsize=9)
    axes[0].set_ylabel("%")
    axes[0].set_title("(a) Severity prediction: effect of cost-aware decisions")
    axes[0].legend(fontsize=8, loc="upper center", ncol=3)

    piv = q.pivot(index="Severity", columns="Policy", values="Mean wait (min)").loc[SEVERITIES]
    x = np.arange(len(SEVERITIES))
    for k, col in enumerate(policies):
        axes[1].bar(x + (k - 1) * 0.27, piv[col], 0.27, label=col)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(SEVERITIES)
    axes[1].set_ylabel("Mean waiting time (min)")
    axes[1].set_title(f"(b) Queue simulation (desk utilisation {util:.0%})")
    axes[1].legend(fontsize=8)
    savefig(fig, "fig09_urgency_queue")

    save_json({"desk_utilisation": util, "critical_wait_fifo": piv.loc["Critical", "FIFO (current)"],
               "critical_wait_ai": piv.loc["Critical", "AI priority (proposed)"]}, "queue_summary")
    pd.DataFrame({"complaint_id": te["complaint_id"].values, "pred_severity": p_cost}).to_csv(
        PROC / "test_severity_predictions.csv", index=False)


if __name__ == "__main__":
    main()
