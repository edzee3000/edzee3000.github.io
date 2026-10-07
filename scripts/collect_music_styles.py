"""Collect community genre tags with strict name matching and provenance.

MusicBrainz artist tags are contextual suggestions, never track-level facts.
Only positive-vote, recognized genre tags survive. Ambiguous matches stay pending.
One network request per second, cached under ignored local/.
"""
import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / 'local/music-atlas/style-sources'
ALIASES = {
 '法兹乐队 FAZI':'法兹', '腰乐队':'腰', '声音碎片乐队':'声音碎片', '九宝乐队':'Nine Treasures',
 '痛仰乐队':'痛仰', 'STOLEN秘密行动':'STOLEN', '南青乐队':'南青', '椿乐队':'椿',
 'YĪN YĪN':'Yin Yin', 'C.S.B.Q乐队':'C.S.B.Q', 'THE BOOTLEGS 靴腿':'The Bootlegs',
 '霜冻前夜乐队':'Frosty Eve', '郁乐队':'郁', '小雨乐队':'小雨', '木马Muma':'木马',
 '黑豹乐队':'黑豹', 'Sunken Boat 沉舟乐队':'沉舟', '橘子海 (Orange Ocean)':'Orange Ocean',
 '平人乐队CommonCitizens':'Common Citizens', '脆莓(Brickleberry)':'脆莓',
 '伍佰 & China Blue':'伍佰 & China Blue', '唐朝乐队':'唐朝', '棱镜乐队':'棱镜',
 '福禄寿FloruitShow':'福禄寿', 'DengeL（单舟）':'DengEL', '莉莉周她说 Lily Chou-Chou Lied':'莉莉周她说',
 '犬儒乐队':'犬儒', '声音玩具':'声音玩具', 'DeepMountains深山':'Deep Mountains',
 '当代电影大师':'當代電影大師', '陳嫺靜':'陳嫺靜', '虚极乐队':'虚极', '黑麒':'Black Kirin',
 '安达组合 Anda union':'Anda Union', '杭盖乐队':'杭盖', '高旗&超载乐队':'超载',
 '椅子乐团 The Chairs':'椅子樂團', '康姆士COM\'Z':'康姆士', '沉默演讲（Silent Speech）':'Silent Speech',
}


def normalize(name):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFKC', name).casefold())


def collect(name):
    query_name = ALIASES.get(name, name)
    target = CACHE / (hashlib.sha256(query_name.encode()).hexdigest()[:20] + '.json')
    if target.exists():
        data = json.loads(target.read_text(encoding='utf8'))
    else:
        query = 'artist:"' + query_name.replace('"', '') + '"'
        url = 'https://musicbrainz.org/ws/2/artist/?' + urllib.parse.urlencode({'query':query, 'fmt':'json', 'limit':10})
        req = urllib.request.Request(url, headers={'User-Agent':'PersonalMusicAtlas/1.0 (https://edzee3000.github.io/music/)'})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                data = json.load(response)
            target.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
        finally:
            time.sleep(1.05)
    matches = []
    valid_names = {normalize(name), normalize(query_name)}
    for artist in data.get('artists', []):
        names = {normalize(artist.get('name', '')), normalize(artist.get('sort-name', ''))}
        names.update(normalize(a['name']) for a in artist.get('aliases', []))
        if valid_names & names and artist.get('score', 0) >= 90:
            matches.append(artist)
    if len(matches) != 1:
        return dict(name=name, status='ambiguous' if matches else 'unmatched', tags=[])
    artist = matches[0]
    return dict(name=name, matchedName=artist['name'], mbid=artist['id'], status='artist-context',
        source='https://musicbrainz.org/artist/' + artist['id'] + '/tags',
        disambiguation=artist.get('disambiguation', ''),
        tags=[t for t in artist.get('tags', []) if t.get('count', 0) > 0],
        scope='MusicBrainz 社区艺人标签，推定到歌曲仅作探索，不是逐首确认')


if __name__ == '__main__':
    raw = json.loads((ROOT / '_data/music.json').read_text(encoding='utf8'))
    counts = {}
    for song in raw:
        for artist in song['artists']:
            counts[artist['name']] = counts.get(artist['name'], 0) + 1
    CACHE.mkdir(parents=True, exist_ok=True)
    path = ROOT / '_data/music_style_sources.json'
    result = json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
    for index, name in enumerate(sorted(counts, key=lambda n:(-counts[n],n)), 1):
        try:
            result[name] = collect(name)
        except Exception as exc:
            result[name] = dict(name=name, status='error', tags=[], error=str(exc))
        if index % 20 == 0 or index == len(counts):
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
            print(f'{index}/{len(counts)} artists; {sum(bool(a.get("tags")) for a in result.values())} tagged profiles', flush=True)
