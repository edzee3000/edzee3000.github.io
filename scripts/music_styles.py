"""Multi-label style navigation, with provenance and explicit context scope."""
from collections import Counter
import copy
import math

# id | Chinese display | English/source tag | parent IDs | visual family
DEFINITIONS = '''
rock|摇滚|rock||alternative
alternative-rock|另类摇滚|alternative rock|rock|alternative
indie|独立音乐|indie||alternative
indie-rock|独立摇滚|indie rock|rock,indie|alternative
indie-pop|独立流行|indie pop|pop,indie|pop
pop|流行|pop||pop
pop-rock|流行摇滚|pop rock|rock,pop|pop
art-rock|艺术摇滚|art rock|rock|progressive
experimental-rock|实验摇滚|experimental rock|rock|progressive
progressive-rock|前卫摇滚|progressive rock|rock|progressive
psychedelic-rock|迷幻摇滚|psychedelic rock|rock|progressive
psychedelic-pop|迷幻流行|psychedelic pop|pop|progressive
krautrock|德国实验摇滚|krautrock|experimental-rock|progressive
space-rock|太空摇滚|space rock|rock|progressive
post-rock|后摇 Post-Rock|post-rock|rock|postrock
math-rock|数学摇滚|math rock|rock|emo
emo|Emo 情绪摇滚|emo|rock|emo
midwest-emo|Midwest Emo|midwest emo|emo|emo
emo-pop|Emo Pop|emo pop|emo,pop|emo
screamo|Screamo|screamo|emo,hardcore-punk|emo
post-hardcore|后硬核|post-hardcore|rock|emo
shoegaze|盯鞋 Shoegaze|shoegaze|alternative-rock|haze
dream-pop|梦幻流行|dream pop|pop|haze
noise-pop|噪音流行|noise pop|pop|haze
noise-rock|噪音摇滚|noise rock|rock|alternative
slowcore|慢核|slowcore|indie-rock|haze
ambient|氛围音乐|ambient||haze
dark-ambient|暗氛围|dark ambient|ambient|haze
post-punk|后朋克|post-punk|rock|postpunk
new-wave|新浪潮|new wave|rock|postpunk
coldwave|冷潮|coldwave|post-punk|postpunk
darkwave|暗潮|darkwave|post-punk|postpunk
gothic-rock|哥特摇滚|gothic rock|post-punk|postpunk
synth-pop|合成器流行|synth-pop|pop,electronic|electronic
electropop|电子流行|electropop|pop,electronic|electronic
synthwave|合成器波|synthwave|electronic|electronic
electronic|电子音乐|electronic||electronic
electronica|Electronica|electronica|electronic|electronic
downtempo|缓拍|downtempo|electronic|electronic
trip-hop|Trip-Hop|trip hop|electronic|electronic
techno|Techno|techno|electronic|electronic
house|House|house|electronic|electronic
industrial|工业音乐|industrial||electronic
industrial-rock|工业摇滚|industrial rock|industrial,rock|postpunk
disco|Disco|disco||electronic
folk|民谣|folk||folk
folk-rock|民谣摇滚|folk rock|folk,rock|folk
indie-folk|独立民谣|indie folk|folk,indie|folk
contemporary-folk|当代民谣|contemporary folk|folk|folk
country|乡村|country||folk
country-rock|乡村摇滚|country rock|country,rock|folk
americana|Americana|americana|folk,country|folk
singer-songwriter|唱作人|singer-songwriter||folk
blues|布鲁斯|blues||classic
blues-rock|布鲁斯摇滚|blues rock|blues,rock|classic
classic-rock|经典摇滚|classic rock|rock|classic
hard-rock|硬摇滚|hard rock|rock|classic
southern-rock|南方摇滚|southern rock|rock|classic
glam-rock|华丽摇滚|glam rock|rock|classic
garage-rock|车库摇滚|garage rock|rock|alternative
grunge|Grunge 垃圾摇滚|grunge|alternative-rock|alternative
post-grunge|后 Grunge|post-grunge|alternative-rock|alternative
britpop|英伦流行 Britpop|britpop|alternative-rock,pop|alternative
british-rock|英伦摇滚|british rock|rock|alternative
punk|朋克|punk||punk
punk-rock|朋克摇滚|punk rock|punk,rock|punk
pop-punk|流行朋克|pop punk|punk-rock,pop|punk
hardcore-punk|硬核朋克|hardcore punk|punk|punk
post-punk-revival|后朋克复兴|post-punk revival|post-punk|postpunk
ska|Ska|ska||punk
ska-punk|Ska Punk|ska punk|ska,punk|punk
reggae|雷鬼|reggae||folk
metal|金属|metal||metal
heavy-metal|重金属|heavy metal|metal|metal
alternative-metal|另类金属|alternative metal|metal|metal
nu-metal|新金属|nu metal|alternative-metal|metal
rap-metal|说唱金属|rap metal|metal,hip-hop|metal
thrash-metal|鞭挞金属|thrash metal|metal|metal
speed-metal|速度金属|speed metal|metal|metal
death-metal|死亡金属|death metal|metal|metal
melodic-death-metal|旋律死亡金属|melodic death metal|death-metal|metal
black-metal|黑金属|black metal|metal|metal
atmospheric-black-metal|氛围黑金属|atmospheric black metal|black-metal|metal
depressive-black-metal|抑郁黑金属 DSBM|depressive black metal|black-metal|metal
post-black-metal|后黑金属|post-black metal|black-metal|metal
blackgaze|黑金盯鞋 Blackgaze|blackgaze|black-metal,shoegaze|haze
post-metal|后金属|post-metal|metal|metal
doom-metal|厄运金属|doom metal|metal|metal
sludge-metal|泥浆金属|sludge metal|metal|metal
folk-metal|民谣金属|folk metal|metal|metal
symphonic-metal|交响金属|symphonic metal|metal|metal
power-metal|力量金属|power metal|metal|metal
progressive-metal|前卫金属|progressive metal|metal|metal
gothic-metal|哥特金属|gothic metal|metal|metal
industrial-metal|工业金属|industrial metal|metal,industrial|metal
metalcore|金属核|metalcore|metal|metal
melodic-metalcore|旋律金属核|melodic metalcore|metalcore|metal
deathcore|死核|deathcore|metal|metal
jazz|爵士|jazz||jazz
jazz-fusion|融合爵士|jazz fusion|jazz|jazz
jazz-rock|爵士摇滚|jazz rock|jazz,rock|jazz
nu-jazz|新爵士|nu jazz|jazz,electronic|jazz
funk|放克|funk||jazz
funk-rock|放克摇滚|funk rock|funk,rock|jazz
soul|灵魂乐|soul||soul
neo-soul|新灵魂乐|neo soul|soul,rnb|soul
rnb|R&B|r&b||soul
alternative-rnb|另类 R&B|alternative r&b|rnb|soul
rhythm-and-blues|节奏布鲁斯|rhythm and blues|rnb|soul
hip-hop|Hip-Hop 嘻哈|hip hop||soul
rap-rock|说唱摇滚|rap rock|hip-hop,rock|alternative
classical|古典|classical||ambient
modern-classical|现代古典|modern classical|classical|ambient
neoclassical|新古典|neoclassical|classical|ambient
soundtrack|原声音乐|soundtrack||ambient
experimental|实验音乐|experimental||ambient
avant-garde|先锋音乐|avant-garde|experimental|ambient
world|世界音乐|world||folk
world-fusion|世界融合|world fusion|world|folk
art-pop|艺术流行|art pop|pop|progressive
baroque-pop|巴洛克流行|baroque pop|pop|progressive
chamber-pop|室内流行|chamber pop|pop|haze
jangle-pop|Jangle Pop|jangle pop|pop|alternative
power-pop|Power Pop|power pop|pop,rock|alternative
bedroom-pop|卧室流行|bedroom pop|indie-pop|haze
ambient-pop|氛围流行|ambient pop|ambient,pop|haze
alternative-pop|另类流行|alternative pop|pop|alternative
avant-pop|先锋流行|avant-pop|pop,experimental|progressive
soft-rock|软摇滚|soft rock|rock|classic
acoustic-rock|原声摇滚|acoustic rock|rock|folk
arena-rock|体育场摇滚|arena rock|rock|classic
album-oriented-rock|AOR 专辑导向摇滚|aor|rock|classic
rock-and-roll|Rock & Roll|rock and roll|rock|classic
symphonic-rock|交响摇滚|symphonic rock|rock|progressive
piano-rock|钢琴摇滚|piano rock|rock|alternative
neo-psychedelia|新迷幻|neo-psychedelia||progressive
psychedelic-soul|迷幻灵魂乐|psychedelic soul|soul|soul
post-britpop|后 Britpop|post-britpop|alternative-rock|alternative
madchester|Madchester|madchester|alternative-rock|alternative
lo-fi|Lo-Fi|lo-fi||haze
indietronica|独立电子|indietronica|indie,electronic|electronic
alternative-dance|另类舞曲|alternative dance|electronic|electronic
dance-rock|舞曲摇滚|dance-rock|rock|electronic
dance-pop|舞曲流行|dance-pop|pop|pop
sophisti-pop|Sophisti-Pop|sophisti-pop|pop|pop
mandopop|华语流行|mandopop|pop|pop
j-pop|J-Pop 日系流行|j-pop|pop|pop
j-rock|J-Rock 日系摇滚|j-rock|rock|alternative
electronic-rock|电子摇滚|electronic rock|electronic,rock|electronic
idm|IDM 智能舞曲|idm|electronic|electronic
edm|电子舞曲 EDM|edm|electronic|electronic
dubstep|Dubstep|dubstep|electronic|electronic
future-bass|Future Bass|future bass|electronic|electronic
drum-and-bass|鼓打贝斯 DnB|drum and bass|electronic|electronic
trance|Trance|trance|electronic|electronic
psytrance|Psytrance|psytrance|trance|electronic
deep-house|Deep House|deep house|house|electronic
minimal-wave|极简波|minimal wave|electronic|postpunk
synth-funk|合成器放克|synth funk|funk,electronic|jazz
electro-funk|电子放克|electro funk|funk,electronic|jazz
smooth-jazz|柔顺爵士|smooth jazz|jazz|jazz
free-jazz|自由爵士|free jazz|jazz|jazz
contemporary-jazz|当代爵士|contemporary jazz|jazz|jazz
spiritual-jazz|灵性爵士|spiritual jazz|jazz|jazz
pop-soul|流行灵魂乐|pop soul|soul,pop|soul
instrumental-hip-hop|器乐 Hip-Hop|instrumental hip hop|hip-hop|soul
trap|Trap|trap|hip-hop|soul
glam-metal|华丽金属|glam metal|metal|metal
rapcore|说唱核|rapcore|rap-rock|metal
stoner-rock|Stoner Rock|stoner rock|rock|classic
stoner-metal|Stoner Metal|stoner metal|metal|metal
melodic-black-metal|旋律黑金属|melodic black metal|black-metal|metal
technical-death-metal|技术死亡金属|technical death metal|death-metal|metal
traditional-folk|传统民谣|traditional folk music|folk|folk
surf-rock|冲浪摇滚|surf rock|rock|alternative
jazz-rap|爵士说唱|jazz rap|jazz,hip-hop|jazz
chillwave|Chillwave|chillwave|electronic,pop|haze
hypnagogic-pop|入眠流行|hypnagogic pop|pop|haze
yacht-rock|游艇摇滚|yacht rock|soft-rock|classic
'''

TAXONOMY = {}
for line in DEFINITIONS.strip().splitlines():
    ident, name, english, parents, family = line.split('|')
    TAXONOMY[ident] = dict(id=ident, name=name, english=english,
        parents=parents.split(',') if parents else [], family=family)
ALIASES = {value: key for key, entry in TAXONOMY.items() for value in [key, entry['english']]}
ALIASES.update({'post rock':'post-rock','post metal':'post-metal','post punk':'post-punk','math-rock':'math-rock',
    'shoegazing':'shoegaze','dream-pop':'dream-pop','synthpop':'synth-pop','rnb':'rnb','rhythm & blues':'rnb',
    'psychedelic':'psychedelic-rock','psychedelic rock':'psychedelic-rock','progressive rock':'progressive-rock',
    'depressive suicidal black metal':'depressive-black-metal','dsbm':'depressive-black-metal',
    'symphonic power metal':'symphonic-metal','mongolian metal':'folk-metal','instrumental rock':'post-rock',
    'alternative':'alternative-rock','indie music':'indie','hip-hop':'hip-hop','rap':'hip-hop',
    'contemporary r&b':'rnb','neo-soul':'neo-soul','chamber pop':'chamber-pop','jangle pop':'jangle-pop',
    'mandarin rock':'rock','chinese rock':'rock','chinese folk':'folk','chinese indie':'indie',
    'nu-metal':'nu-metal','industrial rock':'industrial-rock','pop-punk':'pop-punk','folk-rock':'folk-rock',
    'rock music':'rock','alternative/indie rock':'indie-rock','alternative rock music':'alternative-rock',
    'alt rock':'alternative-rock','contemporary pop/rock':'pop-rock','dark wave':'darkwave',
    'dance pop':'dance-pop','film soundtrack':'soundtrack','rock & roll':'rock-and-roll',
    'traditional folk':'traditional-folk','symphonic black metal':'black-metal'})
# Instrumental rock is not synonymous with post-rock. Broad tags must not create
# narrower labels. Same for generic psychedelic/alternative descriptions.
ALIASES['instrumental rock'] = 'rock'
ALIASES.pop('psychedelic', None)

FAMILIES = {
 'postrock':('后摇 · 远处的回声','POST-ROCK','#aabf9b'),
 'emo':('Emo · 数学摇滚','EMO & PATTERNS','#c6bb88'),
 'haze':('盯鞋 · 梦幻 · 氛围','HAZE & TEXTURE','#aaa0c6'),
 'postpunk':('后朋克 · 冷潮','POST-PUNK & NEW WAVE','#91aba5'),
 'metal':('金属 · 黑金 · 后金','METAL & WEIGHT','#ae948e'),
 'progressive':('前卫 · 迷幻','PROGRESSIVE & PSYCHEDELIC','#b4b581'),
 'alternative':('独立 · 另类摇滚','INDIE & ALTERNATIVE','#bda48d'),
 'folk':('民谣 · 叙事','FOLK & STORIES','#c6b58f'),
 'jazz':('爵士 · 放克','JAZZ & GROOVE','#96b9b6'),
 'soul':('R&B · Soul · Hip-Hop','SOUL & RHYTHM','#b99ab2'),
 'electronic':('电子 · 合成器','ELECTRONIC & SYNTH','#8eafbd'),
 'classic':('经典 · 布鲁斯摇滚','CLASSIC & BLUES','#bca78b'),
 'punk':('朋克 · 直率的声音','PUNK & URGENCY','#b8a17e'),
 'pop':('流行 · 旋律','POP & MELODY','#b4b6a7'),
 'ambient':('实验 · 原声 · 古典','OTHER FORMS','#9aaba0'),
 'pending':('风格待确认','STILL TO EXPLORE','#74847a')}

# Specific labels lead grouping; roots such as "rock" never swallow subgenres.
PRIORITY = ['midwest-emo','math-rock','emo','blackgaze','shoegaze','dream-pop','post-rock',
    'post-metal','black-metal','atmospheric-black-metal','post-black-metal','metalcore','folk-metal',
    'symphonic-metal','progressive-metal','death-metal','thrash-metal','nu-metal','heavy-metal','metal',
    'post-punk','coldwave','darkwave','gothic-rock','new-wave','progressive-rock','psychedelic-rock','krautrock',
    'jazz-fusion','jazz-rock','jazz','funk','neo-soul','alternative-rnb','rnb','soul','hip-hop',
    'indie-folk','folk-rock','folk','singer-songwriter','country','world','synthwave','synth-pop','electronic',
    'grunge','britpop','indie-rock','alternative-rock','punk-rock','punk','hard-rock','blues-rock','classic-rock',
    'indie-pop','pop-rock','pop','ambient','experimental','classical','soundtrack','rock','indie']


def canonical(tag):
    return ALIASES.get(tag.casefold().strip().replace('_',' '))


def apply_styles(network, raw, sources, overrides):
    by_id = {s['id']:s for s in raw}
    manual = overrides.get('artists', {})
    track_overrides = overrides.get('tracks', {})
    counts = Counter()
    for node in network['nodes']:
        song = by_id[node['id']]
        records = {}
        preferred=[]
        def add(ident, scope, url, title, basis, inherited=False, votes=0):
            if ident not in TAXONOMY:
                raise ValueError('Unknown style ID: ' + ident)
            record = dict(id=ident, scope=scope, source=url, sourceTitle=title, basis=basis, inherited=inherited,votes=votes)
            if ident not in records or (records[ident]['scope']=='artist-context' and scope!='artist-context') or (records[ident]['scope']==scope and records[ident]['inherited'] and not inherited):
                records[ident] = record
            for parent in TAXONOMY[ident]['parents']:
                if parent not in records:
                    add(parent,scope,url,title,'由子风格 ' + TAXONOMY[ident]['name'] + ' 展开上位标签',True)
        for artist in song['artists']:
            profile = sources.get(artist['name'], {})
            top_vote=max((t.get('count',0) for t in profile.get('tags',[]) if canonical(t['name'])),default=0)
            minimum_vote=1 if top_vote<3 else max(2,math.ceil(top_vote*.05))
            for tag in profile.get('tags', []):
                ident = canonical(tag['name'])
                if ident and tag.get('count',0)>=minimum_vote:
                    add(ident,'artist-context',profile['source'],'MusicBrainz · '+artist['name'],
                        '艺人社区标签，推定用于歌曲导航；未逐首核验',votes=tag['count'])
            for entry in manual.get(artist['name'], []):
                if entry.get('primary'):preferred.append(entry['primary'])
                scope='release' if song['album']['name'] in entry.get('albums', []) else 'artist-context'
                for ident in entry['labels']:
                    add(ident,scope,entry['url'],entry['title'],
                        '发行页声明的风格标签' if scope=='release' else '艺人或其他发行资料提供的风格背景，推定用于此曲')
        override = track_overrides.get(str(node['id']))
        if override:
            if override.get('primary'):preferred.insert(0,override['primary'])
            for ident in override.get('exclude', []):
                records.pop(ident,None)
            for entry in override.get('labels', []):
                add(entry['id'],'track',entry['url'],entry['title'],entry['basis'])
        labels = sorted(records,key=lambda i:(PRIORITY.index(i) if i in PRIORITY else 200,i))
        # Every node has a label state; unknown style is explicit, not a guessed
        # genre. Pending is a status label excluded from similarity calculations.
        node['styles'] = labels or ['pending']
        node['styleEvidence'] = [records[i] for i in labels]
        detailed=[i for i in labels if not records[i]['inherited'] and i not in ['rock','indie','pop','metal','electronic','punk']]
        options=detailed or labels
        primary=next((p for p in preferred if p in labels),None) or (max(options,key=lambda i:records[i]['votes']) if options else 'pending')
        node['primaryStyle'] = primary
        node['styleGroup'] = 'style-' + (TAXONOMY[primary]['family'] if labels else 'pending')
        counts.update(node['styles'])
    active = Counter(n['styleGroup'] for n in network['nodes'])
    # Area-aware rectangular packing keeps populous regions from becoming dense
    # circles and leaves lanes for inter-style bridges.
    groups = []
    x, y, row_height = 180, 230, 0
    max_width=4600
    for family in FAMILIES:
        ident='style-'+family
        count=active[ident]
        if not count:continue
        columns=max(5,min(24,math.ceil(math.sqrt(count*1.45))))
        rows=math.ceil(count/columns)
        width=columns*80+200; height=rows*84+220
        if x+width>max_width and x>180:
            x=180;y+=row_height+110;row_height=0
        name,english,color=FAMILIES[family]
        groups.append(dict(id=ident,name=name,english=english,color=color,center=[x+width/2,y+height/2],
            bounds=[x,y,width,height],columns=columns,basis='多标签风格资料；按主要标签安排位置，其他标签保留'))
        x+=width+130;row_height=max(row_height,height)
    existing=set(e['id'] for e in network['edges'])
    direct={n['id']:{r['id'] for r in n['styleEvidence'] if not r['inherited']} for n in network['nodes']}
    members=network['nodes']
    usage=Counter()
    # At most three style edges per node. Common root tags never create edges.
    roots={'rock','pop','indie','metal','electronic','experimental','punk','folk','soundtrack'}
    candidates=[]
    for index,a in enumerate(members):
        for b in members[index+1:]:
            shared=(direct[a['id']] & direct[b['id']])-roots
            if not shared:continue
            weight=sum(math.log(1+len(members)/counts[t]) for t in shared)
            union=(direct[a['id']] | direct[b['id']])-roots
            weight/=math.sqrt(max(1,len(union)))
            # Prefer exploration across artists over redundant same-artist links.
            if set(a.get('artistIds',[])) & set(b.get('artistIds',[])):weight*=.65
            candidates.append((-weight,a['id'],b['id'],sorted(shared)))
    for score,a,b,shared in sorted(candidates):
        if usage[a]>=3 or usage[b]>=3:continue
        network['edges'].append(dict(id=f'style-{a}-{b}',source=a,target=b,kind='style',status='candidate',
            styles=shared,weight=round(-score,4),reason='共享风格标签：'+ '、'.join(TAXONOMY[t]['name'] for t in shared)+'。标签来自歌曲、发行或艺人资料；艺人标签推定到歌曲仍需复核。这条线用于风格导航，不证明旋律、音色或情绪相同。'))
        usage[a]+=1;usage[b]+=1
    network['styleView']=dict(groups=groups,width=max_width+150,height=y+row_height+160,
        default=True,note='多标签风格导航；艺人风格为推定，未完成逐首试听')
    network['styleTaxonomy']=[{**TAXONOMY[t],'count':counts[t]} for t in sorted(counts) if t!='pending']
    network['styleTaxonomy'].append(dict(id='pending',name='风格待确认',english='Pending',parents=[],family='pending',count=counts['pending']))
    network['styleCoverage']=dict(total=len(members),labelled=sum(n['styles']!=['pending'] for n in members),
        pending=counts['pending'],labels=len(counts)-bool(counts['pending']),
        averageLabels=round(sum(len(n['styles']) for n in members if n['styles']!=['pending'])/max(1,sum(n['styles']!=['pending'] for n in members)),2))
    return network
