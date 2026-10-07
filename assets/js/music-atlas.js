/* Full catalog. Build-time coordinates; bounded edge/label rendering. */
(() => {
  'use strict';
  const root = document.getElementById('music-atlas');
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const svg = $('network');
  const NS = 'http://www.w3.org/2000/svg';
  const escape = (value) => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const kindNames = { style: '风格', sound: '声音', emotion: '情绪', structure: '结构', acoustic: '声学片段', lyrics: '歌词线索', artist: '同艺人', album: '同专辑' };
  const statusName = edge => edge.status === 'verified' ? '署名 / 发行事实' : edge.status === 'measured' ? '片段特征已测量' : '候选关系 · 待核验';
  let songs = [], network, nodes = [], links = [], songById, nodeById, groups;
  let selection = null, selectedEdge = null, filterGroup = null, filterRelation = 'style', mode = 'map';
  const selectedStyles=new Set();
  let styleById=new Map(), stylesExpanded=false;
  const camera = { x: 0, y: 0, width: 1000, height: 720 };
  const pointers = new Map();
  let gesture = null, suppressClick = false;
  let hoveredId = null, motionEnabled = false, graphInView = true;
  let frame = null, lastFrame = 0, motionTime = 0, labelFrame = null, lastLabels = 0;
  let explicitMotion = false;
  let visibleEdges = [], groupLayers = new Map(), worldWidth = 1000, worldHeight = 720;
  let labelsPlaced = 0;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');
  const el = (tag, attrs = {}, parent) => {
    const item = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, value]) => item.setAttribute(key, value));
    if (parent) parent.append(item);
    return item;
  };
  const artwork = (song, small = false) => new URL(small ? song.coverSmall || song.cover : song.cover, new URL(root.dataset.catalog, location.href)).href;
  const trackHref = (song) => `https://music.163.com/song?id=${song.id}`;
  const imageMarkup = (song, cls = '') => `<img class="${cls}" src="${escape(artwork(song))}" alt="${escape(song.album)} 专辑封面" loading="lazy">`;
  const sourceMarkup = (node) => node?.sources?.length ? `<p class="source-links">发行资料：${node.sources.map(source => `<a href="${escape(source.url)}" target="_blank" rel="noopener noreferrer">${escape(source.title)} ↗</a>`).join(' · ')}</p>` : '';
  const panelTop = (label) => `<div class="panel-eyebrow"><span>${label}</span><button type="button" class="panel-close" data-close aria-label="关闭详情">×</button></div>`;
  const styleMarkup=node=>node?.styles?.length?`<h3 class="note-heading">风格标签</h3><div class="song-tags style-song-tags">${node.styles.map(id=>`<button type="button" data-style="${id}">${escape(styleById.get(id)?.name||id)}</button>`).join('')}</div><p class="style-provenance">${node.styles[0]==='pending'?'风格资料不足，待确认。':'标签来自歌曲、专辑或艺人资料；艺人标签推定用于此曲，尚未逐首试听确认。'}</p>${node.styleEvidence?.length?`<details class="style-evidence"><summary>标签依据</summary>${node.styleEvidence.map(r=>`<p><strong>${escape(styleById.get(r.id)?.name||r.id)}</strong> · ${r.scope==='release'?'专辑资料':r.scope==='track'?'歌曲资料':'艺人背景'}<br><a href="${escape(r.source)}" target="_blank" rel="noopener noreferrer">${escape(r.sourceTitle)} ↗</a></p>`).join('')}</details>`:''}`:'';

  function welcome() {
    selection = null;
    selectedEdge = null;
    $('detail-panel').innerHTML = `<div class="panel-welcome"><div class="panel-eyebrow">FOLLOW A THREAD</div><h2>Every song.<br>A different<br><em>way home.</em></h2><p class="welcome-cn">从一首歌，<br>走进另一片声音。</p><p class="panel-copy">点击一个光点，看看它与哪些歌曲相遇。再沿着连接，寻找熟悉的声音之外的共鸣。</p><div class="panel-divider"></div><span class="small-label">A FEW PLACES TO BEGIN</span>${network.featured.slice(0,3).map(id => {
      const song = songById.get(id);
      return `<button type="button" class="featured-song" data-song="${id}">${imageMarkup(song)}<span><strong>${escape(song.name)}</strong><small>${escape(song.artists)}</small></span><b>↗</b></button>`;
    }).join('')}<p class="panel-hint">全量收藏已展开。<br>实线是发行或署名事实，虚线是片段测量与歌词线索；完整听感解读仍需逐首试听。</p></div>`;
    updateGraph();
  }

  function selectSong(id, focus = false) {
    const song = songById.get(Number(id));
    if (!song) return;
    if (selection === song.id) {
      welcome();
      return;
    }
    selection = song.id;
    selectedEdge = null;
    const node = nodeById.get(song.id);
    const related = node ? links.filter(e => e.source.id === song.id || e.target.id === song.id).sort((a,b) => (a.status === 'verified' ? -1 : 1) - (b.status === 'verified' ? -1 : 1)) : [];
    $('detail-panel').innerHTML = `${panelTop(node ? 'SELECTED TRACK' : 'FROM THE COLLECTION')}<a class="cover-original-link" href="${escape(song.coverOriginal || artwork(song))}" target="_blank" rel="noopener noreferrer" aria-label="查看专辑封面原图（新窗口）" title="查看专辑封面原图">${imageMarkup(song, 'song-cover')}</a><h2 class="song-title">${escape(song.name)}</h2><p class="song-artist">${escape(song.artists)}</p><p class="song-album">${escape(song.album)} · ${formatDuration(song.duration)}</p>${node ? `<div class="song-tags">${node.tags.map(t => `<span>${escape(t)}</span>`).join('')}</div><p class="centrality-note">PageRank 排名 ${node.centrality.rank} / ${nodes.length} · ${node.centrality.degree} 条连接<br><small>大小表示当前关系网的中心性，包含文本候选连接；不表示播放量或个人偏好。</small></p><h3 class="note-heading">发行资料</h3><p class="song-note">${escape(node.fact)}</p>${sourceMarkup(node)}${styleMarkup(node)}<h3 class="note-heading">${node.editorialStatus==='pending'?'编辑解读 · 尚未完成':'探索笔记 · 待试听核验'}</h3><p class="song-note">${escape(node.note)}</p>${node.measurementNote?`<details class="measurement-details"><summary>查看声学与歌词资料</summary>${node.measurementNote.split('\n\n').map(p=>`<p class="song-note">${escape(p)}</p>`).join('')}</details>`:''}` : `<h3 class="note-heading">尚未进入本轮星图</h3><p class="song-note">这首歌已保留在完整收藏中。后续逐首分析会补充歌曲解读及有依据的关系连接。</p>`}<a class="listen-link" href="${trackHref(song)}" target="_blank" rel="noopener noreferrer">去网易云听这首歌 <span>↗</span></a>${related.length ? `<h3 class="note-heading">沿着连接探索 · ${related.length}</h3>${related.map(edge => {
      const other = edge.source.id === song.id ? edge.target : edge.source;
      return `<button type="button" class="related-song" data-edge="${edge.id}"><strong>${escape(other.song.name)} ↗</strong><small>${kindNames[edge.kind]} · ${statusName(edge)}</small></button>`;
    }).join('')}` : ''}`;
    $('detail-panel').scrollTop = 0;
    updateGraph();
    if (focus && node && mode === 'map') centerOn(node);
    if (focus && matchMedia('(max-width:760px)').matches) $('detail-panel').scrollIntoView({behavior:'smooth',block:'start'});
  }

  function selectConnection(id) {
    const edge = links.find(e => e.id === id);
    if (!edge) return;
    if (selectedEdge === id) {
      welcome();
      return;
    }
    selectedEdge = id;
    selection = null;
    $('detail-panel').innerHTML = `${panelTop('BETWEEN TWO SONGS')}<div class="edge-pair"><h2>${escape(edge.source.song.name)}</h2><span>↕</span><h2>${escape(edge.target.song.name)}</h2></div><span class="edge-badge">${kindNames[edge.kind]} · ${statusName(edge)}</span><h3 class="note-heading">为什么连在一起？</h3><p class="song-note">${escape(edge.reason)}</p><div class="panel-divider"></div><span class="small-label">EXPLORE BOTH ENDS</span><button type="button" class="edge-song-link" data-song="${edge.source.id}">${escape(edge.source.song.name)} ↗</button><button type="button" class="edge-song-link" data-song="${edge.target.id}">${escape(edge.target.song.name)} ↗</button><p class="panel-hint">${edge.status === 'verified' ? '发行或署名 ID 已核对，不表示听感必然相似。' : edge.status === 'measured' ? '这条关系基于实际取得的音频片段，只反映七维声学特征接近。' : '候选关系尚待逐首试听或结合歌词语境核验，不能直接当作已完成的音乐分析。'}</p>`;
    updateGraph();
    if (matchMedia('(max-width:760px)').matches) $('detail-panel').scrollIntoView({behavior:'smooth',block:'start'});
  }

  function formatDuration(ms) {
    if (!ms) return '时长待核对';
    const seconds = Math.round(ms / 1000);
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2,'0')}`;
  }

  function matches(song) {
    const query = $('song-search').value.trim().normalize('NFKC').toLocaleLowerCase();
    return !query || `${song.name} ${song.artists} ${song.album}`.normalize('NFKC').toLocaleLowerCase().includes(query);
  }

  function renderCatalog() {
    const results = songs.filter(song => matches(song) && (!filterGroup || nodeById.get(song.id)?.group === filterGroup) && (!selectedStyles.size || [...selectedStyles].every(id=>nodeById.get(song.id)?.styles?.includes(id))));
    $('results-count').textContent = `${results.length} / ${songs.length} 首`;
    $('catalog-rows').innerHTML = results.length ? results.map(song => `<button type="button" class="catalog-row" data-song="${song.id}"><span class="track-number">${String(song.position).padStart(2,'0')}</span>${imageMarkup(song)}<span class="track-info"><strong>${escape(song.name)}</strong><small>${escape(song.artists)}</small></span><span class="track-album">${escape(song.album)}</span>${nodeById.has(song.id) ? '<span class="sample-tag">星图 ↗</span>' : ''}</button>`).join('') : '<div class="empty-state">没有找到匹配的歌曲。<br><button type="button" data-clear>清除搜索与区域筛选</button></div>';
  }

  function setMode(next) {
    mode = next;
    $('map-container').hidden = next !== 'map';
    $('catalog-view').hidden = next !== 'list';
    for (const name of ['map','list']) {
      $(`${name}-view`).classList.toggle('active', name === next);
      $(`${name}-view`).setAttribute('aria-pressed',String(name === next));
    }
    document.querySelector('.relation-controls').hidden = next === 'list';
    if (next === 'list') renderCatalog();
    else updateGraph();
    syncMotion();
  }

  function inViewport(node, margin = 100) {
    return node.x + node.radius >= camera.x - margin && node.x - node.radius <= camera.x + camera.width + margin && node.y + node.radius >= camera.y - margin && node.y - node.radius <= camera.y + camera.height + margin;
  }

  function updateGraph() {
    if (!network) return;
    const related = new Set(selection ? [selection] : []);
    if (selection) links.forEach(e => {
      if ((filterRelation === 'all' || e.kind === filterRelation) && (e.source.id === selection || e.target.id === selection)) { related.add(e.source.id); related.add(e.target.id); }
    });
    const focused = selectedEdge ? links.find(e => e.id === selectedEdge) : null;
    if (focused) { related.add(focused.source.id); related.add(focused.target.id); }
    const visible = node => matches(node.song) && (!filterGroup || node.group === filterGroup) && (!selectedStyles.size || [...selectedStyles].every(id=>node.styles?.includes(id)));
    const zoomLevel = worldWidth / camera.width;
    const unit=1/(svg.getScreenCTM()?.a||.2);
    $('group-labels').querySelectorAll('.group-label').forEach(label=>label.style.fontSize=`${9*unit}px`);
    $('group-labels').querySelectorAll('.group-subtitle').forEach(label=>label.style.fontSize=`${6*unit}px`);
    nodes.forEach(node => {
      const dim = !visible(node) || ((selection || selectedEdge) && !related.has(node.id));
      node.inView = inViewport(node);
      node.element.style.display = node.inView ? '' : 'none';
      node.element.classList.toggle('dim', Boolean(dim));
      node.element.classList.toggle('unreviewed',filterRelation!=='style'&&node.editorialStatus==='pending'&&!selection&&!selectedEdge);
      node.element.classList.toggle('selected', node.id === selection || (focused && related.has(node.id)));
      node.element.setAttribute('aria-pressed', String(node.id === selection));
      node.wantsLabel = node.inView && !dim && (node.featured || node.id === selection || node.id === hoveredId || related.has(node.id) || zoomLevel > 2.2);
      node.showArtist = node.id === selection || node.id === hoveredId;
      const highResolution = node.radius * (svg.getScreenCTM()?.a || .2) > 18;
      if(node.inView && highResolution !== node.highResolution){node.highResolution=highResolution;node.image.setAttribute('href',artwork(node.song,!highResolution));}
    });
    const permitted = links.filter(edge => (selectedEdge===edge.id || (filterRelation === 'all' ? edge.kind!=='acoustic'&&edge.kind!=='lyrics'&&edge.kind!=='style' : filterRelation === edge.kind)) && visible(edge.source) && visible(edge.target) && (edge.source.inView || edge.target.inView));
    const edgePriority = edge => selectedEdge===edge.id ? 10000 : selection && (edge.source.id===selection || edge.target.id===selection) ? 5000 : edge.kind==='style' ? 350+Math.min(25,edge.weight||0)+(edge.source.group!==edge.target.group?12:0) : ['sound','emotion','structure'].includes(edge.kind) ? 350 : edge.kind==='acoustic' ? 300+(1-(edge.distance||0))*50 : edge.kind==='album' ? 230 : edge.kind==='artist' ? 150 : 100;
    const budget = network.layout.edgeBudget || 220;
    const candidates = permitted.filter(edge => !(selection || selectedEdge) || selectedEdge===edge.id || (selection && (edge.source.id===selection || edge.target.id===selection)));
    candidates.sort((a,b)=>edgePriority(b)-edgePriority(a)||a.id.localeCompare(b.id));
    // Fairly distribute overview edges among regions and nodes. Selection always
    // exposes the complete local neighborhood rather than a global top-N slice.
    const chosen = [], degrees = new Map(), kindCounts = new Map(), chosenIds = new Set();
    const quotas={style:220,sound:45,emotion:25,structure:25,artist:75,album:50,acoustic:220,lyrics:220};
    for(const edge of [...candidates,...candidates]){
      if(chosenIds.has(edge.id))continue;
      const firstPass=kindCounts.get('_processed')||0;
      kindCounts.set('_processed',firstPass+1);
      if(!selection&&!selectedEdge&&firstPass<candidates.length&&(kindCounts.get(edge.kind)||0)>=(quotas[edge.kind]||30))continue;
      const cap=selection||selectedEdge?Infinity:3;
      if((degrees.get(edge.source.id)||0)>=cap || (degrees.get(edge.target.id)||0)>=cap)continue;
      chosen.push(edge);chosenIds.add(edge.id);kindCounts.set(edge.kind,(kindCounts.get(edge.kind)||0)+1);degrees.set(edge.source.id,(degrees.get(edge.source.id)||0)+1);degrees.set(edge.target.id,(degrees.get(edge.target.id)||0)+1);
      if(chosen.length>=budget)break;
    }
    visibleEdges = chosen;
    $('edge-layer').replaceChildren();
    visibleEdges.forEach(edge=>drawEdge(edge,Boolean(selection||selectedEdge)));
    $('map-status').textContent = `${nodes.filter(visible).length} 首 · ${visibleEdges.length} / ${links.length} 条关系`;
    root.dataset.visibleEdges=String(visibleEdges.length);
    $('legend').classList.toggle('has-filter', Boolean(filterGroup));
    document.querySelectorAll('[data-group]').forEach(button => { button.classList.toggle('active', button.dataset.group === filterGroup); button.setAttribute('aria-pressed',String(button.dataset.group === filterGroup)); });
    scheduleLabels();
    syncMotion();
  }

  function scheduleLabels() {
    if (labelFrame !== null) return;
    labelFrame = requestAnimationFrame(() => { labelFrame = null; arrangeLabels(); });
  }

  function arrangeLabels() {
    if (mode !== 'map' || !nodes.length || !svg.getScreenCTM()) return;
    const matrix = svg.getScreenCTM(), unit = 1 / matrix.a;
    const rect = $('map-container').getBoundingClientRect();
    const project = (x,y) => new DOMPoint(x,y).matrixTransform(matrix);
    const intersects = (a,b) => a.x < b.x+b.w && a.x+a.w > b.x && a.y < b.y+b.h && a.y+a.h > b.y;
    // All covers and region headings are reserved before any song label is placed.
    const reserved = nodes.filter(n=>n.inView).map(n => { const p = project(n.x,n.y), r = n.radius*matrix.a+3; return {x:p.x-r,y:p.y-r,w:2*r,h:2*r}; });
    $('group-labels').querySelectorAll('text').forEach(text => { const r=text.getBoundingClientRect();reserved.push({x:r.x-5,y:r.y-5,w:r.width+10,h:r.height+10}); });
    const order = [...nodes].sort((a,b) => {
      const priority = n => n.id===selection?1000:n.id===hoveredId?900:n.featured?500:100-n.centrality.rank;
      return priority(b)-priority(a) || a.id-b.id;
    });
    labelsPlaced=0;
    const budget=matchMedia('(max-width:760px)').matches ? network.layout.mobileLabelBudget : network.layout.labelBudget;
    nodes.forEach(node=>{if(node.caption){node.caption.style.display='none';node.leader.style.display='none';}});
    order.forEach(node => {
      if (!node.wantsLabel || !node.inView || labelsPlaced>=budget) return;
      ensureCaption(node);
      const p=project(node.x,node.y), radius=node.radius*matrix.a;
      node.label.style.fontSize=`${11*unit}px`;
      node.artistLabel.style.fontSize=`${9*unit}px`;
      node.artistLabel.style.display=node.showArtist?'':'none';
      // Measure at screen-constant font sizes; zoom reveals more, rather than oversized text.
      node.caption.style.display='';
      const width=Math.max(node.label.getComputedTextLength()/unit,node.showArtist?node.artistLabel.getComputedTextLength()/unit:0)+10;
      const height=node.showArtist?34:20;
      const gap=radius+12;
      const candidates=[...(node.captionOffset?[[p.x+node.captionOffset[0],p.y+node.captionOffset[1]]]:[]),...[0,26,52,85,120].flatMap(extra=>{
        const distance=gap+extra;
        return [[p.x+distance,p.y-height/2],[p.x-distance-width,p.y-height/2],
          [p.x-width/2,p.y+distance],[p.x-width/2,p.y-distance-height],
          [p.x+distance,p.y-distance-height],[p.x-distance-width,p.y-distance-height],
          [p.x+distance,p.y+distance],[p.x-distance-width,p.y+distance]];
      })];
      const bounds={x:rect.x+8,y:rect.y+48,w:rect.width-28,h:rect.height-98};
      const position=candidates.find(([x,y]) => x>=bounds.x && y>=bounds.y && x+width<=bounds.x+bounds.w && y+height<=bounds.y+bounds.h && !reserved.some(r=>intersects({x:x-4,y:y-4,w:width+8,h:height+8},r)));
      if (!position) { node.caption.style.display='none';return; }
      const [x,y]=position;
      node.captionOffset=[x-p.x,y-p.y];
      node.caption.setAttribute('transform',`translate(${(x-p.x)*unit},${(y-p.y)*unit})`);
      const endX=Math.max(x,Math.min(p.x,x+width)),endY=Math.max(y,Math.min(p.y,y+height));
      const distance=Math.hypot(endX-p.x,endY-p.y);
      if(distance>radius+16){
        node.leader.style.display='';
        Object.entries({x1:(endX-p.x)/distance*(node.radius+3),y1:(endY-p.y)/distance*(node.radius+3),x2:(endX-p.x)*unit,y2:(endY-p.y)*unit}).forEach(([k,v])=>node.leader.setAttribute(k,v));
      }
      node.label.setAttribute('x',5*unit);node.label.setAttribute('y',13*unit);
      node.artistLabel.setAttribute('x',5*unit);node.artistLabel.setAttribute('y',27*unit);
      Object.entries({x:0,y:0,width:width*unit,height:height*unit,rx:3*unit}).forEach(([k,v])=>node.labelBackdrop.setAttribute(k,v));
      reserved.push({x:x-6,y:y-6,w:width+12,h:height+12});
      labelsPlaced++;
    });
    root.dataset.visibleLabels=String(labelsPlaced);
  }

  function layout() {
    if(!nodes.every(n=>Array.isArray(n.position)&&n.position.every(Number.isFinite))) throw new Error('Build-time coordinates missing');
    const view=filterRelation==='style'?network.styleView:network.layout;worldWidth=view.width;worldHeight=view.height;
    Object.assign(camera,{x:0,y:0,width:worldWidth,height:worldHeight});
    svg.setAttribute('viewBox',`0 0 ${worldWidth} ${worldHeight}`);
    nodes.forEach(node=>{
      node.group=filterRelation==='style'?node.styleGroup:node.originalGroup;[node.x,node.y]=filterRelation==='style'?node.stylePosition:node.position;
      node.baseX=node.x;node.baseY=node.y;node.radius=node.radius||20;
      node.featured=network.featured.includes(node.id);
      node.phase=((Math.imul(node.id,1664525)+1013904223)>>>0)/4294967296*Math.PI*2;
    });
  }

  function edgePath(edge) {
    const a=edge.source,b=edge.target,dx=b.x-a.x,dy=b.y-a.y;
    return `M${a.x},${a.y} Q${(a.x+b.x)/2-dy*edge.curve},${(a.y+b.y)/2+dx*edge.curve} ${b.x},${b.y}`;
  }

  function drawEdge(edge, highlighted) {
    const g=el('g',{class:`edge-group${highlighted?' highlight':''}`,'data-edge':edge.id},$('edge-layer'));
    edge.curve=(edge.source.id%2?1:-1)*({sound:.06,album:.09,artist:.12,lyrics:.04}[edge.kind]||.065);
    const path=edgePath(edge);
    edge.path=el('path',{d:path,class:`network-edge ${edge.status!=='verified'?'candidate':''}`,stroke:groups.get(edge.source.group).color,'vector-effect':'non-scaling-stroke'},g);
    edge.hit=el('path',{d:path,class:'edge-hit',role:'button','aria-label':`${edge.source.song.name} 与 ${edge.target.song.name}：${kindNames[edge.kind]}`,'vector-effect':'non-scaling-stroke'},g);
    edge.hit.addEventListener('click',()=>{if(!suppressClick)selectConnection(edge.id);});
    edge.element=g;
  }

  function ensureCaption(node) {
    if(node.caption)return;
    const color=groups.get(node.group).color;
    node.leader=el('line',{class:'label-leader',stroke:color,'vector-effect':'non-scaling-stroke'},node.element);
    node.caption=el('g',{class:'node-caption'},node.element);
    node.labelBackdrop=el('rect',{class:'label-backdrop'},node.caption);
    node.label=el('text',{class:'node-label'},node.caption);
    node.label.textContent=node.song.name.length>25?node.song.name.slice(0,23)+'…':node.song.name;
    node.artistLabel=el('text',{class:'node-artist'},node.caption);
    node.artistLabel.textContent=node.song.artists.length>29?node.song.artists.slice(0,27)+'…':node.song.artists;
  }

  function drawGraph() {
    const defs=svg.querySelector('defs');
    [...groups.values()].forEach(group=>{
      groupLayers.set(group.id,el('g',{'data-region':group.id},$('node-layer')));
      if(group.background)return;
      const [cx,cy]=group.center;
      const gradient=el('radialGradient',{id:`wash-${group.id}`},defs);
      el('stop',{offset:'0%','stop-color':group.color,'stop-opacity':'.07'},gradient);
      el('stop',{offset:'100%','stop-color':group.color,'stop-opacity':'0'},gradient);
      const size=Math.max(220,Math.sqrt(nodes.filter(n=>n.group===group.id).length)*43);
      el('ellipse',{cx,cy,rx:size+130,ry:size+80,fill:`url(#wash-${group.id})`},$('group-halos'));
      const [x,y]=group.labelPosition;
      const label=el('text',{x,y,'text-anchor':'middle',class:'group-label'},$('group-labels'));label.textContent=group.name;
      const subtitle=el('text',{x,y:y+34,'text-anchor':'middle',class:'group-subtitle'},$('group-labels'));subtitle.textContent=group.english;
    });
    nodes.forEach(node=>{
      const color=groups.get(node.group).color;
      const g=el('g',{class:'node',transform:`translate(${node.x},${node.y})`,tabindex:'0',role:'button','aria-label':`${node.song.name}，${node.song.artists}`,'data-song':node.id},groupLayers.get(node.group));
      el('circle',{r:node.radius+8,fill:color,class:'halo'},g);
      el('circle',{r:node.radius,fill:'#182019',stroke:node.song.coverEdgeColor,class:'core','vector-effect':'non-scaling-stroke'},g);
      const clip=el('clipPath',{id:`clip-${node.id}`},defs);el('circle',{r:node.radius-.65},clip);
      node.image=el('image',{href:artwork(node.song,true),x:-node.radius+.65,y:-node.radius+.65,width:(node.radius-.65)*2,height:(node.radius-.65)*2,'clip-path':`url(#clip-${node.id})`,preserveAspectRatio:'xMidYMid meet'},g);
      node.highResolution=false;node.element=g;
      g.addEventListener('click',()=>{if(!suppressClick)selectSong(node.id);});
      g.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();selectSong(node.id);}});
      g.addEventListener('pointerenter',event=>{
        if(pointers.size)return;
        hoveredId=node.id;scheduleLabels();node.wantsLabel=true;node.showArtist=true;
        const tip=$('graph-tooltip');tip.innerHTML=`${escape(node.song.name)}<small>${escape(node.song.artists)}</small>`;tip.hidden=false;
        const rect=$('map-container').getBoundingClientRect();
        tip.style.left=`${Math.max(8,Math.min(rect.width-245,event.clientX-rect.left+16))}px`;
        tip.style.top=`${Math.max(45,Math.min(rect.height-90,event.clientY-rect.top-24))}px`;
      });
      g.addEventListener('pointerleave',()=>{hoveredId=null;node.wantsLabel=node.featured||node.id===selection||worldWidth/camera.width>2.2;node.showArtist=node.id===selection;$('graph-tooltip').hidden=true;scheduleLabels();});
      g.addEventListener('focus',()=>{hoveredId=node.id;node.wantsLabel=true;node.showArtist=true;centerOn(node);});
      g.addEventListener('blur',()=>{hoveredId=null;scheduleLabels();});
      node.image.addEventListener('error',()=>{if(!node.image.dataset.failed){node.image.dataset.failed='1';node.image.setAttribute('href',new URL('cover-fallback.svg',new URL(root.dataset.catalog,location.href)).href);}});
    });
  }

  function syncMotion() {
    if (!network || !nodes[0]?.element) return;
    const allowed=motionEnabled&&(!reducedMotion.matches||explicitMotion);
    const highlighted=selection!==null||selectedEdge!==null;
    const running=allowed&&!highlighted&&mode==='map'&&graphInView&&!document.hidden&&!pointers.size;
    root.dataset.motion=running?'running':allowed?'held':'paused';
    $('motion-toggle').setAttribute('aria-pressed',String(allowed));
    $('motion-toggle').textContent=allowed?'Ⅱ 暂停动态':'▷ 开启动态';
    $('motion-toggle').disabled=false;
    $('motion-toggle').title=reducedMotion.matches&&!explicitMotion?'系统偏好减少动态，默认静态；点击可手动开启':'开启或暂停星图动态';
    $('motion-status').textContent=running?'● 动态运行中':highlighted?'○ 高亮中 · 漂浮暂停':allowed?'○ 动态暂歇':'○ 静态';
    if (!running && frame!==null) { cancelAnimationFrame(frame);frame=null;lastFrame=0; }
    if (running && frame===null) { lastFrame=0;frame=requestAnimationFrame(animate); }
  }

  function animate(time) {
    if(root.dataset.motion!=='running'){frame=null;return;}
    if(lastFrame&&time-lastFrame<48){frame=requestAnimationFrame(animate);return;}
    motionTime+=lastFrame?Math.min(.15,(time-lastFrame)/1000):0;lastFrame=time;
    const offsets=new Map();
    [...groups.values()].forEach((group,index)=>{
      const phase=index*1.17, amplitude=network.layout.motionAmplitude||28;
      const x=Math.sin(motionTime*.65+phase)*amplitude,y=Math.cos(motionTime*.55+phase)*amplitude*.7;
      offsets.set(group.id,[x,y]);groupLayers.get(group.id).setAttribute('transform',`translate(${x},${y})`);
    });
    nodes.forEach(node=>{const [x,y]=offsets.get(node.group);node.x=node.baseX+x;node.y=node.baseY+y;});
    visibleEdges.forEach(edge=>{const d=edgePath(edge);edge.path.setAttribute('d',d);edge.hit.setAttribute('d',d);});
    if(time-lastLabels>900){lastLabels=time;scheduleLabels();}
    frame=requestAnimationFrame(animate);
  }

  function applyCamera() {
    svg.setAttribute('viewBox',`${camera.x} ${camera.y} ${camera.width} ${camera.height}`);
    $('zoom-level').textContent=`${Math.round(worldWidth/camera.width*100)}%`;
    updateGraph();
  }
  function zoom(factor,point={x:camera.x+camera.width/2,y:camera.y+camera.height/2}) {
    const width=Math.max(worldWidth/12,Math.min(worldWidth*1.5,camera.width/factor));
    const ratio=width/camera.width;
    camera.x=point.x-(point.x-camera.x)*ratio;camera.y=point.y-(point.y-camera.y)*ratio;
    camera.width=width;camera.height=width*worldHeight/worldWidth;
    applyCamera();
  }
  function worldPoint(clientX,clientY) {
    const point=svg.createSVGPoint();point.x=clientX;point.y=clientY;
    return point.matrixTransform(svg.getScreenCTM().inverse());
  }
  function centerOn(node) {
    camera.width=worldWidth/4;camera.height=camera.width*worldHeight/worldWidth;camera.x=node.x-camera.width/2;camera.y=node.y-camera.height/2;applyCamera();
  }

  function renderStyleFilters() {
    const search=$('style-search').value.trim().toLocaleLowerCase();
    let labels=[...styleById.values()].filter(s=>s.count>0&&(!search||`${s.name} ${s.english}`.toLocaleLowerCase().includes(search)));
    labels.sort((a,b)=>(a.id==='pending')-(b.id==='pending')||b.count-a.count||a.id.localeCompare(b.id));
    const shown=search||stylesExpanded?labels:labels.filter((s,i)=>i<14||selectedStyles.has(s.id));
    $('style-options').innerHTML=shown.map(s=>`<button type="button" data-style="${s.id}" class="${selectedStyles.has(s.id)?'active':''}" aria-pressed="${selectedStyles.has(s.id)}">${escape(s.name)} <small>${s.count}</small></button>`).join('')||'<span class="style-empty">没有匹配的风格</span>';
    $('style-expand').textContent=stylesExpanded?'收起标签 ↑':`全部 ${labels.length} 种标签 ↓`;
    $('style-selection').textContent=selectedStyles.size?`同时包含：${[...selectedStyles].map(id=>styleById.get(id).name).join(' + ')}`:'可以多选标签，寻找风格的交汇。';
    $('style-clear').hidden=!selectedStyles.size;
    $('style-panel').hidden=filterRelation!=='style';
  }

  function setRelation(next) {
    const changeLayout=(next==='style')!==(filterRelation==='style');
    filterRelation=next;
    document.querySelectorAll('[data-relation]').forEach(b=>{const active=b.dataset.relation===next;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
    if(changeLayout){
      filterGroup=null;selection=null;selectedEdge=null;selectedStyles.clear();
      groups=new Map((next==='style'?network.styleView.groups:network.groups).map(g=>[g.id,g]));
      if(frame!==null){cancelAnimationFrame(frame);frame=null;lastFrame=0;}
      groupLayers.clear();
      ['group-halos','edge-layer','group-labels','node-layer'].forEach(id=>$(id).replaceChildren());
      svg.querySelector('defs').replaceChildren();
      nodes.forEach(n=>{n.caption=null;n.captionOffset=null;});
      layout();drawGraph();
      $('legend').innerHTML=[...groups.values()].map(group=>`<button type="button" data-group="${group.id}" aria-pressed="false" style="--group-color:${group.color}"><i></i>${escape(group.name)}</button>`).join('');
      $('group-count').textContent=groups.size;
      $('zoom-level').textContent='100%';
      welcome();
    }
    renderStyleFilters();updateGraph();if(mode==='list')renderCatalog();
  }

  function bind() {
    $('style-search').addEventListener('input',renderStyleFilters);
    $('motion-toggle').addEventListener('click',()=>{const currentlyOn=motionEnabled&&(!reducedMotion.matches||explicitMotion);motionEnabled=!currentlyOn;explicitMotion=motionEnabled;syncMotion();});
    reducedMotion.addEventListener('change',syncMotion);
    document.addEventListener('visibilitychange',syncMotion);
    new IntersectionObserver(entries=>{graphInView=entries[0].isIntersecting;syncMotion();},{threshold:.05}).observe($('map-container'));
    new ResizeObserver(scheduleLabels).observe($('map-container'));
    document.fonts.ready.then(scheduleLabels);
    $('map-view').addEventListener('click',()=>setMode('map'));
    $('list-view').addEventListener('click',()=>setMode('list'));
    $('song-search').addEventListener('input',()=>{
      // Search covers the complete collection, including tracks outside the sample.
      setMode($('song-search').value.trim()?'list':'map');
    });
    document.addEventListener('keydown',event=>{
      if(event.key==='/'&&!['INPUT','TEXTAREA'].includes(document.activeElement.tagName)){event.preventDefault();$('song-search').focus();}
      if(event.key==='Escape'){$('graph-tooltip').hidden=true;welcome();}
    });
    $('about-toggle').addEventListener('click',()=>{const show=$('map-about').hidden;$('map-about').hidden=!show;$('about-toggle').setAttribute('aria-expanded',String(show));});
    $('legend').innerHTML=[...groups.values()].map(group=>`<button type="button" data-group="${group.id}" aria-pressed="false" style="--group-color:${group.color}"><i></i>${escape(group.name)}</button>`).join('');
    root.addEventListener('click',event=>{
      const songButton=event.target.closest('button[data-song]');if(songButton)selectSong(songButton.dataset.song,true);
      const edgeButton=event.target.closest('button[data-edge]');if(edgeButton)selectConnection(edgeButton.dataset.edge);
      if(event.target.closest('[data-close]'))welcome();
      if(event.target.closest('[data-clear]')){$('song-search').value='';filterGroup=null;selectedStyles.clear();renderStyleFilters();renderCatalog();updateGraph();}
      const styleButton=event.target.closest('[data-style]');
      if(styleButton){if(filterRelation!=='style')setRelation('style');const id=styleButton.dataset.style;selectedStyles.has(id)?selectedStyles.delete(id):selectedStyles.add(id);renderStyleFilters();updateGraph();if(mode==='list')renderCatalog();}
      if(event.target.closest('[data-styles-clear]')){selectedStyles.clear();renderStyleFilters();updateGraph();if(mode==='list')renderCatalog();}
      if(event.target.closest('[data-styles-expand]')){stylesExpanded=!stylesExpanded;renderStyleFilters();}
      const groupButton=event.target.closest('[data-group]');
      if(groupButton){filterGroup=filterGroup===groupButton.dataset.group?null:groupButton.dataset.group;updateGraph();if(mode==='list')renderCatalog();}
      const relationButton=event.target.closest('[data-relation]');
      if(relationButton)setRelation(relationButton.dataset.relation);
    });
    $('zoom-in').addEventListener('click',()=>zoom(1.25));
    $('zoom-out').addEventListener('click',()=>zoom(.8));
    $('zoom-reset').addEventListener('click',()=>{Object.assign(camera,{x:0,y:0,width:worldWidth,height:worldHeight});applyCamera();});
    svg.addEventListener('wheel',event=>{event.preventDefault();zoom(Math.exp(-event.deltaY*.0015),worldPoint(event.clientX,event.clientY));},{passive:false});
    svg.addEventListener('pointerdown',event=>{
      if(event.button!==0)return;
      pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
      syncMotion();
      $('graph-tooltip').hidden=true;
      // Gesture positions are client coordinates; the inverse SVG transform also handles letterboxing.
      const points=[...pointers.values()];
      const middle=points.length===2?{x:(points[0].x+points[1].x)/2,y:(points[0].y+points[1].y)/2}:points[0];
      gesture={camera:{...camera},start:middle,world:worldPoint(middle.x,middle.y),distance:points.length===2?Math.hypot(points[0].x-points[1].x,points[0].y-points[1].y):0};
      suppressClick=false;
    });
    svg.addEventListener('pointermove',event=>{
      if(!pointers.has(event.pointerId)||!gesture)return;
      pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
      const points=[...pointers.values()];
      const middle=points.length===2?{x:(points[0].x+points[1].x)/2,y:(points[0].y+points[1].y)/2}:points[0];
      const moved=Math.hypot(middle.x-gesture.start.x,middle.y-gesture.start.y);
      if(moved>4||points.length===2){suppressClick=true;svg.setPointerCapture(event.pointerId);svg.classList.add('dragging');}
      Object.assign(camera,gesture.camera);applyCamera();
      if(points.length===2&&gesture.distance){
        const distance=Math.hypot(points[0].x-points[1].x,points[0].y-points[1].y);
        zoom(distance/gesture.distance,gesture.world);
      }
      const current=worldPoint(middle.x,middle.y);
      camera.x+=gesture.world.x-current.x;camera.y+=gesture.world.y-current.y;applyCamera();
    });
    const endPointer=event=>{
      pointers.delete(event.pointerId);
      svg.classList.remove('dragging');
      if(pointers.size){const point=[...pointers.values()][0];gesture={camera:{...camera},start:point,world:worldPoint(point.x,point.y),distance:0};}
      else{gesture=null;setTimeout(()=>{suppressClick=false;},0);}
      syncMotion();
    };
    svg.addEventListener('pointerup',endPointer);svg.addEventListener('pointercancel',endPointer);
    // Broken covers get a quiet local fallback instead of repeated network retries.
    root.addEventListener('error',event=>{
      if(event.target.tagName==='IMG'&&!event.target.dataset.failed){event.target.dataset.failed='1';event.target.src=new URL('cover-fallback.svg',new URL(root.dataset.catalog,location.href)).href;}
    },true);
  }

  async function init() {
    try {
      const responses=await Promise.all([fetch(root.dataset.catalog),fetch(root.dataset.network)]);
      if(responses.some(r=>!r.ok))throw new Error('Music data unavailable');
      [songs,network]=await Promise.all(responses.map(r=>r.json()));
      songById=new Map(songs.map(s=>[s.id,s]));
      groups=new Map(network.groups.map(g=>[g.id,g]));
      nodes=network.nodes.map(n=>({...n,originalGroup:n.group,song:songById.get(n.id)}));
      styleById=new Map(network.styleTaxonomy.map(s=>[s.id,s]));
      groups=new Map(network.styleView.groups.map(g=>[g.id,g]));
      nodeById=new Map(nodes.map(n=>[n.id,n]));
      links=network.edges.map(e=>({...e,source:nodeById.get(e.source),target:nodeById.get(e.target)}));
      $('total-count').textContent=songs.length;$('sample-count').textContent=nodes.length;$('group-count').textContent=groups.size;
      $('sample-note').textContent=`${nodes.length} 首全量收藏 · ${network.styleCoverage.labelled} 首有来源的风格标签 · ${network.styleCoverage.pending} 首风格待确认 · ${network.styleCoverage.labels} 种标签。艺人风格用于导航推定，未完成逐首试听确认。`;
      layout();drawGraph();bind();renderStyleFilters();welcome();
    } catch(error) {
      console.error(error);
      $('map-status').textContent='星图暂时未能加载';
      $('detail-panel').innerHTML='<p class="load-error">音乐数据暂时未能加载，请刷新重试。<br>你也可以<a href="https://music.163.com/playlist?id=8114560070">直接查看网易云歌单 ↗</a>。</p>';
    }
  }
  init();
})();
