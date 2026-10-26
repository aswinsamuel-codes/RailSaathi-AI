"""Shared paths, plotting style, data loading and text preprocessing."""
import json
import re
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
FIG = ROOT / "figures"
RES = ROOT / "results"
for p in (PROC, FIG, RES):
    p.mkdir(parents=True, exist_ok=True)

TEST_START = "2026-04-01"  # last six months are held out as the test period
SEVERITIES = ["Critical", "High", "Medium", "Low"]
PALETTE = ["#1f4e79", "#c0504d", "#4f8f3a", "#e3a21a", "#7f5fa8", "#2a9d9d", "#7a7a7a", "#b5651d"]

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.3, "legend.frameon": False,
    "figure.dpi": 110, "savefig.dpi": 300, "savefig.bbox": "tight",
    "axes.prop_cycle": matplotlib.cycler(color=PALETTE),
})


def savefig(fig, name: str):
    fig.savefig(FIG / f"{name}.png")
    plt.close(fig)


def save_json(obj: dict, name: str):
    def conv(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return round(float(o), 4)
        return str(o)
    (RES / f"{name}.json").write_text(json.dumps(obj, indent=2, default=conv))


# ---------------------------------------------------------------------------
# Text preprocessing: code-mixed (Hinglish) normalisation + SMS expansion
# ---------------------------------------------------------------------------
HINGLISH_LEXICON = {
    "pani": "water", "ganda": "dirty", "gandi": "dirty", "kachra": "garbage", "safai": "cleaning",
    "badbu": "smell", "pankha": "fan", "band": "off", "thanda": "cool", "thandi": "cold",
    "khana": "food", "kharab": "bad", "bekar": "bad", "chai": "tea", "paise": "money", "zyada": "more",
    "maang": "demand", "rishwat": "bribe", "badtameezi": "rude", "der": "delay", "ruki": "stopped",
    "ghante": "hours", "chori": "stolen", "sharabi": "drunk", "jhagda": "fight", "tabiyat": "health",
    "bukhar": "fever", "bacche": "child", "aadmi": "man", "ladki": "girl", "pareshan": "harass",
    "chadar": "bedsheet", "kambal": "blanket", "khidki": "window", "tooti": "broken", "toota": "broken",
    "darwaza": "door", "chhat": "roof", "tapak": "leak", "nahi": "not", "nhi": "not", "mila": "given",
    "diya": "given", "kat": "deducted", "bana": "issued", "tez": "high", "bahut": "very",
}
SMS_LEXICON = {"pls": "please", "plz": "please", "u": "you", "nt": "not", "wrkng": "working", "coch": "coach",
               "snce": "since", "hrs": "hours", "urgnt": "urgent", "trn": "train", "watr": "water", "hlp": "help",
               "tt": "tte"}
_TOKEN = re.compile(r"[a-z]+|\d+")


def normalise_text(text: str, use_lexicon: bool = True) -> str:
    text = str(text).lower() if isinstance(text, str) else ""
    text = re.sub(r"@\w+", " ", text)
    text = re.sub(r"\b\d{10}\b", " pnrnum ", text)   # PNR numbers carry no category signal
    text = re.sub(r"\b\d{5}\b", " trainnum ", text)
    tokens = _TOKEN.findall(text)
    if use_lexicon:
        tokens = [HINGLISH_LEXICON.get(t, SMS_LEXICON.get(t, t)) for t in tokens]
    return " ".join(tokens)


def multimodal_text(df: pd.DataFrame, use_lexicon: bool = True, use_ocr: bool = True, use_vision: bool = True) -> pd.Series:
    """Fuse complaint text, OCR text and vision tags into one document."""
    out = df["complaint_text"].map(lambda t: normalise_text(t, use_lexicon))
    if use_ocr:
        out = out + " " + df["ocr_text"].fillna("").map(lambda t: " ".join("ocr_" + w for w in normalise_text(t).split()))
    if use_vision:
        out = out + " " + df["vision_tags"].fillna("").map(
            lambda t: " ".join("img_" + tag.replace(" ", "_") for tag in t.split("|") if tag))
    return out.str.strip()


def load_data() -> pd.DataFrame:
    df = pd.read_csv(RAW / "rail_madad_complaints.csv", parse_dates=["timestamp"], dtype={"train_no": str, "pnr": str})
    df["ocr_text"] = df["ocr_text"].fillna("")
    df["vision_tags"] = df["vision_tags"].fillna("")
    df["feedback_text"] = df["feedback_text"].fillna("")
    df["hour"] = df["timestamp"].dt.hour
    df["month"] = df["timestamp"].dt.to_period("M").astype(str)
    df["is_night"] = ((df["hour"] >= 22) | (df["hour"] < 6)).astype(int)
    df["split"] = np.where(df["timestamp"] >= TEST_START, "test", "train")
    return df
