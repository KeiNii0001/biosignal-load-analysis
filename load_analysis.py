"""
Physical-load analysis from wearable heart-rate and inertial data.

For each recording it computes:
  - average heart rate
  - time spent in a high-HR "danger" zone
  - average acceleration magnitude (activity intensity)
  - an HR / motion ratio (a simple "effort per unit of movement" index)

It then compares each tool against the Baseline condition and plots the
percentage improvement per subject.

Input: synthetic .xlsx files produced by generate_synthetic_data.py
(see README.md). No real measured data is included in this repository.
"""

import os
import glob
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")           # headless backend; no display needed
import matplotlib.pyplot as plt
import seaborn as sns

HEADER_ROW_INDEX = 9
SAMPLING_FREQUENCY = 1000
HR_DANGER_THRESHOLD = 130
BASELINE_TOOL = "Baseline"

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "..", "output_load_analysis")


# ---------- filename parsing (abstract labels) ----------
def get_subject(filename):
    base = os.path.basename(filename)
    for s in ["S1", "S2", "S3", "S4", "S5"]:
        if f"_{s}." in base or f"_{s}_" in base:
            return s
    return "Unknown"


def get_tool(filename):
    parts = os.path.basename(filename).split("_")
    return parts[2] if len(parts) > 2 else "Unknown"


def get_condition(filename):
    if "Light" in filename:
        return "Light"
    if "Heavy" in filename:
        return "Heavy"
    return "Other"


# ---------- per-file metrics ----------
def process_file(filename):
    try:
        df = pd.read_excel(filename, header=HEADER_ROW_INDEX, engine="openpyxl")
        df = df.loc[:, ~df.columns.astype(str).str.startswith("Unnamed")]

        if "Acc_Mag" not in df.columns and {"加速度X", "加速度Y", "加速度Z"}.issubset(df.columns):
            df["Acc_Mag"] = np.sqrt(df["加速度X"] ** 2 + df["加速度Y"] ** 2 + df["加速度Z"] ** 2)

        avg_hr, danger_time = np.nan, 0
        if "HR" in df.columns:
            valid_hr = df["HR"][df["HR"] > 30]          # drop obvious noise
            if not valid_hr.empty:
                avg_hr = valid_hr.mean()
                danger_time = (valid_hr >= HR_DANGER_THRESHOLD).sum() / SAMPLING_FREQUENCY

        avg_acc = df["Acc_Mag"].mean() if "Acc_Mag" in df.columns else np.nan
        hr_motion_ratio = avg_hr / avg_acc if (avg_acc and avg_acc > 0 and not np.isnan(avg_hr)) else np.nan

        return {
            "File": os.path.basename(filename),
            "Subject": get_subject(filename),
            "Tool": get_tool(filename),
            "Condition": get_condition(filename),
            "Avg_HR": avg_hr,
            "Danger_Time_s": danger_time,
            "Avg_Acc": avg_acc,
            "HR_Motion_Ratio": hr_motion_ratio,
        }
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        return None


# ---------- improvement vs baseline ----------
def create_improvement_charts(df_subj, subject, output_folder):
    rows = []
    for cond in df_subj["Condition"].unique():
        df_cond = df_subj[df_subj["Condition"] == cond]
        base = df_cond[df_cond["Tool"].str.contains(BASELINE_TOOL)]
        if base.empty:
            continue
        b_hr = base.iloc[0]["Avg_HR"]
        b_danger = base.iloc[0]["Danger_Time_s"]
        b_ratio = base.iloc[0]["HR_Motion_Ratio"]
        for _, r in df_cond.iterrows():
            if BASELINE_TOOL in r["Tool"]:
                continue
            rows.append({
                "Tool": r["Tool"],
                "Condition": cond,
                "Imp_HR": (b_hr - r["Avg_HR"]) / b_hr * 100 if b_hr > 0 else 0,
                "Imp_Danger": (b_danger - r["Danger_Time_s"]) / b_danger * 100 if b_danger > 0 else 0,
                "Imp_Ratio": (b_ratio - r["HR_Motion_Ratio"]) / b_ratio * 100 if b_ratio > 0 else 0,
            })
    if not rows:
        print(f"   -> no baseline ('{BASELINE_TOOL}') for subject {subject}; skipping improvement chart")
        return

    df_imp = pd.DataFrame(rows)
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    fig.suptitle(f"Subject {subject}: improvement vs Baseline", fontsize=18, y=1.03)

    specs = [
        ("Imp_HR", "Greens", "1. Avg HR reduction [%]\n(higher = easier)"),
        ("Imp_Danger", "Oranges", "2. High-HR time reduction [%]\n(higher = safer)"),
        ("Imp_Ratio", "Purples", "3. Effort/motion ratio improvement [%]\n(higher = more efficient)"),
    ]
    for ax, (col, pal, title) in zip(axes, specs):
        sns.barplot(x="Tool", y=col, hue="Condition", data=df_imp, ax=ax, palette=pal)
        ax.set_title(title, fontsize=12)
        ax.set_ylabel("Improvement (%)")
        ax.set_xlabel("")
        ax.axhline(0, color="gray", linestyle="--")
        ax.grid(axis="y", alpha=0.3)
        ax.legend(loc="upper right", framealpha=0.9)

    plt.tight_layout()
    path = os.path.join(output_folder, f"Improvement_Subject_{subject}.png")
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"   -> saved {path}")


def main():
    print("--- physical-load analysis (synthetic demo data) ---")
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    files = glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
    files = [f for f in files if not os.path.basename(f).startswith("_")]
    print(f"found {len(files)} files")

    metrics = [process_file(f) for f in files]
    metrics = [m for m in metrics if m]
    if not metrics:
        print("no valid data; run generate_synthetic_data.py first")
        return

    df_all = pd.DataFrame(metrics)
    plt.rcParams["axes.unicode_minus"] = False

    for subj in df_all["Subject"].unique():
        print(f"subject {subj}...")
        df_subj = df_all[df_all["Subject"] == subj].copy()

        # summary spreadsheet
        cols = ["Subject", "Condition", "Tool", "Avg_HR", "Danger_Time_s", "Avg_Acc", "HR_Motion_Ratio", "File"]
        df_subj[[c for c in cols if c in df_subj.columns]].to_excel(
            os.path.join(OUTPUT_FOLDER, f"Summary_Subject_{subj}.xlsx"), index=False)

        # absolute-value comparison
        df_subj = df_subj.sort_values("Tool")
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle(f"Subject {subj}: load & efficiency summary", fontsize=18, y=0.98)
        panels = [
            (axes[0, 0], "Avg_HR", "Blues", "1. Avg HR [bpm]", "bpm", ""),
            (axes[0, 1], "Danger_Time_s", "Reds", f"2. High-HR time (>{HR_DANGER_THRESHOLD}bpm) [s]", "seconds", ""),
            (axes[1, 0], "Avg_Acc", "Greens", "3. Activity intensity [g]", "g", "Tool"),
            (axes[1, 1], "HR_Motion_Ratio", "Purples", "4. HR/motion ratio [bpm/g]", "ratio", "Tool"),
        ]
        for ax, col, pal, title, ylab, xlab in panels:
            sns.barplot(x="Tool", y=col, hue="Condition", data=df_subj, ax=ax, palette=pal)
            ax.set_title(title)
            ax.set_ylabel(ylab)
            ax.set_xlabel(xlab)
            ax.tick_params(axis="x", rotation=15)
            ax.grid(axis="y", alpha=0.3)
            ax.legend(loc="upper right", framealpha=0.9)
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        plt.savefig(os.path.join(OUTPUT_FOLDER, f"Absolute_Subject_{subj}.png"))
        plt.close()

        create_improvement_charts(df_subj, subj, OUTPUT_FOLDER)

    print(f"done -> {os.path.abspath(OUTPUT_FOLDER)}")


if __name__ == "__main__":
    main()
