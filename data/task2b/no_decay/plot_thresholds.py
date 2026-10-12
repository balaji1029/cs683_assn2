#!/usr/bin/env python3
import csv
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches
import matplotlib.pyplot as plt

DIR = os.path.dirname(os.path.abspath(__file__))
TASK2A = os.path.join(DIR, "..", "task2a")
THRESHOLDS = [0.2, 0.3, 0.35, 0.4, 0.5]
TRACES = [1, 2, 3]
COLORS = {"dyn": "#2a78d6", "irrip": "#1baf7a", "rrip": "#eb6834", "adapt": "#3d3c38"}

PATTERNS = {
    "ipc": r"CPU 0 cumulative IPC:\s+([\d.]+)",
    "l2c_load": r"^L2C LOAD\s+ACCESS:.*MPKI:\s+([\d.]+)",
    "l2c_instr": r"^L2C INSTRUCTION LOAD MPKI:\s+([\d.]+)",
    "l2c_data": r"^L2C DATA LOAD MPKI:\s+([\d.]+)",
}

METRICS = [
    ("speedup", "Speedup vs LRU", "{:.4f}"),
    ("l2c_load", "L2C Load MPKI", "{:.3f}"),
    ("l2c_instr", "L2C Instr. Load MPKI", "{:.3f}"),
    ("l2c_data", "L2C Data Load MPKI", "{:.3f}"),
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
adapt = {t: parse(os.path.join(DIR, f"dyn_irrip_adapt_{t}.txt")) for t in TRACES}
dyn = {th: {t: parse(os.path.join(DIR, f"dyn_irrip_thresh{th}_{t}.txt")) for t in TRACES} for th in THRESHOLDS}

for runs in [irrip, rrip, adapt] + list(dyn.values()):
    for t in TRACES:
        runs[t]["speedup"] = runs[t]["ipc"] / lru[t]["ipc"]

with open(os.path.join(DIR, "threshold_sweep.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Trace", "Policy", "IPC"] + [label for _, label, _ in METRICS])
    for t in TRACES:
        rows = [("SRRIP", rrip[t]), ("iRRIP", irrip[t])] + [(f"dyn_iRRIP (thresh {th})", dyn[th][t]) for th in THRESHOLDS] + [("dyn_iRRIP (adaptive)", adapt[t])]
        for name, s in rows:
            w.writerow([f"Trace{t}", name, f"{s['ipc']:.4f}"] + [fmt.format(s[key]) for key, _, fmt in METRICS])

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#8a8984", "axes.labelcolor": "#52514e",
                     "xtick.color": "#52514e", "ytick.color": "#52514e"})
fig, axes = plt.subplots(len(METRICS), len(TRACES), figsize=(14, 13), sharex=True)

for r, (key, label, _) in enumerate(METRICS):
    for c, t in enumerate(TRACES):
        ax = axes[r][c]
        ax.plot(THRESHOLDS, [dyn[th][t][key] for th in THRESHOLDS], color=COLORS["dyn"], linewidth=2,
                marker="o", markersize=8, markeredgecolor="#fcfcfb", markeredgewidth=2, label="dyn_iRRIP", zorder=3)
        ax.axhline(irrip[t][key], color=COLORS["irrip"], linewidth=2, linestyle="--", label="iRRIP (static)", zorder=2)
        ax.axhline(rrip[t][key], color=COLORS["rrip"], linewidth=2, linestyle=":", label="SRRIP (static)", zorder=2)
        ax.axhline(adapt[t][key], color=COLORS["adapt"], linewidth=1.5, linestyle="-.", label="dyn_iRRIP (adaptive)", zorder=2)
        ax.grid(axis="y", color="#e4e3df", linewidth=0.8, zorder=0)
        ax.tick_params(length=0)
        ax.set_xticks(THRESHOLDS)
        ax.ticklabel_format(axis="y", useOffset=False)
        if r == 0:
            ax.set_title(f"Trace{t}", fontsize=12, color="#0b0b0b")
        if c == 0:
            ax.set_ylabel(label)
        if r == len(METRICS) - 1:
            ax.set_xlabel("INSTR_THRESH")

handles, names = axes[0][0].get_legend_handles_labels()
fig.legend(handles, names, loc="upper left", bbox_to_anchor=(0.005, 0.975), ncol=4, frameon=False, fontsize=11)
fig.suptitle("Dynamic iRRIP: threshold sweep vs static iRRIP / SRRIP (25M warmup + 25M sim)", x=0.01, ha="left",
             fontsize=13, color="#0b0b0b")
fig.tight_layout(rect=(0, 0, 1, 0.95))
out = os.path.join(DIR, "threshold_sweep.png")
fig.savefig(out, dpi=150, facecolor="#fcfcfb")
print("wrote", out)


traj = {}
for t in TRACES:
    pts = re.findall(r"DYN_ADAPT ratio: ([\d.]+) thresh: ([\d.]+) .* use_irrip: (\d)",
                     open(os.path.join(DIR, f"dyn_irrip_adapt_{t}.txt")).read())
    traj[t] = [(float(r), float(th), int(u)) for r, th, u in pts]

fig, axes = plt.subplots(1, len(TRACES), figsize=(15, 4.5), sharey=True)
for ax, t in zip(axes, TRACES):
    xs = list(range(1, len(traj[t]) + 1))
    ax.plot(xs, [p[0] for p in traj[t]], color=COLORS["dyn"], linewidth=2, marker="o", markersize=6,
            markeredgecolor="#fcfcfb", markeredgewidth=1.5, label="ratio (SRRIP leaders)", zorder=3)
    ax.step(xs, [p[1] for p in traj[t]], where="mid", color=COLORS["adapt"], linewidth=2, linestyle="-.",
            label="threshold", zorder=3)
    for x, p in zip(xs, traj[t]):
        if p[2]:
            ax.axvspan(x - 0.5, x + 0.5, color=COLORS["irrip"], alpha=0.12, linewidth=0, zorder=0)
    ax.set_title(f"Trace{t}", fontsize=12, color="#0b0b0b")
    ax.set_xlabel("decision # (every 4096 SRRIP-leader accesses, incl. warmup)")
    ax.grid(axis="y", color="#e4e3df", linewidth=0.8, zorder=0)
    ax.tick_params(length=0)
axes[0].set_ylabel("value")
handles, names = axes[0].get_legend_handles_labels()
handles.append(matplotlib.patches.Patch(color=COLORS["irrip"], alpha=0.25))
names.append("followers use iRRIP")
fig.legend(handles, names, loc="upper right", ncol=3, frameon=False, fontsize=11)
fig.suptitle("Adaptive threshold: ratio vs threshold at each decision", x=0.01, ha="left", fontsize=13, color="#0b0b0b")
fig.tight_layout(rect=(0, 0, 1, 0.9))
out = os.path.join(DIR, "adaptive_threshold.png")
fig.savefig(out, dpi=150, facecolor="#fcfcfb")
print("wrote", out)
