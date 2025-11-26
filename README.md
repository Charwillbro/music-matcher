# Music Matcher

A simple web dashboard to match your Spotify playlists with your local music library.

🔗 **GitHub Repository:** https://github.com/Charwillbro/music-matcher

## Features

- Scans Spotify playlist CSV files from the configured directory
- **Select which playlists to scan** - Check/uncheck playlists before scanning
- **Collapsible playlists** - Expand/collapse playlist sections to manage large lists
- Matches playlist songs to your local music files
- Shows progress by playlist and overall statistics with live counters
- **Ignore list** - Hide songs you're not interested in (persists across runs)
- **Hide found songs toggle** - Show only missing songs to focus on what you need
- **Auto-scan on page load** - Automatically scans when library path is set
- **Tracks progress over time** - See how your library coverage improves
- Historical charts showing match percentage and song counts
- Clean, modern web dashboard with interactive charts and animations

## Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. The app is configured with:
   - Playlist directory: `C:\Users\Charles Broderick\Downloads\spotify_playlists`
   - Default music library: `F:\Media Monkey Library`
   - You can change these in `app.py` if needed

3. Run the application:
```bash
python app.py
```

4. Open your browser to `http://localhost:5000`

5. The app will auto-scan on load if a library path is configured, or:
   - Enter the path to your music library folder (or use the default)
   - Select which playlists you want to scan (check/uncheck playlists)
   - Click "Scan Library"

## How It Works

- The app reads CSV files from the playlists directory (only selected playlists)
- It extracts track names and artist names from each playlist
- It filters out songs in your ignore list
- It scans your music library folder for audio files (mp3, flac, m4a, wav, aac, ogg, wma)
- It matches songs by normalizing track names and artist names
- Displays results showing which songs you have and which are missing
- **Saves each scan to a local SQLite database** (`scan_history.db`)
- Shows progress charts tracking your library coverage over time

## Playlist Selection

- Use the checkboxes to select which playlists to include in the scan
- Click "Select All" or "Deselect All" for quick selection
- Only checked playlists will be scanned

## Ignore List

- Click the "Ignore" button on any song to immediately hide it from the current view
- Ignored songs are stored in the database and automatically filtered out from future scans
- **Persistent across app restarts** - Ignored songs remain ignored until you remove them
- View all ignored songs using "View All Ignored Songs" button
- Remove songs from the ignore list to see them again in scans
- Live counter shows total ignored songs with animations

## View Options

- **Collapsible Playlists** - Click playlist headers to expand/collapse song lists
- **Hide Found Songs** - Toggle to show only missing songs for focused viewing
- All view preferences work together for better organization

## Data Storage

The app uses a SQLite database (`scan_history.db`) to store:
- Scan history with timestamps
- Playlist scan results
- Ignored songs list

You can delete `scan_history.db` to reset all history and ignored songs.

## Progress Tracking

The app automatically tracks your progress over time:
- Each scan is saved with a timestamp
- View historical charts showing match percentage trends
- See how many songs you've matched vs. missing over time
- Charts update automatically after each scan

The progress data is stored locally in `scan_history.db` - you can delete this file to reset history.

## Matching Logic

Songs are matched by:
1. Normalizing track names and artist names (lowercase, removing special characters)
2. Checking if the track name appears in the music file filename
3. Verifying artist names appear in the filename when available

Note: Matching is based on filename patterns. For best results, ensure your music files have descriptive filenames that include track names and artist names.

