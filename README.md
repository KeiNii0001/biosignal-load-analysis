# biosignal-load-analysis

Analysis pipeline for estimating **physical workload from wearable biosignals** —
heart rate, tri-axial acceleration / angular velocity, and surface-EMG.

The pipeline takes raw-style sensor exports and produces per-subject workload
metrics, automatic EMG peak detection with dynamic/static motion classification,
and comparison charts across tool/load conditions.

> **Data note:** This repository ships with **synthetic demo data only**.
> `generate_synthetic_data.py` fabricates plausible but entirely artificial
> recordings so the pipeline can be run end-to-end by anyone. No real measured
> data is included. The analysis code reflects a real workflow I built for
> occupational-ergonomics measurement; the data here is a stand-in.

---

## What it does

**1. Physical-load analysis** (`load_analysis.py`)

From HR + acceleration it computes, per recording:

- average heart rate
- time spent in a high-HR "danger" zone (default > 130 bpm)
- average acceleration magnitude (activity intensity)
- an **HR / motion ratio** — a simple "effort per unit of movement" index

Then it computes each tool's **percentage improvement vs the Baseline
condition** and plots it per subject.

**2. EMG peak analysis** (`emg_peak_analysis.py`)

From the EMG ARV envelope + inertial data it:

- auto-selects a detection threshold at the **95th percentile** of each signal
- detects peaks (`scipy.signal.find_peaks`) with a minimum inter-peak distance
- classifies each peak as **Dynamic vs Static** using the angular-velocity burst
  in a short window right after the peak
- measures peak **width** and integrated **area** (mV·s)
- aggregates results per subject / tool / condition into Excel + plots

---

## Example output

Physical-load improvement vs baseline (synthetic):

![improvement](example_improvement.png)

EMG peak detection with dynamic (red ×) / static (blue +) classification:

![emg](example_emg.png)

---

## Repository layout

```
.
├── generate_synthetic_data.py   # creates synthetic demo recordings -> data/
├── load_analysis.py             # HR + acceleration workload analysis
├── emg_peak_analysis.py         # EMG peak detection & classification
├── example_improvement.png      # sample figure (physical-load analysis)
├── example_emg.png              # sample figure (EMG peak analysis)
├── LICENSE
└── README.md
```

Running the scripts additionally creates:

```
data/                    # synthetic .xlsx recordings (generated)
output_load_analysis/    # results & figures from load_analysis.py
output_emg/              # results & figures from emg_peak_analysis.py
```

---

## Quick start

```bash
# 1. install dependencies
pip install pandas numpy scipy matplotlib seaborn openpyxl

# 2. generate synthetic demo data  ->  data/*.xlsx
python generate_synthetic_data.py

# 3. run the analyses
python load_analysis.py       # -> output_load_analysis/
python emg_peak_analysis.py   # -> output_emg/
```

Python 3.9+ recommended.

---

## Input format

Each recording is an `.xlsx` whose real header sits on row 10 (rows above are
instrument metadata), sampled at 1000 Hz, with columns such as:

| column       | meaning                          |
| ------------ | -------------------------------- |
| `シーケンス番号`    | sample sequence number           |
| `HR`         | heart rate [bpm]                 |
| `加速度X/Y/Z`   | acceleration [g]                 |
| `角速度X/Y/Z`   | angular velocity [deg/s]         |
| `ARV`        | EMG average rectified value [mV] |

Filenames encode the experimental condition, e.g.
`01_Heavy_ToolA_ID01_001_S1.xlsx` → load = Heavy, tool = ToolA, subject = S1.

---

## Tech

Python · pandas · NumPy · SciPy (signal processing) · matplotlib · seaborn · openpyxl

## License

MIT — see [LICENSE](LICENSE).
