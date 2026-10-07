"""Evidence-limited, reproducible per-track analysis and conservative links.

Audio descriptors are excerpt measurements, not genre/emotion/structure claims.
Lyrics are keyword co-occurrences, not human listening conclusions. Keep these
categories distinct in output and never invent measurements for missing audio.
"""
from collections import Counter, defaultdict
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
from scipy.spatial.distance import cdist

FEATURES = ['centroidHz', 'bandwidthHz', 'flatness', 'lowRatio', 'highRatio', 'dynamicSpreadDb', 'flux']
FEATURE_NAMES = dict(centroidHz='频谱重心', bandwidthHz='频谱宽度', flatness='频谱平坦度',
    lowRatio='低频占比', highRatio='高频占比', dynamicSpreadDb='片段响度起伏', flux='频谱变化')
COLORS = ['#aabf9b', '#aaa0c6', '#c6bb88', '#c39a82', '#95b9b7', '#b5a2a0', '#b8a478', '#8caaa4']


def feature_vector(features):
    # Log transforms for skewed quantities; coarse band energies are redundant
    # with low/high ratios and deliberately excluded from distance calculations.
    return np.array([np.log1p(features['centroidHz']), np.log1p(features['bandwidthHz']),
        np.log(max(1e-7, features['flatness'])), features['lowRatio'], features['highRatio'],
        features['dynamicSpreadDb'], features['flux']], dtype=float)


def analyze(raw, annotations, evidence):
    raw = sorted(raw, key=lambda s: s['id'])
    by_id = {s['id']: s for s in raw}
    records = {s['id']: s for s in evidence.get('tracks', []) if s['id'] in by_id}
    measured_ids = sorted(i for i, s in records.items() if s.get('audio', {}).get('status') == 'measured')
    old_nodes = {n['id']: n for n in annotations['nodes']}
    vectors = np.array([feature_vector(records[i]['audio']['features']) for i in measured_ids])
    bounds = np.percentile(vectors, [1, 99], axis=0) if len(vectors) else np.array([np.zeros(7), np.ones(7)])
    fitted = np.clip(vectors, bounds[0], bounds[1]) if len(vectors) else vectors
    mean = fitted.mean(axis=0) if len(vectors) else np.zeros(7)
    scale = fitted.std(axis=0) if len(vectors) else np.ones(7)
    scale[scale < 1e-8] = 1
    standardized = np.clip((fitted - mean) / scale, -3, 3) if len(vectors) else vectors
    nodes = []
    for song in raw:
        ident = song['id']
        rec = records.get(ident, {})
        audio, lyrics = rec.get('audio', {}), rec.get('lyrics', {})
        authors = ' / '.join(a['name'] for a in song['artists'])
        duration = song.get('duration', 0)
        minutes, seconds = divmod(round(duration / 1000), 60)
        track_number = song.get('no')
        fact = f'《{song["name"]}》由 {authors} 署名，收录于《{song["album"]["name"]}》，时长 {minutes}:{seconds:02d}。'
        if track_number:
            fact += f'平台记录为第 {track_number} 轨。'
        tags, paragraphs, dimensions = [], [], {}
        if audio.get('status') == 'measured':
            f = audio['features']
            rank_index = measured_ids.index(ident)
            z = standardized[rank_index]
            if z[0] > .6:
                tags.append('频谱重心偏高')
                paragraphs.append(f'采样频谱重心约 {f["centroidHz"]:.0f} Hz，在这份收藏中偏高，片段的能量分布更靠近高频端。')
            elif z[0] < -.6:
                tags.append('频谱重心偏低')
                paragraphs.append(f'采样频谱重心约 {f["centroidHz"]:.0f} Hz，在这份收藏中偏低，片段的能量分布更靠近低频端。')
            else:
                tags.append('频谱重心居中')
                paragraphs.append(f'采样频谱重心约 {f["centroidHz"]:.0f} Hz，位于这份收藏的中间范围。')
            if z[3] > .6:
                tags.append('低频占比偏高')
            if z[2] > .6:
                tags.append('频谱较平坦')
            if z[5] > .6:
                tags.append('片段起伏明显')
            elif z[5] < -.6:
                tags.append('片段起伏较小')
            paragraphs.append(f'低于 250 Hz 的能量占比约 {f["lowRatio"]*100:.1f}%，片段帧能量的 P90−P10 差约 {f["dynamicSpreadDb"]:.1f} dB。两段合计测得 {audio["sampledSeconds"]:.1f} 秒；这些数据不能据此确认配器、整曲高潮、拍号或情绪。')
            dimensions = {FEATURE_NAMES[name]: dict(value=f[name], relativeZ=round(float(z[j]), 3)) for j, name in enumerate(FEATURES)}
        else:
            tags.append('音频未测得')
            paragraphs.append('公开接口未能提供可按统一方法测量的音频。保留歌曲、发行和歌词资料，不为它生成声学相似连线，也不猜测其音色或结构。')
        themes = lyrics.get('themes', {})
        if lyrics.get('status') == 'instrumental-platform-label':
            tags.append('平台标为纯音乐')
            paragraphs.append('平台将这首歌标为纯音乐；这一标签没有经过人声分离或完整试听复核，因此不把“没有返回歌词”当成人声不存在的证明。')
        elif lyrics.get('status') == 'available':
            tags.append(lyrics['language'])
            repetition = lyrics.get('repetition', 0)
            if themes:
                strongest = sorted(themes, key=lambda t: (-themes[t]['distinctTerms'], -themes[t]['occurrences'], t))[:3]
                tags.extend(strongest)
                paragraphs.append('歌词中检出与' + '、'.join(strongest) + '相关的词语共现，可作为文本探索入口；这属于词汇层面的线索，不直接判定作者意图或听感情绪。')
            else:
                paragraphs.append('已取得歌词文本，但预定义主题词未形成足够共现，不强行归入悲伤、治愈等情绪。')
            paragraphs.append(f'去除平台时间戳和常见制作署名后记录 {lyrics["lineCount"]} 行、{lyrics["uniqueLineCount"]} 个不同文本行；完全重复行占比约 {repetition*100:.0f}%。这仅描述平台歌词文本，不能代替歌曲段落分析。')
        else:
            tags.append('歌词资料不足')
            paragraphs.append('未取得足够歌词文本，无法据此分析主题；缺少歌词也不证明是器乐曲。')
        old = old_nodes.get(ident)
        sources = [dict(title='网易云 · 歌曲与发行资料', url=f'https://music.163.com/song?id={ident}')]
        if old:
            sources.extend(copy.deepcopy(old.get('sources', [])))
        node = dict(id=ident, group='unclassified', tags=list(dict.fromkeys(tags)),
            status='excerpt-measured' if audio.get('status') == 'measured' else 'evidence-limited',
            fact=fact, note='\n\n'.join(paragraphs), sources=sources,
            evidence=dict(audioStatus=audio.get('status', 'not-collected'), lyricStatus=lyrics.get('status', 'not-collected'),
                sampledSeconds=audio.get('sampledSeconds', 0), dimensions=dimensions,
                audioHashes=audio.get('sha256', []), lyricHash=lyrics.get('sha256'), themes=themes),
            artistIds=[a['id'] for a in song['artists'] if a.get('id')])
        if old:
            node['editorial'] = dict(fact=old.get('fact'), listeningQuestion=old.get('note'), status='prior-sample-unverified')
        nodes.append(node)
    edges, edge_keys = [], set()

    def add(a, b, kind, status, reason, **extra):
        a, b = sorted([a, b])
        key = (a, b, kind)
        if a == b or key in edge_keys:
            return
        edge_keys.add(key)
        edges.append(dict(id=f'{kind}-{a}-{b}', source=a, target=b, kind=kind, status=status, reason=reason, **extra))

    # Identity relations are separate layers, never interpreted as sound likeness.
    for kind, key in [('album', lambda s: [s['album']['id']] if s['album']['id'] else []),
                       ('artist', lambda s: [a['id'] for a in s['artists'] if a.get('id')])]:
        buckets = defaultdict(list)
        for song in raw:
            for value in key(song):
                buckets[value].append(song['id'])
        for value, members in sorted(buckets.items()):
            members.sort()
            for index, a in enumerate(members):
                for b in members[index + 1:index + 3]:
                    if kind == 'album':
                        reason = f'两首歌的专辑 ID 均为 {value}，同收录于《{by_id[a]["album"]["name"]}》。这是发行关系，不证明音色或心情相似。'
                    else:
                        name = next(x['name'] for x in by_id[a]['artists'] if x['id'] == value)
                        reason = f'两首歌都由 {name} 署名（艺人 ID {value}）。这是署名关系，不假定同艺人的每首歌有相同听感。'
                    add(a, b, kind, 'verified', reason, provenance=f'netease-{kind}-id:{value}', weight=.8 if kind == 'album' else .55)
    if len(measured_ids) > 1:
        distances = cdist(standardized, standardized) / np.sqrt(len(FEATURES))
        np.fill_diagonal(distances, np.inf)
        neighbors = np.argsort(distances, axis=1, kind='stable')[:, :4]
        # Mutual nearest neighbors plus a global upper bound prevent obligatory
        # links to distant outliers. No inferred acoustic edges for missing tracks.
        for i, near in enumerate(neighbors):
            for j in near:
                if i >= j or i not in neighbors[j] or distances[i, j] > .9:
                    continue
                a, b = measured_ids[i], measured_ids[j]
                difference = np.abs(standardized[i] - standardized[j])
                closest = np.argsort(difference)[:3]
                evidence_names = '、'.join(FEATURE_NAMES[FEATURES[t]] for t in closest)
                reason = f'在可测音频中互为四个最近邻之一。两首歌分别取两个约 20 秒片段，七维声学特征标准化后的均方根距离为 {distances[i,j]:.3f}，其中{evidence_names}较接近。仅证明所取片段的数值特征接近；不证明流派、旋律、和声或情绪相同。'
                add(a, b, 'sound', 'measured', reason, distance=round(float(distances[i, j]), 4),
            method='mutual-4nn-winsorized-standardized-7-features', weight=float(1 / (1 + distances[i, j])))
    # Text links need at least TWO shared themes, each already requiring two
    # distinct words. Cap two links per node to avoid generic love/night hairballs.
    text_counts = Counter()
    lyric_ids = sorted(i for i, r in records.items() if r.get('lyrics', {}).get('status') == 'available')
    candidates = []
    for index, a in enumerate(lyric_ids):
        a_themes = records[a]['lyrics'].get('themes', {})
        for b in lyric_ids[index + 1:]:
            common = sorted(a_themes.keys() & records[b]['lyrics'].get('themes', {}).keys())
            if len(common) >= 2:
                union = set(a_themes) | set(records[b]['lyrics']['themes'])
                candidates.append((-len(common) / len(union), a, b, common))
    for score, a, b, common in sorted(candidates):
        if text_counts[a] >= 2 or text_counts[b] >= 2:
            continue
        add(a, b, 'lyrics', 'candidate', '两首歌的歌词均检出' + '、'.join(common) + '相关词语，每个主题至少涉及两个不同词语。这是关键词共现得到的文本候选关系；未核实语境、隐喻、否定关系或听感情绪。',
            themes=common, method='two-shared-keyword-themes', weight=.3)
        text_counts[a] += 1
        text_counts[b] += 1
    # Editorial interpretation leads the page. Acoustic measurements remain a
    # separate optional layer; they must not dictate the musical neighborhoods.
    editorial_groups = copy.deepcopy(annotations['groups'])
    editorial_centers = [[920, 660], [2400, 560], [1750, 1230], [810, 1850], [2640, 1900], [3050, 1080]]
    for group, center in zip(editorial_groups, editorial_centers):
        group['center'] = center
        group['basis'] = '样稿编辑探索分区；未完成逐首试听，不是自动测量分类'
    editorial_groups.append(dict(id='unclassified', name='待逐首解读', english='STILL TO LISTEN',
        color='#8c978d', center=[1750, 1300], background=True,
        basis='未完成编辑解读；在关系图中按发行与署名连接分布，不赋予虚构音乐风格'))
    for node in nodes:
        original = old_nodes.get(node['id'])
        node['measurementNote'] = node['note']
        node['editorialStatus'] = 'sample-listening-question' if original else 'pending'
        if original:
            node['group'] = original['group']
            node['note'] = original['note']
            node['fact'] += '\n\n' + original.get('fact', '')
            node['tags'] = copy.deepcopy(original['tags'])
        else:
            node['group'] = 'unclassified'
            themes = node['evidence']['themes']
            node['tags'] = ['待逐首解读'] + list(themes)[:2]
            node['note'] = '这首歌已接入完整收藏，但尚未完成逐首音乐解读。'
            if themes:
                node['note'] += '已取得的歌词包含' + '、'.join(list(themes)[:3]) + '相关词汇线索，仍需结合完整语境和音乐核验。'
            node['note'] += '音频测量与文本统计可在下方资料中查看，不替代编辑解读。'
    for edge in edges:
        if edge['kind'] == 'sound' and edge['status'] == 'measured':
            edge['kind'] = 'acoustic'
            edge['id'] = edge['id'].replace('sound-', 'acoustic-', 1)
    for original in annotations['edges']:
        if original['kind'] != 'album':
            preserved = copy.deepcopy(original)
            preserved['id'] = 'editorial-' + preserved.get('id', f'{preserved["source"]}-{preserved["target"]}')
            preserved['status'] = 'candidate'
            edges.append(preserved)
    counts = Counter(r.get('audio', {}).get('status', 'not-collected') for r in records.values())
    coverage = dict(total=len(raw), audioMeasured=counts['measured'], audioUnavailable=len(raw)-counts['measured'],
        lyricsAvailable=sum(r.get('lyrics', {}).get('status') == 'available' for r in records.values()),
        platformInstrumental=sum(r.get('lyrics', {}).get('status') == 'instrumental-platform-label' for r in records.values()),
        fullTrackListeningReviewed=0, editorialQuestions=len(old_nodes), relations=dict(Counter(e['kind'] for e in edges)))
    return dict(version=3, stage='full-catalog-editorial-incomplete', analysisStatus='excerpt-measurements-and-text-cues',
        nodes=nodes, edges=sorted(edges, key=lambda e: (e['source'], e['target'], e['kind'])), groups=editorial_groups,
        featured=[i for i in annotations.get('featured', []) if i in by_id],
        coverage=coverage, collectedAt=evidence.get('collectedAt'), reconciliation=evidence.get('reconciliation'),
        analysisMethod=dict(features=FEATURES, normalization='log transforms; 1/99 percentile winsorization; population z-score; clip to +/-3',
            transformMean=mean.tolist(), transformScale=scale.tolist(), winsorBounds=bounds.tolist(),
            neighbors=4, maxRmsDistance=.9, editorialRegions=len(annotations['groups']), seed=811456,
            limitations='未完成全曲逐首试听；片段测量、歌词共现和发行事实分别呈现，不编造情绪、结构或配器。'))
