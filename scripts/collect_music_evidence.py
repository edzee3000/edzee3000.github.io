"""Cache public NetEase evidence and measure two audio excerpts per track.

No cookies, authentication or access-control bypass. Missing/denied audio stays
missing. Copyrighted lyrics and audio are never published in the web assets.
Audio exists only in memory during measurement; private raw API caches live in
ignored local/. Public output contains derived features, hashes and provenance.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request

os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import numpy as np
from scipy.signal import stft

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'local/music-atlas/evidence'
PUBLIC = ROOT / '_data/music_evidence.json'
VERSION = 1


def api(path, query):
    req = urllib.request.Request('https://music.163.com' + path + '?' + urllib.parse.urlencode(query),
        headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://music.163.com/'})
    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.load(response)
    if data.get('code') != 200:
        raise ValueError(f'API code {data.get("code")}')
    return data


def cache_api(kind, ident, path, query):
    target = CACHE / kind / f'{ident}.json'
    if target.exists():
        return json.loads(target.read_text(encoding='utf8'))
    data = api(path, query)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
    return data


def lyric_lines(data):
    text = data.get('lrc', {}).get('lyric', '')
    lines = []
    credit = re.compile(r'^(作[词曲]|编曲|制作|录音|混音|母带|词\s*[:：]|曲\s*[:：]|Written|Composer|Lyricist|Producer|Arrangement|Mixing|Mastering|Vocals|Guitar|Bass|Drums|版权所有|未经|发行|出品|统筹|策划|监制|[Bb][Yy][:：])', re.I)
    for line in text.splitlines():
        clean = re.sub(r'\[[^\]]*\]', '', line).strip()
        if clean and not credit.match(clean) and not re.search(r'纯音乐|请欣赏|暂无歌词|无歌词', clean):
            lines.append(clean)
    return lines


THEMES = {
    '距离与离别': ['离开', '离去', '离别', '再见', '远方', '分开', '告别', 'goodbye', 'farewell', 'leave', 'leaving', 'far away', 'apart'],
    '夜色与梦境': ['黑夜', '夜晚', '月光', '梦', 'night', 'dream', 'moon'],
    '回忆与时间': ['回忆', '记忆', '昨天', '从前', '过去', '岁月', 'remember', 'memory', 'memories', 'yesterday', 'past', 'time'],
    '孤独与失落': ['孤独', '寂寞', '失落', '眼泪', '哭泣', '悲伤', 'alone', 'lonely', 'tears', 'cry', 'sad', 'lost'],
    '亲密与爱': ['爱', '拥抱', '亲吻', '温柔', 'love', 'kiss', 'hold me', 'heart'],
    '旅途与归处': ['故乡', '家乡', '路上', '流浪', '旅行', '归来', '回家', 'home', 'road', 'journey', 'travel'],
    '抵抗与自由': ['自由', '反抗', '挣脱', '牢笼', '愤怒', '挣扎', 'freedom', 'fight', 'prison', 'anger', 'rage'],
    '自然与天气': ['海', '雨', '风', '山', '河流', '太阳', '天空', 'sea', 'ocean', 'rain', 'wind', 'sun', 'sky', 'river'],
}


def lyric_summary(data):
    lines = lyric_lines(data)
    unique = list(dict.fromkeys(lines))
    text = '\n'.join(lines).lower()
    theme_matches = {}
    for theme, terms in THEMES.items():
        hits = []
        for term in terms:
            count = len(re.findall(r'(?<![a-z])' + re.escape(term) + r'(?![a-z])', text)) if term.isascii() else text.count(term)
            if count:
                hits.append((term, count))
        # A single broad word (e.g. 海, 爱, time) is not enough for a theme link.
        if len(hits) >= 2:
            theme_matches[theme] = {'distinctTerms': len(hits), 'occurrences': sum(n for _, n in hits)}
    han = len(re.findall(r'[\u4e00-\u9fff]', text))
    latin = len(re.findall(r'[a-z]', text))
    language = '中文' if han > latin / 3 else '英文或拉丁字母语言' if latin else '其他或无法识别'
    if re.search(r'[\u3040-\u30ff]', text):
        language = '日文'
    if re.search(r'[\u0400-\u04ff]', text):
        language = '西里尔字母语言'
    pure = bool(data.get('pureMusic'))
    return dict(status='instrumental-platform-label' if pure else 'available' if len(unique) >= 3 else 'insufficient',
        language=language if lines and not pure else None, lineCount=len(lines), uniqueLineCount=len(unique),
        repetition=round(1 - len(unique) / len(lines), 3) if lines else None,
        themes=theme_matches, sha256=hashlib.sha256(data.get('lrc', {}).get('lyric', '').encode()).hexdigest(),
        source='https://music.163.com/song?id=' + str(data.get('_song_id', '')),
        method='关键词共现；不等同于情绪分类或完整歌词解读')


def measure_pcm(pcm, sr=16000):
    y = np.frombuffer(pcm, dtype='<f4').astype(np.float64)
    if len(y) < sr * 8 or not np.isfinite(y).all():
        raise ValueError('Audio segment too short or invalid')
    freq, times, z = stft(y, fs=sr, nperseg=1024, noverlap=768, boundary=None)
    mag = np.abs(z)
    power = mag ** 2
    sums = mag.sum(axis=0) + 1e-12
    centroid = (freq[:, None] * mag).sum(axis=0) / sums
    bandwidth = np.sqrt((((freq[:, None] - centroid) ** 2) * mag).sum(axis=0) / sums)
    flatness = np.exp(np.log(power + 1e-12).mean(axis=0)) / (power.mean(axis=0) + 1e-12)
    frame_energy = np.sqrt(power.sum(axis=0))
    db = 20 * np.log10(frame_energy + 1e-9)
    low_ratio = power[freq < 250].sum(axis=0) / (power.sum(axis=0) + 1e-12)
    high_ratio = power[freq > 3000].sum(axis=0) / (power.sum(axis=0) + 1e-12)
    norm = mag / sums
    flux = np.maximum(0, np.diff(norm, axis=1)).sum(axis=0)
    # Band energy proportions describe coarse timbre; no chord/key inference.
    band_edges = [0, 125, 250, 500, 1000, 2000, 4000, 8001]
    bands = [float(power[(freq >= a) & (freq < b)].sum() / (power.sum() + 1e-12))
             for a, b in zip(band_edges, band_edges[1:])]
    return dict(seconds=round(len(y) / sr, 2), centroidHz=round(float(np.median(centroid)), 1),
        bandwidthHz=round(float(np.median(bandwidth)), 1), flatness=round(float(np.median(flatness)), 6),
        lowRatio=round(float(np.median(low_ratio)), 5), highRatio=round(float(np.median(high_ratio)), 5),
        dynamicSpreadDb=round(float(np.percentile(db, 90) - np.percentile(db, 10)), 2),
        flux=round(float(np.median(flux)), 5), rms=round(float(np.sqrt(np.mean(y ** 2))), 6), bands=bands)


def measure_audio(ident):
    existing = CACHE / 'audio' / f'{ident}.json'
    if existing.exists():
        result = json.loads(existing.read_text(encoding='utf8'))
        if result.get('version') == VERSION:
            return result
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise ValueError('ffmpeg unavailable')
    data = api('/api/song/enhance/player/url', {'ids': json.dumps([ident]), 'br': 128000})
    entry = next((x for x in data.get('data', []) if x.get('id') == ident), {})
    if not entry.get('url') or entry.get('code') != 200:
        result = dict(version=VERSION, status='unavailable', reason='公开接口没有返回可播放音频')
    elif entry.get('freeTrialInfo'):
        result = dict(version=VERSION, status='unavailable', reason='仅有试听片段，无法按统一位置取样')
    elif entry.get('type') != 'mp3' or not entry.get('size'):
        result = dict(version=VERSION, status='unavailable', reason='公开音频不支持此取样格式')
    else:
        url = entry['url'].replace('http:', 'https:', 1)
        size, bitrate = entry['size'], entry.get('br') or 128000
        length = min(int(bitrate / 8 * 20), int(size * .19))
        segments, hashes = [], []
        for fraction in [.25, .65]:
            start = int(size * fraction)
            req = urllib.request.Request(url, headers={'Range': f'bytes={start}-{start + length - 1}', 'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status != 206:
                    raise ValueError('Server did not honor bounded range request')
                content_range = response.headers.get('Content-Range', '')
                if not content_range.startswith(f'bytes {start}-'):
                    raise ValueError('Unexpected range response')
                mp3 = response.read(length)
            hashes.append(hashlib.sha256(mp3).hexdigest())
            decoded = subprocess.run([ffmpeg, '-v', 'error', '-threads', '1', '-f', 'mp3', '-i', 'pipe:0',
                '-ac', '1', '-ar', '16000', '-f', 'f32le', 'pipe:1'], input=mp3,
                capture_output=True, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if decoded.returncode:
                raise ValueError('Audio excerpt decoding failed')
            features = measure_pcm(decoded.stdout)
            features['byteFraction'] = fraction
            segments.append(features)
        aggregate = {key: round(float(np.mean([s[key] for s in segments])), 6)
            for key in ['centroidHz', 'bandwidthHz', 'flatness', 'lowRatio', 'highRatio', 'dynamicSpreadDb', 'flux', 'rms']}
        aggregate['bands'] = np.mean([s['bands'] for s in segments], axis=0).tolist()
        result = dict(version=VERSION, status='measured', segments=segments, features=aggregate,
            sampledSeconds=round(sum(s['seconds'] for s in segments), 2), sha256=hashes,
            source=f'https://music.163.com/song?id={ident}',
            method='两个 MP3 字节位置 25%/65% 附近约 20 秒片段；单声道 16 kHz STFT；不代表全曲结构或试听解读')
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text(json.dumps(result, ensure_ascii=False), encoding='utf8')
    return result


def collect_song(song):
    ident = song['id']
    evidence = {'id': ident}
    try:
        lyrics = cache_api('lyrics', ident, '/api/song/lyric', {'id': ident, 'lv': -1, 'kv': -1, 'tv': -1})
        lyrics['_song_id'] = ident
        evidence['lyrics'] = lyric_summary(lyrics)
    except Exception as exc:
        evidence['lyrics'] = dict(status='unavailable', reason=str(exc))
    try:
        evidence['audio'] = measure_audio(ident)
    except Exception as exc:
        evidence['audio'] = dict(version=VERSION, status='error', reason=str(exc))
    return evidence


def main(limit=None, workers=4):
    raw = json.loads((ROOT / '_data/music.json').read_text(encoding='utf8'))
    CACHE.mkdir(parents=True, exist_ok=True)
    playlist = cache_api('playlist', 8114560070, '/api/v6/playlist/detail', {'id': 8114560070})['playlist']
    remote = [x['id'] for x in playlist['trackIds']]
    local = {s['id'] for s in raw}
    reconciliation = dict(advertisedCount=playlist.get('trackCount'), accessibleCount=len(remote),
        missingLocally=sorted(set(remote) - local), absentRemotely=sorted(local - set(remote)),
        source='https://music.163.com/playlist?id=8114560070')
    print('Playlist reconciliation:', json.dumps(reconciliation), flush=True)
    by_id = {}
    if PUBLIC.exists():
        by_id = {x['id']: x for x in json.loads(PUBLIC.read_text(encoding='utf8')).get('tracks', [])}
    selected = raw[:limit] if limit else raw
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(collect_song, s): s['id'] for s in selected}
        for completed, future in enumerate(as_completed(futures), 1):
            result = future.result()
            by_id[result['id']] = result
            if completed % 20 == 0 or completed == len(selected):
                output = dict(version=VERSION, collectedAt=datetime.now(timezone.utc).isoformat(),
                    reconciliation=reconciliation, tracks=[by_id[i] for i in sorted(by_id)])
                PUBLIC.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
                statuses = {s: sum(v.get('audio', {}).get('status') == s for v in by_id.values()) for s in ['measured', 'unavailable', 'error']}
                print(f'{completed}/{len(selected)} in {time.monotonic()-started:.0f}s: {statuses}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    main(args.limit, args.workers)
