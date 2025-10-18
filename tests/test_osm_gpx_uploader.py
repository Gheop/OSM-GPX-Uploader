#!/usr/bin/env python3
"""Tests unitaires pour OSM-GPX-Uploader"""
import pytest
import json
import tempfile
import os
import importlib.util
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, mock_open, MagicMock

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
    """Tests pour la gestion de la configuration"""

    def test_default_config_values(self):
        """Test que la configuration par défaut contient les bonnes valeurs"""
        assert uploader.DEFAULT_CONFIG["visibility"] == "identifiable"
        assert uploader.DEFAULT_CONFIG["tags"] == "survey"
        assert (
            uploader.DEFAULT_CONFIG["description"] == "Automatically uploaded trace"
        )  # English version
        assert uploader.DEFAULT_CONFIG["client_id"] == ""
        assert uploader.DEFAULT_CONFIG["client_secret"] == ""

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data='{"client_id": "test_id", "client_secret": "test_secret", "visibility": "public", "tags": "test", "description": "Test"}',
    )
    @patch("pathlib.Path.exists", return_value=True)
    def test_load_existing_config(self, mock_exists, mock_file):
        """Test le chargement d'une configuration existante"""
        config = uploader.load_or_create_config()
        assert config["client_id"] == "test_id"
        assert config["client_secret"] == "test_secret"
        assert config["visibility"] == "public"

    @patch("builtins.input", side_effect=["new_id", "new_secret", "", "", ""])
    @patch("pathlib.Path.exists", return_value=False)
    @patch("builtins.open", new_callable=mock_open)
    def test_create_new_config(self, mock_file, mock_exists, mock_input):
        """Test la création d'une nouvelle configuration"""
        config = uploader.load_or_create_config()
        assert config["client_id"] == "new_id"
        assert config["client_secret"] == "new_secret"

    @patch("builtins.open", side_effect=Exception("Write error"))
    @patch("builtins.input", side_effect=["id", "secret", "", "", ""])
    @patch("pathlib.Path.exists", return_value=False)
    def test_config_save_error(self, mock_exists, mock_input, mock_file):
        """Test l'erreur lors de la sauvegarde de la config"""
        with pytest.raises(SystemExit):
            uploader.load_or_create_config()


class TestGPXParsing:
    """Tests pour l'extraction de données des fichiers GPX"""

    def test_extract_gpx_timestamp_from_trkpt(self):
        """Test l'extraction du timestamp depuis les track points"""
        gpx_content = """<?xml version="1.0"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
            <trk>
                <trkseg>
                    <trkpt lat="48.8566" lon="2.3522">
                        <time>2023-11-22T14:04:00Z</time>
                    </trkpt>
                </trkseg>
            </trk>
        </gpx>"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            f.flush()
            temp_path = f.name

        try:
            timestamp = uploader.extract_gpx_timestamp(Path(temp_path))
            assert timestamp is not None
            assert timestamp.year == 2023
            assert timestamp.month == 11
            assert timestamp.day == 22
        finally:
            os.unlink(temp_path)

    def test_extract_gpx_timestamp_from_waypoints(self):
        """Test l'extraction depuis les waypoints"""
        gpx_content = """<?xml version="1.0"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
            <wpt lat="48.8566" lon="2.3522">
                <time>2024-01-15T10:30:00Z</time>
            </wpt>
        </gpx>"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            f.flush()
            temp_path = f.name

        try:
            timestamp = uploader.extract_gpx_timestamp(Path(temp_path))
            assert timestamp is not None
            assert timestamp.year == 2024
        finally:
            os.unlink(temp_path)

    def test_extract_gpx_timestamp_no_time(self):
        """Test le comportement sans timestamp"""
        gpx_content = """<?xml version="1.0"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
            <trk><trkseg><trkpt lat="48.8566" lon="2.3522"/></trkseg></trk>
        </gpx>"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write(gpx_content)
            f.flush()
            temp_path = f.name

        try:
            timestamp = uploader.extract_gpx_timestamp(Path(temp_path))
            assert timestamp is None
        finally:
            os.unlink(temp_path)

    def test_extract_gpx_timestamp_invalid_file(self):
        """Test avec un fichier invalide"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".gpx", delete=False) as f:
            f.write("invalid xml content")
            f.flush()
            temp_path = f.name

        try:
            timestamp = uploader.extract_gpx_timestamp(Path(temp_path))
            assert timestamp is None
        finally:
            os.unlink(temp_path)

    def test_format_trace_name(self):
        """Test le formatage du nom de trace"""
        dt = datetime(2023, 11, 22, 14, 4, 30)
        assert uploader.format_trace_name(dt) == "20231122 - 14:04"

    def test_format_trace_name_midnight(self):
        """Test le formatage à minuit"""
        dt = datetime(2023, 1, 1, 0, 0, 0)
        assert uploader.format_trace_name(dt) == "20230101 - 00:00"

    def test_format_trace_name_end_of_day(self):
        """Test le formatage en fin de journée"""
        dt = datetime(2023, 12, 31, 23, 59, 0)
        assert uploader.format_trace_name(dt) == "20231231 - 23:59"


class TestOAuthFlow:
    """Tests pour le flux OAuth"""

    @patch("requests.get")
    @patch("builtins.open", new_callable=mock_open, read_data="valid_token")
    @patch("os.path.exists", return_value=True)
    def test_get_access_token_existing_valid(self, mock_exists, mock_file, mock_get):
        """Test avec un token valide existant"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        token = uploader.get_access_token("client_id", "client_secret")
        assert token == "valid_token"

    @patch("requests.get")
    @patch("builtins.open", new_callable=mock_open, read_data="invalid_token")
    @patch("os.path.exists", return_value=True)
    @patch.object(uploader, "get_authorization_code", return_value="new_code")
    @patch("requests.post")
    def test_get_access_token_existing_invalid(
        self, mock_post, mock_auth, mock_exists, mock_file, mock_get
    ):
        """Test avec un token invalide existant"""
        mock_get.return_value.status_code = 401
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"access_token": "new_token"}

        token = uploader.get_access_token("client_id", "client_secret")
        assert token == "new_token"

    @patch("requests.post")
    @patch("builtins.open", new_callable=mock_open)
    def test_get_access_token_exchange_code(self, mock_file, mock_post):
        """Test l'échange d'un code contre un token"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "new_token"}
        mock_post.return_value = mock_response

        token = uploader.get_access_token("client_id", "client_secret", "auth_code")
        assert token == "new_token"

    @patch("requests.post")
    def test_get_access_token_error(self, mock_post):
        """Test l'erreur lors de l'obtention du token"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        with pytest.raises(SystemExit):
            uploader.get_access_token("client_id", "client_secret", "bad_code")


class TestTraceManagement:
    """Tests pour la gestion des traces"""

    @patch("requests.get")
    def test_get_existing_traces_success(self, mock_get):
        """Test la récupération des traces existantes"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "traces": [
                {"id": 1, "description": "20231122 - 14:04 - Test"},
                {"id": 2, "description": "20240315 - 09:23 - Another"},
                {"id": 3, "description": "No timestamp"},
            ]
        }
        mock_get.return_value = mock_response

        traces = uploader.get_existing_traces("test_token")
        assert len(traces) == 2
        assert "20231122 - 14:04" in traces
        assert "20240315 - 09:23" in traces

    @patch("requests.get")
    def test_get_existing_traces_empty(self, mock_get):
        """Test sans traces existantes"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"traces": []}
        mock_get.return_value = mock_response

        traces = uploader.get_existing_traces("test_token")
        assert len(traces) == 0

    @patch("requests.get")
    def test_get_existing_traces_error(self, mock_get):
        """Test erreur API"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        traces = uploader.get_existing_traces("test_token")
        assert len(traces) == 0

    @patch("requests.get")
    def test_get_existing_traces_exception(self, mock_get):
        """Test exception lors de la récupération"""
        mock_get.side_effect = Exception("Network error")
        traces = uploader.get_existing_traces("test_token")
        assert len(traces) == 0

    @patch("requests.post")
    @patch("builtins.open", new_callable=mock_open, read_data=b"gpx content")
    def test_upload_gpx_success(self, mock_file, mock_post):
        """Test upload réussi"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "12091792"
        mock_post.return_value = mock_response

        config = {"description": "Test", "tags": "test", "visibility": "identifiable"}
        result = uploader.upload_gpx(
            "token", Path("test.gpx"), "20231122 - 14:04", config
        )
        assert result is True

    @patch("requests.post")
    @patch("builtins.open", new_callable=mock_open, read_data=b"gpx content")
    def test_upload_gpx_failure(self, mock_file, mock_post):
        """Test échec upload"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        config = {"description": "Test", "tags": "test", "visibility": "identifiable"}
        result = uploader.upload_gpx(
            "token", Path("test.gpx"), "20231122 - 14:04", config
        )
        assert result is False

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_upload_gpx_file_not_found(self, mock_file):
        """Test fichier non trouvé"""
        config = {"description": "Test", "tags": "test", "visibility": "identifiable"}
        result = uploader.upload_gpx(
            "token", Path("missing.gpx"), "20231122 - 14:04", config
        )
        assert result is False


class TestMainWorkflow:
    """Tests pour le workflow principal"""

    @patch.object(uploader, "upload_gpx", return_value=True)
    @patch.object(uploader, "get_existing_traces", return_value={"20231122 - 14:04"})
    @patch.object(uploader, "get_access_token", return_value="test_token")
    @patch.object(uploader, "load_or_create_config")
    @patch("pathlib.Path.glob")
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_dir", return_value=True)
    @patch("sys.argv", ["script.py", "test_dir"])
    def test_main_skip_duplicate(
        self,
        mock_is_dir,
        mock_exists,
        mock_glob,
        mock_config,
        mock_token,
        mock_traces,
        mock_upload,
    ):
        """Test que les doublons sont ignorés"""
        mock_config.return_value = {
            "client_id": "test",
            "client_secret": "test",
            "description": "Test",
            "tags": "test",
            "visibility": "identifiable",
        }

        # Create proper mock with comparison support using MagicMock
        mock_gpx = MagicMock(spec=Path)
        mock_gpx.name = "test.gpx"
        mock_stat = MagicMock()
        mock_stat.st_mtime = 1700000000.0
        mock_gpx.stat.return_value = mock_stat

        # Make it sortable by implementing comparison methods
        mock_gpx.__lt__ = MagicMock(return_value=False)
        mock_gpx.__gt__ = MagicMock(return_value=False)
        mock_gpx.__eq__ = MagicMock(return_value=True)
        mock_gpx.__le__ = MagicMock(return_value=True)
        mock_gpx.__ge__ = MagicMock(return_value=True)

        mock_glob.return_value = [mock_gpx]

        with patch.object(
            uploader,
            "extract_gpx_timestamp",
            return_value=datetime(2023, 11, 22, 14, 4),
        ):
            try:
                uploader.main()
            except SystemExit:
                pass

        mock_upload.assert_not_called()

    @patch.object(uploader, "load_or_create_config")
    @patch("pathlib.Path.exists", return_value=False)
    @patch("sys.argv", ["script.py", "invalid_dir"])
    def test_main_directory_not_found(self, mock_exists, mock_config):
        """Test répertoire non trouvé"""
        mock_config.return_value = {
            "client_id": "test",
            "client_secret": "test",
            "description": "Test",
            "tags": "test",
            "visibility": "identifiable",
        }
        with pytest.raises(SystemExit):
            uploader.main()

    @patch.object(uploader, "load_or_create_config")
    @patch("pathlib.Path.glob", return_value=[])
    @patch("pathlib.Path.exists", return_value=True)
    @patch("pathlib.Path.is_dir", return_value=True)
    @patch("sys.argv", ["script.py", "empty_dir"])
    def test_main_no_gpx_files(self, mock_is_dir, mock_exists, mock_glob, mock_config):
        """Test sans fichiers GPX"""
        mock_config.return_value = {
            "client_id": "test",
            "client_secret": "test",
            "description": "Test",
            "tags": "test",
            "visibility": "identifiable",
        }
        with pytest.raises(SystemExit):
            uploader.main()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
