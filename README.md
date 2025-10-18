# OSM-GPX-Uploader

🗺️ Python script to automatically upload your GPX traces to OpenStreetMap with duplicate detection.

[![Python Version](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![OpenStreetMap](https://img.shields.io/badge/OpenStreetMap-API%20v0.6-7ebc6f.svg)](https://wiki.openstreetmap.org/wiki/API_v0.6)

## ✨ Features

- 📤 **Batch upload**: Upload all your GPX files from a directory with a single command
- 🔍 **Duplicate detection**: Avoids re-uploading already sent traces by comparing dates/times
- 📅 **Automatic naming**: Extracts date/time from GPX and names traces as `YYYYMMDD - hh:mm`
- 🔐 **OAuth 2.0 authentication**: Secure and modern, with persistent token storage
- ⚙️ **External configuration**: Your credentials and settings in a JSON file
- 🎯 **Customizable visibility**: Choose between public, identifiable, trackable, or private
- 🏷️ **Custom tags**: Add your own tags to organize your traces

## 📋 Prerequisites

- Python 3.7 or higher
- An [OpenStreetMap](https://www.openstreetmap.org/) account
- Python libraries: `requests`

## 🚀 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/OSM-GPX-Uploader.git
   cd OSM-GPX-Uploader
   ```

2. **Install dependencies**:
   ```bash
   pip install requests
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

✅ Configuration saved in osm_config.json
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

### `osm_config.json` file

After first use, an `osm_config.json` file is created:

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

## 🔧 Troubleshooting

### Token is invalid every time

Delete the `osm_token.txt` file and restart:
```bash
rm osm_token.txt
python OSM-GPX-Uploader.py traces
```

### Error 403 when retrieving traces

Check that you have enabled **"Read user GPS traces"** in your OAuth application permissions.

### Script doesn't detect duplicates

The script compares dates/times in descriptions. If you uploaded traces with another tool, they won't be detected as duplicates.

### No timestamp in GPX

If the GPX file doesn't contain a timestamp, the script uses the file's modification date.

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

### Report a bug

1. Check that the bug isn't already reported in [Issues](https://github.com/YOUR_USERNAME/OSM-GPX-Uploader/issues)
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
- ✅ Reliable duplicate detection
- ✅ Quick identification of your traces

## 🔒 Security

- ⚠️ **Never commit** your `osm_config.json` or `osm_token.txt` to Git
- These files are already in `.gitignore` by default
- Your Client Secret should not be shared with anyone
- If you think your credentials have been compromised, revoke the application on OpenStreetMap and create a new one

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [OpenStreetMap](https://www.openstreetmap.org/) for the API and platform
- The OSM community for the documentation
- All project contributors

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/YOUR_USERNAME/OSM-GPX-Uploader/issues)
- **OSM Wiki**: [API v0.6](https://wiki.openstreetmap.org/wiki/API_v0.6)
- **OSM Forum**: [Community Forum](https://community.openstreetmap.org/)

---

Made with ❤️ for the OpenStreetMap community