"""Extract contextual genre terms from public artist profiles, not track audio.

Raw biographies stay in ignored local/. Do not transfer an artist-wide label to
an individual track as a confirmed genre, or infer instruments from biographies.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import re
from collect_music_evidence import ROOT, cache_api

GENRES = {
    '后摇': r'后摇|post[ -]?rock', '数学摇滚': r'数学摇滚|数摇|math[ -]?rock',
    '情绪摇滚': r'情绪摇滚|\bemo\b', '盯鞋': r'盯鞋|自赏|shoegaz',
    '梦幻流行': r'梦幻流行|dream[ -]?pop', '后朋克': r'后朋克|post[ -]?punk',
    '朋克': r'朋克|\bpunk\b', '金属': r'金属|\bmetal\b', '民谣': r'民谣|\bfolk\b',
    '爵士': r'爵士|\bjazz\b', '电子': r'电子|\belectronic\b|\btechno\b',
    '独立摇滚': r'独立摇滚|indie[ -]?rock', '独立流行': r'独立流行|indie[ -]?pop',
    '氛围': r'氛围|\bambient\b', '摇滚': r'摇滚|\brock\b',
    '布鲁斯': r'布鲁斯|\bblues\b', '放克': r'放克|\bfunk\b',
    '嘻哈': r'嘻哈|hip[ -]?hop|说唱|\brap\b', '灵魂乐': r'灵魂乐|\bsoul\b',
}


def collect(artist):
    ident = artist['id']
    try:
        data = cache_api('artists', ident, '/api/artist/introduction', {'id': ident})
        text = data.get('briefDesc') or ''
        # Restrict to the short profile rather than matching historical sections
        # that often discuss other bands and collaborations.
        tags = [name for name, pattern in GENRES.items() if re.search(pattern, text, re.I)]
        if '后朋克' in tags and '朋克' in tags:
            tags.remove('朋克')
        if len(tags) > 1 and '摇滚' in tags:
            tags.remove('摇滚')
        return dict(id=ident, name=artist['name'], terms=tags,
            source=f'https://music.163.com/artist/desc?id={ident}', status='profile-terms' if tags else 'no-specific-terms',
            scope='平台艺人简介中的风格词，不保证此曲属于该流派；简介中的其他艺人或否定语境可能造成误检')
    except Exception as exc:
        return dict(id=ident, name=artist['name'], terms=[], status='unavailable', reason=str(exc))


if __name__ == '__main__':
    raw = json.loads((ROOT / '_data/music.json').read_text(encoding='utf8'))
    artists = {a['id']: a for song in raw for a in song['artists'] if a.get('id')}
    with ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(collect, [artists[i] for i in sorted(artists)]))
    (ROOT / '_data/music_artist_context.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(f'{len(result)} artist profiles; {sum(bool(a["terms"]) for a in result)} with genre terms')
