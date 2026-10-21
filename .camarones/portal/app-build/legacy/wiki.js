'use strict';
// OpenWiki as its own space: one navigable wiki per repo (own menu, backlinks), separate from the Docs tree.

function wikiSide(active, page) {
  const rows = (WIKIS || []).filter((w) => w.pages);
  const w = rows.find((r) => r.repo === active);
  $('#side-head').innerHTML = `<div class="side-title">📚 ${esc(t('wikis'))}</div>
    ${rows.length > 1 && w ? `<select id="w-repo" aria-label="repo">${rows.map((r) =>
      `<option value="${esc(r.repo)}" ${r.repo === active ? 'selected' : ''}>${esc(r.repo)}</option>`).join('')}</select>` : ''}`;
  $('#tree').innerHTML = w
    ? `<div class="group"><a href="#/wikis" class="back">← ${esc(t('allWikis'))}</a></div>
       <div class="group"><a href="#/wiki/${esc(w.repo)}" class="${page === 'graph' ? 'on' : ''}">🕸️ ${esc(t('graph'))}</a></div>
       <div class="group"><div class="group-title">${esc(w.repo)} · ${esc(t('wikiPages'))}</div>
       ${w.nav.pages.map((p) => `<a href="${esc(hrefFor(p.path))}" class="${p.path === page ? 'on' : ''}">${esc(p.title)}</a>`).join('')}</div>`
    : `<div class="group">${rows.map((r) => `<a href="#/wiki/${esc(r.repo)}" class="${r.repo === active ? 'on' : ''}">${esc(r.repo)}
        <span class="count">${r.pages}</span></a>`).join('') || `<p class="muted small">${esc(t('noWiki'))}</p>`}</div>`;
  $('#w-repo')?.addEventListener('change', (e) => { location.hash = `#/wiki/${e.target.value}`; });
}

async function showWiki(repo, rel, anchor) {
  const rows = await loadWikis();
  const w = rows.find((r) => r.repo === repo);
  const nav = w?.nav || { home: null, pages: [], backlinks: {} };
  const path = rel ? `repos/${repo}/${rel}` : nav.home;
  drawChrome('wikis');
  wikiSide(repo, path);
  if (!path || !BY_PATH[path]) {
    drawToc(null);
    $('#main').innerHTML = `<div class="page"><div class="crumbs"><a href="#/wikis">${esc(t('wikis'))}</a> › ${esc(repo)}</div>
      <h1>${esc(repo)}</h1><p class="muted">${esc(path ? t('notFound') : t('noWikiPages'))}</p></div>`;
    return;
  }
  const back = nav.backlinks[path] || [];
  const title = (p) => nav.pages.find((x) => x.path === p)?.title || p.split('/').pop();
  await showPage(path, anchor, {
    crumbs: [[`#/wikis`, t('wikis')], [`#/wiki/${repo}`, repo]],
    order: nav.pages.map((p) => p.path),
    extra: `<a class="button ghost small" href="#/wiki/${esc(repo)}">🕸️ ${esc(t('graph'))}</a>`,
    banner: w.old ? `<div class="banner">${esc(t('wikiOld'))} <a href="#/wikis/">${esc(t('wikis'))} →</a></div>` : '',
    after: back.length ? `<div class="box backlinks"><b>${esc(t('linkedFrom'))}</b><ul class="list">${back.map((p) =>
      `<li><a href="${esc(hrefFor(p))}">${esc(title(p))}</a></li>`).join('')}</ul></div>` : '',
  });
}

// A wiki opens on OpenWiki's own visualizer (page graph + reader); live mode builds it first when missing or stale.
async function showWikiGraph(repo) {
  const w = (await loadWikis()).find((r) => r.repo === repo);
  drawChrome('wikis', { viewer: true, bare: true });     // the visualizer brings its own page list
  wikiSide(repo, 'graph');
  if (!w?.pages) {
    $('#main').innerHTML = `<div class="page"><div class="crumbs"><a href="#/wikis">${esc(t('wikis'))}</a> › ${esc(repo)}</div>
      <h1>${esc(repo)}</h1><p class="muted">${esc(t('noWikiPages'))}</p></div>`;
    return;
  }
  const src = `wiki-graph/${encodeURIComponent(repo)}/`;
  const bar = (state, rebuild) => viewerBar([`<b>📚 ${esc(repo)}</b>`, state,
    `<a href="${esc(hrefFor(w.nav.home))}">📄 ${esc(t('readPages'))}</a>`,
    w.graph ? `<a href="${src}" target="_blank" rel="noopener">${esc(t('openTab'))} ↗</a>` : ''], rebuild);
  const oldNote = w.old ? `<div class="banner flush">${esc(t('wikiOld'))} <a href="#/wikis/">${esc(t('wikis'))} →</a></div>` : '';
  if (w.graph && (STATIC || !w.graphStale)) {
    $('#main').innerHTML = oldNote + bar(`<span class="muted small">${esc(t('pages', { n: w.pages }))}</span>`, t('rebuild'))
      + `<iframe class="viewer" src="${src}" title="wiki graph"></iframe>`;
    bindBuild('wiki-graph', repo, () => { WIKIS = null; route(); });
    return;
  }
  if (STATIC) return location.replace(hrefFor(w.nav.home));
  $('#main').innerHTML = bar(`<span class="muted small">${esc(t('graphBuilding'))}</span>`, '');
  startBuild('wiki-graph', repo, {}, $('#v-log'), (j) => {
    WIKIS = null;
    if (j.status === 'done') route();
    else $('#main .vbar span').textContent = t('graphFailed');
  });
}

async function showWikis(open) {
  drawChrome('wikis');
  drawToc(null);
  const rows = await loadWikis();
  wikiSide('', '');
  const engines = T.engines || [];
  const engSel = engines.length > 1 ? `<select class="w-eng">${engines.map((e) => `<option>${esc(e)}</option>`).join('')}</select>` : '';
  $('#main').innerHTML = `<div class="page wide"><h1>📚 ${esc(t('wikis'))} <span class="muted small">OpenWiki</span></h1>
    <p class="lead">${esc(t('wikisHelp'))}</p>
    ${!STATIC && !engines.length ? `<div class="banner">${esc(t('noEngine'))}</div>` : ''}
    <div class="cards">${rows.map((w) => `<div class="card ${w.repo === open ? 'open' : ''}" data-repo="${esc(w.repo)}">
      <div class="card-h">${w.pages ? `<a href="#/wiki/${esc(w.repo)}"><b>${esc(w.repo)}</b></a>` : `<b>${esc(w.repo)}</b>`}
        <span class="muted small">${w.pages ? esc(t('pages', { n: w.pages })) + ' · ' + esc(t('updated', { when: ago(w.at) })) : esc(w.cloned ? t('noWiki') : t('notCloned'))}</span>
        ${w.stale ? `<span class="warn small">⚠️ ${esc(t('stale'))}</span>` : ''}
        ${w.unit ? `<span class="chip">${esc(t('unit'))}: ${esc(w.unit)}</span>` : ''}</div>
      <div class="row">
        ${w.pages ? `<a class="button small" href="#/wiki/${esc(w.repo)}">🕸️ ${esc(t('graph'))}</a>
          <a class="button ghost small" href="${esc(hrefFor(w.nav.home))}">📄 ${esc(t('readPages'))}</a>` : ''}
        ${!STATIC && !w.chosen && !w.pages ? `<span class="muted small">${esc(t('notChosen'))}</span>` : ''}
        ${!STATIC && w.chosen && !w.ready ? `<span class="muted small">${esc(t('needBrief'))}</span>` : ''}
        ${!STATIC && engines.length && w.cloned && (w.chosen || w.pages) && w.ready ? `<button class="ghost small w-gen" type="button">${esc(w.pages ? t('update') : t('generate'))}</button>${engSel ? ` ${esc(t('via'))} ${engSel}` : ` <span class="muted small">${esc(t('via'))} ${esc(engines[0])}</span>`}` : ''}
      </div>
      ${w.old ? `<p class="warn small">${esc(t('wikiOld'))}</p>` : ''}
      <pre class="joblog" hidden></pre></div>`).join('')}</div></div>`;
  $$('#main .card').forEach((card) => {
    const repo = card.dataset.repo;
    card.querySelector('.w-gen')?.addEventListener('click', async (e) => {
      e.target.disabled = true;
      const engine = card.querySelector('.w-eng')?.value || '';
      try {
        watchJob(await api('wiki', {}, { repo, engine }), card.querySelector('.joblog'), async (j) => {
          await loadTree();
          if (j.status === 'done' && location.hash.startsWith('#/wikis')) showWikis(repo); else e.target.disabled = false;
        });
      } catch (err) { toast(err.message); e.target.disabled = false; }
    });
  });
  if (!STATIC) {       // reattach to a wiki run started earlier (from this page or another tab)
    const jobs = await api('jobs');
    for (const j of jobs.filter((x) => x.kind === 'wiki' && x.status === 'running')) {
      const card = $$('#main .card').find((c) => j.label.endsWith(' ' + c.dataset.repo));
      if (card) {
        card.querySelector('.w-gen')?.setAttribute('disabled', '');
        watchJob(j, card.querySelector('.joblog'), async (r) => { if (r.status === 'done') { await loadTree(); showWikis(card.dataset.repo); } });
      }
    }
  }
}
