"""Read artist infobox genre fields; no biography-wide keyword inference."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from collect_music_styles import ROOT, ALIASES
from music_styles import canonical

TRANSLATIONS={
 '摇滚':'rock','搖滾':'rock','摇滚乐':'rock','搖滾樂':'rock','另类摇滚':'alternative-rock','另類搖滾':'alternative-rock',
 '独立摇滚':'indie-rock','獨立搖滾':'indie-rock','独立音乐':'indie','獨立音樂':'indie','獨立流行':'indie-pop','独立流行':'indie-pop',
 '流行音樂':'pop','流行音乐':'pop','流行':'pop','流行搖滾':'pop-rock','流行摇滚':'pop-rock',
 '後搖滾':'post-rock','后摇滚':'post-rock','後搖':'post-rock','后摇':'post-rock',
 '數學搖滾':'math-rock','数学摇滚':'math-rock','數字搖滾':'math-rock','数字摇滚':'math-rock',
 '情緒搖滾':'emo','情绪摇滚':'emo','盯鞋搖滾':'shoegaze','盯鞋摇滚':'shoegaze','盯鞋':'shoegaze',
 '夢幻流行':'dream-pop','梦幻流行':'dream-pop','迷幻搖滾':'psychedelic-rock','迷幻摇滚':'psychedelic-rock',
 '前衛搖滾':'progressive-rock','前卫摇滚':'progressive-rock','藝術搖滾':'art-rock','艺术摇滚':'art-rock',
 '實驗搖滾':'experimental-rock','实验摇滚':'experimental-rock','實驗音樂':'experimental','实验音乐':'experimental',
 '後朋克':'post-punk','后朋克':'post-punk','新浪潮':'new-wave','哥德搖滾':'gothic-rock','哥特摇滚':'gothic-rock',
 '民謠':'folk','民谣':'folk','民謠搖滾':'folk-rock','民谣摇滚':'folk-rock','鄉村音樂':'country','乡村音乐':'country',
 '重金屬':'heavy-metal','重金属':'heavy-metal','金屬':'metal','金属':'metal','民謠金屬':'folk-metal','民谣金属':'folk-metal',
 '交響金屬':'symphonic-metal','交响金属':'symphonic-metal','新金屬':'nu-metal','新金属':'nu-metal',
 '黑金屬':'black-metal','黑金属':'black-metal','後金屬':'post-metal','后金属':'post-metal',
 '死亡金屬':'death-metal','死亡金属':'death-metal','力量金屬':'power-metal','力量金属':'power-metal',
 '鞭笞金屬':'thrash-metal','鞭笞金属':'thrash-metal','前衛金屬':'progressive-metal','前卫金属':'progressive-metal',
 '爵士樂':'jazz','爵士乐':'jazz','爵士':'jazz','爵士搖滾':'jazz-rock','爵士摇滚':'jazz-rock',
 '放克':'funk','放克搖滾':'funk-rock','放克摇滚':'funk-rock','靈魂樂':'soul','灵魂乐':'soul',
 '節奏藍調':'rnb','节奏布鲁斯':'rnb','藍調':'blues','布鲁斯':'blues','藍調搖滾':'blues-rock','布鲁斯摇滚':'blues-rock',
 '朋克':'punk','龐克':'punk','龐克搖滾':'punk-rock','朋克摇滚':'punk-rock','朋克搖滾':'punk-rock',
 '流行朋克':'pop-punk','流行龐克':'pop-punk','硬核朋克':'hardcore-punk','後硬核':'post-hardcore','后硬核':'post-hardcore',
 '油漬搖滾':'grunge','垃圾摇滚':'grunge','英倫搖滾':'british-rock','英伦摇滚':'british-rock','英倫流行':'britpop','英伦流行':'britpop',
 '電子音樂':'electronic','电子音乐':'electronic','電子':'electronic','电子':'electronic','合成器流行':'synth-pop',
 '電子搖滾':'electronic-rock','电子摇滚':'electronic-rock','華語流行音樂':'mandopop','华语流行音乐':'mandopop','華語流行':'mandopop','日系搖滾':'j-rock','日系摇滚':'j-rock','電子流行':'electropop','电子流行':'electropop','電子舞曲':'electronic','电子舞曲':'electronic','工業搖滾':'industrial-rock',
 '硬式搖滾':'hard-rock','硬摇滚':'hard-rock','硬搖滾':'hard-rock','華麗搖滾':'glam-rock','华丽摇滚':'glam-rock',
 '饒舌':'hip-hop','说唱':'hip-hop','嘻哈':'hip-hop','说唱摇滚':'rap-rock','世界音樂':'world','世界音乐':'world',
 '古典音樂':'classical','古典音乐':'classical','雷鬼':'reggae','原聲音樂':'soundtrack','原声音乐':'soundtrack',
}
OVERRIDES={'法兹乐队 FAZI':'法兹','九宝乐队':'Nine Treasures','腰乐队':'腰乐队','声音碎片乐队':'声音碎片',
 '万能青年旅店':'万能青年旅店','梅卡德尔':'梅卡德尔','草东没有派对':'草东没有派对','郁乐队':'郁乐队',
 'The Cheers Cheers':'The Cheers Cheers','小雨乐队':'小雨乐队','Prince':'Prince (musician)',
 'Queen':'Queen (band)','Heart':'Heart (band)','Nirvana':'Nirvana (band)','MONO':'Mono (Japanese band)',
 'STOLEN秘密行动':'STOLEN','deca joins':'Deca Joins','PREP':'Prep (band)','The Cure':'The Cure','toe':'Toe (band)',
 'Múm':'Múm','椅子乐团 The Chairs':'椅子樂團','当代电影大师':'當代電影大師'}
CACHE=ROOT/'local/music-atlas/wiki-style-sources'


def fetch(language,title):
 key=hashlib.sha256((language+title).encode()).hexdigest()[:20]
 target=CACHE/(key+'.json')
 if target.exists():return json.loads(target.read_text(encoding='utf8'))
 query=urllib.parse.urlencode({'action':'parse','page':title,'prop':'wikitext','format':'json','redirects':1})
 req=urllib.request.Request(f'https://{language}.wikipedia.org/w/api.php?'+query,headers={'User-Agent':'PersonalMusicAtlas/1.0 (https://edzee3000.github.io/music/)'})
 with urllib.request.urlopen(req,timeout=20) as response:result=json.load(response)
 target.write_text(json.dumps(result,ensure_ascii=False),encoding='utf8')
 time.sleep(.35)
 return result


def collect(name):
 # Wikipedia's Sadness (band) is the Swiss death/doom band, whereas these
 # playlist tracks belong to Damián Ojeda's US project. Use official sources.
 if name=='Sadness':return dict(name=name,labels=[],status='ambiguous')
 title=OVERRIDES.get(name,ALIASES.get(name,name))
 lang='zh' if re.search(r'[\u4e00-\u9fff]',title) else 'en'
 titles=[title]
 if lang=='en' and '(' not in title:titles+=[title+' (band)',title+' (musician)']
 elif lang=='zh' and not title.endswith('乐队'):titles+=[title+'乐队']
 for query in titles:
  try:
   data=fetch(lang,query); parsed=data.get('parse',{});text=parsed.get('wikitext',{}).get('*','')
   if not re.search(r'\{\{\s*(infobox musical artist|infobox band|藝人|艺人|音樂人物|音乐人物)',text[:6000],re.I):continue
   match=re.search(r'^\|\s*(?:genre|music_genre|音樂類型|音乐类型|音乐风格|音樂風格)\s*=\s*(.*?)(?=\n\s*\||\n\}\})',text,re.I|re.M|re.S)
   if not match:continue
   field=match.group(1)
   field=re.sub(r'<ref\b.*?(?:/>|</ref>)','',field,flags=re.S)
   terms=[m.split('|')[0].split('#')[0].strip() for m in re.findall(r'\[\[(.*?)\]\]',field)]
   plain=re.sub(r'\{\{[^}]*\}\}',' ',field)
   terms+=re.split(r'[,，、;；\n|/]',re.sub(r'\[\[|\]\]|<[^>]*>',' ',plain))
   labels=set()
   for term in terms:
    term=term.strip().strip("' ")
    ident=TRANSLATIONS.get(term) or canonical(term)
    if ident:labels.add(ident)
   if labels:
    return dict(name=name,labels=sorted(labels),status='artist-context',matchedTitle=parsed['title'],
     source=f'https://{lang}.wikipedia.org/wiki/'+urllib.parse.quote(parsed['title'].replace(' ','_'),safe=''),
     scope='百科艺人信息框风格；推定用于歌曲导航，非逐首确认')
  except Exception:continue
 return dict(name=name,labels=[],status='unmatched')


if __name__=='__main__':
 raw=json.loads((ROOT/'_data/music.json').read_text(encoding='utf8'))
 names=sorted({a['name'] for s in raw for a in s['artists']})
 CACHE.mkdir(parents=True,exist_ok=True)
 results={};path=ROOT/'_data/music_wiki_style_sources.json'
 with ThreadPoolExecutor(max_workers=3) as pool:
  for index,result in enumerate(pool.map(collect,names),1):
   results[result['name']]=result
   if index%30==0 or index==len(names):
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(f'{index}/{len(names)} Wikipedia profiles; {sum(bool(r["labels"]) for r in results.values())} with genre fields',flush=True)
