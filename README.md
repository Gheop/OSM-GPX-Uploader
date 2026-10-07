# OSM-GPX-Uploader

🗺️ Python script to automatically upload your GPX traces to OpenStreetMap with duplicate detection.

[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![OpenStreetMap](https://img.shields.io/badge/OpenStreetMap-API%20v0.6-7ebc6f.svg)](https://wiki.openstreetmap.org/wiki/API_v0.6)
[![Tests](https://github.com/Gheop/OSM-GPX-Uploader/actions/workflows/tests.yml/badge.svg)](https://github.com/Gheop/OSM-GPX-Uploader/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/Gheop/OSM-GPX-Uploader/branch/main/graph/badge.svg)](https://codecov.io/gh/Gheop/OSM-GPX-Uploader)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## ✨ Features

- 📤 **Batch upload**: Upload all your GPX files from a directory with a single command
- 🔍 **Duplicate detection**: Avoids re-uploading already sent traces by comparing dates/times
- 📅 **Automatic naming**: Extracts date/time from GPX and names traces as `YYYYMMDD - hh:mm`
- 🔐 **OAuth 2.0 authentication**: Secure and modern, with persistent token storage
- ⚙️ **External configuration**: Your credentials and settings in a JSON file
- 🎯 **Customizable visibility**: Choose between public, identifiable, trackable, or private
- 🏷️ **Custom tags**: Add your own tags to organize your traces

## 📋 Prerequisites

- Python 3.11 or higher
- An [OpenStreetMap](https://www.openstreetmap.org/) account
- Python libraries: `requests`

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Gheop/OSM-GPX-Uploader.git
   cd OSM-GPX-Uploader
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create an OAuth application on OpenStreetMap**:
   - Go to [https://www.openstreetmap.org/oauth2/applications](https://www.openstreetmap.org/oauth2/applications)
   - Click **"Register new application"**
   - Fill in the form:
     - **Name**: `GPX Uploader` (or whatever you want)
     - **Redirect URI**: `http://127.0.0.1:8000/callback` ⚠️ **Exactly this value**
     - **Permissions**: Check ✅ **"Read user GPS traces"** AND ✅ **"Upload GPS traces"**
   - Validate and copy your **Client ID** and **Client Secret**

## 🎯 Usage

### First use

Run the script, it will guide you through the configuration:

```bash
python OSM-GPX-Uploader.py /path/to/your/gpx
```

The script will ask for:
- Client ID
- Client Secret
- Visibility (public/identifiable/trackable/private)
- Default description
- Tags

### Example output

```
======================================================================
🔧 INITIAL CONFIGURATION
======================================================================

To use this script, you need to create an OAuth2 application on OSM:
1. Go to: https://www.openstreetmap.org/oauth2/applications
2. Click 'Register new application'
3. Fill in:
   - Name: GPX Uploader (or other)
   - Redirect URI: http://127.0.0.1:8000/callback
   - Permissions: Check 'Read user GPS traces' AND 'Upload GPS traces'
4. Validate and copy your credentials

Client ID: Qeso9BQyqaRuaxp-BbWSX2IbWeG_DzQ0X5ynml0kDHE
Client Secret: ********************************
📝 Trace parameters (press Enter to keep default values)
Visibility [identifiable]: 
Description [Automatically uploaded trace]: 
Tags [survey]: 

✅ Configuration saved in /home/you/.config/osm-gpx-uploader/osm_config.json
   You can edit this file directly if needed.

📁 3 GPX file(s) found

🔐 Authorization required...
A browser will open for you to connect to OpenStreetMap.

✅ Access token obtained and saved

🔍 Retrieving existing traces...
   5 existing trace(s)

📄 2023-11-22_15-04_UTC_Le_petit_Xambes__10km_.gpx
  📅 Date/time: 20231122 - 14:04
  ⏭️  Already uploaded, skipped

📄 2024-03-15_09-23_UTC_Paris_Avenue_des_Champs-Élysées.gpx
  📅 Date/time: 20240315 - 09:23
  ✅ Successfully uploaded (ID: 12091792)
  📝 Description: 20240315 - 09:23

📄 2024-10-18_16-45_UTC_Lyon_Vieux-Lyon.gpx
  📅 Date/time: 20241018 - 16:45
  ✅ Successfully uploaded (ID: 12091793)
  📝 Description: 20241018 - 16:45

============================================================
✅ Uploaded: 2
⏭️  Skipped (already present): 1
❌ Errors: 0
============================================================
```

### Subsequent uses

Once configured, it's even simpler:

```bash
python OSM-GPX-Uploader.py /path/to/your/gpx
```

The script automatically uses the saved configuration and token!

## ⚙️ Configuration

### Files location

The script keeps its files in your user directories, so it works the same from any folder:

| System  | Configuration and token                           | Cache                                |
|---------|---------------------------------------------------|--------------------------------------|
| Linux   | `~/.config/osm-gpx-uploader/`                     | `~/.cache/osm-gpx-uploader/`         |
| macOS   | `~/Library/Application Support/osm-gpx-uploader/` | `~/Library/Caches/osm-gpx-uploader/` |
| Windows | `%APPDATA%\osm-gpx-uploader\`                     | `%LOCALAPPDATA%\osm-gpx-uploader\`   |

On Linux, `XDG_CONFIG_HOME` and `XDG_CACHE_HOME` are honoured. Set `OSM_GPX_UPLOADER_DIR` to keep all files in one folder of your choice instead.

Older versions kept `osm_config.json`, `osm_token.txt` and `osm_gpx_cache.json` in the folder the script was run from. The first run of this version moves them to the locations above; if a file already exists there, the old copy is left in place and ignored.

### `osm_config.json` file

After first use, `osm_config.json` is created in the configuration directory:

```json
{
  "client_id": "your_client_id",
  "client_secret": "your_secret",
  "visibility": "identifiable",
  "description": "Automatically uploaded trace",
  "tags": "survey"
}
```

You can edit this file directly to modify settings.

### Visibility options

- **`identifiable`**: Public trace with your name and timestamps (recommended for mapping)
- **`public`**: Public trace with your name but without timestamps
- **`trackable`**: Anonymous public trace with timestamps
- **`private`**: Visible only by you

### Tags

Add tags separated by commas to organize your traces:
```json
"tags": "survey,bike,paris"
```

### `osm_gpx_cache.json` file

The script stores the date/time it extracted from each GPX file in `osm_gpx_cache.json`, in the cache directory, so the next runs only read new or modified files. A file is read again when its size or modification time changes. Deleting the cache is always safe: the next run rebuilds it.

## 🔧 Troubleshooting

### Authorization is asked again

The script reuses the saved token. When OpenStreetMap rejects it (revoked, or created without the GPS traces permissions), the script asks for a new authorization once and saves the new token. If the new token is rejected too, check the application permissions (see below).

To force a new authorization, delete `osm_token.txt` from the configuration directory (see [Files location](#files-location)). On Linux:
```bash
rm ~/.config/osm-gpx-uploader/osm_token.txt
```

### Error 403 when retrieving traces

Check that you have enabled **"Read user GPS traces"** in your OAuth application permissions.

### Script doesn't detect duplicates

The script compares dates/times in descriptions. If you uploaded traces with another tool, they won't be detected as duplicates. See [How duplicates are detected](#how-duplicates-are-detected) for the other limits.

### No timestamp in GPX

If the GPX file doesn't contain a timestamp, the script uses the file's modification date.

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Development setup

1. **Fork and clone the repository**:
   ```bash
   git clone https://github.com/Gheop/OSM-GPX-Uploader.git
   cd OSM-GPX-Uploader
   ```

2. **Install development dependencies and the Git hooks**:
   ```bash
   pip install -r requirements-dev.txt
   pre-commit install
   ```
   The hooks run `black` and the blocking `flake8` checks before each commit, as the CI lint job does.

3. **Run tests**:
   ```bash
   # Run all tests
   pytest

   # Run with coverage
   pytest --cov=. --cov-report=html

   # Run specific test file
   pytest tests/test_osm_gpx_uploader.py -v
   ```

4. **Check code style**:
   ```bash
   # Check formatting
   black --check .

   # Auto-format code
   black .

   # Lint code
   flake8 .
   ```

### Report a bug

1. Check that the bug isn't already reported in [Issues](https://github.com/Gheop/OSM-GPX-Uploader/issues)
2. Create a new issue with:
   - A clear description of the problem
   - Steps to reproduce it
   - Script output with debug logs
   - Your Python version (`python --version`)

### Propose an improvement

1. Open an issue to discuss your idea
2. Fork the project
3. Create a branch for your feature (`git checkout -b feature/my-awesome-feature`)
4. Commit your changes (`git commit -am 'Add my awesome feature'`)
5. Push to the branch (`git push origin feature/my-awesome-feature`)
6. Open a Pull Request

### Improvement ideas

- [ ] Support for ZIP files containing multiple GPX
- [ ] Graphical User Interface (GUI)
- [ ] Upload to other platforms (Strava, etc.)
- [ ] HTML report of uploads
- [ ] Filtering by date/geographic area
- [ ] Dry-run mode to test without uploading
- [ ] Support for API v0.7 when released

## 📝 Trace format

The script automatically names your traces in `YYYYMMDD - hh:mm` format in the description:

```
20231122 - 14:04 - Automatically uploaded trace
```

This format allows:
- ✅ Easy chronological sorting
- ✅ Duplicate detection (see below)
- ✅ Quick identification of your traces

### How duplicates are detected

Before uploading, the script downloads the list of your traces and reads the `YYYYMMDD - hh:mm` found in each description. A GPX file whose oldest time gives a name already in that list is skipped. This has limits:

- Two different traces that start within the same minute get the same name: only the first one is uploaded.
- If you edit a trace description on OpenStreetMap and remove its `YYYYMMDD - hh:mm`, the next run uploads that file again.
- Traces uploaded with another tool are not recognised unless their description contains the same date/time format.
- If the list of your traces cannot be retrieved (network error, OpenStreetMap unavailable), the script stops without uploading anything rather than risk duplicates.

## 🔒 Security

- Your token and Client Secret are stored in your user configuration directory, readable by you only
- ⚠️ **Never commit** your `osm_config.json` or `osm_token.txt` to Git; if older copies remain in your project folder, they are listed in `.gitignore`
- Your Client Secret should not be shared with anyone
- If you think your credentials have been compromised, revoke the application on OpenStreetMap and create a new one

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [OpenStreetMap](https://www.openstreetmap.org/) for the API and platform
- The OSM community for the documentation
- All project contributors

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Gheop/OSM-GPX-Uploader/issues)
- **OSM Wiki**: [API v0.6](https://wiki.openstreetmap.org/wiki/API_v0.6)
- **OSM Forum**: [Community Forum](https://community.openstreetmap.org/)

---

Made with ❤️ for the OpenStreetMap community

## README changelog

| Version | Date       | Changes                                               |
|---------|------------|-------------------------------------------------------|
| 1.2.3   | 2026-10-07 | Document the pre-commit hooks                         |
| 1.2.2   | 2026-10-07 | Require Python 3.11 or higher                         |
| 1.2.1   | 2026-10-07 | Explain when authorization is asked again             |
| 1.2.0   | 2026-10-07 | Document how duplicates are detected and their limits |
| 1.1.0   | 2026-10-07 | Add files location section for user directories       |
| 1.0.2   | 2026-10-07 | Require Python 3.10 or higher                         |
| 1.0.1   | 2026-10-07 | Install dependencies from requirements.txt            |
| 1.0.0   | 2026-10-07 | Document the timestamp cache file                     |
