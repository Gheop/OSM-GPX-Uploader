#!/usr/bin/env python3
"""Check that every GPX file still maps to the same trace name.

Usage:
  python bench/check_names.py GPX_DIR --record   # write the golden file
  python bench/check_names.py GPX_DIR            # compare against it
"""
import importlib.util
import json
import sys
from contextlib import redirect_stdout
from datetime import datetime
from io import StringIO
from pathlib import Path

from run_scan import GOLDEN


ROOT = Path(__file__).resolve().parent.parent


def load_uploader():
    spec = importlib.util.spec_from_file_location(
        "uploader", ROOT / "OSM-GPX-Uploader.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def trace_names(gpx_dir):
    uploader = load_uploader()
    names = {}
    for gpx_file in sorted(gpx_dir.glob("*.gpx")) + sorted(gpx_dir.glob("*.GPX")):
        with redirect_stdout(StringIO()):
            timestamp = uploader.extract_gpx_timestamp(gpx_file)
        if timestamp is None:
            timestamp = datetime.fromtimestamp(gpx_file.stat().st_mtime)
        names[gpx_file.name] = uploader.format_trace_name(timestamp)
    return names


def main():
    gpx_dir = Path(sys.argv[1])
    names = trace_names(gpx_dir)
    if "--record" in sys.argv:
        GOLDEN.write_text(json.dumps(names, indent=1, sort_keys=True))
        print(f"recorded {len(names)} names in {GOLDEN}")
        return
    expected = json.loads(GOLDEN.read_text())
    diff = {
        k: (expected.get(k), names.get(k))
        for k in expected.keys() | names.keys()
        if expected.get(k) != names.get(k)
    }
    if diff:
        print(f"MISMATCH on {len(diff)} file(s): {dict(list(diff.items())[:5])}")
        sys.exit(1)
    print(f"OK: {len(names)} names identical")


if __name__ == "__main__":
    main()
