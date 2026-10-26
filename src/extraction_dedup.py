"""
Enhanced data extraction and duplicate-incident grouping.

1. Rule-based information extraction (regular expressions) of train number,
   coach and PNR from the complaint text and from OCR text of photos.
2. Location from EXIF GPS: nearest station by haversine distance.
3. Duplicate detection: several passengers often report the same fault.
   Complaints on the same train within a 6-hour window are linked when
   their predicted category agrees and either (a) they come from the same
   coach (known from the PNR booking record) or (b) their TF-IDF cosine
   similarity exceeds a threshold; connected components form one ticket.
"""
import re

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import connected_components
from scipy.sparse import coo_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import adjusted_rand_score

from common import PROC, RES, load_data, multimodal_text, save_json, savefig
from generate_dataset import STATIONS

TRAIN_RE = re.compile(r"\b(?:train|trn|tr)\s*(?:no\.?|number)?\s*(\d{5})\b|\b(\d{5})\b", re.I)
COACH_RE = re.compile(r"\b(?:coach|coch)\s*([A-Z]{1,3}\d{0,2})\b|\b([SBAHCDE]\d{1,2})\b(?=\s*(?:/|\d{5}))", re.I)
PNR_RE = re.compile(r"\b(\d{10})\b")


def first_group(m):
    return next((g for g in m.groups() if g), None) if m else None


def extract(text: str):
    text = text or ""
    return (first_group(TRAIN_RE.search(text)), (first_group(COACH_RE.search(text)) or "").upper() or None,
            first_group(PNR_RE.search(text)))


def extraction_eval(df):
    rows = []
    for source, cols in (("Complaint text only", ["complaint_text"]), ("Text + OCR", ["complaint_text", "ocr_text"])):
        joined = df[cols].fillna("").agg(" ".join, axis=1)
        ex = joined.map(extract)
        for k, field in enumerate(["train_no", "coach", "pnr"]):
            got = ex.map(lambda e: e[k])
            found = got.notna()
            truth = df[field].astype(str).str.upper()
            present = pd.Series([t in j.upper() for t, j in zip(truth, joined)], index=df.index)
            correct = (got == truth) & found
            rows.append({"Source": source, "Field": field, "Mentioned (%)": 100 * present.mean(),
                         "Recall (%)": 100 * correct.mean(),
                         "Recall when mentioned (%)": 100 * correct[present].mean(),
                         "Precision (%)": 100 * correct.sum() / max(found.sum(), 1)})
    res = pd.DataFrame(rows)
    res.round(2).to_csv(RES / "entity_extraction.csv", index=False)
    print(res.round(1).to_string(index=False))
    return res


def gps_eval(df):
    codes = list(STATIONS)
    lat = np.radians([STATIONS[c][1] for c in codes])
    lon = np.radians([STATIONS[c][2] for c in codes])
    g = df.dropna(subset=["gps_lat"])
    la, lo = np.radians(g["gps_lat"].values)[:, None], np.radians(g["gps_lon"].values)[:, None]
    a = np.sin((la - lat) / 2) ** 2 + np.cos(la) * np.cos(lat) * np.sin((lo - lon) / 2) ** 2
    dist = 2 * 6371 * np.arcsin(np.sqrt(a))
    nearest = np.array(codes)[dist.argmin(1)]
    out = {"complaints_with_gps": len(g), "share_with_gps": len(g) / len(df),
           "nearest_station_accuracy": np.mean(nearest == g["nearest_station"].values),
           "median_distance_km": np.median(dist.min(1))}
    print(out)
    return out


def group_duplicates(df, docs, threshold, window_h=6, use_coach=True):
    """Link complaints (same train, within window, similar text, same category) -> components."""
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1).fit(docs)
    X = vec.transform(docs)
    t = df["timestamp"].values.astype("datetime64[m]").astype(np.int64)
    rows, cols = [], []
    for _, idx in df.groupby("train_no").indices.items():
        idx = idx[np.argsort(t[idx])]
        for a_pos, a in enumerate(idx):
            b_pos = a_pos + 1
            while b_pos < len(idx) and t[idx[b_pos]] - t[a] <= window_h * 60:
                b = idx[b_pos]
                same_coach = use_coach and df["coach"].values[a] == df["coach"].values[b]
                if df["pred_category"].values[a] == df["pred_category"].values[b] and \
                        (same_coach or X[a].multiply(X[b]).sum() >= threshold):
                    rows.append(a)
                    cols.append(b)
                b_pos += 1
    n = len(df)
    graph = coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n))
    _, labels = connected_components(graph, directed=False)
    return labels


def pairwise_scores(true, pred):
    """Pairwise precision/recall over all complaint pairs that share a group."""
    def pairs(lab):
        s = pd.Series(lab).value_counts()
        return (s * (s - 1) / 2).sum()
    tp = pairs(pd.Series(true).astype(str) + "|" + pd.Series(pred).astype(str))
    p_pairs, t_pairs = pairs(pred), pairs(true)
    prec = tp / p_pairs if p_pairs else 0.0
    rec = tp / t_pairs if t_pairs else 0.0
    return prec, rec, 2 * prec * rec / (prec + rec) if prec + rec else 0.0


def dedup_eval(df):
    te = df[df["split"] == "test"].copy().reset_index(drop=True)
    preds = pd.read_csv(PROC / "test_category_predictions.csv")[["complaint_id", "pred_category"]]
    te = te.merge(preds, on="complaint_id")
    docs = multimodal_text(te, use_ocr=False, use_vision=False)
    rows = []
    for use_coach in (False, True):
        for thr in [0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.01]:
            lab = group_duplicates(te, docs, thr, use_coach=use_coach)
            p, r, f = pairwise_scores(te["incident_id"].values, lab)
            rows.append({"method": "text + coach" if use_coach else "text only", "threshold": thr,
                         "pair_precision": p, "pair_recall": r, "pair_F1": f,
                         "ARI": adjusted_rand_score(te["incident_id"], lab), "tickets_after_grouping": len(set(lab))})
    res = pd.DataFrame(rows)
    res["tickets_before"] = len(te)
    res["true_incidents"] = te["incident_id"].nunique()
    res.round(4).to_csv(RES / "duplicate_grouping.csv", index=False)
    print(res.round(3).to_string(index=False))

    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for (method, g), ls in zip(res[res["threshold"] <= 1].groupby("method", sort=False), ["--", "-"]):
        ax.plot(g["threshold"], g["pair_precision"] * 100, marker="o", ls=ls, color="#1f4e79", label=f"Precision ({method})")
        ax.plot(g["threshold"], g["pair_recall"] * 100, marker="s", ls=ls, color="#e3a21a", label=f"Recall ({method})")
        ax.plot(g["threshold"], g["pair_F1"] * 100, marker="^", ls=ls, color="#c0504d", lw=2, label=f"F1 ({method})")
    ax.legend(fontsize=8, ncol=2, loc="center right", bbox_to_anchor=(1.0, 0.62))
    ax.set_xlabel("Cosine-similarity threshold")
    ax.set_ylabel("%")
    ax.set_title("Duplicate-incident grouping (same train, 6 h window)")
    savefig(fig, "fig10_duplicate_grouping")
    return res


def main():
    df = load_data()
    ext = extraction_eval(df)
    gps = gps_eval(df)
    save_json(gps, "gps_metadata")
    dedup_eval(df)


if __name__ == "__main__":
    main()
