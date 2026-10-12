#!/usr/bin/env python3
import csv
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA_DIR = os.path.join(ROOT, "data", "task2a")
RESULTS_DIR = os.path.join(ROOT, "results", "task2")
PLOTS_DIR = os.path.join(ROOT, "plots", "task2a")
POLICIES = [("lru", "LRU"), ("rrip", "SRRIP"), ("irrip_moderate", "iRRIP-Moderate"),
            ("irrip", "iRRIP")]
TRACES = [1, 2, 3]
COLORS = dict(zip([p for p, _ in POLICIES], ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]))

PATTERNS = {
    "ipc": r"CPU 0 cumulative IPC:\s+([\d.]+)",
    "l2c_load": r"^L2C LOAD\s+ACCESS:.*MPKI:\s+([\d.]+)",
    "l2c_instr": r"^L2C INSTRUCTION LOAD MPKI:\s+([\d.]+)",
    "l2c_data": r"^L2C DATA LOAD MPKI:\s+([\d.]+)",
}

METRICS = [
    ("ipc", "IPC", "{:.4f}"),
    ("speedup", "Speedup vs LRU", "{:.4f}"),
    ("l2c_load", "L2C Load MPKI", "{:.3f}"),
    ("l2c_instr", "L2C Instr. Load MPKI", "{:.3f}"),
    ("l2c_data", "L2C Data Load MPKI", "{:.3f}"),
    ("l2c_load_norm", "Normalized L2C Load MPKI", "{:.4f}"),
    ("l2c_load_red", "L2C Load MPKI Reduction vs LRU (%)", "{:.2f}"),
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


stats = {p: {t: parse(os.path.join(DATA_DIR, f"{p}_{t}.txt")) for t in TRACES} for p, _ in POLICIES}
for p, _ in POLICIES:
    for t in TRACES:
        s, base = stats[p][t], stats["lru"][t]
        s["speedup"] = s["ipc"] / base["ipc"]
        s["l2c_load_norm"] = s["l2c_load"] / base["l2c_load"]
        s["l2c_load_red"] = (1 - s["l2c_load_norm"]) * 100

rows = [[f"Trace{t}", name] + [fmt.format(stats[p][t][key]) for key, _, fmt in METRICS]
        for t in TRACES for p, name in POLICIES]
header = ["Trace", "Policy"] + [label for _, label, _ in METRICS]

table = "\n".join(["| " + " | ".join(header) + " |", "|---|---|" + "---:|" * len(METRICS)]
                  + ["| " + " | ".join(r) + " |" for r in rows])
with open(os.path.join(RESULTS_DIR, "results_2a.md"), "w") as f:
    f.write("# L2C replacement policy comparison (25M warmup + 25M sim)\n\n" + table + "\n")
print(table)

with open(os.path.join(RESULTS_DIR, "results_2a.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(header)
    w.writerows(rows)

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#8a8984", "axes.labelcolor": "#52514e",
                     "xtick.color": "#52514e", "ytick.color": "#52514e"})
PLOTS = [(key, label) for key, label, _ in METRICS[:5]] + \
        [("l2c_load_norm", "Normalized L2C Load MPKI (LRU = 1, lower is better)")]
fig, axes = plt.subplots(2, 3, figsize=(15, 8))
x = np.arange(len(TRACES))
width = 0.8 / len(POLICIES)

for ax, (key, title) in zip(axes.flat, PLOTS):
    for i, (p, name) in enumerate(POLICIES):
        vals = [stats[p][t][key] for t in TRACES]
        bars = ax.bar(x + (i - (len(POLICIES) - 1) / 2) * width, vals, width - 0.02,
                      color=COLORS[p], label=name, zorder=2)
        if key == "l2c_load_norm" and p != "lru":
            for b, t in zip(bars, TRACES):
                ax.annotate(f"{-stats[p][t]['l2c_load_red']:+.1f}%", (b.get_x() + b.get_width() / 2, b.get_height()),
                            xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", rotation=90,
                            fontsize=8, color="#52514e")
    ax.set_title(title, loc="left", fontsize=11, color="#0b0b0b")
    ax.set_xticks(x, [f"Trace{t}" for t in TRACES])
    ax.grid(axis="y", color="#e4e3df", linewidth=0.8, zorder=0)
    ax.tick_params(length=0)
    if key in ("speedup", "l2c_load_norm"):
        ax.axhline(1.0, color="#52514e", linewidth=1, linestyle="--", zorder=3)
    if key == "speedup":
        vals = [stats[p][t][key] for p, _ in POLICIES for t in TRACES]
        ax.set_ylim(min(vals) - 0.01, max(vals) + 0.01)
    if key == "l2c_load_norm":
        ax.set_ylim(0.7, 1.12)

handles, names = axes.flat[0].get_legend_handles_labels()
fig.legend(handles, names, loc="upper right", ncol=len(POLICIES), frameon=False, fontsize=11)
fig.suptitle("L2C replacement: LRU vs SRRIP vs iRRIP variants (25M warmup + 25M sim)", x=0.01, ha="left",
             fontsize=13, color="#0b0b0b")
fig.tight_layout(rect=(0, 0, 1, 0.97))
out = os.path.join(PLOTS_DIR, "results.png")
fig.savefig(out, dpi=150, facecolor="#fcfcfb")
print("wrote", out)
