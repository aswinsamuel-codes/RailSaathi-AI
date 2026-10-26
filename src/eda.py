"""Exploratory data analysis of Rail Madad complaints."""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import RES, SEVERITIES, load_data, savefig


def summary_tables(df):
    overview = {
        "complaints": len(df), "incidents": df["incident_id"].nunique(), "trains": df["train_no"].nunique(),
        "period": f"{df['timestamp'].min().date()} to {df['timestamp'].max().date()}",
        "train_rows": int((df["split"] == "train").sum()), "test_rows": int((df["split"] == "test").sum()),
        "share_with_photo_or_video": df["media_type"].isin(["photo", "video"]).mean(),
        "share_hinglish": df["is_hinglish"].mean(), "sla_breach_rate": df["sla_breached"].mean(),
        "feedback_given": df["feedback_rating"].notna().mean(),
    }
    pd.Series(overview).to_csv(RES / "dataset_overview.csv", header=["value"])
    tab = pd.crosstab(df["category"], df["severity"])[SEVERITIES]
    tab["Total"] = tab.sum(axis=1)
    tab["Department"] = df.groupby("category")["department"].first()
    tab.sort_values("Total", ascending=False).to_csv(RES / "category_severity_table.csv")
    print(pd.Series(overview).to_string())


def plot_category(df):
    counts = df["category"].value_counts().sort_values()
    sev = pd.crosstab(df["category"], df["severity"]).loc[counts.index, SEVERITIES]
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    left = np.zeros(len(sev))
    colors = ["#c0504d", "#e3a21a", "#2a9d9d", "#9fb7cc"]
    for s, c in zip(SEVERITIES, colors):
        ax.barh(sev.index, sev[s], left=left, color=c, label=s)
        left += sev[s].values
    ax.set_xlabel("Number of complaints")
    ax.set_title("Complaint volume by category and severity")
    ax.legend(title="Severity", loc="lower right")
    savefig(fig, "fig02_category_severity")


def plot_seasonality(df):
    monthly = pd.crosstab(df["month"], df["category"])
    share = monthly.div(monthly.sum(axis=1), axis=0)
    rel = share / share.mean()  # >1 means above-average share in that month
    keep = ["Electrical Equipment", "Water Availability", "Coach Maintenance", "Punctuality",
            "Bed Roll", "Security", "Coach Cleanliness", "Catering & Vending"]
    fig, ax = plt.subplots(figsize=(9.5, 3.8))
    im = ax.imshow(rel[keep].T, aspect="auto", cmap="RdBu_r", vmin=0.4, vmax=1.6)
    ax.set_yticks(range(len(keep)))
    ax.set_yticklabels(keep)
    ax.set_xticks(range(0, len(rel), 2))
    ax.set_xticklabels(rel.index[::2], rotation=45, ha="right")
    ax.grid(False)
    ax.set_title("Seasonality: monthly share of each category relative to its average")
    fig.colorbar(im, ax=ax, pad=0.01, label="Relative share")
    savefig(fig, "fig03_seasonality")


def plot_operations(df):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))
    order = df.groupby("department")["resolution_hours"].median().sort_values().index
    data = [np.log10(df.loc[df["department"] == d, "resolution_hours"]) for d in order]
    axes[0].boxplot(data, vert=False, showfliers=False, patch_artist=True,
                    boxprops=dict(facecolor="#9fb7cc"), medianprops=dict(color="#c0504d"))
    axes[0].set_yticks(range(1, len(order) + 1))
    axes[0].set_yticklabels(order)
    axes[0].set_xticks([-1, 0, 1, 2])
    axes[0].set_xticklabels(["0.1 h", "1 h", "10 h", "100 h"])
    axes[0].set_title("(a) Resolution time by department")

    z = df.groupby("zone").agg(breach=("sla_breached", "mean"), n=("sla_breached", "size")).sort_values("breach")
    axes[1].barh(z.index, 100 * z["breach"], color="#1f4e79")
    axes[1].set_xlabel("SLA breach rate (%)")
    axes[1].set_title("(b) SLA breach rate by railway zone")
    savefig(fig, "fig04_operations")
    z.round(3).to_csv(RES / "zone_sla_breach.csv")


def plot_media_hour(df):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    hourly = df.groupby("hour").size()
    axes[0].bar(hourly.index, hourly.values, color="#2a9d9d")
    axes[0].set_xlabel("Hour of day")
    axes[0].set_ylabel("Complaints")
    axes[0].set_title("(a) Complaints by hour of registration")
    ct = pd.crosstab(df["channel"], df["media_type"], normalize="index") * 100
    ct = ct[["text", "photo", "video", "audio"]]
    ct.plot(kind="barh", stacked=True, ax=axes[1], color=["#9fb7cc", "#1f4e79", "#e3a21a", "#c0504d"], width=0.7)
    axes[1].set_xlabel("Share of complaints (%)")
    axes[1].set_ylabel("")
    axes[1].set_title("(b) Media type by channel")
    axes[1].legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.18))
    savefig(fig, "fig05_media_hour")


def main():
    df = load_data()
    summary_tables(df)
    plot_category(df)
    plot_seasonality(df)
    plot_operations(df)
    plot_media_hour(df)


if __name__ == "__main__":
    main()
