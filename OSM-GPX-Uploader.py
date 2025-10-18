#!/usr/bin/env python3
"""
Script to upload GPX traces to OpenStreetMap with duplicate detection
Uses OAuth 2.0 authentication
"""

import os
import sys
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import requests
import webbrowser
from urllib.parse import urlencode, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

# ============================================================================
# CONFIGURATION
# ============================================================================
OSM_WEB_URL = "https://www.openstreetmap.org"  # For OAuth
OSM_API_URL = "https://api.openstreetmap.org"  # For GPX API
REDIRECT_URI = "http://127.0.0.1:8000/callback"  # Do not modify

# Configuration files
CONFIG_FILE = "osm_config.json"
TOKEN_FILE = "osm_token.txt"

# Default configuration
DEFAULT_CONFIG = {
    "client_id": "",
    "client_secret": "",
    "visibility": "identifiable",  # public, identifiable, trackable, private
    "description": "Automatically uploaded trace",
    "tags": "survey"
}


# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================

def load_or_create_config():
    """Load or create the configuration file"""
    config_path = Path(CONFIG_FILE)
    
    # If file exists, load it
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Check that credentials are present
            if config.get('client_id') and config.get('client_secret'):
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
    
    config['client_id'] = input("Client ID: ").strip()
    config['client_secret'] = input("Client Secret: ").strip()
    
    print("\n📝 Trace parameters (press Enter to keep default values)")
    
    visibility = input(f"Visibility [{config['visibility']}]: ").strip()
    if visibility:
        config['visibility'] = visibility
    
    description = input(f"Description [{config['description']}]: ").strip()
    if description:
        config['description'] = description
    
    tags = input(f"Tags [{config['tags']}]: ").strip()
    if tags:
        config['tags'] = tags
    
    # Save configuration
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
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

# Global variable to store authorization code
auth_code = None  # noqa: F841


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback"""
    def do_GET(self):
        global auth_code
        query = parse_qs(self.path.split('?')[1] if '?' in self.path else '')
        
        if 'code' in query:
            auth_code = query['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Authorization successful!</h1>'
                           b'<p>You can close this window.</p></body></html>')
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Error</h1>'
                           b'<p>No code received.</p></body></html>')
    
    def log_message(self, format, *args):
        pass  # Suppress server logs


def get_authorization_code(client_id):
    """Launch OAuth 2.0 flow to obtain an authorization code"""
    global auth_code
    
    # Authorization request parameters
    params = {
        'client_id': client_id,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'read_gpx write_gpx'
    }
    
    auth_url = f"{OSM_WEB_URL}/oauth2/authorize?{urlencode(params)}"
    
    print("\n🔐 Authorization required...")
    print("A browser will open for you to connect to OpenStreetMap.")
    print(f"If the browser doesn't open, copy this URL:\n{auth_url}\n")
    
    # Start local server to receive callback
    server = HTTPServer(('127.0.0.1', 8000), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.daemon = True
    server_thread.start()
    
    # Open browser
    webbrowser.open(auth_url)
    
    # Wait for callback (max 2 minutes)
    server_thread.join(timeout=120)
    server.server_close()
    
    if auth_code is None:
        print("❌ Timeout: no authorization received")
        sys.exit(1)
    
    return auth_code


def get_access_token(client_id, client_secret, auth_code_param=None):
    """Exchange authorization code for an access token"""
    
    # Check if we already have a saved token
    if auth_code_param is None and os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                token = f.read().strip()
                # Test if token is valid
                headers = {'Authorization': f'Bearer {token}'}
                response = requests.get(
                    f"{OSM_API_URL}/api/0.6/user/details.json",
                    headers=headers
                )
                if response.status_code == 200:
                    print("✅ Valid existing token found")
                    return token
                else:
                    print("⚠️  Existing token invalid, new authorization required")
        except Exception:
            pass
    
    # If no code provided, get one
    if auth_code_param is None:
        auth_code_param = get_authorization_code(client_id)
    
    # Exchange code for token
    token_url = f"{OSM_WEB_URL}/oauth2/token"
    
    # Use Basic Auth for credentials
    from requests.auth import HTTPBasicAuth
    
    data = {
        'grant_type': 'authorization_code',
        'code': auth_code_param,
        'redirect_uri': REDIRECT_URI
    }
    
    response = requests.post(
        token_url,
        data=data,
        auth=HTTPBasicAuth(client_id, client_secret)
    )
    
    if response.status_code != 200:
        print(f"❌ Error obtaining token: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    token_data = response.json()
    access_token = token_data['access_token']
    
    # Save token
    with open(TOKEN_FILE, 'w') as f:
        f.write(access_token)
    
    print("✅ Access token obtained and saved")
    return access_token


# ============================================================================
# GPX FUNCTIONS
# ============================================================================

def extract_gpx_timestamp(gpx_file):
    """Extract the oldest timestamp from a GPX file"""
    try:
        tree = ET.parse(gpx_file)
        root = tree.getroot()
        
        # GPX Namespace
        ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
        if not root.tag.endswith('gpx'):
            # Extract namespace from root
            if '}' in root.tag:
                ns_uri = root.tag.split('}')[0].strip('{')
                ns = {'gpx': ns_uri}
        
        timestamps = []
        
        # Search in trkpt (track points)
        for time_elem in root.findall('.//gpx:trkpt/gpx:time', ns):
            if time_elem.text:
                timestamps.append(time_elem.text)
        
        # Search in wpt (waypoints)
        for time_elem in root.findall('.//gpx:wpt/gpx:time', ns):
            if time_elem.text:
                timestamps.append(time_elem.text)
        
        # Search in metadata
        metadata_time = root.find('.//gpx:metadata/gpx:time', ns)
        if metadata_time is not None and metadata_time.text:
            timestamps.append(metadata_time.text)
        
        if not timestamps:
            return None
        
        # Take the oldest timestamp
        timestamps.sort()
        dt = datetime.fromisoformat(timestamps[0].replace('Z', '+00:00'))
        return dt
        
    except Exception as e:
        print(f"  ⚠️  Error extracting timestamp: {e}")
        return None


def format_trace_name(dt):
    """Format trace name according to YYYYMMDD - hh:mm format"""
    return dt.strftime("%Y%m%d - %H:%M")


def get_existing_traces(access_token):
    """Retrieve list of user's existing traces"""
    try:
        url = f"{OSM_API_URL}/api/0.6/user/gpx_files.json"
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print(f"⚠️  Error retrieving traces: {response.status_code}")
            return set()
        
        # Parse JSON response
        data = response.json()
        
        # API returns "traces" not "gpx_files"
        traces_list = data.get('traces', data.get('gpx_files', []))
        
        trace_names = set()
        
        for gpx_file in traces_list:
            # Extract YYYYMMDD - hh:mm format from description
            if 'description' in gpx_file and gpx_file['description']:
                desc = gpx_file['description']
                # Search for date/time pattern in description
                match = re.search(r'\d{8} - \d{2}:\d{2}', desc)
                if match:
                    trace_names.add(match.group())
        
        return trace_names
        
    except Exception as e:
        print(f"⚠️  Error retrieving traces: {e}")
        return set()


def upload_gpx(access_token, gpx_file, trace_name, config):
    """Upload a GPX file to OpenStreetMap"""
    try:
        url = f"{OSM_API_URL}/api/0.6/gpx/create"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        description = f"{trace_name} - {config['description']}"
        
        with open(gpx_file, 'rb') as f:
            files = {'file': (gpx_file.name, f, 'application/gpx+xml')}
            # Put formatted name directly in description
            data = {
                'description': description,
                'tags': config['tags'],
                'visibility': config['visibility']
            }
            
            response = requests.post(url, files=files, data=data, headers=headers)
        
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
    gpx_files = list(directory.glob("*.gpx")) + list(directory.glob("*.GPX"))
    
    if not gpx_files:
        print(f"❌ No GPX files found in '{directory}'")
        sys.exit(1)
    
    print(f"📁 {len(gpx_files)} GPX file(s) found\n")
    
    # Get access token
    access_token = get_access_token(config['client_id'], config['client_secret'])
    
    # Retrieve existing traces
    print("\n🔍 Retrieving existing traces...")
    existing_traces = get_existing_traces(access_token)
    print(f"   {len(existing_traces)} existing trace(s)\n")
    
    # Process each file
    uploaded = 0
    skipped = 0
    errors = 0
    
    for gpx_file in sorted(gpx_files):
        print(f"📄 {gpx_file.name}")
        
        # Extract timestamp
        timestamp = extract_gpx_timestamp(gpx_file)
        
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
                existing_traces.add(trace_name)  # Add to avoid duplicates in this session
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