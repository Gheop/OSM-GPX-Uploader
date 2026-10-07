#!/usr/bin/env python3
"""Tests unitaires pour OSM-GPX-Uploader"""
import pytest
import json
import re
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
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "OSM-GPX-Uploader.py")
)
uploader = importlib.util.module_from_spec(spec)
with patch('webbrowser.open'), patch('http.server.HTTPServer'):
    spec.loader.exec_module(uploader)


class TestConfiguration:
    """Tests pour la gestion de la configuration"""
    
    def test_default_config_values(self):
        """Test que la configuration par défaut contient les bonnes valeurs"""
        assert uploader.DEFAULT_CONFIG['visibility'] == 'identifiable'
        assert uploader.DEFAULT_CONFIG['tags'] == 'survey'
        assert uploader.DEFAULT_CONFIG['description'] == 'Automatically uploaded trace'
        assert uploader.DEFAULT_CONFIG['client_id'] == ''
        assert uploader.DEFAULT_CONFIG['client_secret'] == ''
    
    @patch('builtins.open', new_callable=mock_open, read_data='{"client_id": "test_id", "client_secret": "test_secret", "visibility": "public", "tags": "test", "description": "Test"}')
    @patch('pathlib.Path.exists', return_value=True)
    def test_load_existing_config(self, mock_exists, mock_file):
        """Test le chargement d'une configuration existante"""
        config = uploader.load_or_create_config()
        assert config['client_id'] == 'test_id'
        assert config['client_secret'] == 'test_secret'
        assert config['visibility'] == 'public'
    
    @patch('builtins.input', side_effect=['new_id', 'new_secret', '', '', ''])
    @patch('pathlib.Path.exists', return_value=False)
    @patch('builtins.open', new_callable=mock_open)
    def test_create_new_config(self, mock_file, mock_exists, mock_input):
        """Test la création d'une nouvelle configuration"""
        config = uploader.load_or_create_config()
        assert config['client_id'] == 'new_id'
        assert config['client_secret'] == 'new_secret'
    
    @patch('builtins.open', side_effect=Exception("Write error"))
    @patch('builtins.input', side_effect=['id', 'secret', '', '', ''])
    @patch('pathlib.Path.exists', return_value=False)
    def test_config_save_error(self, mock_exists, mock_input, mock_file):
        """Test l'erreur lors de la sauvegarde de la config"""
        with pytest.raises(SystemExit):
            uploader.load_or_create_config()


class TestGPXParsing:
    """Tests pour l'extraction de données des fichiers GPX"""
    
    def test_extract_gpx_timestamp_from_trkpt(self):
        """Test l'extraction du timestamp depuis les track points"""
        gpx_content = '''<?xml version="1.0"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
            <trk>
                <trkseg>
                    <trkpt lat="48.8566" lon="2.3522">
                        <time>2023-11-22T14:04:00Z</time>
                    </trkpt>
                </trkseg>
            </trk>
        </gpx>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gpx', delete=False) as f:
            f.write(gpx_content)
            temp_path = f.name
        
        try:
            timestamp = uploader.extract_gpx_timestamp(Path(temp_path))
            assert timestamp is not None
            assert timestamp.year == 2023
            assert timestamp.month == 11
            assert timestamp.day == 22
        finally:
            try:
                os.unlink(temp_path)
            except (PermissionError, OSError):
                pass
    
    def test_extract_gpx_timestamp_from_metadata(self):
        """Test l'extraction du timestamp depuis les métadonnées"""
        gpx_content = '''<?xml version="1.0"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
            <metadata>
                <time>2024-03-15T09:23:00Z</time>
            </metadata>
        </gpx>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gpx', delete=False) as f:
            f.write(gpx_content)
            temp_path = f.name
        
        try:
            timestamp = uploader.extract_gpx_timestamp(Path(temp_path))
            assert timestamp is not None
            assert timestamp.year == 2024
            assert timestamp.month == 3
            assert timestamp.day == 15
        finally:
            try:
                os.unlink(temp_path)
            except (PermissionError, OSError):
                pass
    
    def test_extract_gpx_timestamp_from_waypoints(self):
        """Test l'extraction depuis les waypoints"""
        gpx_content = '''<?xml version="1.0"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
            <wpt lat="48.8566" lon="2.3522">
                <time>2024-01-15T10:30:00Z</time>
            </wpt>
        </gpx>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gpx', delete=False) as f:
            f.write(gpx_content)
            temp_path = f.name
        
        try:
            timestamp = uploader.extract_gpx_timestamp(Path(temp_path))
            assert timestamp is not None
            assert timestamp.year == 2024
        finally:
            try:
                os.unlink(temp_path)
            except (PermissionError, OSError):
                pass
    
    def test_extract_gpx_timestamp_no_time(self):
        """Test le comportement sans timestamp"""
        gpx_content = '''<?xml version="1.0"?>
        <gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
            <trk><trkseg><trkpt lat="48.8566" lon="2.3522"/></trkseg></trk>
        </gpx>'''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gpx', delete=False) as f:
            f.write(gpx_content)
            temp_path = f.name
        
        try:
            timestamp = uploader.extract_gpx_timestamp(Path(temp_path))
            assert timestamp is None
        finally:
            try:
                os.unlink(temp_path)
            except (PermissionError, OSError):
                pass
    
    def test_extract_gpx_timestamp_invalid_file(self):
        """Test avec un fichier invalide"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.gpx', delete=False) as f:
            f.write("invalid xml content")
            temp_path = f.name
        
        try:
            timestamp = uploader.extract_gpx_timestamp(Path(temp_path))
            assert timestamp is None
        finally:
            try:
                os.unlink(temp_path)
            except (PermissionError, OSError):
                pass
    
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
    
    @patch('requests.get')
    @patch('builtins.open', new_callable=mock_open, read_data='valid_token')
    @patch('os.path.exists', return_value=True)
    def test_get_access_token_existing_valid(self, mock_exists, mock_file, mock_get):
        """Test avec un token valide existant"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        token = uploader.get_access_token('client_id', 'client_secret')
        assert token == 'valid_token'
    
    @patch('requests.get')
    @patch('builtins.open', new_callable=mock_open, read_data='invalid_token')
    @patch('os.path.exists', return_value=True)
    @patch.object(uploader, 'get_authorization_code', return_value='new_code')
    @patch('requests.post')
    def test_get_access_token_existing_invalid(self, mock_post, mock_auth, mock_exists, mock_file, mock_get):
        """Test avec un token invalide existant"""
        mock_get.return_value.status_code = 401
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {'access_token': 'new_token'}
        
        token = uploader.get_access_token('client_id', 'client_secret')
        assert token == 'new_token'
    
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open)
    def test_get_access_token_exchange_code(self, mock_file, mock_post):
        """Test l'échange d'un code contre un token"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'access_token': 'new_token'}
        mock_post.return_value = mock_response
        
        token = uploader.get_access_token('client_id', 'client_secret', 'auth_code')
        assert token == 'new_token'
    
    @patch('requests.post')
    def test_get_access_token_error(self, mock_post):
        """Test l'erreur lors de l'obtention du token"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Bad request'
        mock_post.return_value = mock_response
        
        with pytest.raises(SystemExit):
            uploader.get_access_token('client_id', 'client_secret', 'bad_code')


class TestTraceManagement:
    """Tests pour la gestion des traces"""
    
    @patch('requests.get')
    def test_get_existing_traces_success(self, mock_get):
        """Test la récupération des traces existantes"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'traces': [
                {'id': 1, 'description': '20231122 - 14:04 - Test'},
                {'id': 2, 'description': '20240315 - 09:23 - Another'},
                {'id': 3, 'description': 'No timestamp'},
            ]
        }
        mock_get.return_value = mock_response
        
        traces = uploader.get_existing_traces('test_token')
        assert len(traces) == 2
        assert '20231122 - 14:04' in traces
        assert '20240315 - 09:23' in traces
    
    @patch('requests.get')
    def test_get_existing_traces_empty(self, mock_get):
        """Test sans traces existantes"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'traces': []}
        mock_get.return_value = mock_response
        
        traces = uploader.get_existing_traces('test_token')
        assert len(traces) == 0
    
    @patch('requests.get')
    def test_get_existing_traces_error(self, mock_get):
        """Test erreur API"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        traces = uploader.get_existing_traces('test_token')
        assert len(traces) == 0
    
    @patch('requests.get')
    def test_get_existing_traces_exception(self, mock_get):
        """Test exception lors de la récupération"""
        mock_get.side_effect = Exception("Network error")
        traces = uploader.get_existing_traces('test_token')
        assert len(traces) == 0
    
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open, read_data=b'gpx content')
    def test_upload_gpx_success(self, mock_file, mock_post):
        """Test upload réussi"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '12091792'
        mock_post.return_value = mock_response
        
        config = {'description': 'Test', 'tags': 'test', 'visibility': 'identifiable'}
        result = uploader.upload_gpx('token', Path('test.gpx'), '20231122 - 14:04', config)
        assert result is True
    
    @patch('requests.post')
    @patch('builtins.open', new_callable=mock_open, read_data=b'gpx content')
    def test_upload_gpx_failure(self, mock_file, mock_post):
        """Test échec upload"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Bad request'
        mock_post.return_value = mock_response
        
        config = {'description': 'Test', 'tags': 'test', 'visibility': 'identifiable'}
        result = uploader.upload_gpx('token', Path('test.gpx'), '20231122 - 14:04', config)
        assert result is False
    
    @patch('builtins.open', side_effect=FileNotFoundError())
    def test_upload_gpx_file_not_found(self, mock_file):
        """Test fichier non trouvé"""
        config = {'description': 'Test', 'tags': 'test', 'visibility': 'identifiable'}
        result = uploader.upload_gpx('token', Path('missing.gpx'), '20231122 - 14:04', config)
        assert result is False


class TestMainWorkflow:
    """Tests pour le workflow principal"""
    
    @pytest.mark.skip(reason="Mock sorting issue - needs refactoring")
    @patch.object(uploader, 'upload_gpx', return_value=True)
    @patch.object(uploader, 'get_existing_traces', return_value={'20231122 - 14:04'})
    @patch.object(uploader, 'get_access_token', return_value='test_token')
    @patch.object(uploader, 'load_or_create_config')
    @patch('pathlib.Path.glob')
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_dir', return_value=True)
    @patch('sys.argv', ['script.py', 'test_dir'])
    def test_main_skip_duplicate(self, mock_is_dir, mock_exists, mock_glob, mock_config, mock_token, mock_traces, mock_upload):
        """Test que les doublons sont ignorés"""
        mock_config.return_value = {
            'client_id': 'test', 'client_secret': 'test',
            'description': 'Test', 'tags': 'test', 'visibility': 'identifiable'
        }
        
        mock_gpx = Mock(spec=Path)
        mock_gpx.name = 'test.gpx'
        mock_gpx.stat.return_value.st_mtime = 1700000000
        mock_gpx.__lt__ = Mock(return_value=False)
        mock_gpx.__gt__ = Mock(return_value=False)
        mock_gpx.__eq__ = Mock(return_value=True)
        mock_glob.return_value = [mock_gpx]
        
        with patch.object(uploader, 'extract_gpx_timestamp', return_value=datetime(2023, 11, 22, 14, 4)):
            try:
                uploader.main()
            except SystemExit:
                pass
        
        mock_upload.assert_not_called()
    
    @patch.object(uploader, 'load_or_create_config', return_value={'client_id': 'id', 'client_secret': 'secret'})
    @patch('pathlib.Path.exists', return_value=False)
    @patch('sys.argv', ['script.py', 'invalid_dir'])
    def test_main_directory_not_found(self, mock_exists, mock_config):
        """Test répertoire non trouvé"""
        with pytest.raises(SystemExit):
            uploader.main()
    
    @patch('pathlib.Path.glob', return_value=[])
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.is_dir', return_value=True)
    @patch('sys.argv', ['script.py', 'empty_dir'])
    def test_main_no_gpx_files(self, mock_is_dir, mock_exists, mock_glob):
        """Test sans fichiers GPX"""
        with pytest.raises(SystemExit):
            uploader.main()


class TestEdgeCases:
    """Tests pour les cas limites"""
    
    def test_format_trace_name_midnight(self):
        """Test le formatage à minuit"""
        dt = datetime(2023, 1, 1, 0, 0, 0)
        trace_name = uploader.format_trace_name(dt)
        assert trace_name == "20230101 - 00:00"
    
    def test_format_trace_name_end_of_day(self):
        """Test le formatage en fin de journée"""
        dt = datetime(2023, 12, 31, 23, 59, 59)
        trace_name = uploader.format_trace_name(dt)
        assert trace_name == "20231231 - 23:59"
    
    @patch('requests.get')
    def test_get_existing_traces_empty(self, mock_get):
        """Test la récupération quand il n'y a aucune trace"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'traces': []}
        mock_get.return_value = mock_response
        
        traces = uploader.get_existing_traces('test_token')
        assert len(traces) == 0
    
    @patch('requests.get')
    def test_get_existing_traces_api_error(self, mock_get):
        """Test le comportement en cas d'erreur API"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        traces = uploader.get_existing_traces('test_token')
        assert len(traces) == 0



def write_gpx_files(directory, count):
    """Écrit count fichiers GPX minimaux, un par minute à partir de 14:00"""
    for minute in range(count):
        (directory / f"trace_{minute:02d}.gpx").write_text(
            '<?xml version="1.0"?>'
            '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">'
            f'<trk><trkseg><trkpt lat="0" lon="0"><time>2023-11-22T14:{minute:02d}:00Z</time>'
            '</trkpt></trkseg></trk></gpx>'
        )
    return sorted(directory.glob("*.gpx"))



def extract_from(tmp_path, gpx_content):
    """Écrit gpx_content dans un fichier et en extrait le timestamp"""
    gpx_file = tmp_path / "trace.gpx"
    gpx_file.write_text(gpx_content)
    return uploader.extract_gpx_timestamp(gpx_file)


class TestTimestampSelection:
    """Tests pour l'espace de noms GPX et le choix de l'heure la plus ancienne"""

    def test_gpx_1_0_track_points(self, tmp_path):
        """Test qu'un GPX 1.0 est lu au lieu de retomber sur la date du fichier"""
        timestamp = extract_from(tmp_path, (
            '<gpx xmlns="http://www.topografix.com/GPX/1/0" version="1.0">'
            '<trk><trkseg><trkpt lat="0" lon="0"><time>2023-11-22T14:04:00Z</time></trkpt>'
            '</trkseg></trk></gpx>'
        ))
        assert uploader.format_trace_name(timestamp) == "20231122 - 14:04"

    def test_gpx_1_0_document_time(self, tmp_path):
        """Test que le <time> direct sous <gpx> (GPX 1.0) compte"""
        timestamp = extract_from(tmp_path, (
            '<gpx xmlns="http://www.topografix.com/GPX/1/0" version="1.0">'
            '<time>2023-11-22T13:00:00Z</time>'
            '<trk><trkseg><trkpt lat="0" lon="0"><time>2023-11-22T14:04:00Z</time></trkpt>'
            '</trkseg></trk></gpx>'
        ))
        assert uploader.format_trace_name(timestamp) == "20231122 - 13:00"

    def test_gpx_without_namespace(self, tmp_path):
        """Test un GPX sans espace de noms"""
        timestamp = extract_from(tmp_path, (
            '<gpx version="1.1"><wpt lat="0" lon="0"><time>2023-11-22T14:04:00Z</time></wpt></gpx>'
        ))
        assert uploader.format_trace_name(timestamp) == "20231122 - 14:04"

    def test_oldest_is_chronological_across_offsets(self, tmp_path):
        """Test que 15:30+02:00 (13:30 UTC) est plus ancien que 14:00Z"""
        timestamp = extract_from(tmp_path, (
            '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1"><trk><trkseg>'
            '<trkpt lat="0" lon="0"><time>2023-11-22T14:00:00Z</time></trkpt>'
            '<trkpt lat="0" lon="0"><time>2023-11-22T15:30:00+02:00</time></trkpt>'
            '</trkseg></trk></gpx>'
        ))
        # Le nom garde l'heure telle qu'écrite dans le fichier
        assert uploader.format_trace_name(timestamp) == "20231122 - 15:30"

    def test_oldest_with_mixed_precision(self, tmp_path):
        """Test que 14:00:00.500Z est plus récent que 14:00:00Z"""
        timestamp = extract_from(tmp_path, (
            '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">'
            '<metadata><time>2023-11-22T14:00:00.500Z</time></metadata><trk><trkseg>'
            '<trkpt lat="0" lon="0"><time>2023-11-22T14:00:00Z</time></trkpt>'
            '</trkseg></trk></gpx>'
        ))
        assert timestamp.microsecond == 0

    def test_time_without_offset_is_utc(self, tmp_path):
        """Test qu'une heure sans fuseau se compare comme de l'UTC"""
        timestamp = extract_from(tmp_path, (
            '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1"><trk><trkseg>'
            '<trkpt lat="0" lon="0"><time>2023-11-22T14:00:00</time></trkpt>'
            '<trkpt lat="0" lon="0"><time>2023-11-22T14:30:00+01:00</time></trkpt>'
            '</trkseg></trk></gpx>'
        ))
        assert uploader.format_trace_name(timestamp) == "20231122 - 14:30"

    def test_invalid_time_is_ignored(self, tmp_path):
        """Test qu'une heure illisible n'empêche pas de lire les autres"""
        timestamp = extract_from(tmp_path, (
            '<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1"><trk><trkseg>'
            '<trkpt lat="0" lon="0"><time>0000-garbage</time></trkpt>'
            '<trkpt lat="0" lon="0"><time>2023-11-22T14:04:00Z</time></trkpt>'
            '</trkseg></trk></gpx>'
        ))
        assert uploader.format_trace_name(timestamp) == "20231122 - 14:04"

class TestParallelExtraction:
    """Tests pour l'extraction des timestamps en processus séparés"""

    def test_extract_with_messages_captures_warning(self, tmp_path):
        """Test que le message d'erreur est renvoyé au lieu d'être affiché"""
        broken = tmp_path / "broken.gpx"
        broken.write_text("not xml")
        timestamp, messages = uploader.extract_with_messages(broken)
        assert timestamp is None
        assert "Error extracting timestamp" in messages

    def test_extract_all_timestamps_sequential_below_threshold(self, tmp_path):
        """Test qu'aucun processus n'est lancé pour peu de fichiers"""
        files = write_gpx_files(tmp_path, 3)
        with patch.object(uploader, 'ProcessPoolExecutor', side_effect=AssertionError):
            results = uploader.extract_all_timestamps(files)
        assert [ts.minute for ts, _ in results] == [0, 1, 2]

    def test_extract_all_timestamps_falls_back_without_multiprocessing(self, tmp_path):
        """Test le repli séquentiel quand les processus sont indisponibles"""
        files = write_gpx_files(tmp_path, uploader.PARALLEL_MIN_FILES)
        with patch.object(uploader, 'ProcessPoolExecutor', side_effect=OSError):
            results = uploader.extract_all_timestamps(files)
        assert [ts.minute for ts, _ in results] == list(range(uploader.PARALLEL_MIN_FILES))

    def test_main_parallel_keeps_order_and_messages(self, tmp_path, monkeypatch, capsys):
        """Test de bout en bout : workers réels, sortie dans l'ordre des fichiers"""
        gpx_dir = tmp_path / "gpx"
        gpx_dir.mkdir()
        write_gpx_files(gpx_dir, 20)
        (gpx_dir / "trace_99_broken.gpx").write_text("not xml")
        monkeypatch.chdir(tmp_path)
        (tmp_path / "osm_config.json").write_text(json.dumps({
            'client_id': 'id', 'client_secret': 'secret',
            'description': 'Test', 'tags': 'test', 'visibility': 'private',
        }))
        (tmp_path / "osm_token.txt").write_text("token")
        response = Mock(status_code=200)
        response.json.return_value = {'traces': [
            {'description': f'20231122 - 14:{minute:02d} - Test'} for minute in range(20)
        ]}
        script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "OSM-GPX-Uploader.py")

        from concurrent.futures import ProcessPoolExecutor

        class RecordingPool(ProcessPoolExecutor):
            """Retient que les workers ont réellement produit les résultats"""
            completed = False

            def map(self, *args, **kwargs):
                results = list(super().map(*args, **kwargs))
                RecordingPool.completed = True
                return iter(results)

        # Run as __main__ so that worker processes can re-import the script
        import runpy
        import requests
        with patch('concurrent.futures.ProcessPoolExecutor', RecordingPool), \
                patch.object(requests, 'get', return_value=response), \
                patch.object(requests, 'post', side_effect=AssertionError("unexpected upload")), \
                patch('sys.argv', [script, str(gpx_dir)]):
            runpy.run_path(script, run_name='__main__')

        assert RecordingPool.completed
        output = capsys.readouterr().out
        names = re.findall(r"📅 Date/time: (.+)", output)
        assert names[:20] == [f"20231122 - 14:{minute:02d}" for minute in range(20)]
        broken_block = output.split("📄 trace_99_broken.gpx\n")[1]
        assert broken_block.startswith("  ⚠️  Error extracting timestamp")
        assert "Skipped (already present): 20" in output


class TestTimestampCache:
    """Tests pour le cache des timestamps entre deux exécutions"""

    def test_second_run_reuses_cache(self, tmp_path, monkeypatch):
        """Test qu'un fichier inchangé n'est pas reparsé"""
        monkeypatch.chdir(tmp_path)
        files = write_gpx_files(tmp_path, 2)
        first = uploader.extract_timestamps_cached(files)
        with patch.object(uploader, 'extract_gpx_timestamp', side_effect=AssertionError):
            second = uploader.extract_timestamps_cached(files)
        assert second == first
        assert [ts.minute for ts, _ in second] == [0, 1]

    def test_modified_file_is_extracted_again(self, tmp_path, monkeypatch):
        """Test qu'un fichier modifié invalide son entrée"""
        monkeypatch.chdir(tmp_path)
        files = write_gpx_files(tmp_path, 1)
        uploader.extract_timestamps_cached(files)
        files[0].write_text(files[0].read_text().replace("14:00:00", "15:30:00"))
        os.utime(files[0], ns=(0, files[0].stat().st_mtime_ns + 1))
        [(timestamp, _)] = uploader.extract_timestamps_cached(files)
        assert (timestamp.hour, timestamp.minute) == (15, 30)

    def test_failed_extraction_keeps_its_message(self, tmp_path, monkeypatch):
        """Test qu'un échec en cache réaffiche le même avertissement"""
        monkeypatch.chdir(tmp_path)
        broken = tmp_path / "broken.gpx"
        broken.write_text("not xml")
        first = uploader.extract_timestamps_cached([broken])
        second = uploader.extract_timestamps_cached([broken])
        assert second == first
        assert second[0][0] is None
        assert "Error extracting timestamp" in second[0][1]

    @pytest.mark.parametrize("content", [
        "not json",
        '["a list"]',
        '{"version": 0, "files": {}}',
        '{"version": CURRENT, "files": {"FILE": "not a dict"}}',
    ])
    def test_unusable_cache_is_rebuilt(self, tmp_path, monkeypatch, content):
        """Test qu'un cache corrompu ou d'une autre version est ignoré"""
        monkeypatch.chdir(tmp_path)
        files = write_gpx_files(tmp_path, 1)
        (tmp_path / uploader.CACHE_FILE).write_text(
            content.replace("CURRENT", str(uploader.CACHE_VERSION))
            .replace("FILE", str(files[0].resolve()))
        )
        [(timestamp, _)] = uploader.extract_timestamps_cached(files)
        assert timestamp.minute == 0
        cache = json.loads((tmp_path / uploader.CACHE_FILE).read_text())
        assert cache["version"] == uploader.CACHE_VERSION

    def test_deleted_files_are_pruned(self, tmp_path, monkeypatch):
        """Test que les fichiers disparus sortent du cache"""
        monkeypatch.chdir(tmp_path)
        files = write_gpx_files(tmp_path, 2)
        uploader.extract_timestamps_cached(files)
        files[0].unlink()
        new_file = tmp_path / "new.gpx"
        new_file.write_text(files[1].read_text())
        uploader.extract_timestamps_cached([files[1], new_file])
        cached = json.loads((tmp_path / uploader.CACHE_FILE).read_text())["files"]
        assert str(files[0].resolve()) not in cached
        assert len(cached) == 2

    def test_unwritable_cache_does_not_stop_the_run(self, tmp_path, monkeypatch, capsys):
        """Test qu'une erreur d'écriture du cache est signalée sans arrêter"""
        monkeypatch.chdir(tmp_path)
        files = write_gpx_files(tmp_path, 1)
        with patch.object(uploader.os, 'replace', side_effect=OSError("read-only")):
            [(timestamp, _)] = uploader.extract_timestamps_cached(files)
        assert timestamp.minute == 0
        assert "Unable to save cache" in capsys.readouterr().out

if __name__ == '__main__':
    pytest.main([__file__, '-v'])