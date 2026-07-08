"""
Generate synthetic wearable-sensor recordings for demo purposes.

This script fabricates *plausible but entirely artificial* time-series data
(heart rate, tri-axial acceleration, tri-axial angular velocity, and a surface-EMG
ARV channel) for a set of subjects performing a repetitive physical task under
several tool/load conditions.

Nothing here is measured data. The numbers are drawn from random distributions
chosen only to exercise the analysis pipeline. See README.md.
"""

import os
import numpy as np
import pandas as pd

# ----- experiment design (fully abstract labels) -----
SUBJECTS = ["S1", "S2", "S3"]
TOOLS = ["ToolA", "ToolB", "Baseline"]          # "Baseline" is the reference condition
LOADS = ["Light", "Heavy"]                        # two load conditions
FS = 1000                                         # sampling frequency [Hz]
DURATION_SEC = 60                                 # length of each recording
HEADER_PADDING_ROWS = 9                           # mimic instrument export offset

RNG = np.random.default_rng(42)                   # fixed seed => reproducible demo

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _synth_one(subject, tool, load):
    n = FS * DURATION_SEC
    t = np.arange(n) / FS

    # baseline physiological load depends on tool + load, plus per-subject offset
    tool_effect = {"Baseline": 1.00, "ToolA": 0.88, "ToolB": 0.80}[tool]
    load_effect = {"Light": 1.00, "Heavy": 1.15}[load]
    subj_offset = {"S1": 0, "S2": 6, "S3": -4}[subject]

    # --- heart rate: slow drift + noise, scaled by effort ---
    base_hr = (95 + subj_offset) * tool_effect * load_effect
    drift = 12 * np.sin(2 * np.pi * t / DURATION_SEC)
    hr = base_hr + drift + RNG.normal(0, 3, n)
    hr = np.clip(hr, 45, 190)

    # --- acceleration magnitude: repetitive "digging" cycles ~0.5 Hz ---
    cycle = np.abs(np.sin(2 * np.pi * 0.5 * t))
    acc_mag = 0.9 * load_effect * cycle + RNG.normal(0, 0.05, n) + 1.0  # +1g gravity-ish
    ax = acc_mag / np.sqrt(3) + RNG.normal(0, 0.02, n)
    ay = acc_mag / np.sqrt(3) + RNG.normal(0, 0.02, n)
    az = acc_mag / np.sqrt(3) + RNG.normal(0, 0.02, n)

    # --- angular velocity: bursts during the active phase of each cycle ---
    gyro = 40 * load_effect * (cycle ** 3) + RNG.normal(0, 2, n)
    gx = gyro / np.sqrt(3) + RNG.normal(0, 1, n)
    gy = gyro / np.sqrt(3) + RNG.normal(0, 1, n)
    gz = gyro / np.sqrt(3) + RNG.normal(0, 1, n)

    # --- EMG ARV (already rectified/averaged envelope): peaks on exertion ---
    arv = 0.15 * tool_effect * load_effect * (cycle ** 2)
    # inject discrete exertion peaks
    n_peaks = 40
    peak_idx = RNG.integers(0, n, n_peaks)
    arv[peak_idx] += RNG.uniform(0.2, 0.6, n_peaks) * load_effect
    arv = np.clip(arv + RNG.normal(0, 0.01, n), 0, None)

    df = pd.DataFrame({
        "シーケンス番号": np.arange(1, n + 1),
        "HR": hr,
        "加速度X": ax, "加速度Y": ay, "加速度Z": az,
        "角速度X": gx, "角速度Y": gy, "角速度Z": gz,
        "ARV": arv,
    })
    return df


def _write_with_header_padding(df, path):
    """Write an .xlsx whose real header sits on row HEADER_PADDING_ROWS,
    mimicking a raw instrument export (blank metadata rows on top)."""
    import openpyxl
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    # pad blank metadata rows
    for r in range(HEADER_PADDING_ROWS):
        ws.append([f"# synthetic-metadata-line-{r+1}"])
    # header + data
    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append(list(row))
    wb.save(path)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    count = 0
    for subject in SUBJECTS:
        for tool in TOOLS:
            for load in LOADS:
                df = _synth_one(subject, tool, load)
                cond = "Light" if load == "Light" else "Heavy"
                # filename pattern: 01_<load>_<tool>_ID01_001_<subject>.xlsx
                fname = f"01_{cond}_{tool}_ID01_001_{subject}.xlsx"
                path = os.path.join(DATA_DIR, fname)
                _write_with_header_padding(df, path)
                count += 1
                print(f"  wrote {fname}")
    print(f"Done. {count} synthetic files in {os.path.abspath(DATA_DIR)}")


if __name__ == "__main__":
    main()
