"""Build the catalog, artwork palette and graph from ID-keyed source data.

Song metadata: _data/music.json. Editorial annotations: _data/music_atlas.json.
Only album co-membership is generated automatically; similarity requires an
explicit editorial edge. No audio or lyric interpretations are inferred here.
"""
import argparse
import copy
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate(raw, annotations):
    ids = [song['id'] for song in raw]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate song IDs in playlist')
    if any(type(i) is not int or i <= 0 for i in ids):
        raise ValueError('Song IDs must be positive integers')
    for song in raw:
        if not song.get('name') or not song.get('artists') or 'album' not in song:
            raise ValueError(f'Incomplete song metadata: {song["id"]}')
    nodes = annotations['nodes']
    node_ids = [node['id'] for node in nodes]
    group_ids = [group['id'] for group in annotations['groups']]
    if len(node_ids) != len(set(node_ids)) or len(group_ids) != len(set(group_ids)):
        raise ValueError('Duplicate node or group IDs')
    if not set(node_ids).issubset(ids):
        raise ValueError('Editorial annotations reference missing songs')
    if any(node['group'] not in group_ids for node in nodes):
        raise ValueError('Node references a missing group')
    seen = set()
    for edge in annotations['edges']:
        a, b = edge['source'], edge['target']
        key = (*sorted((a, b)), edge['kind'])
        if a == b or a not in node_ids or b not in node_ids or key in seen:
            raise ValueError(f'Invalid or duplicate edge: {key}')
        if edge['kind'] not in ['style', 'album', 'artist', 'lyrics', 'acoustic', 'sound', 'emotion', 'structure']:
            raise ValueError('Unknown relation type')
        if edge['status'] not in ['verified', 'measured', 'candidate'] or not edge.get('reason'):
            raise ValueError('Edges require status and explanation')
        seen.add(key)
    if not set(annotations.get('featured', [])).issubset(node_ids):
        raise ValueError('Featured song is not in the graph')


def edge_color(image):
    """Dominant perimeter color, using the outer 8% of all four sides."""
    small = image.convert('RGB').resize((64, 64), Image.Resampling.LANCZOS)
    pixels = [small.getpixel((x, y)) for y in range(64) for x in range(64)
              if x < 5 or x >= 59 or y < 5 or y >= 59]
    strip = Image.new('RGB', (len(pixels), 1))
    strip.putdata(pixels)
    quantized = strip.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    dominant = max(quantized.getcolors(), key=lambda item: item[0])[1]
    palette = quantized.getpalette()
    rgb = palette[dominant * 3:dominant * 3 + 3]
    return '#' + ''.join(f'{value:02x}' for value in rgb)


def page_rank(ids, edges, damping=.85):
    """Equal-weight undirected PageRank, including explicitly candidate edges."""
    ids = sorted(ids)
    if not ids:
        return {}
    adjacency = {i: set() for i in ids}
    for edge in edges:
        adjacency[edge['source']].add(edge['target'])
        adjacency[edge['target']].add(edge['source'])
    n = len(ids)
    scores = dict.fromkeys(ids, 1 / n)
    for _ in range(200):
        dangling = sum(scores[i] for i in ids if not adjacency[i])
        updated = dict.fromkeys(ids, (1 - damping + damping * dangling) / n)
        for i in ids:
            if adjacency[i]:
                share = damping * scores[i] / len(adjacency[i])
                for target in sorted(adjacency[i]):
                    updated[target] += share
        delta = sum(abs(updated[i] - scores[i]) for i in ids)
        scores = updated
        if delta < 1e-12:
            break
    order = sorted(ids, key=lambda i: (-scores[i], i))
    return {i: dict(pageRank=scores[i], rank=order.index(i) + 1,
                    degree=len(adjacency[i])) for i in ids}


def build(root=ROOT, output=None):
    root = Path(root)
    out = Path(output) if output else root / 'assets/music'
    raw = read_json(root / '_data/music.json')
    annotations = read_json(root / '_data/music_atlas.json')
    validate(raw, annotations)
    evidence_path = root / '_data/music_evidence.json'
    full_library = evidence_path.exists()
    if full_library:
        from analyze_music_library import analyze
        annotations = analyze(raw, annotations, read_json(evidence_path))
        validate(raw, annotations)
    out.mkdir(parents=True, exist_ok=True)
    media_path=root / '_data/music_artwork.json'
    media=read_json(media_path) if media_path.exists() else {}
    assets=media.get('assets',{})
    existing_path = root / 'assets/music/catalog.json'
    existing = {s['id']: s for s in read_json(existing_path)} if existing_path.exists() else {}
    def hosted(path):
        return f"https://huggingface.co/datasets/{media['repo']}/resolve/{media['revision']}/{path}"
    catalog = []
    for position, song in enumerate(raw, 1):
        source_url = song['album'].get('picUrl', '')
        asset=assets.get(source_url)
        previous=existing.get(song['id'],{})
        color=previous.get('coverEdgeColor','#9ca690') if previous.get('coverSource')==source_url else '#9ca690'
        if asset:
            cover=hosted(asset['preview']);small=hosted(asset['small']);original=hosted(asset['original'])
            color=asset['edgeColor']
        elif source_url:
            # New covers remain external until their original is archived/uploaded.
            # The build never creates image files in the GitHub source tree.
            separator='&' if '?' in source_url else '?'
            cover=source_url+separator+'param=512y512';small=source_url+separator+'param=64y64';original=source_url
        else:
            cover=small=original='cover-fallback.svg'
        catalog.append(dict(id=song['id'], name=song['name'],
                            artists=' / '.join(a['name'] for a in song['artists']),
                            album=song['album']['name'], albumId=song['album']['id'],
                            cover=cover, coverSource=source_url, coverEdgeColor=color,
                            coverSmall=small, coverOriginal=original,
                            position=position, duration=song.get('duration', 0)))
    by_id = {song['id']: song for song in catalog}
    network = copy.deepcopy(annotations)
    style_path=root / '_data/music_style_sources.json'
    if full_library and style_path.exists():
        from music_styles import apply_styles
        override_path=root / '_data/music_style_overrides.json'
        style_overrides=read_json(override_path) if override_path.exists() else {}
        for source_file,source_title in [('music_wiki_style_sources.json','Wikipedia'),('music_yaogun_style_sources.json','Chinese Rock Database')]:
            wiki_path=root / '_data' / source_file
            if not wiki_path.exists():continue
            for name,profile in read_json(wiki_path).items():
                if profile.get('labels'):
                    style_overrides.setdefault('artists',{}).setdefault(name,[]).append(dict(
                        labels=profile['labels'],url=profile['source'],title=source_title+' · '+profile['matchedTitle']))
        apply_styles(network,raw,read_json(style_path),style_overrides)
    # Generated album links may change when new metadata arrives; preserve all
    # explicitly authored non-album links and never manufacture new similarity.
    edges = list(network['edges']) if full_library else [edge for edge in network['edges'] if edge['kind'] != 'album']
    keys = {tuple(sorted((e['source'], e['target']))) for e in edges}
    album_nodes = defaultdict(list)
    for node in ([] if full_library else network['nodes']):
        if by_id[node['id']]['albumId']:
            album_nodes[by_id[node['id']]['albumId']].append(node['id'])
    for album_id, members in sorted(album_nodes.items()):
        # ID ordering keeps links stable when the playlist is reordered.
        members.sort()
        for i, a in enumerate(members):
            for b in members[i + 1:i + 4]:
                key = (a, b)
                if key in keys:
                    continue
                keys.add(key)
                edges.append(dict(id=f'{a}-{b}', source=a, target=b, kind='album', status='verified',
                                  reason=f'两首歌的专辑 ID 相同，均收录于《{by_id[a]["album"]}》。这是发行关系，不自动证明声音或情绪相似。'))
    network['edges'] = sorted(edges, key=lambda e: (min(e['source'], e['target']), max(e['source'], e['target'])))
    scores = page_rank([n['id'] for n in network['nodes']], network['edges'])
    for node in network['nodes']:
        node['centrality'] = scores[node['id']]
    if full_library:
        for group in (g for g in network['groups'] if not g.get('background')):
            members = sorted((n for n in network['nodes'] if n['group'] == group['id']), key=lambda n: n['centrality']['rank'])
            network['featured'].extend(n['id'] for n in members[:2] if n['id'] not in network['featured'])
    network['sizing'] = dict(method='undirected-pagerank', damping=.85, minRadius=20 if full_library else 14, maxRadius=28 if full_library else 20,
                             includesCandidateEdges=True, note='当前关系网中的中心性，不表示播放量或个人偏好。')
    network['snapshot'] = dict(playlistId=8114560070, count=len(catalog))
    if full_library:
        from layout_music_atlas import precompute_layout
        precompute_layout(network)
        if network.get('styleView'):
            from layout_music_atlas import precompute_style_layout
            precompute_style_layout(network)
    validate(raw, network)
    for filename, data in [('catalog.json', catalog), ('network.json', network)]:
        (out / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{len(catalog)} tracks; {len(network["nodes"])} nodes; {len(edges)} edges. PageRank total: {sum(v["pageRank"] for v in scores.values()):.12f}')
    return catalog, network


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate source IDs and references without writing')
    args = parser.parse_args()
    if args.check:
        validate(read_json(ROOT / '_data/music.json'), read_json(ROOT / '_data/music_atlas.json'))
        print('Source validation passed.')
    else:
        build()
