#!/usr/bin/env python3
"""Run the uploader on a real GPX directory with the OSM API mocked.

Every trace is reported as already uploaded, so the run measures the local
work only: directory scan, timestamp extraction and duplicate detection.
The script runs as __main__, as it does for users, so that worker processes
can re-import it.

Usage: python bench/run_scan.py SCRIPT GPX_DIR [--verify]
  --verify  check that each file maps to the name in golden.local.json

BENCH_WORKDIR=DIR keeps the working directory (config, token and any cache
the script writes) across runs instead of starting from an empty one.
"""
import io
import json
import os
import re
import runpy
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import requests

GOLDEN = Path(__file__).resolve().parent / "golden.local.json"


def fake_get(trace_names):
    traces = [{"description": f"{name} - bench"} for name in sorted(trace_names)]

    def get(url, **kwargs):
        response = Mock(status_code=200)
        response.json.return_value = {"traces": traces}
        return response

    return get


def check_output(output, expected):
    names = dict(re.findall(r"📄 (.+)\n(?:.*\n)*?  📅 Date/time: (.+)", output))
    if names != expected:
        wrong = {
            k for k in expected.keys() | names.keys() if names.get(k) != expected.get(k)
        }
        sys.exit(f"MISMATCH on {len(wrong)} file(s): {sorted(wrong)[:5]}")
    print(f"OK: {len(names)} names identical", file=sys.stderr)


def main():
    script = Path(sys.argv[1]).resolve()
    gpx_dir = Path(sys.argv[2]).resolve()
    expected = json.loads(GOLDEN.read_text())
    config = {
        "client_id": "id",
        "client_secret": "secret",
        "visibility": "private",
        "description": "bench",
        "tags": "bench",
    }
    output = io.StringIO() if "--verify" in sys.argv else sys.stdout

    # config and token are read from the working directory
    with tempfile.TemporaryDirectory() as tmp:
        workdir = os.environ.get("BENCH_WORKDIR") or tmp
        os.chdir(workdir)
        # The script keeps config, token and cache there too, not in ~/.config
        os.environ["OSM_GPX_UPLOADER_DIR"] = workdir
        Path("osm_config.json").write_text(json.dumps(config))
        Path("osm_token.txt").write_text("token")
        with patch.object(
            requests, "get", side_effect=fake_get(expected.values())
        ), patch.object(
            requests, "post", side_effect=AssertionError("unexpected upload")
        ), patch.object(
            sys, "argv", [str(script), str(gpx_dir)]
        ), redirect_stdout(
            output
        ):
            runpy.run_path(str(script), run_name="__main__")

    if output is not sys.stdout:
        check_output(output.getvalue(), expected)


if __name__ == "__main__":
    main()
