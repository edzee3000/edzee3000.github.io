(() => {
  'use strict';
  const root = document.documentElement;
  const HF = 'https://huggingface.co/datasets/edzee3000/LiveVideoPhoto/resolve/main/';
  const url = (folder, file) => HF + folder.split('/').map(encodeURIComponent).join('/') + '/' + encodeURIComponent(file);
  const themeButton = document.getElementById('theme-toggle');
  function setTheme(theme) {
    root.dataset.theme = theme;
    const light = theme === 'light';
    themeButton.setAttribute('aria-pressed', String(light));
    themeButton.setAttribute('aria-label', light ? '切换到深色模式' : '切换到浅色模式');
    themeButton.title = themeButton.getAttribute('aria-label');
    themeButton.querySelector('.theme-label').textContent = light ? 'Dark mode' : 'Light mode';
    document.getElementById('theme-color').content = light ? '#f3efe7' : '#0d1118';
  }
  setTheme(root.dataset.theme === 'light' ? 'light' : 'dark');
  themeButton.addEventListener('click', () => {
    const theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(theme);
    try { localStorage.setItem('live-theme', theme); } catch (e) { /* Storage may be disabled. */ }
  });

  document.querySelectorAll('a[data-folder][data-file]').forEach(a => { a.href = url(a.dataset.folder, a.dataset.file); });
  document.querySelectorAll('img[data-folder][data-file]').forEach(img => {
    const fail = () => {
      if (img.dataset.fallbackFolder && !img.dataset.fallbackUsed) {
        img.dataset.fallbackUsed = 'true';
        img.src = url(img.dataset.fallbackFolder, img.dataset.file);
      } else img.closest('.media-frame')?.classList.add('image-failed');
    };
    img.addEventListener('error', fail);
    const encoded = url(img.dataset.folder, img.dataset.file);
    if (!img.hasAttribute('data-local-preview') && img.src !== encoded) img.src = encoded;
    if (img.complete && img.naturalWidth === 0) fail();
  });

  const sections = Array.from(document.querySelectorAll('.show-section'));
  const indexLinks = Array.from(document.querySelectorAll('.index-link'));
  const search = document.getElementById('archive-search');
  const yearButtons = Array.from(document.querySelectorAll('.year-filter'));
  let year = 'all';
  let scrollScheduled = false;
  function updateIndex() {
    const visible = sections.filter(section => !section.hidden);
    let active = visible[0];
    for (const section of visible) if (section.getBoundingClientRect().top <= 170) active = section;
    indexLinks.forEach(link => {
      if (active && link.dataset.show === active.id) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
    scrollScheduled = false;
  }
  function filter() {
    const query = search.value.trim().toLocaleLowerCase();
    let count = 0;
    sections.forEach(section => {
      const matches = (year === 'all' || section.dataset.year === year) && section.dataset.search.toLocaleLowerCase().includes(query);
      section.hidden = !matches;
      const link = indexLinks.find(item => item.dataset.show === section.id);
      if (link) link.hidden = !matches;
      if (matches) count++;
    });
    document.getElementById('empty-state').hidden = count > 0;
    document.getElementById('index-count').textContent = count + ' ENTRIES';
    document.getElementById('filter-status').textContent = '显示 ' + count + ' 场演出';
    yearButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.year === year)));
    updateIndex();
  }
  search.addEventListener('input', filter);
  yearButtons.forEach(button => button.addEventListener('click', () => { year = button.dataset.year; filter(); }));
  document.getElementById('clear-filters').addEventListener('click', () => { year = 'all'; search.value = ''; filter(); search.focus(); });
  window.addEventListener('scroll', () => { if (!scrollScheduled) { scrollScheduled = true; requestAnimationFrame(updateIndex); } }, { passive: true });
  updateIndex();

  document.querySelectorAll('.expand-button').forEach(button => button.addEventListener('click', () => {
    const grid = document.getElementById(button.getAttribute('aria-controls'));
    const expanded = grid.classList.toggle('is-expanded');
    button.setAttribute('aria-expanded', String(expanded));
    button.querySelector('.expand-label').textContent = expanded ? 'Show less' : 'View all ' + button.dataset.total + ' ' + button.dataset.type;
    button.querySelector('.expand-symbol').textContent = expanded ? '−' : '+';
    if (!expanded) grid.scrollIntoView({ block: 'start', behavior: 'instant' });
    updateIndex();
  }));

  const dialog = document.getElementById('media-dialog');
  const video = document.getElementById('dialog-video');
  const photo = document.getElementById('dialog-photo');
  const message = document.getElementById('media-message');
  const title = document.getElementById('dialog-title');
  const counter = document.getElementById('dialog-counter');
  const original = document.getElementById('dialog-original');
  let cards = [], position = 0, kind = 'video', artist = '', opener = null, revision = 0;
  function stopVideo() { video.pause(); video.removeAttribute('src'); video.removeAttribute('poster'); video.load(); }
  function displayMedia() {
    const card = cards[position];
    if (!card) return;
    stopVideo();
    const current = ++revision;
    photo.hidden = true;
    photo.removeAttribute('src');
    video.hidden = kind !== 'video';
    title.textContent = (card.dataset.title || artist) + ' / ' + (kind === 'video' ? 'Live film ' : 'Photograph ') + String(position + 1).padStart(2, '0');
    counter.textContent = (position + 1) + ' / ' + cards.length;
    original.href = card.href;
    document.getElementById('dialog-prev').disabled = cards.length < 2;
    document.getElementById('dialog-next').disabled = cards.length < 2;
    message.textContent = kind === 'video' ? '正在加载原始现场视频…' : '正在加载照片…';
    if (kind === 'video') {
      const thumbnail = card.querySelector('img');
      if (thumbnail) video.poster = thumbnail.currentSrc || thumbnail.src;
      video.src = card.href;
      video.play().catch(() => { if (current === revision && dialog.open && !video.error) message.textContent = '点击播放开始观看。'; });
    } else {
      photo.alt = (card.dataset.title || artist) + '，现场照片 ' + (position + 1);
      photo.onload = () => { if (current === revision) { photo.hidden = false; message.textContent = ''; } };
      photo.onerror = () => { if (current === revision) message.textContent = '照片暂时无法加载，可通过 Open original 查看。'; };
      photo.src = card.href;
    }
  }
  function openMedia(list, card, type, label) {
    cards = list;
    position = cards.indexOf(card);
    if (position < 0) return;
    kind = type; artist = label; opener = card;
    dialog.showModal();
    document.body.classList.add('modal-open');
    displayMedia();
  }
  const modifiedClick = event => event.ctrlKey || event.metaKey || event.shiftKey || event.altKey;
  document.querySelectorAll('.media-grid').forEach(grid => grid.addEventListener('click', event => {
    const card = event.target.closest('.media-card');
    if (!card || modifiedClick(event)) return;
    event.preventDefault();
    openMedia(Array.from(grid.querySelectorAll('.media-card')), card, grid.dataset.kind, grid.dataset.title);
  }));
  const editorial = Array.from(document.querySelectorAll('.editorial-photo'));
  editorial.forEach(card => card.addEventListener('click', event => {
    if (modifiedClick(event)) return;
    event.preventDefault(); openMedia(editorial, card, 'photo', 'Field notes');
  }));
  document.getElementById('dialog-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener('close', () => {
    revision++; stopVideo(); photo.removeAttribute('src');
    document.body.classList.remove('modal-open'); opener?.focus({ preventScroll: true });
  });
  function move(delta) { position = (position + delta + cards.length) % cards.length; displayMedia(); }
  document.getElementById('dialog-prev').addEventListener('click', () => move(-1));
  document.getElementById('dialog-next').addEventListener('click', () => move(1));
  dialog.addEventListener('keydown', event => {
    if (event.target === video) return;
    if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); move(event.key === 'ArrowLeft' ? -1 : 1); }
  });
  video.addEventListener('playing', () => { message.textContent = ''; });
  video.addEventListener('waiting', () => { if (dialog.open && kind === 'video') message.textContent = '视频缓冲中…'; });
  video.addEventListener('error', () => { if (dialog.open && video.hasAttribute('src')) message.textContent = '视频暂时无法播放，可通过 Open original 在新窗口打开。'; });
})();
