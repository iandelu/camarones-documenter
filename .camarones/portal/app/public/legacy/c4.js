'use strict';
// Architecture: a gallery of the model's C4 views (interactive web component), the full LikeC4 explorer and the code graph.

const VIEW_GROUPS = ['system', 'element', 'dynamic', 'deployment'];
const viewGroup = (v) => (v.id === 'index' ? 'system' : v.kind);
const defaultView = () => (T.views.find((v) => v.id === 'index') || T.views[0])?.id || '';

function viewerBar(parts, rebuild) {
  return `<div class="vbar">${parts.filter(Boolean).join('')}
    ${RUNS && rebuild ? `<button id="v-build" class="small" type="button">${esc(rebuild)}</button>` : ''}
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
    <div class="c4stage"></div><section id="c4-elements" class="c4el-panel"></section></div>`;
  bindBuild('c4', '', () => location.reload());
  $('.c4stage').append(c4Box(id));
  await Promise.all([drawC4($('#main'), { caption: false, maxH: () => Math.max(320, innerHeight * 0.7) }), drawElements(id)]);
}

// ---------- the view's elements: review, edit and confirm what the AI drafted (lib/c4edit.py) ----------
function elementCard(e, v, edit) {
  const title = (fqn) => v.all.find((x) => x.fqn === fqn)?.title || fqn;
  const status = e.confirmed
    ? `<span class="pill trust confirmed">✓ ${esc(t('c4ConfirmedBy', { by: e.confirmedBy || '?', at: e.confirmedAt || '' }))}</span>`
    : e.draft ? `<span class="pill trust draft">${esc(t('c4Draft'))}</span>` : '';
  const rel = (r, out) => `<li>${out ? '→' : '←'} <b>${esc(title(out ? r.to : r.from))}</b>${r.label ? ` <span class="muted">${esc(r.label)}</span>` : ''}
    ${r.kind ? `<span class="chip">${esc(r.kind)}</span>` : ''}
    ${edit && out ? `<button class="ghost small c4x" type="button" data-act="unrel" data-to="${esc(r.to)}" data-label="${esc(r.label)}" title="${esc(t('c4RemoveRel'))}">×</button>` : ''}</li>`;
  const opts = (list, cur) => list.map((k) => `<option ${k === cur ? 'selected' : ''}>${esc(k)}</option>`).join('');
  return `<article class="c4el ${e.draft ? 'draft' : ''}" data-fqn="${esc(e.fqn)}">
    <div class="c4el-h"><b>${esc(e.title)}</b><span class="chip">${esc(e.kind)}</span><code class="small muted">${esc(e.fqn)}</code>${status}
      ${edit ? `<span class="c4el-act"><button class="ghost small" type="button" data-act="edit">${esc(t('edit'))}</button>
        ${e.confirmed && !e.draft ? '' : `<button class="small" type="button" data-act="confirm">✓ ${esc(t('c4Confirm'))}</button>`}</span>` : ''}</div>
    ${e.technology || e.description ? `<p class="small">${e.technology ? `<b>${esc(e.technology)}</b>` : ''}${e.technology && e.description ? ' · ' : ''}${esc(e.description)}</p>` : ''}
    ${e.out.length || e.in.length ? `<ul class="c4rels">${e.out.map((r) => rel(r, true)).join('')}${e.in.map((r) => rel(r, false)).join('')}</ul>` : ''}
    ${edit ? `<form class="c4el-form" hidden>
      <label>${esc(t('c4Title'))}<input name="title" value="${esc(e.title)}" required></label>
      <label>${esc(t('c4Kind'))}<select name="kind">${opts(v.kinds, e.kind)}</select></label>
      <label>${esc(t('c4Tech'))}<input name="technology" value="${esc(e.technology)}"></label>
      <label class="wide">${esc(t('c4Desc'))}<input name="description" value="${esc(e.description)}"></label>
      <div class="row"><button type="submit" class="small">${esc(t('save'))}</button><button type="button" class="ghost small" data-act="close">${esc(t('cancel'))}</button></div>
    </form>
    <form class="c4rel-form row">
      <select name="to" aria-label="${esc(t('c4To'))}"><option value="">${esc(t('c4AddRel'))} ${esc(t('c4To'))}…</option>
        ${v.all.filter((x) => x.fqn !== e.fqn).map((x) => `<option value="${esc(x.fqn)}">${esc(x.title)} (${esc(x.fqn)})</option>`).join('')}</select>
      <input name="label" placeholder="${esc(t('c4Label'))}" aria-label="${esc(t('c4Label'))}">
      <select name="kind" aria-label="${esc(t('c4Kind'))}"><option value="">—</option>${opts(v.relKinds, '')}</select>
      <button type="submit" class="ghost small">${esc(t('c4AddRel'))}</button>
    </form>` : ''}
  </article>`;
}

async function drawElements(id) {
  const host = $('#c4-elements');
  if (!host) return;
  let v;
  try { v = await api('c4/view', { id }); } catch { host.remove(); return; }
  if (!v.elements.length) { host.remove(); return; }
  const edit = v.editable && !STATIC;
  const drafts = v.elements.filter((e) => e.draft).length;
  host.innerHTML = `<div class="c4el-head"><h2>${esc(t('c4Elements'))}</h2>
      <span class="muted small">${esc(t('c4Count', { n: v.elements.length, d: drafts }))}</span>
      ${edit && drafts ? `<button class="small" id="c4-confirm-all" type="button">✓ ${esc(t('c4ConfirmAll'))}</button>` : ''}</div>
    ${edit ? `<p class="muted small">${esc(t('c4Help'))}</p>` : ''}
    <div class="c4el-list">${v.elements.map((e) => elementCard(e, v, edit)).join('')}</div>`;
  if (!edit) return;
  const change = async (path, body) => {
    try {
      await api(`c4/${path}`, {}, body);
      toast(t('c4Saved'));
      await drawElements(id);
      if (RUNS && (await loadViewers()).c4.model) watchJob(await api('build', {}, { what: 'c4' }), $('#v-log'), () => location.reload());
    } catch (err) { toast(err.message); }
  };
  $('#c4-confirm-all')?.addEventListener('click', () => change('confirm', { view: id }));
  host.addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-act]');
    const card = b?.closest('.c4el');
    if (!card) return;
    const fqn = card.dataset.fqn;
    if (b.dataset.act === 'edit') card.querySelector('.c4el-form').hidden = false;
    else if (b.dataset.act === 'close') card.querySelector('.c4el-form').hidden = true;
    else if (b.dataset.act === 'confirm') change('confirm', { fqns: [fqn] });
    else if (b.dataset.act === 'unrel') change('relation', { action: 'remove', from: fqn, to: b.dataset.to, label: b.dataset.label });
  });
  host.addEventListener('submit', (ev) => {
    ev.preventDefault();
    const f = ev.target, fqn = f.closest('.c4el').dataset.fqn, data = Object.fromEntries(new FormData(f));
    if (f.classList.contains('c4el-form')) change('element', { fqn, ...data });
    else if (data.to) change('relation', { action: 'add', from: fqn, to: data.to, label: data.label, kind: data.kind || null });
  });
}

async function showExplorer() {
  const v = (await loadViewers()).c4;
  $('#main').innerHTML = viewerBar([`<b>${esc(t('explorer'))}</b>`, c4State(v),
    v.exists ? `<a href="architecture/" target="_blank" rel="noopener">${esc(t('openTab'))} ↗</a>` : ''],
    v.model ? (v.exists ? t('rebuild') : t('build')) : t('firstLook'))
    + (v.exists ? '<iframe class="viewer" src="architecture/" title="C4"></iframe>' : '');
  bindBuild(v.model ? 'c4' : 'first-look', '', () => location.reload());   // no model yet: draft it from the code
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
