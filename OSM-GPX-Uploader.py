#!/usr/bin/env python3
"""
Script pour uploader des traces GPX vers OpenStreetMap
avec détection des doublons basée sur le nom de la trace
Utilise OAuth 2.0
"""

import os
import sys
import json
import re
import traceback
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
OSM_WEB_URL = "https://www.openstreetmap.org"  # Pour OAuth
OSM_API_URL = "https://api.openstreetmap.org"  # Pour les API GPX
REDIRECT_URI = "http://127.0.0.1:8000/callback"  # Ne pas modifier

# Fichiers de configuration
CONFIG_FILE = "osm_config.json"
TOKEN_FILE = "osm_token.txt"

# Configuration par défaut
DEFAULT_CONFIG = {
    "client_id": "",
    "client_secret": "",
    "visibility": "identifiable",  # public, identifiable, trackable, private
    "description": "Trace uploadée automatiquement",
    "tags": "survey"
}


# ============================================================================
# GESTION DE LA CONFIGURATION
# ============================================================================

def load_or_create_config():
    """Charge ou crée le fichier de configuration"""
    config_path = Path(CONFIG_FILE)
    
    # Si le fichier existe, le charger
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Vérifier que les credentials sont présents
            if config.get('client_id') and config.get('client_secret'):
                return config
            else:
                print("⚠️  Configuration incomplète détectée\n")
        except Exception as e:
            print(f"⚠️  Erreur lors de la lecture de la config: {e}\n")
    
    # Créer une nouvelle configuration
    print("=" * 70)
    print("🔧 CONFIGURATION INITIALE")
    print("=" * 70)
    print("\nPour utiliser ce script, vous devez créer une application OAuth2 sur OSM:")
    print("1. Allez sur: https://www.openstreetmap.org/oauth2/applications")
    print("2. Cliquez sur 'Enregistrer une nouvelle application'")
    print("3. Remplissez:")
    print("   - Nom: GPX Uploader (ou autre)")
    print("   - URI de redirection: http://127.0.0.1:8000/callback")
    print("   - Permissions: Cochez 'Lire les traces GPS' ET 'Envoyer des traces GPS'")
    print("4. Validez et copiez vos credentials\n")
    
    config = DEFAULT_CONFIG.copy()
    
    config['client_id'] = input("Client ID: ").strip()
    config['client_secret'] = input("Client Secret: ").strip()
    
    print("\n📝 Paramètres des traces (appuyez sur Entrée pour garder les valeurs par défaut)")
    
    visibility = input(f"Visibilité [{config['visibility']}]: ").strip()
    if visibility:
        config['visibility'] = visibility
    
    description = input(f"Description [{config['description']}]: ").strip()
    if description:
        config['description'] = description
    
    tags = input(f"Tags [{config['tags']}]: ").strip()
    if tags:
        config['tags'] = tags
    
    # Sauvegarder la configuration
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, indent=2, fp=f)
        print(f"\n✅ Configuration sauvegardée dans {CONFIG_FILE}")
        print("   Vous pouvez éditer ce fichier directement si besoin.\n")
    except Exception as e:
        print(f"\n❌ Impossible de sauvegarder la config: {e}")
        sys.exit(1)
    
    return config


# ============================================================================
# GESTION OAUTH 2.0
# ============================================================================

# Variable globale pour stocker le code d'autorisation
auth_code = None

class CallbackHandler(BaseHTTPRequestHandler):
    """Gère le callback OAuth"""
    def do_GET(self):
        global auth_code
        query = parse_qs(self.path.split('?')[1] if '?' in self.path else '')
        
        if 'code' in query:
            auth_code = query['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Autorisation reussie!</h1><p>Vous pouvez fermer cette fenetre.</p></body></html>')
        else:
            self.send_response(400)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'<html><body><h1>Erreur</h1><p>Pas de code recu.</p></body></html>')
    
    def log_message(self, format, *args):
        pass  # Supprimer les logs du serveur


def get_authorization_code(client_id):
    """Lance le flux OAuth 2.0 pour obtenir un code d'autorisation"""
    global auth_code
    
    # Paramètres de la requête d'autorisation
    params = {
        'client_id': client_id,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': 'read_gpx write_gpx'  # Ajouter read_gpx pour lire les traces existantes
    }
    
    auth_url = f"{OSM_WEB_URL}/oauth2/authorize?{urlencode(params)}"
    
    print("\n🔐 Autorisation nécessaire...")
    print(f"Un navigateur va s'ouvrir pour vous connecter à OpenStreetMap.")
    print(f"Si le navigateur ne s'ouvre pas, copiez cette URL :\n{auth_url}\n")
    
    # Démarrer un serveur local pour recevoir le callback
    server = HTTPServer(('127.0.0.1', 8000), CallbackHandler)
    server_thread = threading.Thread(target=server.handle_request)
    server_thread.daemon = True
    server_thread.start()
    
    # Ouvrir le navigateur
    webbrowser.open(auth_url)
    
    # Attendre le callback (max 2 minutes)
    server_thread.join(timeout=120)
    server.server_close()
    
    if auth_code is None:
        print("❌ Timeout: aucune autorisation reçue")
        sys.exit(1)
    
    return auth_code


def get_access_token(client_id, client_secret, auth_code=None):
    """Échange le code d'autorisation contre un access token"""
    
    # Vérifier si on a déjà un token sauvegardé
    if auth_code is None and os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                token = f.read().strip()
                # Tester si le token est valide
                headers = {'Authorization': f'Bearer {token}'}
                response = requests.get(f"{OSM_API_URL}/api/0.6/user/details.json", headers=headers)
                if response.status_code == 200:
                    print("✅ Token existant valide trouvé")
                    return token
                else:
                    print("⚠️  Token existant invalide, nouvelle autorisation nécessaire")
        except:
            pass
    
    # Si pas de code fourni, en obtenir un
    if auth_code is None:
        auth_code = get_authorization_code(client_id)
    
    # Échanger le code contre un token
    token_url = f"{OSM_WEB_URL}/oauth2/token"
    
    # Utiliser Basic Auth pour les credentials
    from requests.auth import HTTPBasicAuth
    
    data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'redirect_uri': REDIRECT_URI
    }
    
    response = requests.post(
        token_url, 
        data=data,
        auth=HTTPBasicAuth(client_id, client_secret)
    )
    
    if response.status_code != 200:
        print(f"❌ Erreur lors de l'obtention du token: {response.status_code}")
        print(response.text)
        sys.exit(1)
    
    token_data = response.json()
    access_token = token_data['access_token']
    
    # Sauvegarder le token
    with open(TOKEN_FILE, 'w') as f:
        f.write(access_token)
    
    print("✅ Token d'accès obtenu et sauvegardé")
    return access_token


# ============================================================================
# FONCTIONS GPX
# ============================================================================

def extract_gpx_timestamp(gpx_file):
    """Extrait le timestamp le plus ancien d'un fichier GPX"""
    try:
        tree = ET.parse(gpx_file)
        root = tree.getroot()
        
        # Namespace GPX
        ns = {'gpx': 'http://www.topografix.com/GPX/1/1'}
        if not root.tag.endswith('gpx'):
            # Extraire le namespace du root
            if '}' in root.tag:
                ns_uri = root.tag.split('}')[0].strip('{')
                ns = {'gpx': ns_uri}
        
        timestamps = []
        
        # Chercher dans les trkpt (track points)
        for time_elem in root.findall('.//gpx:trkpt/gpx:time', ns):
            if time_elem.text:
                timestamps.append(time_elem.text)
        
        # Chercher dans les wpt (waypoints)
        for time_elem in root.findall('.//gpx:wpt/gpx:time', ns):
            if time_elem.text:
                timestamps.append(time_elem.text)
        
        # Chercher dans metadata
        metadata_time = root.find('.//gpx:metadata/gpx:time', ns)
        if metadata_time is not None and metadata_time.text:
            timestamps.append(metadata_time.text)
        
        if not timestamps:
            return None
        
        # Prendre le timestamp le plus ancien
        timestamps.sort()
        dt = datetime.fromisoformat(timestamps[0].replace('Z', '+00:00'))
        return dt
        
    except Exception as e:
        print(f"  ⚠️  Erreur lors de l'extraction du timestamp: {e}")
        return None


def format_trace_name(dt):
    """Formate le nom de la trace selon le format YYYYMMDD - hh:mm"""
    return dt.strftime("%Y%m%d - %H:%M")


def get_existing_traces(access_token):
    """Récupère la liste des traces existantes de l'utilisateur"""
    try:
        url = f"{OSM_API_URL}/api/0.6/user/gpx_files.json"
        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"⚠️  Erreur lors de la récupération des traces: {response.status_code}")
            return set()
        
        # Parser la réponse JSON
        data = response.json()
        
        # L'API retourne "traces" et non "gpx_files"
        traces_list = data.get('traces', data.get('gpx_files', []))
        
        trace_names = set()
        
        for gpx_file in traces_list:
            # Extraire le format YYYYMMDD - hh:mm de la description
            if 'description' in gpx_file and gpx_file['description']:
                desc = gpx_file['description']
                # Chercher le pattern de date/heure dans la description
                match = re.search(r'\d{8} - \d{2}:\d{2}', desc)
                if match:
                    trace_names.add(match.group())
                    
        
        return trace_names
        
    except Exception as e:
        print(f"⚠️  Erreur lors de la récupération des traces: {e}")
        import traceback
        return set()


def upload_gpx(access_token, gpx_file, trace_name, config):
    """Upload un fichier GPX vers OpenStreetMap"""
    try:
        url = f"{OSM_API_URL}/api/0.6/gpx/create"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        description = f"{trace_name} - {config['description']}"
        
        with open(gpx_file, 'rb') as f:
            files = {'file': (gpx_file.name, f, 'application/gpx+xml')}
            # Mettre directement le nom formaté dans la description
            data = {
                'description': description,
                'tags': config['tags'],
                'visibility': config['visibility']
            }
            
            /Gheop/ POST vers {url}")
            response = requests.post(url, files=files, data=data, headers=headers)
        
        
        
        if response.status_code in [200, 201]:
            trace_id = response.text.strip()
            print(f"  ✅ Uploadé avec succès (ID: {trace_id})")
            print(f"  📝 Description: {trace_name}")
            return True
        else:
            print(f"  ❌ Échec de l'upload (code: {response.status_code})")
            print(f"     {response.text}")
            return False
            
    except Exception as e:
        print(f"  ❌ Erreur lors de l'upload: {e}")
        import traceback
        
        return False


# ============================================================================
# PROGRAMME PRINCIPAL
# ============================================================================

def main():
    # Charger ou créer la configuration
    config = load_or_create_config()
    
    # Demander le répertoire
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1])
    else:
        directory = Path(input("Chemin du répertoire contenant les GPX: ").strip())
    
    if not directory.exists() or not directory.is_dir():
        print(f"❌ Le répertoire '{directory}' n'existe pas!")
        sys.exit(1)
    
    # Trouver tous les fichiers GPX
    gpx_files = list(directory.glob("*.gpx")) + list(directory.glob("*.GPX"))
    
    if not gpx_files:
        print(f"❌ Aucun fichier GPX trouvé dans '{directory}'")
        sys.exit(1)
    
    print(f"📁 {len(gpx_files)} fichier(s) GPX trouvé(s)\n")
    
    # Obtenir un access token
    access_token = get_access_token(config['client_id'], config['client_secret'])
    
    # Récupérer les traces existantes
    print("\n🔍 Récupération des traces existantes...")
    existing_traces = get_existing_traces(access_token)
    print(f"   {len(existing_traces)} trace(s) existante(s)\n")
    
    # Traiter chaque fichier
    uploaded = 0
    skipped = 0
    errors = 0
    
    for gpx_file in sorted(gpx_files):
        print(f"📄 {gpx_file.name}")
        
        # Extraire le timestamp
        timestamp = extract_gpx_timestamp(gpx_file)
        
        if timestamp is None:
            print(f"  ⚠️  Pas de timestamp trouvé, utilisation de la date de modification du fichier")
            timestamp = datetime.fromtimestamp(gpx_file.stat().st_mtime)
        
        # Créer le nom de la trace
        trace_name = format_trace_name(timestamp)
        print(f"  📅 Date/heure: {trace_name}")
        
        # Vérifier si déjà uploadé
        if trace_name in existing_traces:
            print(f"  ⏭️  Déjà uploadé, ignoré")
            skipped += 1
        else:
            # Upload
            if upload_gpx(access_token, gpx_file, trace_name, config):
                uploaded += 1
                existing_traces.add(trace_name)  # Ajouter pour éviter les doublons dans cette session
            else:
                errors += 1
        
        print()
    
    # Résumé
    print("=" * 60)
    print(f"✅ Uploadés: {uploaded}")
    print(f"⏭️  Ignorés (déjà présents): {skipped}")
    print(f"❌ Erreurs: {errors}")
    print("=" * 60)


if __name__ == "__main__":
    main()