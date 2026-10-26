"""Run the complete pipeline: data generation -> analysis -> models -> figures/results."""
import runpy
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SRC))

STEPS = [
    ("Generate synthetic Rail Madad dataset", "generate_dataset.py"),
    ("Exploratory data analysis", "eda.py"),
    ("Categorisation, fusion and smart routing", "categorize.py"),
    ("Urgency detection and queue simulation", "urgency.py"),
    ("Entity extraction and duplicate grouping", "extraction_dedup.py"),
    ("Predictive maintenance forecasting", "predictive_maintenance.py"),
    ("Sentiment, SLA-breach risk and monitoring", "sentiment_sla.py"),
    ("Pipeline architecture diagram", "architecture.py"),
    ("Export data and model for the website (docs/)", "export_web.py"),
]

if __name__ == "__main__":
    t0 = time.time()
    for title, script in STEPS:
        print(f"\n{'=' * 70}\n{title}  ({script})\n{'=' * 70}", flush=True)
        runpy.run_path(str(SRC / script), run_name="__main__")
    print(f"\nPipeline finished in {time.time() - t0:.0f} s. See results/ and figures/.")
