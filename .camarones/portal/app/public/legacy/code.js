'use strict';
// Code: graphify's graph folded by the server into modules → files (lib/codemap.py), drawn three ways:
// the module map, one module's files, and one file with what it uses and what uses it.

const VIS = 'vendor/vis-network@9.1.6/standalone/umd/vis-network.min.js';
let visReady = null;
let CODEMAP = { repo: '', map: null };
let network = null;

function loadVis() {
  visReady ||= new Promise((resolve) => {
    if (window.vis?.Network) return resolve(true);
    const s = document.createElement('script');
    s.src = VIS;
    s.onload = () => resolve(!!window.vis?.Network);
    s.onerror = () => resolve(false);
    document.head.append(s);
  });
  return visReady;
}

async function codeMap(repo) {
  if (CODEMAP.repo !== repo) CODEMAP = { repo, map: await api('codemap', { repo }) };
  return CODEMAP.map;
}

const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const GROUP_HUES = [24, 205, 145, 280, 340, 50, 180, 100, 0, 230, 310, 70];
const groupColor = (g, soft) => `hsl(${GROUP_HUES[g % GROUP_HUES.length]} ${soft ? '35%' : '70%'} ${isDark() ? (soft ? '28%' : '45%') : (soft ? '92%' : '55%')})`;

function codeSide(repo) {
  const repos = T.codeMaps || [];
  $('#side-head').innerHTML = `<div class="side-title">🧩 ${esc(t('codeTab'))}</div>`;
  $('#tree').innerHTML = `<div class="group">${repos.map((r) =>
    `<a href="#/code/${esc(r)}" class="${r === repo ? 'on' : ''}">${esc(r)}</a>`).join('') || `<p class="muted small">${esc(t('noCodeMap'))}</p>`}</div>`
    + (T.codeGraphs.length ? `<div class="group"><div class="group-title">${esc(t('explore'))}</div>
      <a href="#/code/${esc(repo || 'all')}/graph">🕸️ ${esc(t('fullGraph'))}</a></div>` : '');
}

async function showCodeTab(rest) {
  const [repoArg = '', mode = '', idArg = '', ...subParts] = rest.split('/');
  const sub = subParts.filter(Boolean).join('/');
  const repo = repoArg || (T.codeMaps || [])[0] || (T.codeGraphs.includes('all') ? 'all' : '');
  drawChrome('code', { viewer: true });
  codeSide(repo);
  if (mode === 'graph' || (repo && !(T.codeMaps || []).includes(repo))) return showCode(repo);   // graphify's own page
  if (!repo) {
    $('#main').innerHTML = `<div class="page"><h1>🧩 ${esc(t('codeTab'))}</h1><p class="muted">${esc(t('noCodeMap'))}</p></div>`;
    return;
  }
  const m = await codeMap(repo);
  const id = Number(idArg);
  const view = mode === 'f' && m.files[id] ? 'file' : mode === 'g' && m.groups[id] ? 'group' : 'map';
  if (view === 'group') {                  // a level with a single folder and no files of its own: open the folder
    const files = inSub(m, id, sub);
    const segs = new Set(files.map(([, f]) => nextSeg(f, sub)));
    if (segs.size === 1 && !segs.has('')) return location.replace(subHref(repo, id, sub ? `${sub}/${[...segs][0]}` : [...segs][0]));
  }
  $('#main').innerHTML = `<div class="codemap">
    <div class="code-head">
      <div><div class="crumbs">${codeCrumbs(repo, m, view, id, sub)}</div>
        <h1>${esc(view === 'file' ? m.files[id].label : view === 'group' ? m.groups[id].label + (sub ? '/' + sub : '') : repo)}</h1>
        <div class="meta">${view === 'file' ? `<code class="file">${esc(m.files[id].path)}</code>`
          : `<span class="pill">${esc(t('statFiles', { n: view === 'group' ? inSub(m, id, sub).length : m.stats.files }))}</span>
             ${view === 'map' ? `<span class="pill">${esc(t('statModules', { n: m.stats.groups }))}</span>` : ''}`}
          <span class="muted small">${esc(t('codeHint'))}</span></div></div>
      <div class="code-search"><input id="cs-q" type="search" placeholder="${esc(t('findClass'))}" autocomplete="off"><div id="cs-list" class="cs-list" hidden></div></div>
    </div>
    <div class="code-body"><div id="cm-canvas" class="cm-canvas"></div><aside id="cm-info" class="cm-info"></aside></div></div>`;
  bindCodeSearch(repo, m);
  $('#cm-info').innerHTML = codeInfo(repo, m, view, id, sub);
  if (!(await loadVis())) {
    $('#cm-canvas').innerHTML = `<p class="muted pad">${esc(t('noVis'))}</p>`;
    return;
  }
  drawCodeGraph(repo, m, view, id, sub);
}

const within = (f, sub) => !sub || f.sub === sub || f.sub.startsWith(sub + '/');
const inSub = (m, g, sub) => m.files.map((f, i) => [i, f]).filter(([, f]) => f.group === g && within(f, sub))
  .sort(([, a], [, b]) => (b.deg[0] + b.deg[1]) - (a.deg[0] + a.deg[1]));
const nextSeg = (f, sub) => (sub ? f.sub.slice(sub.length + 1) : f.sub).split('/')[0];
const subHref = (repo, g, sub) => `#/code/${repo}/g/${g}${sub ? '/' + sub : ''}`;

function codeCrumbs(repo, m, view, id, sub) {
  const parts = [`<a href="#/code/${esc(repo)}">${esc(repo)}</a>`];
  const g = view === 'file' ? m.files[id].group : id;
  if (view === 'map') return parts.join('');
  parts.push(`<a href="${esc(subHref(repo, g, ''))}">${esc(m.groups[g].label)}</a>`);
  const segs = (view === 'file' ? m.files[id].sub : sub).split('/').filter(Boolean);
  segs.forEach((seg, i) => parts.push(`<a href="${esc(subHref(repo, g, segs.slice(0, i + 1).join('/')))}">${esc(seg)}</a>`));
  return parts.join('<span class="sep">›</span>');
}

const fileLink = (repo, m, i, w) => `<a href="#/code/${esc(repo)}/f/${i}" title="${esc(m.files[i].path)}">
  <span class="swatch" style="background:${groupColor(m.files[i].group)}"></span>${esc(m.files[i].label)}${w ? ` <span class="count">${w}</span>` : ''}</a>`;

function codeInfo(repo, m, view, id, sub) {
  if (view === 'file') {
    const f = m.files[id];
    const list = (rows, title) => `<h3>${esc(title)} <span class="count">${rows.length}</span></h3>
      ${rows.map(([i, w]) => fileLink(repo, m, i, w)).join('') || `<p class="muted small">${esc(t('none'))}</p>`}`;
    return list(f.out, t('uses')) + list(f.in, t('usedBy'));
  }
  if (view === 'group') {
    const files = inSub(m, id, sub);
    const segs = [...new Set(files.map(([, f]) => nextSeg(f, sub)).filter(Boolean))].sort();
    return (segs.length ? `<h3>${esc(t('packages'))} <span class="count">${segs.length}</span></h3>${segs.map((seg) =>
      `<a href="${esc(subHref(repo, id, sub ? sub + '/' + seg : seg))}">📁 ${esc(seg)} <span class="count">${files.filter(([, f]) => nextSeg(f, sub) === seg).length}</span></a>`).join('')}` : '')
      + `<h3>${esc(t('filesIn'))} <span class="count">${files.length}</span></h3>${files.map(([i]) => fileLink(repo, m, i)).join('')}`;
  }
  return `<h3>${esc(t('coreFiles'))}</h3><p class="muted small">${esc(t('coreHelp'))}</p>${m.core.map((i) => fileLink(repo, m, i)).join('')}
    <h3>${esc(t('modules'))}</h3>${m.groups.slice().sort((a, b) => b.files - a.files).map((g) =>
      `<a href="#/code/${esc(repo)}/g/${g.id}"><span class="swatch" style="background:${groupColor(g.id)}"></span>${esc(g.label)} <span class="count">${g.files}</span></a>`).join('')}`;
}

function bindCodeSearch(repo, m) {
  const input = $('#cs-q');
  const list = $('#cs-list');
  input.oninput = () => {
    const q = input.value.trim().toLowerCase();
    const hits = q.length < 2 ? [] : m.files.map((f, i) => [i, f])
      .filter(([, f]) => f.label.toLowerCase().includes(q) || f.path.toLowerCase().includes(q))
      .sort(([, a], [, b]) => (a.label.toLowerCase().startsWith(q) ? 0 : 1) - (b.label.toLowerCase().startsWith(q) ? 0 : 1)
        || (b.deg[0] + b.deg[1]) - (a.deg[0] + a.deg[1])).slice(0, 10);
    list.hidden = !hits.length;
    list.innerHTML = hits.map(([i, f]) => `<a href="#/code/${esc(repo)}/f/${i}"><b>${esc(f.label)}</b><span class="muted small">${esc(m.groups[f.group].label)}</span></a>`).join('');
  };
  input.onkeydown = (e) => { if (e.key === 'Enter') list.querySelector('a')?.click(); if (e.key === 'Escape') { input.value = ''; list.hidden = true; } };
}

// ---------- graph drawing ----------
const SPLIT_AT = 18;     // a package with more files than this is shown as its sub-packages first

function drawCodeGraph(repo, m, view, id, sub) {
  const ink = css('--ink'), muted = css('--muted'), line = css('--line'), raise = css('--raise'), accent = css('--accent');
  const nodes = [];
  const weights = new Map();
  const font = { color: ink, size: 15, face: 'system-ui, -apple-system, Segoe UI, sans-serif', multi: 'md' };
  const box = (nid, label, g, extra = {}) => nodes.push({ id: nid, label, shape: 'box', margin: 10, font,
    color: { background: groupColor(g, true), border: groupColor(g), highlight: { background: groupColor(g, true), border: accent },
             hover: { background: groupColor(g, true), border: accent } }, borderWidth: 1.5, ...extra });
  const link = (a, b, w, dashed = false) => {
    if (a === undefined || b === undefined || a === b) return;
    const k = `${a}|${b}|${dashed}`;
    weights.set(k, (weights.get(k) || 0) + w);
  };
  const outside = (g) => {
    const nid = `g${g}`;
    if (!nodes.some((n) => n.id === nid)) nodes.push({ id: nid, label: `↗ ${m.groups[g].label}`, shape: 'box', margin: 8,
      font: { ...font, color: muted, size: 13 }, shapeProperties: { borderDashes: [4, 3] }, color: { background: raise, border: line } });
    return nid;
  };

  if (view === 'map') {
    const max = Math.max(1, ...m.groups.map((g) => g.files));
    m.groups.forEach((g) => box(`g${g.id}`, `*${g.label}*\n${t('statFiles', { n: g.files })}`, g.id,
      { borderWidth: 2, font: { ...font, size: 14 + Math.round(10 * g.files / max) } }));
    m.links.forEach((l) => link(`g${l.s}`, `g${l.t}`, l.w));
  } else if (view === 'group') {
    const files = inSub(m, id, sub);
    const segs = new Set(files.map(([, f]) => nextSeg(f, sub)).filter(Boolean));
    const split = files.length > SPLIT_AT && segs.size >= 2;
    const nodeOf = new Map();
    if (split) {
      for (const seg of segs) {
        const n = files.filter(([, f]) => nextSeg(f, sub) === seg).length;
        box(`s${seg}`, `📁 *${seg}*\n${t('statFiles', { n })}`, id, { borderWidth: 2 });
      }
    }
    files.forEach(([i, f]) => {
      const seg = nextSeg(f, sub);
      if (split && seg) nodeOf.set(i, `s${seg}`);
    });
    files.filter(([i]) => !nodeOf.has(i)).slice(0, split ? 12 : 30).forEach(([i, f]) => {
      nodeOf.set(i, `f${i}`);
      box(`f${i}`, f.label, f.group);
    });
    files.forEach(([i, f]) => {
      const from = nodeOf.get(i);
      if (!from) return;
      for (const [j, w] of f.out) {
        const tf = m.files[j];
        if (nodeOf.has(j)) link(from, nodeOf.get(j), w);
        else if (tf.group !== id) link(from, outside(tf.group), w, true);
      }
    });
  } else {
    const f = m.files[id];
    box(`f${id}`, `*${f.label}*`, f.group, { borderWidth: 3, font: { ...font, size: 18 }, color: { background: groupColor(f.group), border: accent } });
    const seen = new Set([id]);
    const add = (j) => { if (!seen.has(j)) { seen.add(j); box(`f${j}`, m.files[j].label, m.files[j].group); } };
    for (const [j, w] of f.in) { add(j); link(`f${j}`, `f${id}`, w); }
    for (const [j, w] of f.out) { add(j); link(`f${id}`, `f${j}`, w); }
  }

  const edges = [...weights].map(([k, w]) => {
    const [from, to, dashed] = k.split('|');
    return { from, to, value: w, title: String(w), dashes: dashed === 'true', arrows: { to: { enabled: true, scaleFactor: 0.6 } },
      color: { color: muted, opacity: 0.5, highlight: accent, hover: accent } };
  });
  network?.destroy();
  const layered = view !== 'group';      // module map top-down, a file between its users and what it uses; a package as a cloud
  network = new vis.Network($('#cm-canvas'), { nodes, edges }, {
    layout: layered ? { hierarchical: { enabled: true, direction: view === 'map' ? 'UD' : 'LR', sortMethod: 'directed', shakeTowards: 'roots',
      levelSeparation: view === 'map' ? 130 : 300, nodeSpacing: view === 'map' ? 180 : 60, treeSpacing: 120 } } : { improvedLayout: true },
    physics: layered ? false : { solver: 'forceAtlas2Based', forceAtlas2Based: { gravitationalConstant: -120, springLength: 160, avoidOverlap: 0.8 },
      stabilization: { iterations: 300, fit: true } },
    edges: { scaling: { min: 1, max: 7 }, smooth: layered
      ? { type: 'cubicBezier', forceDirection: view === 'map' ? 'vertical' : 'horizontal', roundness: 0.5 } : { type: 'continuous' } },
    interaction: { hover: true, tooltipDelay: 150, zoomView: true, dragView: true, keyboard: false },
  });
  if (layered) network.once('afterDrawing', () => network.fit({ animation: false }));
  else network.once('stabilizationIterationsDone', () => { network.setOptions({ physics: false }); network.fit({ animation: { duration: 250 } }); });
  network.on('click', (p) => {
    const n = p.nodes[0];
    if (!n) return;
    if (n[0] === 's') location.hash = subHref(repo, id, sub ? `${sub}/${n.slice(1)}` : n.slice(1));
    else location.hash = `#/code/${repo}/${n[0] === 'g' ? 'g' : 'f'}/${n.slice(1)}`;
  });
}
