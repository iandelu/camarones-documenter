'use strict';
// Architecture: a gallery of the model's C4 views (interactive web component), the full LikeC4 explorer and the code graph.

const VIEW_GROUPS = ['system', 'element', 'dynamic', 'deployment'];
const viewGroup = (v) => (v.id === 'index' ? 'system' : v.kind);
const defaultView = () => (T.views.find((v) => v.id === 'index') || T.views[0])?.id || '';

function viewerBar(parts, rebuild) {
  return `<div class="vbar">${parts.filter(Boolean).join('')}
    ${!STATIC && rebuild ? `<button id="v-build" class="small" type="button">${esc(rebuild)}</button>` : ''}
    <pre id="v-log" class="joblog inline" hidden></pre></div>`;
}

function bindBuild(what, repo, onEnd) {
  $('#v-build')?.addEventListener('click', (e) => startBuild(what, repo, e.target, $('#v-log'), onEnd));
}

function c4State(v) {
  return v.exists ? `<span class="muted small">${esc(t('builtAt', { when: ago(v.at) }))}</span>${v.stale ? ` <span class="warn small">⚠️ ${esc(t('stale'))}</span>` : ''}`
    : `<span class="muted small">${esc(v.model ? t('notBuilt') : t('noC4'))}</span>`;
}

function drawArchSide(active) {
  $('#side-head').innerHTML = `<div class="side-title">🏗️ ${esc(t('c4'))}</div>`;
  const groups = VIEW_GROUPS.map((g) => [g, T.views.filter((v) => viewGroup(v) === g)]).filter(([, vs]) => vs.length);
  const link = (href, label, on, title = '') => `<a href="${esc(href)}" class="${on ? 'on' : ''}" title="${esc(title)}">${esc(label)}</a>`;
  $('#tree').innerHTML = groups.map(([g, vs]) => `<div class="group"><div class="group-title">${esc(t('kind.' + g))}</div>
      ${vs.map((v) => link(`#/c4/${v.id}`, v.title, v.id === active, v.id)).join('')}</div>`).join('')
    + `<div class="group"><div class="group-title">${esc(t('explore'))}</div>
      ${link('#/c4/explorer', '🧭 ' + t('explorer'), active === 'explorer')}
      ${(T.codeMaps || []).length || T.codeGraphs.length ? link('#/code', '🧩 ' + t('codeTab'), false) : ''}</div>`;
}

async function showArch(rest) {
  const [first = '', ...more] = rest.split('/').filter(Boolean);
  drawChrome('c4', { viewer: true });
  if (first === 'code') return location.replace(`#/code/${more.join('/') || 'all'}/graph`);
  const id = first || defaultView();
  drawArchSide(id || 'explorer');
  if (!id || id === 'explorer') return showExplorer();
  const view = T.views.find((v) => v.id === id);
  if (!view) { $('#main').innerHTML = `<div class="page"><h1>${esc(t('notFound'))}</h1><p class="muted"><code>${esc(id)}</code></p></div>`; return; }
  const v = (await loadViewers()).c4;
  const flowDoc = T.docs.find((d) => flowViewId(d.path) === id);
  $('#main').innerHTML = `<div class="arch">
    <div class="arch-head">
      <div><div class="crumbs"><a href="#/c4">${esc(t('c4'))}</a> › ${esc(t('kind.' + viewGroup(view)))}</div>
        <h1>${esc(view.title)}</h1>
        <div class="meta"><span class="pill">${esc(view.kind)}</span><code>${esc(view.id)}</code><span class="muted small">architecture/${esc(view.file)}</span></div></div>
      <div class="row">
        ${flowDoc ? `<a class="button ghost small" href="${esc(hrefFor(flowDoc.path))}">📄 ${esc(t('readFlow'))}</a>` : ''}
        ${v.exists ? `<a class="button ghost small" href="architecture/view/${encodeURIComponent(id)}/" target="_blank" rel="noopener">${esc(t('openExplorer'))} ↗</a>` : ''}
      </div>
    </div>
    ${viewerBar([c4State(v)], v.model ? (v.exists ? t('rebuild') : t('build')) : '')}
    <div class="c4stage"></div></div>`;
  bindBuild('c4', '', () => location.reload());
  $('.c4stage').append(c4Box(id));
  await drawC4($('#main'), { caption: false, maxH: () => Math.max(320, innerHeight - $('.c4stage').getBoundingClientRect().top - 32) });
}

async function showExplorer() {
  const v = (await loadViewers()).c4;
  $('#main').innerHTML = viewerBar([`<b>${esc(t('explorer'))}</b>`, c4State(v),
    v.exists ? `<a href="architecture/" target="_blank" rel="noopener">${esc(t('openTab'))} ↗</a>` : ''], v.model ? (v.exists ? t('rebuild') : t('build')) : '')
    + (v.exists ? '<iframe class="viewer" src="architecture/" title="C4"></iframe>' : '');
  bindBuild('c4', '', () => location.reload());
}

async function showCode(repo) {
  const v = await loadViewers();
  const names = Object.keys(v.graphs);
  repo = names.includes(repo) ? repo : (names[0] || '');
  const g = v.graphs[repo];
  const src = repo === 'all' ? 'code-graph/' : `code-graph/${encodeURIComponent(repo)}/`;
  const sel = names.length ? `<select id="v-repo">${names.map((n) => `<option value="${esc(n)}" ${n === repo ? 'selected' : ''}>${esc(n === 'all' ? t('allRepos') : n)}</option>`).join('')}</select>` : '';
  const state = g ? `<span class="muted small">${esc(t('builtAt', { when: ago(g.at) }))}</span>${g.stale ? ` <span class="warn small">⚠️ ${esc(t('stale'))}</span>` : ''}`
    : `<span class="muted small">${esc(t('noGraph'))}</span>`;
  $('#main').innerHTML = viewerBar([`<b>${esc(t('code'))}</b>`, sel, state, g ? `<a href="${src}" target="_blank" rel="noopener">${esc(t('openTab'))} ↗</a>` : ''],
    v.graphify ? (names.length ? t('rebuild') : t('build')) : '') + (g ? `<iframe class="viewer" src="${src}" title="code graph"></iframe>` : '');
  $('#v-repo')?.addEventListener('change', (e) => { location.hash = `#/code/${e.target.value}/graph`; });
  bindBuild('graph');
}
