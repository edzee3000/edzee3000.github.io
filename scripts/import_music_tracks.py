"""Merge a NetEase JSON export by stable song ID, preserving existing analysis.

Preview changes by default. --apply adds/updates metadata, puts new songs into
the unclassified region, and rebuilds. Existing songs are not implicitly deleted.
Input may be a track list, {playlist:{tracks:[]}} or {result:{tracks:[]}}.
"""
import argparse
import copy
import json
from pathlib import Path
import urllib.parse
import urllib.request
from build_music_atlas import ROOT, build, read_json, validate


def merge(raw, annotations, incoming):
    raw, annotations = copy.deepcopy(raw), copy.deepcopy(annotations)
    if isinstance(incoming, dict):
        incoming = incoming.get('playlist', incoming.get('result', incoming))
        incoming = incoming.get('tracks', [])
    if not isinstance(incoming, list) or not incoming:
        raise ValueError('Input must contain a non-empty track list')
    positions = {song['id']: i for i, song in enumerate(raw)}
    added, updated, seen = [], [], set()
    for entry in incoming:
        song = copy.deepcopy(entry)
        song['artists'] = song.get('artists', song.get('ar', []))
        song['album'] = song.get('album', song.get('al', {}))
        song['duration'] = song.get('duration', song.get('dt', 0))
        song_id = song['id']
        if song_id in seen:
            raise ValueError(f'Duplicate ID in import: {song_id}')
        seen.add(song_id)
        if song_id in positions:
            old = raw[positions[song_id]]
            # Exported partial records must not discard existing metadata.
            replacement = {**old, **song, 'album': {**old['album'], **song['album']}}
            if replacement != old:
                raw[positions[song_id]] = replacement
                updated.append(song_id)
        else:
            positions[song_id] = len(raw)
            raw.append(song)
            added.append(song_id)
            annotations['nodes'].append(dict(id=song_id, group='unclassified', tags=['新加入 · 待分析'],
                status='draft', fact='歌名、歌手和专辑来自导入记录。',
                note='这首歌已加入星图，尚未完成逐首分析。相似性关系会在取得证据后补充。', sources=[]))
    if added and not any(g['id'] == 'unclassified' for g in annotations['groups']):
        annotations['groups'].append(dict(id='unclassified', name='新来的声音', english='YET TO EXPLORE',
                                         color='#90998e', center=[500, 610]))
    validate(raw, annotations)
    return raw, annotations, dict(added=added, updated=updated, total=len(raw))


def fetch_playlist(playlist_id):
    """Read public metadata. Fail closed if any advertised ID is unavailable."""
    def request(path, query):
        url = 'https://music.163.com' + path + '?' + urllib.parse.urlencode(query)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://music.163.com/'})
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.load(response)
        if data.get('code') != 200:
            raise ValueError(f'NetEase metadata request failed: {data.get("code")}')
        return data
    metadata = request('/api/v6/playlist/detail', {'id': playlist_id})
    playlist = metadata.get('playlist', {})
    ids = [item['id'] for item in playlist.get('trackIds', [])]
    if not ids or len(ids) != len(set(ids)):
        raise ValueError('Missing or duplicate track IDs in playlist response')
    by_id = {}
    for offset in range(0, len(ids), 50):
        batch = request('/api/song/detail', {'ids': json.dumps(ids[offset:offset + 50])})
        by_id.update({song['id']: song for song in batch.get('songs', [])})
    missing = set(ids) - by_id.keys()
    if missing:
        raise ValueError(f'{len(missing)} track IDs have no metadata; import cancelled. Try a complete JSON export.')
    print(json.dumps({'playlist': playlist_id, 'advertisedCount': playlist.get('trackCount'), 'resolvedIDs': len(ids)}, ensure_ascii=False))
    return [by_id[i] for i in ids]


def apply_import(incoming, root=ROOT):
    root = Path(root)
    raw_path, analysis_path = root / '_data/music.json', root / '_data/music_atlas.json'
    raw, analysis, report = merge(read_json(raw_path), read_json(analysis_path), incoming)
    # Keep a recovery copy. If building fails, restore both source files.
    original_raw, original_analysis = raw_path.read_bytes(), analysis_path.read_bytes()
    backup = root / 'local/music-atlas/import-backups'
    backup.mkdir(parents=True, exist_ok=True)
    import time
    stamp = str(time.time_ns())
    (backup / f'{stamp}-music.json').write_bytes(original_raw)
    (backup / f'{stamp}-analysis.json').write_bytes(original_analysis)
    try:
        raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        build(root)
    except Exception:
        raw_path.write_bytes(original_raw)
        analysis_path.write_bytes(original_analysis)
        build(root)
        raise
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, nargs='?', help='NetEase JSON export')
    parser.add_argument('--playlist-id', type=int, help='Read public playlist metadata instead of a JSON file')
    parser.add_argument('--apply', action='store_true', help='Write sources and rebuild; default is a dry run')
    args = parser.parse_args()
    if bool(args.input) == bool(args.playlist_id):
        parser.error('Provide either an input JSON file or --playlist-id')
    incoming = fetch_playlist(args.playlist_id) if args.playlist_id else read_json(args.input)
    if args.apply:
        report = apply_import(incoming)
    else:
        _, _, report = merge(read_json(ROOT / '_data/music.json'), read_json(ROOT / '_data/music_atlas.json'), incoming)
    print(json.dumps(report, ensure_ascii=False, indent=2))
