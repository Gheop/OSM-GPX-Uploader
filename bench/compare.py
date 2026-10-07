#!/usr/bin/env python3
"""Interleave runs of two checkouts of the project and compare them.

Alternating A/B runs cancels most thermal and frequency drift, which
dominates noise on laptops where the governor cannot be pinned.

Both checkouts run under this checkout's harness.

Usage: python bench/compare.py [--warm] BASELINE_ROOT CANDIDATE_ROOT GPX_DIR [RUNS] [CPUS]
A single root measures that checkout alone (writes nothing).
CPUS is a taskset list, e.g. 12 or 12-19.
--warm keeps one working directory per checkout across runs, so a cache
written by the script survives (repeated runs); default is a fresh one each run.
"""
import json
import os
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

HARNESS = Path(__file__).resolve().parent / "run_scan.py"


def run_once(root, gpx_dir, cpu, env=None):
    # time writes "<wall seconds> <max RSS KB> <user seconds> <sys seconds>"
    # to stderr. Max RSS covers the largest single process, not the sum of
    # workers: measure the total with bench/mem_peak.sh
    cmd = ["/usr/bin/time", "-f", "%e %M %U %S", "taskset", "-c", cpu,
           sys.executable, str(HARNESS), str(Path(root) / "OSM-GPX-Uploader.py"), gpx_dir]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                          text=True, check=True, env=env)
    wall, rss, user, system = proc.stderr.strip().splitlines()[-1].split()
    return float(wall), int(rss), float(user) + float(system)


def summarize(samples):
    walls = sorted(s[0] for s in samples)
    return {
        "runs": len(samples),
        "median_s": statistics.median(walls),
        "p95_s": walls[min(len(walls) - 1, round(0.95 * (len(walls) - 1)))],
        "stdev_s": statistics.stdev(walls),
        "rss_max_kb": max(s[1] for s in samples),
        "cpu_median_s": statistics.median(s[2] for s in samples),
    }


def main():
    args = [a for a in sys.argv[1:] if a != "--warm"]
    roots = [a for a in args if Path(a, "OSM-GPX-Uploader.py").exists()]
    gpx_dir, *rest = args[len(roots):]
    runs = int(rest[0]) if rest else 15
    cpu = rest[1] if len(rest) > 1 else "12"

    envs = {root: None for root in roots}
    if "--warm" in sys.argv:
        workdirs = tempfile.TemporaryDirectory()
        for index, root in enumerate(roots):
            os.mkdir(Path(workdirs.name, str(index)))
            envs[root] = {**os.environ, "BENCH_WORKDIR": str(Path(workdirs.name, str(index)))}

    for root in roots:  # warmup: page cache, bytecode cache, script cache
        for _ in range(2):
            run_once(root, gpx_dir, cpu, envs[root])
    samples = {root: [] for root in roots}
    for _ in range(runs):
        for root in roots:
            samples[root].append(run_once(root, gpx_dir, cpu, envs[root]))

    results = {root: summarize(s) for root, s in samples.items()}
    print(json.dumps(results, indent=1))
    if len(roots) == 2:
        base, cand = (results[r] for r in roots)
        delta = cand["median_s"] / base["median_s"] - 1
        noise = max(base["stdev_s"] / base["median_s"], cand["stdev_s"] / cand["median_s"])
        rss = cand["rss_max_kb"] / base["rss_max_kb"] - 1
        # per-pair ratios: both runs of a pair share the same thermal state
        ratios = sorted(c[0] / b[0] for b, c in zip(*(samples[r] for r in roots)))
        q1, q3 = statistics.quantiles(ratios, n=4)[0], statistics.quantiles(ratios, n=4)[2]
        print(f"median {delta:+.1%} (noise {noise:.1%}), RSS {rss:+.1%}")
        print(f"paired ratio median {statistics.median(ratios) - 1:+.1%}, IQR [{q1 - 1:+.1%}, {q3 - 1:+.1%}]")


if __name__ == "__main__":
    main()
