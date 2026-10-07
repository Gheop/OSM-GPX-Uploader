#!/usr/bin/env python3
"""
Script to upload GPX traces to OpenStreetMap with duplicate detection
Uses OAuth 2.0 authentication
"""

import os
import sys
import io
import base64
import hashlib
import secrets
import time
import json
import re
from contextlib import redirect_stdout
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import requests
import webbrowser
from urllib.parse import urlencode, parse_qs, urlparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ============================================================================
# CONFIGURATION
# ============================================================================
# Custom User-Agent to avoid being blocked by OSM's CDN (Varnish)
USER_AGENT = "OSM-GPX-Uploader/1.0 (https://github.com/Gheop/OSM-GPX-Uploader)"
OSM_WEB_URL = "https://www.openstreetmap.org"  # For OAuth
OSM_API_URL = "https://api.openstreetmap.org"  # For GPX API
REDIRECT_URI = "http://127.0.0.1:8000/callback"  # Do not modify
# Seconds; requests waits forever by default
API_TIMEOUT = 30
# (connect, read): OSM processes the whole GPX file before answering
UPLOAD_TIMEOUT = (30, 300)

# Below this many files, starting worker processes costs more than it saves
PARALLEL_MIN_FILES = 16
# Each worker holds a full GPX tree in memory: cap the total footprint
MAX_WORKERS = 8

# Configuration files
CONFIG_FILE = "osm_config.json"
TOKEN_FILE = "osm_token.txt"
CACHE_FILE = "osm_gpx_cache.json"
# Bump when extract_gpx_timestamp changes: older cached results are dropped
CACHE_VERSION = 2

# Default configuration
DEFAULT_CONFIG = {
    "client_id": "",
    "client_secret": "",
    "visibility": "identifiable",  # public, identifiable, trackable, private
    "description": "Automatically uploaded trace",
    "tags": "survey",
}


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================


def private_opener(path, flags):
    """Opener for files holding a secret: readable by their owner only"""
    fd = os.open(path, flags, 0o600)
    if hasattr(os, "fchmod"):
        # The mode above only applies to new files: tighten existing ones too
        os.fchmod(fd, 0o600)
    return fd


def restrict_to_owner(path):
    """Make a secret file written by an older version readable by its owner only"""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Not ours to change, or no such permission model: keep going


def load_or_create_config():
    """Load or create the configuration file"""
    config_path = Path(CONFIG_FILE)

    # If file exists, load it
    if config_path.exists():
        try:
            restrict_to_owner(config_path)
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Check that credentials are present
            if config.get("client_id") and config.get("client_secret"):
                return config
            else:
                print("⚠️  Incomplete configuration detected\n")
        except Exception as e:
            print(f"⚠️  Error reading config: {e}\n")

    # Create a new configuration
    print("=" * 70)
    print("🔧 INITIAL CONFIGURATION")
    print("=" * 70)
    print("\nTo use this script, you need to create an OAuth2 application on OSM:")
    print("1. Go to: https://www.openstreetmap.org/oauth2/applications")
    print("2. Click 'Register new application'")
    print("3. Fill in:")
    print("   - Name: GPX Uploader (or other)")
    print("   - Redirect URI: http://127.0.0.1:8000/callback")
    print("   - Permissions: Check 'Read user GPS traces' AND 'Upload GPS traces'")
    print("4. Validate and copy your credentials\n")

    config = DEFAULT_CONFIG.copy()

    config["client_id"] = input("Client ID: ").strip()
    config["client_secret"] = input("Client Secret: ").strip()

    print("\n📝 Trace parameters (press Enter to keep default values)")

    visibility = input(f"Visibility [{config['visibility']}]: ").strip()
    if visibility:
        config["visibility"] = visibility

    description = input(f"Description [{config['description']}]: ").strip()
    if description:
        config["description"] = description

    tags = input(f"Tags [{config['tags']}]: ").strip()
    if tags:
        config["tags"] = tags

    # Save configuration
    try:
        with open(config_path, "w", encoding="utf-8", opener=private_opener) as f:
            json.dump(config, indent=2, fp=f)
        print(f"\n✅ Configuration saved in {CONFIG_FILE}")
        print("   You can edit this file directly if needed.\n")
    except Exception as e:
        print(f"\n❌ Unable to save config: {e}")
        sys.exit(1)

    return config


# ============================================================================
# OAUTH 2.0 MANAGEMENT
# ============================================================================

# Seconds the user has to authorize the application in the browser
CALLBACK_TIMEOUT = 120


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback

    The server carries expected_state, and receives auth_code (or
    auth_error) and callback_done once the callback for this authorization
    arrives.
    """

    # Seconds before dropping a client that connects but sends nothing
    timeout = 5

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)

        # Requests without our state (another page, a port scan, a forged
        # redirect) are answered and ignored: keep waiting for the real one
        if url.path != urlparse(REDIRECT_URI).path or query.get("state") != [
            self.server.expected_state
        ]:
            self.respond(400, b"<h1>Error</h1><p>Unexpected request.</p>")
            return

        self.server.callback_done = True
        if "code" in query:
            self.server.auth_code = query["code"][0]
            self.respond(
                200,
                b"<h1>Authorization successful!</h1>"
                b"<p>You can close this window.</p>",
            )
        else:
            # OSM sends error=access_denied when the user refuses
            self.server.auth_error = query.get("error", ["no code received"])[0]
            self.respond(400, b"<h1>Error</h1><p>Authorization not granted.</p>")

    def respond(self, status, body):
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>" + body + b"</body></html>")

    def log_message(self, format, *args):
        pass  # Suppress server logs


def pkce_pair():
    """PKCE code verifier and its S256 challenge (RFC 7636)"""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def get_authorization_code(client_id):
    """Launch OAuth 2.0 flow to obtain an authorization code

    Returns (code, code_verifier): the verifier goes with the code when it is
    exchanged for a token.
    """
    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = pkce_pair()

    # Authorization request parameters
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "read_gpx write_gpx",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    auth_url = f"{OSM_WEB_URL}/oauth2/authorize?{urlencode(params)}"

    print("\n🔐 Authorization required...")
    print("A browser will open for you to connect to OpenStreetMap.")
    print(f"If the browser doesn't open, copy this URL:\n{auth_url}\n")

    # Start local server to receive callback
    port = urlparse(REDIRECT_URI).port
    try:
        server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    except OSError as e:
        print(f"❌ Cannot listen on 127.0.0.1:{port} for the OSM callback: {e}")
        print(f"   Close the program using port {port}, then run the script again.")
        sys.exit(1)
    server.expected_state = state
    server.auth_code = None
    server.auth_error = None
    server.callback_done = False
    # handle_request() returns after 1 s without a request, to check the deadline
    server.timeout = 1

    def serve_until_callback():
        deadline = time.monotonic() + CALLBACK_TIMEOUT
        while not server.callback_done and time.monotonic() < deadline:
            server.handle_request()

    server_thread = threading.Thread(target=serve_until_callback)
    server_thread.daemon = True
    server_thread.start()

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback (max 2 minutes)
    server_thread.join(timeout=CALLBACK_TIMEOUT + CallbackHandler.timeout)
    server.server_close()

    if server.auth_error:
        print(f"❌ Authorization not granted on OpenStreetMap: {server.auth_error}")
        sys.exit(1)
    if server.auth_code is None:
        print("❌ Timeout: no authorization received")
        sys.exit(1)

    return server.auth_code, code_verifier


def get_access_token(client_id, client_secret, auth_code_param=None):
    """Exchange authorization code for an access token"""

    # Check if we already have a saved token
    if auth_code_param is None and os.path.exists(TOKEN_FILE):
        try:
            restrict_to_owner(TOKEN_FILE)
            with open(TOKEN_FILE, "r") as f:
                token = f.read().strip()
        except OSError:
            token = None  # Unreadable token file: authorize again

        if token:
            # Test if token is valid
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
            }
            try:
                response = requests.get(
                    f"{OSM_API_URL}/api/0.6/user/details.json",
                    headers=headers,
                    timeout=API_TIMEOUT,
                )
            except requests.RequestException as e:
                print(f"❌ Cannot reach OpenStreetMap: {e}")
                sys.exit(1)

            if response.status_code == 200:
                print("✅ Valid existing token found")
                return token
            # Only a rejected token calls for a new authorization: on a server
            # error, opening the browser would not help
            if response.status_code not in (401, 403):
                print(f"❌ OpenStreetMap unavailable (code: {response.status_code})")
                sys.exit(1)
            print("⚠️  Existing token invalid, new authorization required")

    # If no code provided, get one
    code_verifier = None
    if auth_code_param is None:
        auth_code_param, code_verifier = get_authorization_code(client_id)

    # Exchange code for token
    token_url = f"{OSM_WEB_URL}/oauth2/token"

    # Use Basic Auth for credentials
    from requests.auth import HTTPBasicAuth

    data = {
        "grant_type": "authorization_code",
        "code": auth_code_param,
        "redirect_uri": REDIRECT_URI,
    }
    if code_verifier:
        data["code_verifier"] = code_verifier

    try:
        response = requests.post(
            token_url,
            data=data,
            auth=HTTPBasicAuth(client_id, client_secret),
            headers={"User-Agent": USER_AGENT},
            timeout=API_TIMEOUT,
        )
    except requests.RequestException as e:
        print(f"❌ Error obtaining token: {e}")
        sys.exit(1)

    if response.status_code != 200:
        print(f"❌ Error obtaining token: {response.status_code}")
        print(response.text)
        sys.exit(1)

    token_data = response.json()
    access_token = token_data["access_token"]

    # Save token
    with open(TOKEN_FILE, "w", opener=private_opener) as f:
        f.write(access_token)

    print("✅ Access token obtained and saved")
    return access_token


# ============================================================================
# GPX FUNCTIONS
# ============================================================================


def parse_gpx_time(text):
    """Parse a GPX time, or return None if it is not a valid ISO 8601 date"""
    try:
        return datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def utc_sort_key(dt):
    """Comparable instant for a GPX time; GPX times without offset are UTC"""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def extract_gpx_timestamp(gpx_file):
    """Extract the oldest timestamp from a GPX file"""
    try:
        tree = ET.parse(gpx_file)
        root = tree.getroot()

        # Use the document's own namespace: GPX 1.0 and 1.1 differ
        ns_uri = root.tag[1:].split("}")[0] if root.tag.startswith("{") else ""

        def q(name):
            return f"{{{ns_uri}}}{name}" if ns_uri else name

        texts = []

        # Search in trkpt (track points)
        for time_elem in root.findall(f".//{q('trkpt')}/{q('time')}"):
            if time_elem.text:
                texts.append(time_elem.text)

        # Search in wpt (waypoints)
        for time_elem in root.findall(f".//{q('wpt')}/{q('time')}"):
            if time_elem.text:
                texts.append(time_elem.text)

        # Search in metadata (GPX 1.1), or directly under <gpx> (GPX 1.0)
        for document_time in (
            root.find(f".//{q('metadata')}/{q('time')}"),
            root.find(q("time")),
        ):
            if document_time is not None and document_time.text:
                texts.append(document_time.text)

        timestamps = [dt for dt in map(parse_gpx_time, texts) if dt is not None]
        if not timestamps:
            return None

        # Oldest instant, compared across time zones; it keeps its own offset
        return min(timestamps, key=utc_sort_key)

    except Exception as e:
        print(f"  ⚠️  Error extracting timestamp: {e}")
        return None


def extract_with_messages(gpx_file):
    """Run extract_gpx_timestamp, returning its printed messages with the result

    Workers cannot print directly: their output would interleave out of order.
    """
    messages = io.StringIO()
    with redirect_stdout(messages):
        timestamp = extract_gpx_timestamp(gpx_file)
    return timestamp, messages.getvalue()


def extract_all_timestamps(gpx_files):
    """Extract timestamps of all files, in worker processes when worth it

    Returns a list of (timestamp, messages) in the order of gpx_files.
    """
    if len(gpx_files) >= PARALLEL_MIN_FILES:
        workers = min(os.cpu_count() or 1, MAX_WORKERS)
        try:
            with ProcessPoolExecutor(workers) as executor:
                return list(executor.map(extract_with_messages, gpx_files, chunksize=4))
        except (OSError, NotImplementedError, BrokenProcessPool):
            pass  # No usable multiprocessing here: fall back to sequential

    return [extract_with_messages(gpx_file) for gpx_file in gpx_files]


def load_timestamp_cache():
    """Load cached extraction results, keyed by absolute file path"""
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        if cache.get("version") == CACHE_VERSION:
            return cache["files"]
    except (OSError, ValueError, KeyError, AttributeError):
        pass  # Missing or unreadable cache: rebuild it
    return {}


def save_timestamp_cache(entries):
    """Write the cache atomically, dropping files that no longer exist"""
    entries = {path: entry for path, entry in entries.items() if os.path.exists(path)}
    tmp_file = f"{CACHE_FILE}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({"version": CACHE_VERSION, "files": entries}, f)
        os.replace(tmp_file, CACHE_FILE)
    except OSError as e:
        print(f"⚠️  Unable to save cache: {e}")


def extract_timestamps_cached(gpx_files):
    """Extract timestamps, reusing results for files unchanged since last run

    A file counts as unchanged when its size and modification time match.
    Returns a list of (timestamp, messages) in the order of gpx_files.
    """
    cache = load_timestamp_cache()
    keys = []
    missing = []
    for gpx_file in gpx_files:
        stat = gpx_file.stat()
        key = str(gpx_file.resolve())
        keys.append(key)
        entry = cache.get(key)
        if (
            not isinstance(entry, dict)
            or entry.get("size") != stat.st_size
            or entry.get("mtime_ns") != stat.st_mtime_ns
        ):
            missing.append((gpx_file, key, stat))

    extracted = extract_all_timestamps([gpx_file for gpx_file, _, _ in missing])
    for (gpx_file, key, stat), (timestamp, messages) in zip(missing, extracted):
        cache[key] = {
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "timestamp": timestamp.isoformat() if timestamp else None,
            "messages": messages,
        }

    if missing:
        save_timestamp_cache(cache)

    results = []
    for key in keys:
        timestamp = cache[key]["timestamp"]
        results.append(
            (
                datetime.fromisoformat(timestamp) if timestamp else None,
                cache[key]["messages"],
            )
        )
    return results


def format_trace_name(dt):
    """Format trace name according to YYYYMMDD - hh:mm format"""
    return dt.strftime("%Y%m%d - %H:%M")


def get_existing_traces(access_token):
    """Retrieve list of user's existing traces

    Returns None when the list could not be retrieved: an empty set would
    mean "nothing uploaded yet" and every file would be uploaded again.
    """
    try:
        url = f"{OSM_API_URL}/api/0.6/user/gpx_files.json"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
        }
        response = requests.get(url, headers=headers, timeout=API_TIMEOUT)

        if response.status_code != 200:
            print(f"❌ Error retrieving traces: {response.status_code}")
            return None

        # Parse JSON response
        data = response.json()

        # API returns "traces" not "gpx_files"
        traces_list = data.get("traces", data.get("gpx_files"))
        if not isinstance(traces_list, list):
            print("❌ Error retrieving traces: unexpected response format")
            return None

        trace_names = set()

        for gpx_file in traces_list:
            # Extract YYYYMMDD - hh:mm format from description
            if "description" in gpx_file and gpx_file["description"]:
                desc = gpx_file["description"]
                # Search for date/time pattern in description
                match = re.search(r"\d{8} - \d{2}:\d{2}", desc)
                if match:
                    trace_names.add(match.group())

        return trace_names

    except Exception as e:
        print(f"❌ Error retrieving traces: {e}")
        return None


def upload_gpx(access_token, gpx_file, trace_name, config):
    """Upload a GPX file to OpenStreetMap"""
    try:
        url = f"{OSM_API_URL}/api/0.6/gpx/create"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "User-Agent": USER_AGENT,
        }

        description = f"{trace_name} - {config['description']}"

        with open(gpx_file, "rb") as f:
            files = {"file": (gpx_file.name, f, "application/gpx+xml")}
            # Put formatted name directly in description
            data = {
                "description": description,
                "tags": config["tags"],
                "visibility": config["visibility"],
            }

            response = requests.post(
                url, files=files, data=data, headers=headers, timeout=UPLOAD_TIMEOUT
            )

        if response.status_code in [200, 201]:
            trace_id = response.text.strip()
            print(f"  ✅ Successfully uploaded (ID: {trace_id})")
            print(f"  📝 Description: {trace_name}")
            return True
        else:
            print(f"  ❌ Upload failed (code: {response.status_code})")
            print(f"     {response.text}")
            return False

    except Exception as e:
        print(f"  ❌ Error during upload: {e}")
        return False


# ============================================================================
# MAIN PROGRAM
# ============================================================================


def main():
    """Main program"""
    # Load or create configuration
    config = load_or_create_config()

    # Ask for directory
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
    else:
        directory = Path(input("Path to directory containing GPX files: ").strip())

    if not directory.exists() or not directory.is_dir():
        print(f"❌ Directory '{directory}' does not exist!")
        sys.exit(1)

    # Find all GPX files
    # One pass with a case-insensitive suffix: globbing "*.gpx" then "*.GPX"
    # lists every file twice where matching ignores case (Windows)
    gpx_files = [
        path
        for path in directory.iterdir()
        if path.suffix.lower() == ".gpx" and path.is_file()
    ]

    if not gpx_files:
        print(f"❌ No GPX files found in '{directory}'")
        sys.exit(1)

    print(f"📁 {len(gpx_files)} GPX file(s) found\n")

    # Get access token
    access_token = get_access_token(config["client_id"], config["client_secret"])

    # Retrieve existing traces
    print("\n🔍 Retrieving existing traces...")
    existing_traces = get_existing_traces(access_token)
    if existing_traces is None:
        print("   Nothing uploaded: without this list, duplicates cannot be detected.")
        sys.exit(1)
    print(f"   {len(existing_traces)} existing trace(s)\n")

    # Process each file
    uploaded = 0
    skipped = 0
    errors = 0

    gpx_files = sorted(gpx_files)
    extracted = extract_timestamps_cached(gpx_files)

    for gpx_file, (timestamp, messages) in zip(gpx_files, extracted):
        print(f"📄 {gpx_file.name}")
        print(messages, end="")

        if timestamp is None:
            print("  ⚠️  No timestamp found, using file modification date")
            timestamp = datetime.fromtimestamp(gpx_file.stat().st_mtime)

        # Create trace name
        trace_name = format_trace_name(timestamp)
        print(f"  📅 Date/time: {trace_name}")

        # Check if already uploaded
        if trace_name in existing_traces:
            print("  ⏭️  Already uploaded, skipped")
            skipped += 1
        else:
            # Upload
            if upload_gpx(access_token, gpx_file, trace_name, config):
                uploaded += 1
                existing_traces.add(
                    trace_name
                )  # Add to avoid duplicates in this session
            else:
                errors += 1

        print()

    # Summary
    print("=" * 60)
    print(f"✅ Uploaded: {uploaded}")
    print(f"⏭️  Skipped (already present): {skipped}")
    print(f"❌ Errors: {errors}")
    print("=" * 60)


if __name__ == "__main__":
    main()
