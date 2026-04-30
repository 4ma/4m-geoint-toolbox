/* app.js — project_research_tool frontend */

// ── Shared state ──────────────────────────────────────────
let selectedProject = null;   // { project_id, project_name, company_name, request_ts, state }
let pipelineResults = null;   // full results JSON after pipeline run

// ── Index page ────────────────────────────────────────────
function initIndexPage() {
  const searchInput   = document.getElementById('search-input');
  const dropdown      = document.getElementById('search-dropdown');
  const confirm       = document.getElementById('project-confirm');
  const runBtn        = document.getElementById('run-btn');
  const form          = document.getElementById('pipeline-form');
  const overlay       = document.getElementById('loading-overlay');
  const loadingMsg    = document.getElementById('loading-msg');
  const filtersToggle = document.getElementById('filters-toggle');
  const filtersBody   = document.getElementById('filters-body');

  if (!searchInput) return;

  // Debounced live search
  let debounceTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const q = searchInput.value.trim();
    if (q.length < 2) { closeDropdown(); return; }
    debounceTimer = setTimeout(() => fetchProjects(q), 300);
  });

  // Close dropdown on outside click
  document.addEventListener('click', e => {
    if (!e.target.closest('.search-wrapper')) closeDropdown();
  });

  // Collapsible filters
  if (filtersToggle) {
    filtersToggle.addEventListener('click', () => {
      filtersToggle.classList.toggle('open');
      filtersBody.classList.toggle('open');
    });
  }

  // Form submit
  if (form) {
    form.addEventListener('submit', async e => {
      e.preventDefault();
      if (!selectedProject) return;

      runBtn.disabled = true;
      loadingMsg.textContent = `Running pipeline for ${selectedProject.project_name}…`;
      overlay.classList.add('visible');

      const filters = collectFilters();
      try {
        const res = await fetch('/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ project_id: selectedProject.project_id, filters }),
        });
        const data = await res.json();
        // Store results in sessionStorage and redirect to results page
        sessionStorage.setItem('pipeline_results', JSON.stringify(data));
        window.location.href = '/results';
      } catch (err) {
        overlay.classList.remove('visible');
        runBtn.disabled = false;
        alert('Pipeline failed: ' + err.message);
      }
    });
  }

  function closeDropdown() {
    dropdown.classList.remove('open');
    dropdown.innerHTML = '';
  }

  async function fetchProjects(query) {
    const res = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    const projects = await res.json();
    renderDropdown(projects);
  }

  function renderDropdown(projects) {
    dropdown.innerHTML = '';
    if (!projects.length) {
      dropdown.innerHTML = '<div class="dropdown-empty">No projects found</div>';
    } else {
      projects.forEach(p => {
        const item = document.createElement('div');
        item.className = 'dropdown-item';
        item.innerHTML = `
          <div class="item-name">${esc(p.project_name)}</div>
          <div class="item-meta">${esc(p.project_id)} · ${esc(p.company_name || '')} · ${esc(p.state || '')}</div>
        `;
        item.addEventListener('click', () => selectProject(p));
        dropdown.appendChild(item);
      });
    }
    dropdown.classList.add('open');
  }

  function selectProject(project) {
    selectedProject = project;
    searchInput.value = project.project_name;
    closeDropdown();
    confirm.classList.add('visible');
    confirm.innerHTML = `
      <strong>${esc(project.project_name)}</strong> &nbsp;·&nbsp;
      <span style="color:var(--muted)">${esc(project.project_id)}</span><br>
      <span style="color:var(--muted);font-size:12px">${esc(project.company_name || '')} &nbsp;·&nbsp; Created: ${esc(project.request_ts || '')}</span>
    `;
    runBtn.disabled = false;
  }

  function collectFilters() {
    const get = id => document.getElementById(id);
    const checkedValues = name => [...document.querySelectorAll(`input[name="${name}"]:checked`)].map(el => el.value);
    return {
      steps_to_run:      checkedValues('step'),
      buffer_m:          parseInt(get('filter-buffer')?.value || '500'),
      source_ids:        checkedValues('filter-source'),
      min_file_size_mb:  parseFloat(get('filter-min-size')?.value || '0'),
    };
  }
}

// ── Results page ──────────────────────────────────────────
function initResultsPage() {
  // Flask serves /results as a separate route that renders results.html.
  // Results data is in window.__RESULTS__ (injected by Jinja) or sessionStorage.
  const data = window.__RESULTS__ || JSON.parse(sessionStorage.getItem('pipeline_results') || 'null');
  if (!data) { window.location.href = '/'; return; }

  pipelineResults = data;
  renderTopBar(data);
  renderSummary(data);
  renderPrioritizer(data.steps?.prioritizer);
  renderDownloader(data.steps?.downloader);
  renderInternalLayers(data.steps?.internal_layers);
  renderClassifier(data.steps?.classifier);
  renderUtilityOwners(data.steps?.utility_owners);
  renderFCC(data.steps?.fcc);
  renderResearch(data.steps?.research);
  initSidebar();
  initSaveToDrive(data);
}

function renderTopBar(data) {
  const p = data.project || {};
  const drive = data.drive || {};

  setText('tb-name',         p.project_name);
  setText('tb-id',           p.project_id);
  setText('tb-state',        p.state);
  setText('tb-county',       p.county);
  setText('tb-municipality', p.municipality);
  setText('tb-company',      p.company_name);
  setText('tb-created',      p.request_ts ? p.request_ts.split('T')[0] : '—');
  setText('tb-runtime',      data.runtime_seconds != null ? data.runtime_seconds + 's' : '—');

  const driveBtn = document.getElementById('tb-drive-btn');
  if (driveBtn && drive.folder_url) {
    driveBtn.href = drive.folder_url;
    driveBtn.style.display = 'inline-flex';
  }
}

function renderSummary(data) {
  const p = data.project || {};
  const steps = data.steps || {};
  const drive = data.drive || {};

  const stepStatus = name => {
    const s = steps[name];
    if (!s) return 'pending';
    if (s.status === 'error') return 'error';
    if (s.status === 'not_implemented') return 'stub';
    return 'success';
  };

  const badge = status => {
    const map = { success: '✅ Success', error: '❌ Failed', stub: '⚙ Pending', pending: '— —', warning: '⚠ Partial' };
    return `<span class="badge badge-${status}">${map[status] || status}</span>`;
  };

  const el = document.getElementById('summary-content');
  if (!el) return;
  el.innerHTML = `
    <dl class="summary-grid">
      <dt>Project</dt>          <dd>${esc(p.project_name || '—')}</dd>
      <dt>Project ID</dt>       <dd><code>${esc(p.project_id || '—')}</code></dd>
      <dt>State / County / Municipality</dt>
      <dd>${esc(p.state || '—')} / ${esc(p.county || '—')} / ${esc(p.municipality || '—')}</dd>
      <dt>Company</dt>          <dd>${esc(p.company_name || '—')}</dd>
      <dt>Created</dt>          <dd>${esc(p.request_ts ? p.request_ts.split('T')[0] : '—')}</dd>
      <dt>Run Date</dt>         <dd>${new Date(data.run_at).toLocaleString()}</dd>
      <dt>Runtime</dt>          <dd>${data.runtime_seconds != null ? data.runtime_seconds + 's' : '—'}</dd>
      <dt>Drive Folder</dt>     <dd>${drive.folder_url ? `<a href="${drive.folder_url}" target="_blank" style="color:var(--accent2)">Open ↗</a>` : '—'}</dd>
    </dl>
    <div style="margin-top:20px;display:flex;flex-wrap:wrap;gap:10px">
      <div class="card" style="flex:1;min-width:160px">
        <div style="color:var(--muted);font-size:11px;margin-bottom:4px">PRIORITIZER</div>
        ${badge(stepStatus('prioritizer'))}
        <div style="font-size:12px;color:var(--muted);margin-top:4px">${steps.prioritizer?.count ?? 0} records</div>
      </div>
      <div class="card" style="flex:1;min-width:160px">
        <div style="color:var(--muted);font-size:11px;margin-bottom:4px">CLASSIFIER</div>
        ${badge(stepStatus('classifier'))}
        <div style="font-size:12px;color:var(--muted);margin-top:4px">${steps.classifier?.count ?? 0} files</div>
      </div>
      <div class="card" style="flex:1;min-width:160px">
        <div style="color:var(--muted);font-size:11px;margin-bottom:4px">UTILITY OWNERS</div>
        ${badge(stepStatus('utility_owners'))}
        <div style="font-size:12px;color:var(--muted);margin-top:4px">${steps.utility_owners?.count ?? 0} owners</div>
      </div>
      <div class="card" style="flex:1;min-width:160px">
        <div style="color:var(--muted);font-size:11px;margin-bottom:4px">FCC</div>
        ${badge(stepStatus('fcc'))}
        <div style="font-size:12px;color:var(--muted);margin-top:4px">${steps.fcc?.count ?? 0} points</div>
      </div>
      <div class="card" style="flex:1;min-width:160px">
        <div style="color:var(--muted);font-size:11px;margin-bottom:4px">WEB RESEARCH</div>
        ${badge(stepStatus('research'))}
        <div style="font-size:12px;color:var(--muted);margin-top:4px">${steps.research?.source_count ?? 0} sources</div>
      </div>
    </div>
  `;
}

function renderPrioritizer(step) {
  const el = document.getElementById('prioritizer-content');
  if (!el) return;
  if (!step || step.status === 'skipped') { el.innerHTML = skippedCard('Blueprints Prioritizer was not selected for this run.'); return; }
  if (step.status === 'not_implemented') { el.innerHTML = stubCard('Blueprint Prioritizer not yet wired up.'); return; }
  if (step.status === 'error') { el.innerHTML = errorCard(step.message); return; }

  const records = step.records || [];
  if (!records.length) { el.innerHTML = '<p style="color:var(--muted)">No blueprints found for this project area.</p>'; return; }

  setCount('prioritizer-count', records.length);
  el.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>File Name</th><th>Source</th><th>Type</th><th>Utilities</th><th>State</th><th>Drive</th><th>S3</th>
        </tr></thead>
        <tbody>
          ${records.map(r => `<tr>
            <td>${esc(r.original_file_name || r.raw_file_name || '—')}</td>
            <td>${esc(r.source_id || '—')}</td>
            <td>${esc(r.pdf_type || r.blueprint_type || '—')}</td>
            <td>${esc(r.existing_utilities || '—')}</td>
            <td>${esc(r.state || '—')}</td>
            <td>${r.drive_link ? `<a href="${esc(r.drive_link)}" target="_blank" style="color:var(--accent2)">↗</a>` : '—'}</td>
            <td>${r.raw_file_bucket ? `<code style="font-size:11px">${esc(r.raw_file_bucket)}/${esc(r.raw_file_prefix)}</code>` : '—'}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderDownloader(step) {
  const el = document.getElementById('downloader-content');
  if (!el) return;
  if (!step || step.status === 'skipped') { el.innerHTML = skippedCard('Downloader was not selected for this run.'); return; }
  if (step.status === 'not_implemented') { el.innerHTML = stubCard('Downloader not yet wired up.'); return; }
  if (step.status === 'error') { el.innerHTML = errorCard(step.message); return; }

  const summary = step.summary_by_source || {};
  const sources = Object.entries(summary);
  if (!sources.length) { el.innerHTML = '<p style="color:var(--muted)">No files downloaded.</p>'; return; }

  el.innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:12px">` +
    sources.map(([name, info]) => `
      <div class="card" style="min-width:200px">
        <div style="font-weight:600;margin-bottom:6px">${esc(name)}</div>
        <div style="font-size:12px;color:var(--muted)">${info.count} files · ${info.total_size_mb?.toFixed(1)} MB</div>
      </div>
    `).join('') + `</div>`;
}

function renderInternalLayers(step) {
  const el = document.getElementById('internal-layers-content');
  if (!el) return;
  if (!step || step.status === 'skipped') { el.innerHTML = skippedCard('Internal Layers was not selected for this run.'); return; }
  if (step.status === 'not_implemented') { el.innerHTML = stubCard('Internal Layers / Query Plugin not yet wired up.'); return; }
  if (step.status === 'error') { el.innerHTML = errorCard(step.message); return; }
  // Future: render layer results here
  el.innerHTML = `<pre style="font-size:12px;color:var(--muted)">${JSON.stringify(step, null, 2)}</pre>`;
}

function renderClassifier(step) {
  const el = document.getElementById('classifier-content');
  if (!el) return;
  if (!step || step.status === 'skipped') { el.innerHTML = skippedCard('Documents Classifying was not selected for this run.'); return; }
  if (step.status === 'not_implemented') { el.innerHTML = stubCard('Gemini classifier not yet wired up.'); return; }
  if (step.status === 'error') { el.innerHTML = errorCard(step.message); return; }

  const files = step.files || [];
  if (!files.length) { el.innerHTML = '<p style="color:var(--muted)">No files classified.</p>'; return; }

  setCount('classifier-count', files.length);
  el.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>File Name</th><th>Source</th><th>Type</th><th>Utility Owners</th><th>Key Insights</th><th>Score</th><th>Drive</th>
        </tr></thead>
        <tbody>
          ${files.map(f => {
            const score = f.relevance_score ?? 0;
            const scoreClass = score >= .7 ? 'score-high' : score >= .4 ? 'score-mid' : 'score-low';
            return `<tr>
              <td>${esc(f.file_name || '—')}</td>
              <td>${esc(f.source_table || '—')}</td>
              <td>${esc(f.file_type || '—')}</td>
              <td>${esc((f.utility_owners || []).join(', ') || '—')}</td>
              <td>${esc(f.key_insights || '—')}</td>
              <td class="${scoreClass}">${(score * 100).toFixed(0)}%</td>
              <td>${f.drive_link ? `<a href="${esc(f.drive_link)}" target="_blank" style="color:var(--accent2)">↗</a>` : '—'}</td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderUtilityOwners(step) {
  const el = document.getElementById('owners-content');
  if (!el) return;
  if (!step || step.status === 'skipped') { el.innerHTML = skippedCard('Utility Owners was not selected for this run.'); return; }
  if (step.status === 'not_implemented') { el.innerHTML = stubCard('Utility Owners plugin not yet wired up.'); return; }
  if (step.status === 'error') { el.innerHTML = errorCard(step.message); return; }

  const owners = step.owners || [];
  if (!owners.length) { el.innerHTML = '<p style="color:var(--muted)">No utility owners found.</p>'; return; }

  setCount('owners-count', owners.length);
  el.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Organization</th><th>Sector</th><th>Response</th><th>Phone</th><th>Last Response</th>
        </tr></thead>
        <tbody>
          ${owners.map(o => `<tr>
            <td>${esc(o.organization_name || '—')}</td>
            <td>${esc((o.sector || []).join(', ') || '—')}</td>
            <td>${esc(o.last_owner_response || '—')}</td>
            <td>${esc(o.organization_phone || '—')}</td>
            <td>${esc(o.last_response_creation_ts ? o.last_response_creation_ts.split('T')[0] : '—')}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderFCC(step) {
  const el = document.getElementById('fcc-content');
  if (!el) return;
  if (!step || step.status === 'skipped') { el.innerHTML = skippedCard('FCC Data was not selected for this run.'); return; }
  if (step.status === 'not_implemented') { el.innerHTML = stubCard('FCC plugin not yet wired up.'); return; }
  if (step.status === 'error') { el.innerHTML = errorCard(step.message); return; }

  const points = step.points || [];
  if (!points.length) { el.innerHTML = '<p style="color:var(--muted)">No FCC data found.</p>'; return; }

  setCount('fcc-count', points.length);
  el.innerHTML = `
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>Owner</th><th>Latitude</th><th>Longitude</th><th>License Type</th><th>Frequency Band</th>
        </tr></thead>
        <tbody>
          ${points.map(pt => `<tr>
            <td>${esc(pt.owner_name || '—')}</td>
            <td>${pt.latitude ?? '—'}</td>
            <td>${pt.longitude ?? '—'}</td>
            <td>${esc(pt.license_type || '—')}</td>
            <td>${esc(pt.frequency_band || '—')}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>
    ${step.gpkg_path ? `<div style="margin-top:12px"><a class="btn btn-ghost btn-sm" href="/download-gpkg?project_id=${esc(pipelineResults?.project?.project_id || '')}">Download .gpkg</a></div>` : ''}
  `;
}

function renderResearch(step) {
  const el = document.getElementById('research-content');
  if (!el) return;
  if (!step || step.status === 'skipped') { el.innerHTML = skippedCard('Web Research was not selected for this run.'); return; }
  if (step.status === 'not_implemented') { el.innerHTML = stubCard('Web Research requires ANTHROPIC_API_KEY.'); return; }
  if (step.status === 'error') { el.innerHTML = step ? errorCard(step.message) : errorCard('Research step did not run.'); return; }

  setCount('research-count', step.source_count ?? 0);
  const sources = step.sources || [];

  el.innerHTML = `
    ${step.summary ? `<div class="card" style="margin-bottom:16px;line-height:1.8">${esc(step.summary)}</div>` : ''}
    ${sources.length ? `
      <h3 style="margin-bottom:10px">Sources</h3>
      <div class="source-cards">
        ${sources.map(s => `
          <div class="source-card">
            <a href="${esc(s.url)}" target="_blank">${esc(s.title || s.url)}</a>
            ${s.relevance_note ? `<div class="source-note">${esc(s.relevance_note)}</div>` : ''}
          </div>
        `).join('')}
      </div>
    ` : '<p style="color:var(--muted)">No sources found.</p>'}
    ${step.full_response ? `
      <div style="margin-top:16px">
        <button class="toggle-btn" onclick="toggleResponse(this)">Show full response ▾</button>
        <pre class="full-response-body">${esc(step.full_response)}</pre>
      </div>
    ` : ''}
  `;
}

// ── Sidebar Intersection Observer ─────────────────────────
function initSidebar() {
  const sections = document.querySelectorAll('.result-section');
  const navItems = document.querySelectorAll('.nav-item');

  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id;
        navItems.forEach(n => n.classList.toggle('active', n.getAttribute('href') === `#${id}`));
      }
    });
  }, { rootMargin: '-20% 0px -70% 0px' });

  sections.forEach(s => observer.observe(s));

  navItems.forEach(n => {
    n.addEventListener('click', e => {
      e.preventDefault();
      const target = document.querySelector(n.getAttribute('href'));
      if (target) target.scrollIntoView({ behavior: 'smooth' });
    });
  });
}

function initSaveToDrive(data) {
  const btn = document.getElementById('save-drive-btn');
  if (!btn) return;
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = 'Saving…';
    try {
      const res = await fetch('/save-to-drive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: data.project?.project_id,
          html: document.documentElement.outerHTML,
        }),
      });
      const result = await res.json();
      if (result.status === 'ok') showToast('Saved to Drive ✓');
      else showToast('Save failed: ' + result.error);
    } catch (e) {
      showToast('Save failed');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Save Results to Drive';
    }
  });
}

// ── Utilities ─────────────────────────────────────────────
function esc(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val ?? '—';
}
function setCount(id, n) {
  const el = document.getElementById(id);
  if (el) el.textContent = n;
}
function errorCard(msg) {
  return `<div class="error-card">❌ ${esc(msg || 'Step failed')}</div>`;
}
function stubCard(msg) {
  return `<div class="stub-card">⚙ ${esc(msg)}</div>`;
}
function skippedCard(msg) {
  return `<div class="stub-card" style="opacity:.55">— ${esc(msg)}</div>`;
}
function showToast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 3000);
}
function toggleResponse(btn) {
  const body = btn.nextElementSibling;
  body.classList.toggle('open');
  btn.textContent = body.classList.contains('open') ? 'Hide full response ▴' : 'Show full response ▾';
}

// ── Boot ──────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('search-input')) initIndexPage();
  if (document.getElementById('summary-content')) initResultsPage();
});