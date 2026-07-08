"""
Surface-EMG peak analysis with automatic thresholding and motion classification.

For each recording it:
  - auto-selects a peak threshold at the 95th percentile of the ARV signal
  - detects peaks (scipy.signal.find_peaks) with a minimum inter-peak distance
  - classifies each peak as Dynamic vs Static using the angular-velocity burst
    in a short window after the peak
  - measures peak width and integrated area (mV*s)
  - aggregates per subject / tool / condition into Excel + plots

Input: synthetic .xlsx files from generate_synthetic_data.py (README.md).
No real measured data is included in this repository.
"""

import os
import glob
import re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")           # headless backend; no display needed
import matplotlib.pyplot as plt

try:
    from scipy.signal import find_peaks, peak_prominences, peak_widths
    SCIPY_LEGACY = False
except ImportError:                       # pragma: no cover
    from scipy.signal import find_peaks
    SCIPY_LEGACY = True

# numpy renamed trapz -> trapezoid in newer versions; support both
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))

HEADER_ROW_INDEX = 9
SAMPLING_FREQUENCY = 1000
PEAK_THRESHOLD_PERCENTILE = 95
MOTION_THRESHOLD_GYRO = 30.0      # deg/s
MOTION_WINDOW_SEC = 0.1
PEAK_MIN_DISTANCE_SEC = 1.0

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
ANALYSIS_FOLDER = os.path.join(os.path.dirname(__file__), "..", "output_emg", "analysis")
SUMMARY_FOLDER = os.path.join(os.path.dirname(__file__), "..", "output_emg", "summary")
GRAPH_FOLDER = os.path.join(os.path.dirname(__file__), "..", "output_emg", "graphs")


# ---------- filename parsing ----------
def get_subject(fn):
    for s in ["S1", "S2", "S3", "S4", "S5"]:
        if f"_{s}." in fn or f"_{s}_" in fn:
            return s
    return "Unknown"


def get_condition(fn):
    if "Light" in fn:
        return "Light"
    if "Heavy" in fn:
        return "Heavy"
    return "Other"


def get_tool(fn):
    parts = os.path.basename(fn).split("_")
    return parts[2] if len(parts) > 2 else "Unknown"


# ---------- io / preprocessing ----------
def load_and_preprocess(filename):
    df = pd.read_excel(filename, header=HEADER_ROW_INDEX, engine="openpyxl")
    df = df.loc[:, ~df.columns.duplicated()]

    if "Time (s)" not in df.columns:
        if "シーケンス番号" in df.columns:
            df["Time (s)"] = df["シーケンス番号"] / SAMPLING_FREQUENCY
        else:
            df["Time (s)"] = df.index / SAMPLING_FREQUENCY

    if "Acc_Mag" not in df.columns and "加速度X" in df.columns:
        df["Acc_Mag"] = np.sqrt(df["加速度X"] ** 2 + df["加速度Y"] ** 2 + df["加速度Z"] ** 2)
    if "Gyro_Mag" not in df.columns and "角速度X" in df.columns:
        df["Gyro_Mag"] = np.sqrt(df["角速度X"] ** 2 + df["角速度Y"] ** 2 + df["角速度Z"] ** 2)
    return df


# ---------- core analysis ----------
def analyze(df, threshold, title, filename_base):
    if "ARV" not in df.columns:
        return None, None

    arv = df["ARV"]
    peaks, _ = find_peaks(arv, height=threshold, distance=int(PEAK_MIN_DISTANCE_SEC * SAMPLING_FREQUENCY))
    if len(peaks) == 0:
        print(f"   no peaks above {threshold:.3f} mV")
        return None, None
    print(f"   {len(peaks)} peaks above {threshold:.3f} mV")

    widths = np.full(len(peaks), np.nan)
    areas = np.full(len(peaks), np.nan)
    if not SCIPY_LEGACY:
        try:
            widths = peak_widths(arv, peaks, rel_height=0.5)[0] / SAMPLING_FREQUENCY
            _, lb, rb = peak_prominences(arv, peaks)   # (prominences, left_bases, right_bases)
            areas = np.array([
                _trapz(df["ARV"].iloc[l:r + 1].values, df["Time (s)"].iloc[l:r + 1].values)
                for l, r in zip(lb, rb)
            ])
        except Exception as e:
            print(f"   (width/area calc skipped: {e})")
            widths = np.full(len(peaks), np.nan)
            areas = np.full(len(peaks), np.nan)

    # Dynamic vs Static from post-peak gyro burst
    motion, max_gyro = [], []
    win = int(MOTION_WINDOW_SEC * SAMPLING_FREQUENCY)
    if "Gyro_Mag" in df.columns:
        g = df["Gyro_Mag"].values
        for p in peaks:
            wmax = np.max(g[p:min(p + win + 1, len(g))])
            max_gyro.append(wmax)
            motion.append("Dynamic" if wmax >= MOTION_THRESHOLD_GYRO else "Static")
    else:
        motion = ["Unknown"] * len(peaks)
        max_gyro = [np.nan] * len(peaks)

    peaks_df = pd.DataFrame({
        "Time (s)": df["Time (s)"].iloc[peaks].values,
        "ARV_mV": arv.iloc[peaks].values,
        "Motion_Type": motion,
        "Max_Gyro_degps": max_gyro,
        "Width_s": widths,
        "Area_mVs": areas,
    })

    summary = {
        "Total_Peaks": [len(peaks)],
        "Avg_Height_mV": [peaks_df["ARV_mV"].mean()],
        "Total_Area_mVs": [peaks_df["Area_mVs"].sum()],
    }
    for m in ["Dynamic", "Static"]:
        sub = peaks_df[peaks_df["Motion_Type"] == m]
        summary[f"Peaks_{m}"] = [len(sub)]
        summary[f"Avg_Height_{m}_mV"] = [sub["ARV_mV"].mean() if not sub.empty else np.nan]
        summary[f"Total_Area_{m}_mVs"] = [sub["Area_mVs"].sum() if not sub.empty else 0]
    summary_df = pd.DataFrame(summary)

    _plot(df, peaks_df, threshold, title, filename_base)
    return peaks_df, summary_df


def _plot(df, peaks_df, threshold, title, filename_base):
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(15, 12), sharex=True)
    ax1.plot(df["Time (s)"], df["ARV"], color="gray", alpha=0.5, label="ARV")
    dyn = peaks_df[peaks_df["Motion_Type"] == "Dynamic"]
    sta = peaks_df[peaks_df["Motion_Type"] == "Static"]
    if not dyn.empty:
        ax1.plot(dyn["Time (s)"], dyn["ARV_mV"], "x", color="red", ms=10, mew=2, label="Dynamic peak")
    if not sta.empty:
        ax1.plot(sta["Time (s)"], sta["ARV_mV"], "+", color="blue", ms=12, mew=2, label="Static peak")
    ax1.set_title(f"ARV - {title} (thresh={threshold:.3f} mV, {PEAK_THRESHOLD_PERCENTILE}%ile)")
    ax1.set_ylabel("ARV [mV]"); ax1.legend(loc="upper right"); ax1.grid(True)

    if "Acc_Mag" in df.columns:
        ax2.plot(df["Time (s)"], df["Acc_Mag"], color="green", label="Acc Mag")
        ax2.set_ylabel("Acc [g]"); ax2.legend(loc="upper right"); ax2.grid(True)
    if "Gyro_Mag" in df.columns:
        ax3.plot(df["Time (s)"], df["Gyro_Mag"], color="purple", label="Gyro Mag")
        ax3.axhline(MOTION_THRESHOLD_GYRO, color="red", linestyle="--", alpha=0.5,
                    label=f"motion thresh ({MOTION_THRESHOLD_GYRO} deg/s)")
        ax3.set_ylabel("Gyro [deg/s]"); ax3.set_xlabel("Time [s]")
        ax3.legend(loc="upper right"); ax3.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPH_FOLDER, f"{filename_base}_comparison.png"))
    plt.close(fig)


def add_metadata(sum_df, peak_df, fn):
    meta = {
        "Subject": get_subject(os.path.basename(fn)),
        "Condition": get_condition(fn),
        "Tool": get_tool(fn),
        "Source_File": os.path.splitext(os.path.basename(fn))[0],
    }
    for k, v in reversed(meta.items()):
        sum_df.insert(0, k, v)
        peak_df.insert(0, k, v)


def main():
    print("--- EMG peak analysis (synthetic demo data) ---")
    for d in [ANALYSIS_FOLDER, SUMMARY_FOLDER, GRAPH_FOLDER]:
        os.makedirs(d, exist_ok=True)

    files = [f for f in glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
             if not os.path.basename(f).startswith("_")]
    if not files:
        print("no data; run generate_synthetic_data.py first")
        return

    summaries, peaks_all = [], []
    for fn in files:
        print(f"processing {os.path.basename(fn)}")
        try:
            df = load_and_preprocess(fn)
            if "ARV" not in df.columns:
                continue
            thresh = df["ARV"].quantile(PEAK_THRESHOLD_PERCENTILE / 100.0)
            base = os.path.splitext(os.path.basename(fn))[0]
            peaks_df, summary_df = analyze(df, thresh, base, base)
            if peaks_df is not None:
                add_metadata(summary_df, peaks_df, fn)
                summaries.append(summary_df)
                peaks_all.append(peaks_df)
        except Exception as e:
            print(f"   error: {e}")

    if summaries:
        master = pd.concat(summaries, ignore_index=True)
        peaks_master = pd.concat(peaks_all, ignore_index=True)
        out = os.path.join(SUMMARY_FOLDER, "_EMG_Summary.xlsx")
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            master.to_excel(w, sheet_name="summary", index=False)
            peaks_master.to_excel(w, sheet_name="peaks", index=False)
        print(f"done -> {os.path.abspath(SUMMARY_FOLDER)}")
    else:
        print("no summaries produced")


if __name__ == "__main__":
    main()
