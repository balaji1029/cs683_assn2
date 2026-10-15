#!/usr/bin/env python3
import csv
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TASK2A = os.path.join(ROOT, "data", "task2a")
LEADERS_DIR = os.path.join(ROOT, "data", "task2b_leaders")
RESULTS_DIR = os.path.join(ROOT, "results", "task2")
PLOTS_DIR = os.path.join(ROOT, "plots", "task2b_leaders")
TRACES = [1, 2, 3]
LEADERS = [8, 16, 32, 64]
THRESHOLDS = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
LEADER_COLORS = {8: "#eda100", 16: "#2a78d6", 32: "#eb6834", 64: "#1baf7a"}
LEADER_MARKERS = {8: "^", 16: "o", 32: "s", 64: "D"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

PATTERNS = {
    "ipc": r"CPU 0 cumulative IPC:\s+([\d.]+)",
    "l2c_load": r"^L2C LOAD\s+ACCESS:.*MPKI:\s+([\d.]+)",
    "l2c_instr": r"^L2C INSTRUCTION LOAD MPKI:\s+([\d.]+)",
    "l2c_data": r"^L2C DATA LOAD MPKI:\s+([\d.]+)",
}


def parse(path):
    text = open(path).read()
    out = {}
    for key, pat in PATTERNS.items():
        m = re.search(pat, text, re.M)
        if not m:
            raise ValueError(f"{key} not found in {path}")
        out[key] = float(m.group(1))
    return out


def geomean(xs):
    return float(np.exp(np.mean(np.log(xs))))


lru = {t: parse(os.path.join(TASK2A, f"lru_{t}.txt")) for t in TRACES}


def load(path_fn):
    runs = {t: parse(path_fn(t)) for t in TRACES}
    for t in TRACES:
        runs[t]["speedup"] = runs[t]["ipc"] / lru[t]["ipc"]
    return runs


def summary(runs, key):
    vals = [runs[t][key] for t in TRACES]
    return geomean(vals) if key == "speedup" else float(np.mean(vals))


irrip = load(lambda t: os.path.join(TASK2A, f"irrip_{t}.txt"))
rrip = load(lambda t: os.path.join(TASK2A, f"rrip_{t}.txt"))
sweep = {(L, th): load(lambda t, L=L, th=th: os.path.join(LEADERS_DIR, f"L{L}_t{int(round(th * 100)):03d}_{t}.txt"))
         for L in LEADERS for th in THRESHOLDS}

with open(os.path.join(RESULTS_DIR, "results_2b_leaders.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["NUM_LEADERS", "INSTR_THRESH"]
               + [f"Trace{t} Speedup" for t in TRACES] + [f"Trace{t} Instr. MPKI" for t in TRACES]
               + [f"Trace{t} Data MPKI" for t in TRACES] + ["Geomean Speedup", "Mean Instr. MPKI", "Mean Data MPKI"])
    for (L, th), runs in sweep.items():
        w.writerow([L, th] + [f"{runs[t]['speedup']:.4f}" for t in TRACES]
                   + [f"{runs[t]['l2c_instr']:.3f}" for t in TRACES] + [f"{runs[t]['l2c_data']:.3f}" for t in TRACES]
                   + [f"{summary(runs, 'speedup'):.4f}", f"{summary(runs, 'l2c_instr'):.3f}",
                      f"{summary(runs, 'l2c_data'):.3f}"])

rank = lambda k: (round(summary(sweep[k], "speedup"), 4), -summary(sweep[k], "l2c_instr"))
best = {L: max([(L, th) for th in THRESHOLDS], key=rank) for L in LEADERS}
for L in LEADERS:
    k = best[L]
    print(f"best for {L} leaders: INSTR_THRESH={k[1]}  geomean speedup={summary(sweep[k], 'speedup'):.4f}  "
          f"mean instr MPKI={summary(sweep[k], 'l2c_instr'):.3f}")
print(f"overall best: NUM_LEADERS={max(best.values(), key=rank)[0]}, INSTR_THRESH={max(best.values(), key=rank)[1]}")

plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#8a8984", "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2})

for key, label, fname in [("speedup", "Speedup vs LRU", "speedup_vs_threshold.png"),
                          ("l2c_instr", "L2C Instr. Load MPKI", "instr_mpki_vs_threshold.png"),
                          ("l2c_data", "L2C Data Load MPKI", "data_mpki_vs_threshold.png")]:
    fig, axes = plt.subplots(1, len(TRACES) + 1, figsize=(19, 4.8))
    panels = [(f"Trace{t}", lambda runs, t=t: runs[t][key]) for t in TRACES]
    panels.append(("Geomean" if key == "speedup" else "Mean", lambda runs: summary(runs, key)))
    for ax, (title, get) in zip(axes, panels):
        for L in LEADERS:
            ax.plot(THRESHOLDS, [get(sweep[(L, th)]) for th in THRESHOLDS], color=LEADER_COLORS[L], linewidth=2,
                    marker=LEADER_MARKERS[L], markersize=7, markeredgecolor=SURFACE, markeredgewidth=1.5,
                    label=f"{L} leaders", zorder=3)
        ax.axhline(get(irrip), color=INK2, linewidth=1.5, linestyle="--", label="static iRRIP", zorder=2)
        ax.axhline(get(rrip), color=INK2, linewidth=1.5, linestyle=":", label="SRRIP", zorder=2)
        ax.set_title(title, fontsize=12, color=INK)
        ax.set_xticks(THRESHOLDS)
        ax.set_xticklabels([f"{th:g}" for th in THRESHOLDS])
        ax.set_xlabel("INSTR_THRESH")
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        ax.tick_params(length=0)
        ax.ticklabel_format(axis="y", useOffset=False)
    axes[0].set_ylabel(label)
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="upper left", bbox_to_anchor=(0.005, 0.93), ncol=6, frameon=False)
    fig.suptitle(f"Threshold method, leader-set sensitivity: {label}", x=0.01, ha="left", fontsize=14, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(os.path.join(PLOTS_DIR, fname), dpi=150, facecolor=SURFACE)
    plt.close(fig)
    print("wrote", fname)

fig, ax = plt.subplots(figsize=(10, 4.8))
vals = [summary(sweep[best[L]], "speedup") for L in LEADERS]
bars = ax.bar([f"{L} leaders\n(thresh {best[L][1]:g})" for L in LEADERS], vals,
              color=[LEADER_COLORS[L] for L in LEADERS], width=0.6, zorder=2)
for b, v in zip(bars, vals):
    ax.annotate(f"{v:.4f}", (b.get_x() + b.get_width() / 2, v), xytext=(0, 4), textcoords="offset points",
                ha="center", fontsize=10, color=INK2)
ax.axhline(summary(irrip, "speedup"), color=INK2, linewidth=1.5, linestyle="--", label="static iRRIP", zorder=3)
ax.set_ylim(min(vals + [summary(irrip, "speedup")]) - 0.002, max(vals + [summary(irrip, "speedup")]) + 0.002)
ax.set_ylabel("Geomean speedup vs LRU")
ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
ax.tick_params(length=0)
ax.ticklabel_format(axis="y", useOffset=False)
ax.legend(loc="upper left", frameon=False)
fig.suptitle("Best threshold per leader count", x=0.01, ha="left", fontsize=14, color=INK)
fig.tight_layout()
fig.savefig(os.path.join(PLOTS_DIR, "best_per_leaders.png"), dpi=150, facecolor=SURFACE)
plt.close(fig)
print("wrote best_per_leaders.png")
