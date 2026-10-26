"""
Feedback sentiment analysis, SLA-breach early warning and performance
monitoring.

* Sentiment (positive / neutral / negative) is learned from the
  complainants' free-text feedback; labels come from their star rating.
* SLA-breach risk is predicted at registration time so that supervisors
  can intervene before the deadline is missed.
* Monthly KPIs per department (breach rate, negative sentiment, median
  resolution time) form the monitoring view.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.sparse import hstack
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, roc_auc_score

from common import RES, load_data, normalise_text, save_json, savefig

SLA_FEATS = ["category", "severity", "department", "zone", "channel", "media_type", "train_type",
             "hour", "is_night", "train_age_years", "weekday"]


def sentiment(df):
    fb = df[df["feedback_text"] != ""].copy()
    fb["sentiment"] = pd.cut(fb["feedback_rating"], [0, 2, 3, 5], labels=["Negative", "Neutral", "Positive"]).astype(str)
    tr, te = fb[fb["split"] == "train"], fb[fb["split"] == "test"]
    word = TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=2, sublinear_tf=True)
    dtr, dte = tr["feedback_text"].map(normalise_text), te["feedback_text"].map(normalise_text)
    Xtr = hstack([word.fit_transform(dtr), char.fit_transform(dtr)]).tocsr()
    Xte = hstack([word.transform(dte), char.transform(dte)]).tocsr()
    clf = LogisticRegression(C=4, max_iter=2000, class_weight="balanced").fit(Xtr, tr["sentiment"])
    p = clf.predict(Xte)
    res = {"n_feedback_test": len(te), "accuracy": accuracy_score(te["sentiment"], p),
           "macro_F1": f1_score(te["sentiment"], p, average="macro"),
           "negative_recall": np.mean(p[te["sentiment"].values == "Negative"] == "Negative")}
    print("Sentiment:", res)
    save_json(res, "sentiment_results")
    fb.loc[te.index, "pred_sentiment"] = p
    fb.loc[tr.index, "pred_sentiment"] = clf.predict(Xtr)

    # what drives negative sentiment?
    drv = fb.groupby(["department", "sla_breached"])["pred_sentiment"].apply(lambda s: (s == "Negative").mean()).unstack()
    drv.columns = ["Within SLA", "SLA breached"]
    drv.round(3).to_csv(RES / "negative_sentiment_by_department.csv")
    return fb


def sla_model(df):
    d = df.copy()
    d["weekday"] = d["timestamp"].dt.dayofweek
    X = d[SLA_FEATS].copy()
    for c in ["category", "severity", "department", "zone", "channel", "media_type", "train_type"]:
        X[c] = X[c].astype("category")
    tr, te = d["split"] == "train", d["split"] == "test"
    y = d["sla_breached"]

    hgb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                         categorical_features="from_dtype", random_state=0)
    hgb.fit(X[tr], y[tr])
    p_hgb = hgb.predict_proba(X[te])[:, 1]
    Xd = pd.get_dummies(X, columns=[c for c in X if str(X[c].dtype) == "category"], dtype=float)
    lr = LogisticRegression(max_iter=3000, C=1.0).fit(Xd[tr], y[tr])
    p_lr = lr.predict_proba(Xd[te])[:, 1]

    res = pd.DataFrame([
        {"Model": "Prior rate (no model)", "ROC-AUC": 0.5, "PR-AUC": y[te].mean()},
        {"Model": "Logistic Regression", "ROC-AUC": roc_auc_score(y[te], p_lr), "PR-AUC": average_precision_score(y[te], p_lr)},
        {"Model": "Gradient Boosting", "ROC-AUC": roc_auc_score(y[te], p_hgb), "PR-AUC": average_precision_score(y[te], p_hgb)},
    ]).set_index("Model")
    # top-20 % risk flagging
    k = int(0.2 * te.sum())
    top = np.argsort(-p_hgb)[:k]
    res.loc["Gradient Boosting", "Breaches caught in top-20% risk"] = y[te].values[top].sum() / y[te].sum()
    res.round(4).to_csv(RES / "sla_breach_model.csv")
    print(res.round(3).to_string())

    imp = permutation_importance(hgb, X[te], y[te], scoring="roc_auc", n_repeats=5, random_state=0)
    imp = pd.Series(imp.importances_mean, index=SLA_FEATS).sort_values()
    imp.round(4).to_csv(RES / "sla_feature_importance.csv", header=["AUC drop"])
    return imp


def monitoring_figure(df, fb, imp):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.8))
    axes[0].barh([s.replace("_", " ") for s in imp.index], imp.values, color="#1f4e79")
    axes[0].set_xlabel("Drop in ROC-AUC when shuffled")
    axes[0].set_title("(a) SLA-breach drivers (permutation importance)")

    m = df.groupby("month").agg(breach=("sla_breached", "mean"))
    m["negative"] = fb.groupby("month")["pred_sentiment"].apply(lambda s: (s == "Negative").mean())
    axes[1].plot(m.index, 100 * m["breach"], marker="o", ms=3, label="SLA breach rate")
    axes[1].plot(m.index, 100 * m["negative"], marker="s", ms=3, label="Negative feedback (predicted)")
    axes[1].set_xticks(range(0, len(m), 3))
    axes[1].set_xticklabels(m.index[::3], rotation=30)
    axes[1].set_ylabel("%")
    axes[1].set_title("(b) Monthly performance monitoring KPIs")
    axes[1].legend()
    savefig(fig, "fig12_sla_sentiment")
    corr = np.corrcoef(m["breach"], m["negative"])[0, 1]
    save_json({"monthly_corr_breach_vs_negative": corr}, "monitoring_summary")
    print("Monthly correlation breach vs negative sentiment:", round(corr, 3))


def main():
    df = load_data()
    fb = sentiment(df)
    imp = sla_model(df)
    monitoring_figure(df, fb, imp)


if __name__ == "__main__":
    main()
