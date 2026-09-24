'use strict';
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const TRUST = { confirmed: '✅', draft: '🤖', 'needs-reconfirm': '⚠️' };
const BANNER = {
  draft: 'AI-generated draft — not yet confirmed by a human. Verify it against the code, then confirm it.',
  'needs-reconfirm': 'Changed after a human confirmed it — review the change and confirm again.',
};
let T = { docs: [], langs: [] };
let lang = localStorage.getItem('cam-lang') || '';

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Camarones': '1' }, body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

function toast(msg) {
  const t = $('#toast');
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast.h); toast.h = setTimeout(() => { t.hidden = true; }, 3000);
}

mermaid.initialize({ startOnLoad: false, theme: matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'default' });

function render(md, docPath) {
  const body = md.replace(/^---\n[\s\S]*?\n---\n?/, '').replace(/^\s*#\s+.+\n/, '');   // the page header shows the title
  const html = DOMPurify.sanitize(marked.parse(body, { gfm: true }));
  const el = document.createElement('div');
  el.className = 'doc';
  el.innerHTML = html;
  const base = docPath.split('/').slice(0, -1);
  const resolve = (href) => {
    const parts = [...base];
    for (const p of href.split('/')) { if (p === '..') parts.pop(); else if (p && p !== '.') parts.push(p); }
    return parts.join('/');
  };
  el.querySelectorAll('a[href]').forEach((a) => {
    const href = a.getAttribute('href');
    if (/^[a-z]+:|^#|^\//i.test(href)) return;
    const [file, anchor] = href.split('#');
    if (file.endsWith('.md')) a.setAttribute('href', `#/doc/${resolve(file)}${anchor ? '::' + anchor : ''}`);
  });
  el.querySelectorAll('img[src]').forEach((img) => {
    const src = img.getAttribute('src');
    if (!/^[a-z]+:|^\//i.test(src)) img.src = '/raw/' + resolve(src);
  });
  el.querySelectorAll('pre code.language-mermaid').forEach((c) => {
    const d = document.createElement('div');
    d.className = 'mermaid';
    d.textContent = c.textContent;
    c.parentElement.replaceWith(d);
  });
  return el;
}

async function drawMermaid(root) {
  const nodes = root.querySelectorAll('.mermaid');
  if (nodes.length) { try { await mermaid.run({ nodes }); } catch (e) { console.warn(e); } }
}

function drawTree(active) {
  const q = $('#search').value.trim().toLowerCase();
  const groups = {};
  for (const d of T.docs) {
    if (q && !(d.title + ' ' + d.path).toLowerCase().includes(q)) continue;
    const g = d.path.includes('/') ? d.path.split('/').slice(0, d.path.startsWith('repos/') ? 2 : 1).join('/') : 'root';
    (groups[g] ||= []).push(d);
  }
  $('#tree').innerHTML = Object.entries(groups).map(([g, items]) => `<h4>${esc(g)}</h4>` + items.map((d) =>
    `<a href="#/doc/${esc(d.path)}" class="${d.path === active ? 'on' : ''}" title="${esc(d.path)}">${TRUST[d.trust] || ''} ${esc(d.title)}</a>`
  ).join('')).join('') || '<p class="muted">No pages match.</p>';
}

async function loadTree() {
  T = await api('/api/tree');
  document.title = `${T.project} — docs`;
  $('#project').textContent = T.project;
  const s = T.summary;
  $('#summary').textContent = `✅ ${s.confirmed} · 🤖 ${s.draft} · ⚠️ ${s['needs-reconfirm']}` + (T.feedback ? ` · ✏️ ${T.feedback}` : '');
  $('#lnk-graph').hidden = !T.codeGraph;
  $('#lnk-c4').hidden = !T.site;
  $('#lnk-site').hidden = !T.site;
  $('#lang').innerHTML = ['<option value="">English</option>', ...T.langs.map((l) => `<option value="${l}">${l}</option>`)].join('');
  $('#lang').value = lang;
}

async function showDoc(path, anchor) {
  drawTree(path);
  const d = await api(`/api/doc?path=${encodeURIComponent(path)}&lang=${lang}`);
  const main = $('#main');
  const human = d.owner === 'human';
  main.innerHTML = `
    <h1>${esc(d.title)}</h1>
    <div class="meta">
      <span class="badge ${esc(d.trust)}">${TRUST[d.trust] || ''} ${esc(d.trust)}</span>
      <code>${esc(d.file)}</code>
      ${d.confirmed && d.confirmed.by ? `<span>confirmed by ${esc(d.confirmed.by)} · ${esc(String(d.confirmed.at).slice(0, 10))}</span>` : ''}
      ${human ? '<span>✍️ human-owned page</span>' : ''}
      ${lang && !d.exists ? `<span>no ${esc(lang)} translation yet</span>` : ''}
    </div>
    ${BANNER[d.trust] ? `<div class="banner ${esc(d.trust)}">${BANNER[d.trust]}</div>` : ''}
    <div class="actions">
      <button id="a-edit">Edit</button>
      ${d.trust !== 'confirmed' ? '<button id="a-confirm" class="ghost">✅ Confirm as correct</button>' : ''}
      <button id="a-fb" class="ghost">✏️ Request a change</button>
    </div>
    <div id="panel"></div>
    ${d.feedback.length ? `<div class="box"><b>Pending review comments</b><ul class="list">${d.feedback.map((f) => `<li>${esc(f.slice(6))}</li>`).join('')}</ul></div>` : ''}
    <div id="body"></div>
    ${d.sources.length ? `<div class="box"><b>Sources</b><ul class="list">${d.sources.map((s) => `<li><code>${esc(s)}</code></li>`).join('')}</ul></div>` : ''}`;
  const body = render(d.exists ? d.raw : '_Nothing here yet — use Edit to write it._', path);
  $('#body').append(body);
  await drawMermaid(body);
  if (anchor) document.getElementById(anchor)?.scrollIntoView();
  else window.scrollTo(0, 0);
  $('#a-edit').onclick = () => editDoc(d);
  $('#a-confirm')?.addEventListener('click', () => confirmPanel(d));
  $('#a-fb').onclick = () => feedbackPanel(d);
}

function confirmPanel(d) {
  $('#panel').innerHTML = `<div class="box"><b>Confirm this page</b>
    <p class="muted">You checked it against how the system really works. Agents will treat it as the source of truth.</p>
    <div class="row"><input id="c-by" value="${esc(T.reviewer)}" placeholder="Your name" style="max-width:16rem">
    <button id="c-go">Confirm</button><button id="c-x" class="ghost">Cancel</button></div></div>`;
  $('#c-x').onclick = () => { $('#panel').innerHTML = ''; };
  $('#c-go').onclick = async () => {
    await api('/api/confirm', { path: d.path, lang, by: $('#c-by').value });
    await afterChange(d.path, 'Confirmed');
  };
}

function feedbackPanel(d) {
  $('#panel').innerHTML = `<div class="box"><b>Request a change</b>
    <p class="muted">Describe what is wrong or missing. The next AI session applies it (unit review-fixes).</p>
    <textarea id="f-text" rows="4"></textarea>
    <div class="row"><input id="f-by" value="${esc(T.reviewer)}" placeholder="Your name" style="max-width:16rem">
    <button id="f-go">Send</button><button id="f-x" class="ghost">Cancel</button></div></div>`;
  $('#f-x').onclick = () => { $('#panel').innerHTML = ''; };
  $('#f-go').onclick = async () => {
    if (!$('#f-text').value.trim()) return;
    await api('/api/feedback', { path: d.path, text: $('#f-text').value, by: $('#f-by').value });
    await afterChange(d.path, 'Comment saved');
  };
}

function editDoc(d) {
  const main = $('#main');
  main.innerHTML = `<h1>Editing: ${esc(d.title)}</h1>
    <div class="meta"><code>${esc(d.file)}</code>${lang ? ` · translation ${esc(lang)}` : ''}</div>
    ${d.trust === 'confirmed' ? '<div class="banner">This page is confirmed: saving a change makes it “needs re-confirmation”.</div>' : ''}
    <div class="editor"><textarea id="e-src" spellcheck="true"></textarea><div class="preview" id="e-prev"></div></div>
    <div class="row">
      <input id="e-msg" placeholder="What changed? (commit message)" style="flex:1;min-width:14rem">
      <label><input type="checkbox" id="e-commit" checked> commit to cam-docs</label>
      <button id="e-save">Save</button><button id="e-x" class="ghost">Cancel</button>
    </div>`;
  const src = $('#e-src');
  src.value = d.raw || `---\ntitle: ${d.title}\n---\n\n# ${d.title}\n`;
  const preview = () => { const p = $('#e-prev'); p.innerHTML = ''; const el = render(src.value, d.path); p.append(el); drawMermaid(el); };
  let h; src.oninput = () => { clearTimeout(h); h = setTimeout(preview, 250); };
  preview();
  $('#e-x').onclick = () => route();
  $('#e-save').onclick = async () => {
    $('#e-save').disabled = true;
    try {
      await api('/api/doc', { path: d.path, lang, raw: src.value });
      if ($('#e-commit').checked) {
        const c = await api('/api/commit', { message: $('#e-msg').value || `edit ${d.path}` });
        toast(c.committed ? `Saved and committed: ${c.head}` : 'Saved (nothing to commit)');
      } else toast('Saved');
      await loadTree();
      location.hash = `#/doc/${d.path}`;
      route();
    } catch (e) { toast(e.message); $('#e-save').disabled = false; }
  };
}

async function afterChange(path, msg) {
  toast(msg);
  await loadTree();
  await showDoc(path);
}

async function showStatus() {
  drawTree('');
  const s = await api('/api/status');
  const changed = Object.entries(s.changes).filter(([, c]) => c.status !== 'up-to-date');
  $('#main').innerHTML = `<h1>Review &amp; status</h1>
    <p class="muted">Plan ${s.plan.done}/${s.plan.total} units · ${T.summary.total} pages</p>
    <div class="box"><b>Waiting for a human (${s.queue.length})</b><ul class="list">${s.queue.map((r) =>
      `<li>${TRUST[r.trust]} <a href="#/doc/${esc(r.path)}">${esc(r.title)}</a> <span class="muted">${esc(r.path)}</span></li>`).join('') || '<li class="muted">Nothing — all confirmed.</li>'}</ul></div>
    <div class="box"><b>Change requests not applied yet (${s.feedback.length})</b><ul class="list">${s.feedback.map((f) => `<li>${esc(f.slice(6))}</li>`).join('') || '<li class="muted">None.</li>'}</ul></div>
    <div class="box"><b>Code changed since the docs were updated (${changed.length})</b><ul class="list">${changed.map(([n, c]) =>
      `<li><b>${esc(n)}</b> — ${esc(c.status)}${c.files ? ` (${c.files.length} files)` : ''}</li>`).join('') || '<li class="muted">All repos documented at their current commit.</li>'}</ul>
      <p class="muted">Ask an agent: “update the docs for the latest changes” (skill cam-docs-update).</p></div>
    <div class="box"><b>Checks</b><ul class="list">${[...s.check.errors.map((e) => `<li>❌ ${esc(e)}</li>`), ...s.check.warnings.map((w) => `<li>⚠️ ${esc(w)}</li>`)].join('') || '<li class="muted">All checks pass.</li>'}</ul></div>`;
}

function newPage() {
  $('#main').innerHTML = `<h1>New page</h1><div class="box">
    <input id="n-title" placeholder="Title">
    <div class="row"><input id="n-path" placeholder="section/page.md (e.g. guides/onboarding.md)"></div>
    <div class="row"><button id="n-go">Create</button></div></div>`;
  $('#n-title').oninput = () => { $('#n-path').value = 'guides/' + $('#n-title').value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.md'; };
  $('#n-go').onclick = async () => {
    try {
      const d = await api('/api/new', { path: $('#n-path').value, title: $('#n-title').value });
      await loadTree();
      location.hash = `#/doc/${d.path}`;
      editDoc(d);
    } catch (e) { toast(e.message); }
  };
}

async function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  try {
    if (h.startsWith('/doc/')) {
      const [path, anchor] = h.slice(5).split('::');
      return await showDoc(path, anchor);
    }
    if (h === '/status') return await showStatus();
    const first = T.docs.find((d) => d.path === 'index.md') || T.docs.find((d) => d.path.startsWith('overview')) || T.docs[0];
    if (first) return await showDoc(first.path);
    $('#main').innerHTML = '<h1>No documentation yet</h1><p>Run the next unit from the Camarones wizard, or create a page.</p>';
  } catch (e) {
    $('#main').innerHTML = `<h1>Error</h1><p>${esc(e.message)}</p>`;
  }
}

$('#search').oninput = () => drawTree((decodeURIComponent(location.hash).match(/#\/doc\/([^:]+)/) || [])[1]);
$('#lang').onchange = (e) => { lang = e.target.value; localStorage.setItem('cam-lang', lang); route(); };
$('#wide').onclick = () => { document.body.classList.toggle('wide'); localStorage.setItem('cam-wide', document.body.classList.contains('wide') ? '1' : ''); };
$('#new').onclick = newPage;
if (localStorage.getItem('cam-wide')) document.body.classList.add('wide');
addEventListener('hashchange', route);
loadTree().then(route).catch((e) => { $('#main').innerHTML = `<h1>Cannot reach the docs server</h1><p>${esc(e.message)}</p>`; });
