#!/usr/bin/env python3
"""Build Task 3 and its references in temporary Docker workspaces."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--traces", type=Path, default=ROOT.parent / "traces")
    parser.add_argument("--image", default="ubuntu-gcc7")
    parser.add_argument("--task1-ref", default="main")
    parser.add_argument("--task2-ref", default="task2")
    parser.add_argument("--task3-ref", default="HEAD")
    args = parser.parse_args()
    traces = args.traces.resolve()
    for trace in range(1, 4):
        if not (traces / f"Trace{trace}.gz").is_file():
            parser.error(f"Missing {traces / f'Trace{trace}.gz'}")
    workspace = Path(tempfile.mkdtemp(prefix="cs683_task3_submission_"))
    (workspace / "data").mkdir()
    configurations = [
        ("baseline", args.task3_ref, "no", "lru"),
        ("standalone_spp", args.task1_ref, "spp", "lru"),
        ("dynamic_irrip", args.task2_ref, "no", "dyn_irrip"),
        ("task3", args.task3_ref, "spp", "dyn_irrip"),
    ]
    metadata = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "warmup_instructions": 25000000,
        "simulation_instructions": 25000000,
        "platform": "linux/amd64", "image": args.image,
        "workspace": str(workspace), "configurations": {},
        "traces": {f"Trace{t}.gz": {
            "bytes": (traces / f"Trace{t}.gz").stat().st_size,
            "sha256": sha256(traces / f"Trace{t}.gz"),
        } for t in range(1, 4)},
    }
    for name, ref, prefetcher, replacement in configurations:
        commit = subprocess.check_output(
            ["git", "rev-parse", ref], cwd=ROOT, text=True).strip()
        destination = workspace / name
        destination.mkdir()
        archive = subprocess.check_output(["git", "archive", commit], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            source.extractall(destination)
        metadata["configurations"][name] = {
            "ref": ref, "commit": commit, "prefetcher": prefetcher,
            "replacement": replacement,
            "spp_sha256": sha256(destination / "prefetcher/spp.l1d_pref"),
            "replacement_sha256": sha256(
                destination / f"replacement/{replacement}.l2c_repl"),
        }
    (workspace / "plan.json").write_text(json.dumps(metadata, indent=2) + "\n")
    # This driver runs inside the container. It never mounts the source repository.
    driver = '''from concurrent.futures import ThreadPoolExecutor
import json, os, pathlib, subprocess
root = pathlib.Path('/experiments')
plan = json.loads((root / 'plan.json').read_text())
(root / 'compiler.txt').write_text(subprocess.check_output(['g++', '--version'], text=True))
def run(item):
    name, config = item
    directory = root / name
    env = os.environ.copy()
    env['TERM'] = 'xterm'
    with (root / 'data' / f'build_{name}.log').open('w') as output:
        subprocess.run(['bash', './build_champsim.sh', config['prefetcher'],
                        config['replacement'], 'task3_results'], cwd=directory,
                       stdout=output, stderr=subprocess.STDOUT, env=env, check=True)
    binaries = list((directory / 'bin').glob('*task3_results'))
    assert len(binaries) == 1, binaries
    print(f'{name}: build passed', flush=True)
    for trace in range(1, 4):
        with (root / 'data' / f'{name}_trace{trace}.txt').open('w') as output:
            subprocess.run([str(binaries[0]), '-warmup_instructions', '25000000',
                            '-simulation_instructions', '25000000', '-traces',
                            f'/traces/Trace{trace}.gz'], cwd=directory,
                           stdout=output, stderr=subprocess.STDOUT, check=True)
        print(f'{name}: Trace{trace} completed', flush=True)
with ThreadPoolExecutor(max_workers=4) as pool:
    list(pool.map(run, plan['configurations'].items()))
'''
    (workspace / "run_inside.py").write_text(driver)
    print(f"Isolated build directory: {workspace}", flush=True)
    subprocess.run([
        "docker", "run", "--rm", "--platform", "linux/amd64",
        "-v", f"{traces}:/traces:ro", "-v", f"{workspace}:/experiments",
        "-w", "/experiments", args.image, "python3", "/experiments/run_inside.py",
    ], check=True)
    metadata["compiler"] = (workspace / "compiler.txt").read_text().strip()
    metadata["image_id"] = subprocess.check_output([
        "docker", "image", "inspect", args.image, "--format", "{{.Id}}"
    ], text=True).strip()
    metadata["completed_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["logs"] = {}
    output_directory = ROOT / "data/task3"
    output_directory.mkdir(parents=True, exist_ok=True)
    for path in sorted((workspace / "data").iterdir()):
        if path.suffix == ".txt":
            text = path.read_text()
            if "ChampSim completed all CPUs" not in text:
                raise RuntimeError(f"Incomplete simulation: {path}")
        shutil.copy2(path, output_directory / path.name)
        metadata["logs"][path.name] = sha256(path)
    results_directory = ROOT / "results/task3"
    results_directory.mkdir(parents=True, exist_ok=True)
    (results_directory / "provenance.json").write_text(
        json.dumps(metadata, indent=2) + "\n")
    print("Saved 12 simulation logs, build logs, and provenance.", flush=True)


if __name__ == "__main__":
    main()
