"""
Predictive maintenance: forecast next week's maintenance-related complaints
(electrical, water, coach maintenance, cleanliness, bed roll) for every
train, and flag trains that are likely to become hotspots.

Models: last-week naive, 4-week moving average, Poisson GLM and gradient
boosting with a Poisson loss. Features are lagged weekly counts, rolling
means and trends, train age/type and annual seasonality.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_absolute_error, mean_poisson_deviance
from sklearn.preprocessing import StandardScaler

from common import RAW, RES, TEST_START, load_data, save_json, savefig

MAINT_CATS = ["Electrical Equipment", "Water Availability", "Coach Maintenance", "Coach Cleanliness", "Bed Roll"]


def weekly_panel(df):
    m = df[df["category"].isin(MAINT_CATS)].copy()
    m["week"] = m["timestamp"].dt.to_period("W-SUN").dt.start_time
    # only complete weeks (the final, partial week would look like a sudden drop)
    last_full = (df["timestamp"].max() + pd.Timedelta(seconds=1)).to_period("W-SUN").start_time - pd.Timedelta(weeks=1)
    weeks = pd.date_range(df["timestamp"].min().to_period("W-SUN").start_time, last_full, freq="W-MON")
    trains = pd.read_csv(RAW / "train_master.csv", dtype={"train_no": str})
    grid = pd.MultiIndex.from_product([trains["train_no"], weeks], names=["train_no", "week"])
    counts = m.groupby(["train_no", "week"]).size().reindex(grid, fill_value=0).rename("y").reset_index()
    counts = counts.merge(trains[["train_no", "train_type", "age_years", "popularity"]], on="train_no")
    counts = counts.sort_values(["train_no", "week"])
    g = counts.groupby("train_no")["y"]
    for L in (1, 2, 3, 4):
        counts[f"lag{L}"] = g.shift(L)
    counts["roll4"] = g.transform(lambda s: s.shift(1).rolling(4).mean())
    counts["roll12"] = g.transform(lambda s: s.shift(1).rolling(12).mean())
    counts["trend"] = counts["roll4"] - counts["roll12"]         # recent deterioration signal
    counts["ewm"] = g.transform(lambda s: s.shift(1).ewm(halflife=3).mean())
    woy = counts["week"].dt.isocalendar().week.astype(int)
    counts["woy_sin"] = np.sin(2 * np.pi * woy / 52)
    counts["woy_cos"] = np.cos(2 * np.pi * woy / 52)
    counts["is_ac"] = counts["train_type"].isin(["Rajdhani", "Shatabdi", "Vande Bharat"]).astype(int)
    counts["type_code"] = counts["train_type"].astype("category").cat.codes
    return counts.dropna().reset_index(drop=True)


FEATS = ["lag1", "lag2", "lag3", "lag4", "roll4", "roll12", "trend", "ewm", "woy_sin", "woy_cos",
         "age_years", "is_ac", "type_code"]


def main():
    df = load_data()
    det = df.groupby("train_no")["deteriorating_train"].max()
    panel = weekly_panel(df)
    tr, te = panel[panel["week"] < TEST_START], panel[panel["week"] >= TEST_START]

    preds = {"Naive (last week)": te["lag1"].values, "Moving average (4 wk)": te["roll4"].values}
    sc = StandardScaler().fit(tr[FEATS])
    glm = PoissonRegressor(alpha=1e-3, max_iter=1000).fit(sc.transform(tr[FEATS]), tr["y"])
    preds["Poisson GLM"] = glm.predict(sc.transform(te[FEATS]))
    hgb = HistGradientBoostingRegressor(loss="poisson", max_iter=400, learning_rate=0.04, max_leaf_nodes=15,
                                        min_samples_leaf=40, l2_regularization=1.0, random_state=0)
    hgb.fit(tr[FEATS], tr["y"])
    preds["Gradient Boosting (Poisson)"] = hgb.predict(te[FEATS])

    rows = []
    for name, p in preds.items():
        p = np.clip(p, 1e-3, None)
        rows.append({"Model": name, "MAE": mean_absolute_error(te["y"], p),
                     "RMSE": np.sqrt(np.mean((te["y"] - p) ** 2)),
                     "Poisson deviance": mean_poisson_deviance(te["y"], p)})
    res = pd.DataFrame(rows).set_index("Model")
    res.round(4).to_csv(RES / "maintenance_forecast.csv")
    print(res.round(3).to_string())

    # hotspot detection: rank trains on predicted complaints over the first 8 test weeks
    best = res["Poisson deviance"].idxmin()
    te = te.assign(pred=preds[best])
    first = te[te["week"] < pd.Timestamp(TEST_START) + pd.Timedelta(weeks=8)]
    ranking = first.groupby("train_no")["pred"].sum().sort_values(ascending=False)
    later = te[te["week"] >= pd.Timestamp(TEST_START) + pd.Timedelta(weeks=8)].groupby("train_no")["y"].sum()
    k = 8
    top = ranking.index[:k]
    actual_top = later.sort_values(ascending=False).index[:k]
    hot = {
        "model": best, "k": k,
        "precision_at_k_deteriorating": det.loc[top].mean(),
        "random_baseline": det.mean(),
        "overlap_with_actual_future_top_k": len(set(top) & set(actual_top)) / k,
        "flagged_trains": list(top),
    }
    save_json(hot, "hotspot_detection")
    print(hot)

    # figure: weekly network total and one flagged train
    tot = te.groupby("week")[["y", "pred"]].sum()
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6))
    axes[0].plot(tot.index, tot["y"], marker="o", ms=3, label="Actual")
    axes[0].plot(tot.index, tot["pred"], marker="s", ms=3, label=f"Forecast: {best}")
    axes[0].set_title("(a) Weekly maintenance complaints, all trains (test period)")
    axes[0].set_ylabel("Complaints / week")
    axes[0].tick_params(axis="x", rotation=30)
    axes[0].legend()
    tn = top[0]
    s = panel[panel["train_no"] == tn].set_index("week")
    axes[1].plot(s.index, s["y"], color="#7a7a7a", lw=1, label="Actual")
    s_te = te[te["train_no"] == tn].set_index("week")
    axes[1].plot(s_te.index, s_te["pred"], color="#c0504d", lw=2, label="Forecast")
    axes[1].plot(s.index, s["roll12"], color="#1f4e79", ls="--", label="12-week mean")
    axes[1].axvline(pd.Timestamp(TEST_START), color="black", lw=0.8, ls=":")
    axes[1].set_title(f"(b) Highest-risk train flagged: {tn}")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].legend()
    savefig(fig, "fig11_maintenance_forecast")


if __name__ == "__main__":
    main()
