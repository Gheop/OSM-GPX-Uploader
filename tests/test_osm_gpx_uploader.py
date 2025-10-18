#!/usr/bin/env python3
"""Tests unitaires pour OSM-GPX-Uploader"""
import pytest
import json
import tempfile
import os
import importlib.util
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, mock_open

# Importer le module avec des tirets dans le nom
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "uploader",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "OSM-GPX-Uploader.py",
    ),
)
uploader = importlib.util.module_from_spec(spec)
with patch("webbrowser.open"), patch("http.server.HTTPServer"):
    spec.loader.exec_module(uploader)


class TestConfiguration:
    def test_default_config_values(self):
        assert uploader.DEFAULT_CONFIG["visibility"] == "identifiable"
        assert uploader.DEFAULT_CONFIG["tags"] == "survey"


class TestGPXParsing:
    def test_format_trace_name(self):
        dt = datetime(2023, 11, 22, 14, 4, 30)
        trace_name = uploader.format_trace_name(dt)
        assert trace_name == "20231122 - 14:04"


class TestTraceManagement:
    @patch("requests.get")
    def test_get_existing_traces(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "traces": [
                {"id": 1, "description": "20231122 - 14:04 - Test"},
            ]
        }
        mock_get.return_value = mock_response
        traces = uploader.get_existing_traces("test_token")
        assert len(traces) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
