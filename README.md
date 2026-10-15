# ChampSim

ChampSim is a trace-based simulator for microarchitecture research.

Useful trace links:
- Traces (access requires an LDAP ID): https://drive.google.com/drive/folders/1zYchkn-M1auZp_l5wRkIzAcDYPkNtW3H?usp=sharing
- ChampSim wiki: https://champsim.github.io/ChampSim/master/index.html

## Where everything is (CS683 PA2)

The assignment work is split across three branches. The final report and all collected results are on `main` under `deliverables/`.

### Branches

| Branch | What it holds | Key files |
|---|---|---|
| `main` | Task 1 (L1D prefetchers) plus the deliverables for every task | `prefetcher/ip_stride.l1d_pref` (Task 1a), `prefetcher/spp.l1d_pref` (Task 1b, stride pattern prefetcher with dynamic degree), `deliverables/` |
| `task2` | Task 2A (static I-RRIP) and Task 2B (dynamic I-RRIP) for the L2C | `replacement/irrip.l2c_repl`, `replacement/irrip_moderate.l2c_repl`, `replacement/dyn_irrip.l2c_repl`, plus `scripts/`, `data/`, `plots/` and `results/task2/` |
| `task3` | Task 3: prefetch-aware dynamic I-RRIP, run together with the Task 1 SPP prefetcher | `replacement/dyn_irrip.l2c_repl` (prefetch- and writeback-aware version), `prefetcher/spp.l1d_pref`, `scripts/run_task3.py`, `scripts/plot_task3.py` |

The `task2` and `task3` branches also change `inc/cache.h`, `src/cache.cc`, `src/ooo_cpu.cc` and the replacement hooks (`replacement/*.repl`, `base_replacement.cc`) so the L2C replacement policy can tell whether an access is for an instruction. `main` does not have these changes, so build Task 2 and Task 3 binaries from their own branches:

```bash
git checkout task2 && ./build_champsim.sh no dyn_irrip task2b    # Task 2B
git checkout task3 && ./build_champsim.sh spp dyn_irrip task3    # Task 3
git checkout main  && ./build_champsim.sh spp lru task1b         # Task 1b
```

### Deliverables (`deliverables/` on `main`)

| Path | Contents |
|---|---|
| `deliverables/Summary.pdf` | The report covering Tasks 1a, 1b, 2A, 2B and 3.  |
| `deliverables/figures/task1/` | Task 1 plots (PDF): IPC, speedup, MPKI, accuracy, coverage, degree and confidence sensitivity, prefetch distance |
| `deliverables/figures/task2a/` | Comparison of static policies (LRU, SRRIP, I-RRIP variants) |
| `deliverables/figures/task2b/` | Dynamic I-RRIP threshold sweep (speedup and MPKI against threshold) |
| `deliverables/figures/task3/` | Task 3 IPC, speedup, accuracy, coverage, L1D/L2C MPKI |
| `deliverables/data/task1/` | Task 1 metrics and sweep results (CSV) and `provenance.json` |
| `deliverables/data/task2a/`, `task2b/` | Raw ChampSim output for each policy, threshold and trace |
| `deliverables/data/task3/` | Raw ChampSim output for baseline, standalone SPP, dynamic I-RRIP and Task 3, per trace |
| `deliverables/tables/task3/` | LaTeX tables included in the report |

### Other folders

- `traces/`: the three input traces (`Trace1.gz` to `Trace3.gz`). This folder is gitignored, so download the traces from the link below.
- `bin/`: compiled binaries. This folder is gitignored.
- On the `task2` branch, `plots/task2b_leaders/` and `results/task2/results_2b_leaders.csv` hold the extra sweep over the number of leader sets.

All simulations use 25M warmup and 25M simulation instructions.

## Clone the repository

```bash
git clone https://github.com/Shivraj1906/PA2-CS683-2026.git
```

## Compile

To compile ChampSim, specify three parameters: the L1D prefetcher, the L2C replacement policy, and the binary name.

For example, `./build_champsim.sh no lru baseline` builds a single-core processor with a hashed perceptron branch predictor, no L1D data prefetcher, and the LRU replacement policy for the L2C.

You can give the binary any name. Custom names help distinguish binaries that use the same configuration.

```bash
./build_champsim.sh ${L1D_PREFETCHER} ${L2C_REPLACEMENT} ${BINARY_NAME}

./build_champsim.sh no lru baseline
```

## Run simulation

```bash
./bin/[BINARY] -warmup_instructions [N_WARM] -simulation_instructions [N_SIM] -traces [TRACE_DIR]/[TRACE]
./bin/hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline -warmup_instructions 25000000 -simulation_instructions 25000000 -traces ../traces/trace1.champsimtrace.xz
```

Where:
- `${BINARY}`: ChampSim binary compiled by `build_champsim.sh` (for example, `hashed_perceptron-no-no-no-no-no-no-no-lru-lru-lru-lru-lru-lru-lru-lru-1core-baseline`)
- `${N_WARM}`: number of instructions for the warmup period (25 million)
- `${N_SIM}`: number of instructions for the detailed simulation (25 million)
- `${TRACE_DIR}`: directory containing the trace (for example, `../traces/`)
- `${TRACE}`: name of the trace (for example, `trace1.champsimtrace.xz`)

## Evaluate the simulation

ChampSim measures IPC (instructions per cycle) as its main performance metric. It also prints other useful metrics at the end of each simulation.

## Install GCC 7 on Ubuntu

```bash
sudo apt update
sudo add-apt-repository ppa:ubuntu-toolchain-r/test
vim /etc/apt/sources.list
```

Update the last line with:

```bash
deb [arch=amd64] http://archive.ubuntu.com/ubuntu focal main universe
```

Then run:

```bash
sudo add-apt-repository ppa:ubuntu-toolchain-r/test
sudo apt-get install gcc-7
sudo apt-get install g++-7
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-7 0
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-7 0
```

If GCC and G++ are already present in `/usr/bin`, configure the alternatives using:

```bash
sudo update-alternatives --config g++
sudo update-alternatives --config gcc
```

