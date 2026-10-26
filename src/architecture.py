"""Draws the block diagram of the proposed system (Figure 1)."""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from common import savefig

BOXES = {
    # key: (x, y, w, h, text, colour)
    "in":    (0.02, 0.36, 0.15, 0.30, "Complaint inputs\n\nText / Hinglish\nPhoto, Video (OCR,\nvision tags)\nAudio (ASR)\nEXIF time + GPS\nPNR record", "#dbe5f1"),
    "pre":   (0.22, 0.36, 0.15, 0.30, "Pre-processing\n\nHinglish & SMS\nnormalisation\nEntity extraction\n(train, coach, PNR)\nGPS -> station", "#e2efda"),
    "fuse":  (0.42, 0.36, 0.14, 0.30, "Multimodal\nfusion\n\nWord + char\nTF-IDF of text,\nOCR and image\ntags + metadata", "#fff2cc"),
    "cat":   (0.61, 0.72, 0.17, 0.20, "Categorisation\n(13 classes, 7 depts)\nCalibrated linear SVM", "#fce4d6"),
    "urg":   (0.61, 0.46, 0.17, 0.20, "Urgency detection\nCost-sensitive\nBayes decision", "#fce4d6"),
    "dup":   (0.61, 0.20, 0.17, 0.20, "Duplicate incident\ngrouping\n(graph components)", "#fce4d6"),
    "route": (0.83, 0.59, 0.15, 0.24, "Smart routing\n\nconfidence >= t:\nauto-assign\nelse human desk\nPriority queue", "#d9d2e9"),
    "mon":   (0.83, 0.10, 0.15, 0.40, "Analytics layer\n\nPredictive\nmaintenance\n(Poisson GBM)\n\nSLA-breach risk\n\nSentiment &\nKPI monitoring", "#d9d2e9"),
}
ARROWS = [("in", "pre"), ("pre", "fuse"), ("fuse", "cat"), ("fuse", "urg"), ("fuse", "dup"),
          ("cat", "route"), ("urg", "route"), ("dup", "mon"), ("route", "mon")]


def main():
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    for x, y, w, h, text, col in BOXES.values():
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.008", fc=col, ec="#404040", lw=1))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8.5)

    def anchor(k, side):
        x, y, w, h = BOXES[k][:4]
        return {"r": (x + w, y + h / 2), "l": (x, y + h / 2), "t": (x + w / 2, y + h), "b": (x + w / 2, y)}[side]

    for a, b in ARROWS:
        if (a, b) == ("route", "mon"):
            p, q = anchor(a, "b"), anchor(b, "t")
        else:
            p, q = anchor(a, "r"), anchor(b, "l")
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=12, lw=1, color="#404040"))
    ax.set_title("Proposed AI-assisted Rail Madad complaint pipeline", fontsize=12)
    savefig(fig, "fig01_architecture")


if __name__ == "__main__":
    main()
