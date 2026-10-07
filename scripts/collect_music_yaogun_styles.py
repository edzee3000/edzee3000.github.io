"""Read genre fields from Chinese Rock Database, with Chinese-name validation."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup
from collect_music_styles import ROOT

GENRES={'オルタナティブ':'alternative-rock','ロック':'rock','インディーロック':'indie-rock','インディーポップ':'indie-pop',
 'フォーク':'folk','フォークロック':'folk-rock','ブルース':'blues','ブルースロック':'blues-rock',
 'ポストロック':'post-rock','ポストパンク':'post-punk','ニューウェーブ':'new-wave','ダークウェーブ':'darkwave',
 'シューゲイザー':'shoegaze','シューゲイズ':'shoegaze','ドリームポップ':'dream-pop','エモ':'emo','マスロック':'math-rock',
 'パンク':'punk','パンクロック':'punk-rock','ポップパンク':'pop-punk','ハードコア':'hardcore-punk','ポストハードコア':'post-hardcore',
 'メタル':'metal','ヘビーメタル':'heavy-metal','ブラックメタル':'black-metal','デスメタル':'death-metal',
 'スラッシュメタル':'thrash-metal','ニューメタル':'nu-metal','メタルコア':'metalcore','メロディックデスメタル':'melodic-death-metal',
 'フォークメタル':'folk-metal','ポストメタル':'post-metal','インダストリアルメタル':'industrial-metal',
 'ハードロック':'hard-rock','グランジ':'grunge','ブリティッシュロック':'british-rock',
 'サイケデリック':'psychedelic-rock','プログレッシブロック':'progressive-rock','アートロック':'art-rock',
 'ジャズ':'jazz','ジャズロック':'jazz-rock','フュージョン':'jazz-fusion','ファンク':'funk',
 'ヒップホップ':'hip-hop','ラップ':'hip-hop','ラップメタル':'rap-metal','レゲエ':'reggae','スカ':'ska',
 'エレクトロニカ':'electronica','エレクトロロック':'electronic-rock','エレクトロ':'electronic','テクノ':'techno',
 'トリップホップ':'trip-hop','インダストリアル':'industrial','ノイズ':'experimental',
 'ノイズロック':'noise-rock','実験音楽':'experimental','アンビエント':'ambient','ワールドミュージック':'world',
 'ポップ':'pop','ポップロック':'pop-rock','ディスコ':'disco','カントリー':'country'}
MAP=str.maketrans({'铁':'鉄','时':'時','过':'過','车':'車','蓝':'藍','后':'後','团':'団','观':'観','广':'広','发':'発',
 '晓':'暁','岛':'島','阳':'陽','阴':'陰','线':'線','齐':'斉','缘':'縁','万':'万','为':'為','渊':'淵','云':'雲','无':'無',
 '台':'台','东':'東','张':'張','马':'馬','诗':'詩','汉':'漢','声':'声','间':'間','离':'離','飞':'飛','光':'光'})
EXPLICIT={'腰乐队':'腰','STOLEN秘密行动':'秘密行動','文雀':'文雀','时过夏末':'時過夏末','寸铁':'寸鉄',
 'C.S.B.Q乐队':'C.S.B.Q','THE BOOTLEGS 靴腿':'The Bootlegs','当代电影大师':'当代電影大師','灯诱LampLure':'灯誘',
 '椿乐队':'椿','南青乐队':'南青','Kawa乐队':'Kawa','The Cheers Cheers':'The Cheers Cheers',
 'Another One安娜万千':'安娜万千','鱼条 Fish Stick':'魚条','水树':'水樹','Pu Poo Platter 宝宝盘':'宝宝盤',
 '浅水ShallowEnd':'浅水','Sunken Boat 沉舟乐队':'沉舟','发光曲线':'発光曲線','大象体操':'大象体操',
 'DengeL（单舟）':'DengeL','郁乐队':'郁','小雨乐队':'小雨','丢火车':'丢火車','岛屿心情':'島嶼心情',
 '橘子海 (Orange Ocean)':'橘子海','Crispy脆乐团':'脆楽団'}
CACHE=ROOT/'local/music-atlas/yaogun-style-sources'


def norm(text):
 return re.sub(r'[^\w]','',unicodedata.normalize('NFKC',text).casefold()).replace('乐队','').replace('楽隊','')


def collect(name):
 core=EXPLICIT.get(name)
 if not core:
  match=re.search(r'[\u4e00-\u9fff]+',name)
  if not match:return dict(name=name,labels=[],status='unmatched')
  core=re.sub(r'(乐队|乐团)$','',match.group())
 titles=list(dict.fromkeys([core.translate(MAP)+'楽隊',core+'楽隊',core.translate(MAP),core]))
 for title in titles:
  url='https://www.yaogun.com/wiki/'+urllib.parse.quote(title)
  target=CACHE/(hashlib.sha256(url.encode()).hexdigest()[:20]+'.json')
  try:
   if target.exists():data=json.loads(target.read_text(encoding='utf8'))
   else:
    req=urllib.request.Request(url,headers={'User-Agent':'PersonalMusicAtlas/1.0 (https://edzee3000.github.io/music/)'})
    with urllib.request.urlopen(req,timeout=15) as response:html=response.read().decode('utf8')
    soup=BeautifulSoup(html,'html.parser');data={}
    for row in soup.select('table.infobox tr'):
     cells=row.find_all(['th','td'],recursive=False)
     if len(cells)==2:data[cells[0].get_text(' ',strip=True)]=cells[1].get_text(' ',strip=True)
    target.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8');time.sleep(.4)
   identities=[value for key,value in data.items() if key.startswith('中国語名') or key=='英語名・外国語名']
   expected={norm(name),norm(core),norm(core.translate(MAP))}
   if not any(norm(value) in expected for value in identities):continue
   genre=data.get('ジャンル','')
   labels=sorted({GENRES[t.strip()] for t in genre.split('・') if t.strip() in GENRES})
   if labels:return dict(name=name,labels=labels,status='artist-context',source=url,
    matchedTitle=title,genreField=genre,scope='Chinese Rock Database 艺人风格字段，推定用于此曲，不是逐首确认')
  except Exception:continue
 return dict(name=name,labels=[],status='unmatched')


if __name__=='__main__':
 raw=json.loads((ROOT/'_data/music.json').read_text(encoding='utf8'))
 graph=json.loads((ROOT/'assets/music/network.json').read_text(encoding='utf8'))
 pending={n['id'] for n in graph['nodes'] if n.get('styles')==['pending']}
 names=sorted({a['name'] for s in raw if s['id'] in pending for a in s['artists']})
 CACHE.mkdir(parents=True,exist_ok=True)
 path=ROOT/'_data/music_yaogun_style_sources.json';results=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
 with ThreadPoolExecutor(max_workers=2) as pool:
  for index,result in enumerate(pool.map(collect,names),1):
   results[result['name']]=result
   if index%20==0 or index==len(names):
    path.write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(f'{index}/{len(names)} pending artists; {sum(bool(r["labels"]) for r in results.values())} with database styles',flush=True)
