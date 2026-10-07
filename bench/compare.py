#!/usr/bin/env python3
"""Interleave runs of two checkouts of the project and compare them.

Alternating A/B runs cancels most thermal and frequency drift, which
dominates noise on laptops where the governor cannot be pinned.

Usage: python bench/compare.py BASELINE_ROOT CANDIDATE_ROOT GPX_DIR [RUNS] [CPU]
A single root measures that checkout alone (writes nothing).
"""
import json
import statistics
import subprocess
import sys
from pathlib import Path


def run_once(root, gpx_dir, cpu):
    # time writes "<wall seconds> <max RSS KB> <user+sys seconds>" to stderr
    cmd = ["/usr/bin/time", "-f", "%e %M %U %S", "taskset", "-c", cpu,
           sys.executable, str(Path(root) / "bench" / "run_scan.py"), gpx_dir]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                          text=True, check=True)
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
    args = sys.argv[1:]
    roots = [a for a in args if Path(a, "OSM-GPX-Uploader.py").exists()]
    gpx_dir, *rest = args[len(roots):]
    runs = int(rest[0]) if rest else 15
    cpu = rest[1] if len(rest) > 1 else "12"

    for root in roots:  # warmup: page cache and bytecode cache
        for _ in range(2):
            run_once(root, gpx_dir, cpu)
    samples = {root: [] for root in roots}
    for _ in range(runs):
        for root in roots:
            samples[root].append(run_once(root, gpx_dir, cpu))

    results = {root: summarize(s) for root, s in samples.items()}
    print(json.dumps(results, indent=1))
    if len(roots) == 2:
        base, cand = (results[r] for r in roots)
        delta = cand["median_s"] / base["median_s"] - 1
        noise = max(base["stdev_s"] / base["median_s"], cand["stdev_s"] / cand["median_s"])
        rss = cand["rss_max_kb"] / base["rss_max_kb"] - 1
        print(f"median {delta:+.1%} (noise {noise:.1%}), RSS {rss:+.1%}")


if __name__ == "__main__":
    main()
