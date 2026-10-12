#!/usr/bin/env python3
import csv
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TASK2A = os.path.join(ROOT, "data", "task2a")
TASK2B = os.path.join(ROOT, "data", "task2b")
RESULTS_DIR = os.path.join(ROOT, "results", "task2")
PLOTS_DIR = os.path.join(ROOT, "plots", "task2b")
THRESHOLDS = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
TRACES = [1, 2, 3]

POLICY_COLORS = {"dyn": "#2a78d6", "irrip": "#1baf7a", "rrip": "#eb6834"}
TRACE_COLORS = {1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

PATTERNS = {
    "ipc": r"CPU 0 cumulative IPC:\s+([\d.]+)",
    "l2c_load": r"^L2C LOAD\s+ACCESS:.*MPKI:\s+([\d.]+)",
    "l2c_instr": r"^L2C INSTRUCTION LOAD MPKI:\s+([\d.]+)",
    "l2c_data": r"^L2C DATA LOAD MPKI:\s+([\d.]+)",
}

METRICS = [
    ("speedup", "Speedup vs LRU", "{:.4f}", "speedup_vs_threshold.png"),
    ("l2c_instr", "L2C Instr. Load MPKI", "{:.3f}", "instr_mpki_vs_threshold.png"),
    ("l2c_data", "L2C Data Load MPKI", "{:.3f}", "data_mpki_vs_threshold.png"),
    ("l2c_load", "L2C Load MPKI", "{:.3f}", "load_mpki_vs_threshold.png"),
]


def parse(path):
    text = open(path).read()
    out = {}
    for key, pat in PATTERNS.items():
        m = re.search(pat, text, re.M)
        if not m:
            raise ValueError(f"{key} not found in {path}")
        out[key] = float(m.group(1))
    return out


lru = {t: parse(os.path.join(TASK2A, f"lru_{t}.txt")) for t in TRACES}
irrip = {t: parse(os.path.join(TASK2A, f"irrip_{t}.txt")) for t in TRACES}
rrip = {t: parse(os.path.join(TASK2A, f"rrip_{t}.txt")) for t in TRACES}
dyn = {th: {t: parse(os.path.join(TASK2B, f"dyn_irrip_thresh{th}_{t}.txt")) for t in TRACES} for th in THRESHOLDS}

for runs in [lru, irrip, rrip] + list(dyn.values()):
    for t in TRACES:
        s = runs[t]
        s["speedup"] = s["ipc"] / lru[t]["ipc"]
        s["speedup_pct"] = (s["speedup"] - 1) * 100
        s["instr_red_pct"] = (1 - s["l2c_instr"] / lru[t]["l2c_instr"]) * 100
        s["data_red_pct"] = (1 - s["l2c_data"] / lru[t]["l2c_data"]) * 100

with open(os.path.join(RESULTS_DIR, "results_2b.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Trace", "Policy", "IPC"] + [label for _, label, _, _ in METRICS]
               + ["Instr. MPKI Reduction vs LRU (%)", "Data MPKI Reduction vs LRU (%)"])
    for t in TRACES:
        rows = [("SRRIP", rrip[t]), ("iRRIP", irrip[t])] + [(f"dyn_iRRIP (thresh {th})", dyn[th][t]) for th in THRESHOLDS]
        for name, s in rows:
            w.writerow([f"Trace{t}", name, f"{s['ipc']:.4f}"] + [fmt.format(s[key]) for key, _, fmt, _ in METRICS]
                       + [f"{s['instr_red_pct']:.2f}", f"{s['data_red_pct']:.2f}"])

plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#8a8984", "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2})


def style(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.tick_params(length=0)
    ax.set_xticks(THRESHOLDS)
    ax.set_xticklabels([f"{th:g}" for th in THRESHOLDS])
    ax.ticklabel_format(axis="y", useOffset=False)
    ax.set_xlabel("INSTR_THRESH")


def save(fig, name, title):
    fig.suptitle(title, x=0.01, ha="left", fontsize=14, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.9))
    fig.savefig(os.path.join(PLOTS_DIR, name), dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", name)


for key, label, _, fname in METRICS:
    fig, axes = plt.subplots(1, len(TRACES), figsize=(15, 4.8))
    for ax, t in zip(axes, TRACES):
        ax.plot(THRESHOLDS, [dyn[th][t][key] for th in THRESHOLDS], color=POLICY_COLORS["dyn"], linewidth=2,
                marker="o", markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, label="dynamic iRRIP", zorder=3)
        ax.axhline(irrip[t][key], color=POLICY_COLORS["irrip"], linewidth=2, linestyle="--", label="static iRRIP", zorder=2)
        ax.axhline(rrip[t][key], color=POLICY_COLORS["rrip"], linewidth=2, linestyle=":", label="SRRIP", zorder=2)
        ax.set_title(f"Trace{t}", fontsize=12, color=INK)
        style(ax)
    axes[0].set_ylabel(label)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="upper left", bbox_to_anchor=(0.005, 0.93), ncol=3, frameon=False)
    save(fig, fname, f"{label}: dynamic iRRIP threshold sweep")

fig, axes = plt.subplots(1, 3, figsize=(18, 5))
for ax, (key, label) in zip(axes, [("speedup_pct", "Speedup vs LRU (%)"),
                                   ("instr_red_pct", "Instr. MPKI reduction vs LRU (%)"),
                                   ("data_red_pct", "Data MPKI reduction vs LRU (%)")]):
    for t in TRACES:
        vals = [dyn[th][t][key] for th in THRESHOLDS]
        ax.plot(THRESHOLDS, vals, color=TRACE_COLORS[t], linewidth=2, marker="o", markersize=8,
                markeredgecolor=SURFACE, markeredgewidth=2, label=f"Trace{t}", zorder=3)
    ax.axhline(0, color=INK2, linewidth=1, zorder=1)
    ax.set_title(label, loc="left", fontsize=12, color=INK)
    style(ax)
handles, names = axes[0].get_legend_handles_labels()
fig.legend(handles, names, loc="upper left", bbox_to_anchor=(0.005, 0.93), ncol=3, frameon=False)
save(fig, "summary_vs_threshold.png", "Dynamic iRRIP: effect of INSTR_THRESH across traces (higher is better)")
