#!/usr/bin/env python3
"""Run main() on a real GPX directory with the OSM API mocked.

Every trace is reported as already uploaded, so the run measures the local
work only: directory scan, timestamp extraction and duplicate detection.

Usage: python bench/run_scan.py GPX_DIR
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
GOLDEN = Path(__file__).resolve().parent / "golden.local.json"


def load_uploader():
    spec = importlib.util.spec_from_file_location("uploader", ROOT / "OSM-GPX-Uploader.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_get(trace_names):
    traces = [{"description": f"{name} - bench"} for name in sorted(trace_names)]

    def get(url, **kwargs):
        response = Mock(status_code=200)
        response.json.return_value = {"traces": traces}
        return response

    return get


def main():
    gpx_dir = Path(sys.argv[1]).resolve()
    uploader = load_uploader()
    expected = json.loads(GOLDEN.read_text())
    config = {"client_id": "id", "client_secret": "secret", "visibility": "private",
              "description": "bench", "tags": "bench"}

    # get_access_token reads the token from the working directory
    with tempfile.TemporaryDirectory() as workdir:
        os.chdir(workdir)
        Path(uploader.TOKEN_FILE).write_text("token")
        with patch.object(uploader, "load_or_create_config", return_value=config), \
                patch.object(uploader.requests, "get", side_effect=fake_get(expected.values())), \
                patch.object(uploader, "upload_gpx", side_effect=AssertionError("unexpected upload")), \
                patch.object(sys, "argv", ["bench", str(gpx_dir)]):
            uploader.main()

if __name__ == "__main__":
    main()
