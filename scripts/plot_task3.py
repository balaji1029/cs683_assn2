#!/usr/bin/env python3
"""Validate Task 3 logs and regenerate the assignment tables and plots."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "cs683-mpl"))
os.environ.setdefault("XDG_CACHE_HOME", str(Path(tempfile.gettempdir()) / "cs683-font-cache"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/task3"
RESULTS = ROOT / "results/task3"
PLOTS = ROOT / "plots/task3"
CONFIGS = ["baseline", "standalone_spp", "dynamic_irrip", "task3"]
LABELS = {
    "baseline": "No prefetch + LRU",
    "standalone_spp": "Standalone SPP",
    "dynamic_irrip": "Dynamic I-RRIP",
    "task3": "Task 3",
}
COLORS = ["#89939d", "#377eb8", "#e08235", "#228567"]
TRACES = [1, 2, 3]


def capture(pattern, text, label):
    match = re.search(pattern, text, re.M)
    if match is None:
        raise ValueError(f"Missing {label}")
    return match


def parse_log(config, trace, provenance):
    path = DATA / f"{config}_trace{trace}.txt"
    raw = path.read_bytes()
    expected = provenance["logs"][path.name]
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Log hash mismatch: {path}")
    text = raw.decode()
    if "ChampSim completed all CPUs" not in text:
        raise ValueError(f"Incomplete simulation: {path}")
    for header in ("Warmup Instructions: 25000000", "Simulation Instructions: 25000000",
                   f"CPU 0 runs /traces/Trace{trace}.gz"):
        if header not in text:
            raise ValueError(f"Wrong run configuration in {path}: {header}")
    roi = text.split("Region of Interest Statistics", 1)[1]
    match = capture(r"^CPU 0 cumulative IPC:\s+(\S+) instructions:\s+(\d+) cycles:\s+(\d+)",
                    roi, f"ROI instructions/cycles in {path}")
    instructions, cycles = int(match[2]), int(match[3])
    if not 25000000 <= instructions <= 25000010 or cycles <= 0:
        raise ValueError(f"Unexpected ROI length in {path}")
    row = {"configuration": config, "trace": trace, "instructions": instructions,
           "cycles": cycles, "ipc": instructions / cycles,
           "log": str(path.relative_to(ROOT))}
    if abs(row["ipc"] - float(match[1])) > 1e-6:
        raise ValueError(f"IPC does not agree with counts: {path}")
    for cache, key in (("L1D", "l1d_load"), ("L2C", "l2c_load")):
        match = capture(rf"^{cache} LOAD\s+ACCESS:\s+(\d+)\s+HIT:\s+(\d+)\s+MISS:\s+(\d+)",
                        roi, f"{cache} LOAD in {path}")
        accesses, hits, misses = (int(value) for value in match.groups())
        if accesses != hits + misses:
            raise ValueError(f"Inconsistent {cache} load counts: {path}")
        row[f"{key}_accesses"] = accesses
        row[f"{key}_misses"] = misses
        row[f"{key}_mpki"] = misses * 1000 / instructions
    for name, pattern in (
        ("l2_instruction_load_mpki", r"^L2C INSTRUCTION LOAD MPKI:\s+(\S+)"),
        ("l2_data_load_mpki", r"^L2C DATA LOAD MPKI:\s+(\S+)"),
    ):
        row[name] = float(capture(pattern, roi, f"{name} in {path}")[1])
    if abs(row["l2_instruction_load_mpki"] + row["l2_data_load_mpki"]
           - row["l2c_load_mpki"]) > 0.001:
        raise ValueError(f"L2 instruction/data MPKI do not sum to total: {path}")
    match = capture(r"^L1D USEFUL LOAD PREFETCHES:\s+(\d+)\s+PREFETCH ISSUED TO LOWER LEVEL:\s+(\d+)",
                    roi, f"L1D prefetch statistics in {path}")
    useful, lower = int(match[1]), int(match[2])
    row.update(l1d_useful_prefetches=useful, l1d_prefetches_to_lower_level=lower,
               prefetch_accuracy_percent=100 * useful / lower if lower else None)
    if config in ("standalone_spp", "task3") and not lower:
        raise ValueError(f"Prefetch configuration issued no lower-level requests: {path}")
    return row


def table(headers, rows):
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
        *["| " + " | ".join(str(value) for value in row) + " |" for row in rows],
    ])


def geometric_mean(values):
    return math.exp(sum(math.log(value) for value in values) / len(values))


def plot_metric(lookup, key, title, ylabel, filename, *, prefetch_only=False):
    configs = ["standalone_spp", "task3"] if prefetch_only else CONFIGS
    fig, ax = plt.subplots(figsize=(7.2, 4.1))
    positions = np.arange(len(TRACES))
    width = 0.78 / len(configs)
    for index, config in enumerate(configs):
        values = [lookup[config, trace][key] for trace in TRACES]
        if any(value is None for value in values):
            raise ValueError(f"Missing plotted metric {key}: {config}")
        bars = ax.bar(positions + (index - (len(configs) - 1) / 2) * width,
                      values, width * 0.9, label=LABELS[config],
                      color=COLORS[CONFIGS.index(config)], zorder=3)
        precision = 4 if key in ("ipc", "speedup") else 2
        ax.bar_label(bars, labels=[f"{value:.{precision}f}" for value in values],
                     padding=3, fontsize=8, rotation=90 if len(configs) == 4 else 0)
    ax.set_xticks(positions, [f"Trace {trace}" for trace in TRACES])
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color="#e1e5e8", zorder=0)
    ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    if key == "speedup":
        ax.axhline(1, color="#424950", linestyle="--", linewidth=1)
        values = [lookup[c, t][key] for c in configs for t in TRACES]
        ax.set_ylim(min(0.98, min(values) - 0.01), max(values) + 0.025)
    elif key == "prefetch_accuracy_percent":
        ax.set_ylim(0, 100)
    else:
        ax.margins(y=0.22)
    fig.suptitle(title, x=0.06, y=0.98, ha="left", fontsize=14, weight="bold")
    fig.legend(*ax.get_legend_handles_labels(), loc="upper left", bbox_to_anchor=(0.05, 0.91),
               ncol=len(configs), frameon=False, fontsize=9)
    fig.text(0.06, 0.015, "25M warmup + 25M measured instructions; all provided traces",
             fontsize=9, color="#59636d")
    fig.subplots_adjust(left=0.10, right=0.98, bottom=0.12, top=0.78)
    fig.savefig(PLOTS / filename, dpi=170, facecolor="white")
    plt.close(fig)


def main():
    provenance = json.loads((RESULTS / "provenance.json").read_text())
    if provenance["warmup_instructions"] != 25000000 or provenance["simulation_instructions"] != 25000000:
        raise ValueError("Provenance has the wrong simulation length")
    rows = [parse_log(config, trace, provenance) for trace in TRACES for config in CONFIGS]
    lookup = {(row["configuration"], row["trace"]): row for row in rows}
    for row in rows:
        baseline = lookup["baseline", row["trace"]]
        row["speedup"] = row["ipc"] / baseline["ipc"]
        row["coverage_percent"] = 100 * (baseline["l1d_load_misses"] - row["l1d_load_misses"]) / baseline["l1d_load_misses"]
    comparisons = []
    for trace in TRACES:
        task3 = lookup["task3", trace]
        comparisons.append({
            "trace": trace,
            "gain_vs_standalone_spp_percent": 100 * (task3["ipc"] / lookup["standalone_spp", trace]["ipc"] - 1),
            "gain_vs_dynamic_irrip_percent": 100 * (task3["ipc"] / lookup["dynamic_irrip", trace]["ipc"] - 1),
            "l1d_miss_reduction_vs_dynamic_irrip_percent": 100 * (
                1 - task3["l1d_load_misses"] / lookup["dynamic_irrip", trace]["l1d_load_misses"]),
        })
    geometric_gains = {config: 100 * (geometric_mean([
        lookup["task3", trace]["ipc"] / lookup[config, trace]["ipc"] for trace in TRACES]) - 1)
        for config in ("baseline", "standalone_spp", "dynamic_irrip")}
    result = {"rows": rows, "task3_comparisons": comparisons,
              "task3_geometric_mean_gain_percent": geometric_gains}
    (RESULTS / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    PLOTS.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    plot_specs = [
        ("ipc", "IPC by configuration", "Instructions per cycle", "ipc.png", False),
        ("speedup", "Speedup relative to no-prefetch LRU", "IPC / baseline IPC", "speedup.png", False),
        ("prefetch_accuracy_percent", "L1D prefetch accuracy", "Useful / lower-level requests (%)", "accuracy.png", True),
        ("coverage_percent", "L1D load-miss coverage", "Miss reduction vs no-prefetch LRU (%)", "coverage.png", True),
        ("l1d_load_mpki", "L1D load MPKI", "Load misses per 1,000 instructions", "l1d_load_mpki.png", False),
        ("l2c_load_mpki", "L2C load MPKI", "Load misses per 1,000 instructions", "l2c_load_mpki.png", False),
        ("l2_instruction_load_mpki", "L2 instruction load MPKI", "Instruction load misses per 1,000 instructions", "l2_instruction_load_mpki.png", False),
        ("l2_data_load_mpki", "L2 data load MPKI", "Data load misses per 1,000 instructions", "l2_data_load_mpki.png", False),
    ]
    for key, title, ylabel, filename, prefetch_only in plot_specs:
        plot_metric(lookup, key, title, ylabel, filename, prefetch_only=prefetch_only)
    report = ["# Task 3: SPP with prefetch-aware Dynamic I-RRIP", "",
        "All four configurations were rebuilt and rerun on all three provided traces with "
        "25 million warmup and 25 million measured instructions. These results use the current "
        "Task 3 implementation, without periodic instruction insertion or other experimental tuning.", "",
        "## Task 3 results", "",
        table(["Trace", "IPC", "Speedup vs baseline", "L1D accuracy (%)", "L1D coverage (%)",
               "L1D load MPKI", "L2C load MPKI", "L2 instruction MPKI", "L2 data MPKI"], [
            [f"Trace {t}"] + [f"{lookup['task3', t][key]:.6f}" for key in (
                "ipc", "speedup", "prefetch_accuracy_percent", "coverage_percent", "l1d_load_mpki",
                "l2c_load_mpki", "l2_instruction_load_mpki", "l2_data_load_mpki")]
            for t in TRACES]), "", "## Comparison with standalone policies", "",
        table(["Configuration", "Trace 1 IPC", "Trace 2 IPC", "Trace 3 IPC"], [
            [LABELS[c]] + [f"{lookup[c, t]['ipc']:.6f}" for t in TRACES] for c in CONFIGS]), "",
        table(["Trace", "Task 3 vs standalone SPP (%)", "Task 3 vs Dynamic I-RRIP (%)"], [
            [f"Trace {r['trace']}", f"{r['gain_vs_standalone_spp_percent']:+.6f}",
             f"{r['gain_vs_dynamic_irrip_percent']:+.6f}"] for r in comparisons] + [
            ["Geometric mean", f"{geometric_gains['standalone_spp']:+.6f}",
             f"{geometric_gains['dynamic_irrip']:+.6f}"]]), "",
        "These comparisons use each task's own policy: standalone SPP uses LRU; Task 2B uses "
        "regular-RRIP leaders, threshold 0.25, interval 4096, and data-hit RRPV 1 in I-RRIP mode. "
        "Task 3 uses threshold 0.30, interval 8192, gradual data-hit promotion, and prefetch-aware "
        "RRIP updates, including on its leader sets. Thus the comparison evaluates complete "
        "configurations rather than isolating a single code change.", "",
        "## Metric definitions", "",
        "- **Baseline:** no L1D prefetching and LRU at L2. The same baseline is used for every "
        "speedup and primary coverage value.",
        "- **IPC:** measured instruction count divided by measured cycle count, using the final "
        "Region of Interest statistics rather than heartbeat samples.",
        "- **Speedup:** configuration IPC / no-prefetch LRU IPC for the same trace.",
        "- **L1D prefetch accuracy:** useful L1D prefetches / L1D prefetch requests issued to the "
        "lower level, multiplied by 100. This is the simulator's printed accuracy definition, "
        "not useful / all attempted prefetches. The SPP's internal throttling feedback uses "
        "resolved useful/useless prefetches and can differ from this reporting metric.",
        "- **L1D coverage:** (baseline L1D LOAD misses - configuration L1D LOAD misses) / "
        "baseline L1D LOAD misses, multiplied by 100. It measures net miss reduction, including "
        "pollution effects; it is not a count of prefetch hits. Negative values are retained.",
        "- **Load MPKI:** load misses per 1,000 measured instructions. L2 instruction and data "
        "values use the simulator's separate LOAD statistics; RFO, PREFETCH, and translation "
        "misses are excluded. L1D/L2C total load MPKI is calculated directly from miss counts.",
        "- No-prefetch configurations have undefined prefetch accuracy, represented by null in JSON.",
        "", "### Counts supporting Task 3 accuracy and coverage", "",
        table(["Trace", "Baseline L1D load misses", "Task 3 L1D load misses", "Useful L1D prefetches",
               "L1D prefetches to lower level"], [[f"Trace {t}", lookup['baseline', t]['l1d_load_misses'],
               lookup['task3', t]['l1d_load_misses'], lookup['task3', t]['l1d_useful_prefetches'],
               lookup['task3', t]['l1d_prefetches_to_lower_level']] for t in TRACES]), "",
        "## Why handle prefetch packets differently?", "",
        "RRPV ranges from 0 (protected, expected near reuse) to 3 (eviction-eligible). A data "
        "prefetch is speculative, so a PREFETCH fill in RRIP mode is inserted at 3 rather "
        "than the demand-fill value 2. WRITEBACK fills also receive 3 because a dirty-line "
        "transfer does not establish near-term demand reuse. A hit from either packet type "
        "leaves RRPV unchanged, avoiding both artificial promotion and demotion of a line "
        "already known to be useful. A later demand hit provides reuse evidence and promotes "
        "the line: to 0 in RRIP mode, or by decrementing RRPV in I-RRIP mode.", "",
        "In I-RRIP mode, instruction fills receive RRPV 2, instruction hits receive 0, and "
        "all non-instruction fills receive 3. Victim selection prefers non-instruction "
        "lines among candidates already at RRPV 3. This combines instruction protection "
        "with low initial protection for speculative data. The tradeoff is that useful "
        "prefetches or demand-data fills can be evicted before reuse. Packet type identifies "
        "the current access; it is not permanent per-line prefetch provenance.", "",
        "The 32 leader sets select the follower mode using "
        "(instruction accesses + instruction misses) / (all eligible accesses + misses). "
        "WRITEBACK is excluded; PREFETCH and translation traffic remain included. Every "
        "8192 eligible leader updates, the ratio is compared with 0.30, then the four "
        "history counters are multiplied by 0.9. The interval counts accesses, not cycles.", "",
        "**Leader-set distinction:** Task 3 deliberately applies its prefetch-aware RRIP "
        "helper to leaders as well as RRIP-mode followers, so leaders sample that RRIP "
        "variant. Task 2B's leaders use original RRIP. This is an implementation distinction "
        "from Task 2's regular-RRIP leader prescription, not an assertion that the two "
        "leader policies are identical. No implementation changes were made for this evaluation.",
        "", "## Plots", ""]
    for _, title, _, filename, _ in plot_specs:
        report.extend([f"### {title}", "", f"![{title}](../../plots/task3/{filename})", ""])
    report.extend(["## Reproduction and provenance", "",
        "The runner builds immutable Git snapshots in temporary directories and mounts traces "
        "read-only. It does not change the working replacement or prefetcher files. Compiler, "
        "Docker image ID, source hashes, trace hashes, and log hashes are in "
        "[provenance.json](provenance.json). Full-precision metrics and all comparison rows "
        "are in [results.json](results.json). Raw simulation and build logs are under "
        "[data/task3](../../data/task3). Trace files and binaries are not included.", "",
        table(["Configuration", "Source commit", "L1D prefetcher", "L2 policy"], [
            [LABELS[c], provenance['configurations'][c]['commit'],
             provenance['configurations'][c]['prefetcher'],
             provenance['configurations'][c]['replacement']] for c in CONFIGS]), "",
        "Run from the repository root on a host with Docker, the ubuntu-gcc7 image, and the "
        "three traces under ../traces. Exact source revisions for these results:", "", "```bash",
        "python3 scripts/run_task3.py \\",
        f"  --task1-ref {provenance['configurations']['standalone_spp']['commit']} \\",
        f"  --task2-ref {provenance['configurations']['dynamic_irrip']['commit']} \\",
        f"  --task3-ref {provenance['configurations']['task3']['commit']}",
        "python3 scripts/plot_task3.py", "```", "",
        "For a new evaluation of current branch tips, omit the --task*-ref arguments. "
        "Plot regeneration alone requires Python, NumPy, and Matplotlib; no simulations "
        "or trace files are needed. The parser verifies log hashes, simulation lengths, "
        "load-count identities, IPC/count consistency, and the L2 instruction/data split "
        "before producing results.", ""])
    (RESULTS / "README.md").write_text("\n".join(report))
    print(table(["Configuration", "Trace 1 IPC", "Trace 2 IPC", "Trace 3 IPC"], [
        [LABELS[c]] + [f"{lookup[c, t]['ipc']:.6f}" for t in TRACES] for c in CONFIGS]))
    print("Task 3 geometric mean gains (%):", geometric_gains)
    print("Validated 12 logs and generated all eight required metric plots.")


if __name__ == "__main__":
    main()
