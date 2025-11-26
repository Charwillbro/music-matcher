import os
import csv
import json
from flask import Flask, render_template, jsonify, request
from pathlib import Path
import re
from collections import defaultdict
import sqlite3
from datetime import datetime
from contextlib import closing

app = Flask(__name__)

# Configuration
PLAYLISTS_DIR = r"C:\Users\Charles Broderick\Downloads\spotify_playlists"
DEFAULT_MUSIC_LIBRARY = r"F:\Media Monkey Library"
DB_PATH = 'scan_history.db'
MUSIC_EXTENSIONS = {'.mp3', '.flac', '.m4a', '.wav', '.aac', '.ogg', '.wma'}

# Initialize database
def init_db():
    """Initialize the database with scan history tables"""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_songs INTEGER,
                matched INTEGER,
                missing INTEGER,
                library_path TEXT
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS playlist_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER,
                playlist_name TEXT,
                total INTEGER,
                matched INTEGER,
                missing INTEGER,
                FOREIGN KEY (scan_id) REFERENCES scans(id)
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ignored_songs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_name TEXT NOT NULL,
                artist TEXT,
                track_normalized TEXT NOT NULL,
                artist_normalized TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(track_normalized, artist_normalized)
            )
        ''')
        
        conn.commit()

# Initialize database on startup
init_db()

def normalize_text(text):
    """Normalize text for matching: lowercase, remove special chars, trim spaces"""
    if not text:
        return ""
    # Remove common special characters and extra spaces
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def normalize_artist(artist_str):
    """Normalize artist name(s) - handles multiple artists separated by semicolons"""
    if not artist_str:
        return []
    # Split by semicolon and normalize each
    artists = [normalize_text(a.strip()) for a in artist_str.split(';')]
    return [a for a in artists if a]

def parse_playlist_csv(file_path):
    """Parse a Spotify playlist CSV file"""
    songs = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            playlist_name = Path(file_path).stem
            
            for row in reader:
                track_name = row.get('Track Name', '').strip()
                artist_str = row.get('Artist Name(s)', '').strip()
                album = row.get('Album Name', '').strip()
                
                if track_name:
                    songs.append({
                        'track_name': track_name,
                        'artist_str': artist_str,
                        'artists': normalize_artist(artist_str),
                        'track_normalized': normalize_text(track_name),
                        'album': album,
                        'album_normalized': normalize_text(album),
                        'playlist': playlist_name
                    })
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
    
    return songs

def scan_music_library(library_path):
    """Scan music library directory for audio files"""
    music_files = []
    
    if not os.path.exists(library_path):
        return music_files
    
    for root, dirs, files in os.walk(library_path):
        for file in files:
            if Path(file).suffix.lower() in MUSIC_EXTENSIONS:
                full_path = os.path.join(root, file)
                # Extract filename without extension for matching
                filename_base = Path(file).stem
                music_files.append({
                    'path': full_path,
                    'filename': file,
                    'filename_normalized': normalize_text(filename_base)
                })
    
    return music_files

def match_song_to_library(song, music_files):
    """Try to match a song to a music file in the library"""
    track_norm = song['track_normalized']
    
    # Try exact match on filename
    for music_file in music_files:
        filename_norm = music_file['filename_normalized']
        
        # Check if track name is in filename or vice versa
        if track_norm in filename_norm or filename_norm in track_norm:
            # If we have artist info, try to match that too
            if song['artists']:
                filename_lower = filename_norm.lower()
                # Check if any artist appears in filename
                artist_match = any(artist in filename_lower for artist in song['artists'] if artist)
                
                # If no artist match but filename contains track, it's still a potential match
                # but might be weaker
                if artist_match or len(song['artists']) == 0:
                    return music_file['path']
            else:
                # No artist info, just match on track name
                return music_file['path']
    
    return None

@app.route('/')
def index():
    return render_template('index.html', default_library=DEFAULT_MUSIC_LIBRARY)

def get_ignored_songs():
    """Get set of ignored songs from database"""
    ignored = []
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT track_normalized, artist_normalized FROM ignored_songs')
        for row in cursor.fetchall():
            artist_norm = row['artist_normalized'] or ''
            ignored.append((row['track_normalized'], artist_norm))
    return set(ignored)

def is_song_ignored(song, ignored_set):
    """Check if a song is in the ignored list"""
    track_norm = song['track_normalized']
    artist_norm_str = ','.join(sorted(song['artists'])) if song['artists'] else ''
    return (track_norm, artist_norm_str) in ignored_set

@app.route('/api/scan', methods=['POST'])
def scan():
    """Scan playlists and music library, return matching results"""
    data = request.json
    library_path = data.get('library_path', DEFAULT_MUSIC_LIBRARY)
    selected_playlists = data.get('selected_playlists', [])  # List of playlist names to include
    
    if not library_path or not os.path.exists(library_path):
        return jsonify({'error': 'Music library path is invalid or does not exist'}), 400
    
    # Get ignored songs
    ignored_set = get_ignored_songs()
    
    # Scan selected playlists (or all if none selected)
    all_songs = []
    playlist_files = list(Path(PLAYLISTS_DIR).glob('*.csv'))
    
    for playlist_file in playlist_files:
        playlist_name = playlist_file.stem
        # Filter by selected playlists if provided
        if selected_playlists and playlist_name not in selected_playlists:
            continue
            
        songs = parse_playlist_csv(playlist_file)
        all_songs.extend(songs)
    
    # Remove duplicates (same track + artist combo) and filter ignored songs
    seen = set()
    unique_songs = []
    for song in all_songs:
        key = (song['track_normalized'], tuple(sorted(song['artists'])))
        if key not in seen:
            seen.add(key)
            # Skip ignored songs
            if not is_song_ignored(song, ignored_set):
                unique_songs.append(song)
    
    # Scan music library
    music_files = scan_music_library(library_path)
    
    # Match songs
    results = {
        'total_songs': len(unique_songs),
        'matched': 0,
        'missing': 0,
        'playlists': defaultdict(lambda: {'total': 0, 'matched': 0, 'missing': 0, 'songs': []}),
        'songs': []
    }
    
    for song in unique_songs:
        matched_path = match_song_to_library(song, music_files)
        
        song_result = {
            'track_name': song['track_name'],
            'artist': song['artist_str'],
            'album': song['album'],
            'playlist': song['playlist'],
            'found': matched_path is not None,
            'file_path': matched_path
        }
        
        results['songs'].append(song_result)
        results['playlists'][song['playlist']]['total'] += 1
        results['playlists'][song['playlist']]['songs'].append(song_result)
        
        if matched_path:
            results['matched'] += 1
            results['playlists'][song['playlist']]['matched'] += 1
        else:
            results['missing'] += 1
            results['playlists'][song['playlist']]['missing'] += 1
    
    # Convert defaultdict to regular dict for JSON serialization
    results['playlists'] = dict(results['playlists'])
    
    # Save scan results to database
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO scans (total_songs, matched, missing, library_path)
            VALUES (?, ?, ?, ?)
        ''', (results['total_songs'], results['matched'], results['missing'], library_path))
        
        scan_id = cursor.lastrowid
        
        # Save playlist-specific results
        for playlist_name, playlist_data in results['playlists'].items():
            cursor.execute('''
                INSERT INTO playlist_scans (scan_id, playlist_name, total, matched, missing)
                VALUES (?, ?, ?, ?, ?)
            ''', (scan_id, playlist_name, playlist_data['total'], 
                  playlist_data['matched'], playlist_data['missing']))
        
        conn.commit()
    
    # Add timestamp to results
    results['timestamp'] = datetime.now().isoformat()
    results['scan_id'] = scan_id
    
    return jsonify(results)

@app.route('/api/playlists', methods=['GET'])
def list_playlists():
    """List available playlist files"""
    playlist_files = list(Path(PLAYLISTS_DIR).glob('*.csv'))
    playlists = [{'name': p.stem, 'path': str(p)} for p in playlist_files]
    return jsonify({'playlists': playlists})

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get scan history for progress tracking"""
    limit = request.args.get('limit', 50, type=int)
    
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get overall scan history
        cursor.execute('''
            SELECT id, timestamp, total_songs, matched, missing
            FROM scans
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        scans = []
        for row in cursor.fetchall():
            scans.append({
                'id': row['id'],
                'timestamp': row['timestamp'],
                'total_songs': row['total_songs'],
                'matched': row['matched'],
                'missing': row['missing'],
                'percentage': round((row['matched'] / row['total_songs'] * 100) if row['total_songs'] > 0 else 0, 1)
            })
        
        return jsonify({'scans': scans})

@app.route('/api/ignored-songs', methods=['GET'])
def get_ignored_songs_list():
    """Get list of all ignored songs"""
    with closing(sqlite3.connect(DB_PATH)) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT track_name, artist, added_at
            FROM ignored_songs
            ORDER BY added_at DESC
        ''')
        
        ignored = []
        for row in cursor.fetchall():
            ignored.append({
                'track_name': row['track_name'],
                'artist': row['artist'],
                'added_at': row['added_at']
            })
        
        return jsonify({'ignored_songs': ignored})

@app.route('/api/ignored-songs', methods=['POST'])
def add_ignored_song():
    """Add a song to the ignore list"""
    data = request.json
    track_name = data.get('track_name', '').strip()
    artist = data.get('artist', '').strip()
    
    if not track_name:
        return jsonify({'error': 'Track name is required'}), 400
    
    track_normalized = normalize_text(track_name)
    artist_normalized = normalize_artist(artist)
    artist_norm_str = ','.join(sorted(artist_normalized)) if artist_normalized else ''
    
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO ignored_songs (track_name, artist, track_normalized, artist_normalized)
                VALUES (?, ?, ?, ?)
            ''', (track_name, artist, track_normalized, artist_norm_str))
            conn.commit()
            return jsonify({'success': True, 'message': 'Song added to ignore list'})
        except sqlite3.IntegrityError:
            return jsonify({'success': True, 'message': 'Song already in ignore list'})

@app.route('/api/ignored-songs', methods=['DELETE'])
def remove_ignored_song():
    """Remove a song from the ignore list"""
    data = request.json
    track_name = data.get('track_name', '').strip()
    artist = data.get('artist', '').strip()
    
    if not track_name:
        return jsonify({'error': 'Track name is required'}), 400
    
    track_normalized = normalize_text(track_name)
    artist_normalized = normalize_artist(artist)
    artist_norm_str = ','.join(sorted(artist_normalized)) if artist_normalized else ''
    
    with closing(sqlite3.connect(DB_PATH)) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM ignored_songs
            WHERE track_normalized = ? AND artist_normalized = ?
        ''', (track_normalized, artist_norm_str))
        conn.commit()
        
        if cursor.rowcount > 0:
            return jsonify({'success': True, 'message': 'Song removed from ignore list'})
        else:
            return jsonify({'error': 'Song not found in ignore list'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5000)

