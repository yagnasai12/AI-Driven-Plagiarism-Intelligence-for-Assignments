/* ═══════════════════════════════════════════════════════
   AcademIQ — Academic Integrity Agent
   app.js  — Frontend logic
═══════════════════════════════════════════════════════ */

'use strict';

/* ── State ─────────────────────────────────────────────── */
const state = {
  chatHistory: [],
  stats: { analysed: 0, flagged: 0, clear: 0, profiles: 0 },
  log: [],
  riskCounts: { Low: 0, Medium: 0, High: 0, Critical: 0 },
};

/* ── DOM refs ──────────────────────────────────────────── */
const $ = id => document.getElementById(id);

/* ══════════════════════════════════════════════════════════
   THEME
══════════════════════════════════════════════════════════ */
const themeToggle = $('themeToggle');
const htmlEl = document.documentElement;

function applyTheme(dark) {
  htmlEl.setAttribute('data-bs-theme', dark ? 'dark' : 'light');
  themeToggle.innerHTML = dark
    ? '<i class="bi bi-sun-fill"></i>'
    : '<i class="bi bi-moon-stars-fill"></i>';
}

themeToggle.addEventListener('click', () => {
  const dark = htmlEl.getAttribute('data-bs-theme') !== 'dark';
  applyTheme(dark);
  localStorage.setItem('academiqdark', dark ? '1' : '0');
});

// Restore saved theme
(function () {
  const saved = localStorage.getItem('academiqdark');
  if (saved === '1') applyTheme(true);
  else if (window.matchMedia('(prefers-color-scheme: dark)').matches) applyTheme(true);
})();

/* ══════════════════════════════════════════════════════════
   TAB NAVIGATION
══════════════════════════════════════════════════════════ */
document.querySelectorAll('.nav-tab').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    const tab = link.dataset.tab;
    document.querySelectorAll('.nav-tab').forEach(l => l.classList.remove('active'));
    link.classList.add('active');
    document.querySelectorAll('.tab-pane-custom').forEach(p => p.classList.remove('active'));
    const pane = $('tab-' + tab);
    if (pane) pane.classList.add('active');
    if (tab === 'dashboard') refreshDashboard();
  });
});

/* ══════════════════════════════════════════════════════════
   LOADING OVERLAY
══════════════════════════════════════════════════════════ */
function showLoading(msg = 'Analysing…') {
  $('loadingMsg').textContent = msg;
  $('loadingOverlay').classList.remove('d-none');
}
function hideLoading() {
  $('loadingOverlay').classList.add('d-none');
}

/* ══════════════════════════════════════════════════════════
   MARKDOWN → HTML (lightweight)
══════════════════════════════════════════════════════════ */
function renderMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
    .replace(/^[\-•] (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
    .replace(/<\/ul>\s*<ul>/g, '')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[hup])(.+)$/gm, '<p>$1</p>')
    .replace(/<p><\/p>/g, '');
}

/* ══════════════════════════════════════════════════════════
   CHAT
══════════════════════════════════════════════════════════ */
const chatMessages = $('chatMessages');
const chatInput    = $('chatInput');
const sendBtn      = $('sendBtn');

function appendMessage(role, content) {
  const isAgent = role === 'agent';
  const div = document.createElement('div');
  div.className = `msg msg-${role}`;
  div.innerHTML = `
    <div class="msg-avatar"><i class="bi bi-${isAgent ? 'shield-check' : 'person-fill'}"></i></div>
    <div class="msg-bubble">
      ${isAgent ? '<strong>AcademIQ</strong><div class="mt-1 markdown-content">' + renderMarkdown(content) + '</div>'
                : escapeHtml(content)}
    </div>`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendTyping() {
  const div = document.createElement('div');
  div.className = 'msg msg-agent typing-indicator';
  div.id = 'typingIndicator';
  div.innerHTML = `
    <div class="msg-avatar"><i class="bi bi-shield-check"></i></div>
    <div class="msg-bubble">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>`;
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTyping() {
  const el = $('typingIndicator');
  if (el) el.remove();
}

async function sendChat() {
  const msg = chatInput.value.trim();
  if (!msg) return;
  chatInput.value = '';
  appendMessage('user', msg);
  state.chatHistory.push({ role: 'user', content: msg });
  appendTyping();
  sendBtn.disabled = true;

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, history: state.chatHistory }),
    });
    const data = await res.json();
    removeTyping();
    if (data.reply) {
      appendMessage('agent', data.reply);
      state.chatHistory.push({ role: 'assistant', content: data.reply });
    } else {
      appendMessage('agent', '⚠️ ' + (data.error || 'Unknown error'));
    }
  } catch (err) {
    removeTyping();
    appendMessage('agent', '⚠️ Network error: ' + err.message);
  } finally {
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

sendBtn.addEventListener('click', sendChat);
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

$('clearChat').addEventListener('click', () => {
  chatMessages.innerHTML = '';
  state.chatHistory = [];
  appendMessage('agent', 'Chat cleared. How can I help you with academic integrity analysis today?');
});

document.querySelectorAll('.btn-suggestion').forEach(btn => {
  btn.addEventListener('click', () => {
    chatInput.value = btn.dataset.msg;
    chatInput.focus();
  });
});

/* ══════════════════════════════════════════════════════════
   ANALYZE TAB
══════════════════════════════════════════════════════════ */
// Live word count
$('ana-text').addEventListener('input', function () {
  const words = this.value.trim().split(/\s+/).filter(Boolean).length;
  $('ana-wordcount').textContent = words.toLocaleString() + ' word' + (words !== 1 ? 's' : '');
});

$('analyzeBtn').addEventListener('click', async () => {
  const text = $('ana-text').value.trim();
  if (!text) { alert('Please paste a submission text.'); return; }

  showLoading('Running analysis with Granite…');
  try {
    const res = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        student_name:    $('ana-student').value.trim() || 'Anonymous',
        assignment_name: $('ana-assignment').value.trim() || 'Untitled',
        baseline_text:   $('ana-baseline').value.trim(),
      }),
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    renderAnalysisResults(data);
    logEntry(data);
  } catch (err) {
    alert('Error: ' + err.message);
  } finally {
    hideLoading();
  }
});

function renderAnalysisResults(data) {
  $('analysisPlaceholder').classList.add('d-none');
  $('analysisResults').classList.remove('d-none');

  // Risk badge
  const riskScore = data.ai_signals?.ai_risk_score ?? 0;
  const riskLevel = data.ai_risk_level || 'Low';
  const riskBadge = $('riskBadge');
  riskBadge.textContent = riskLevel;
  riskBadge.className = 'risk-badge-large risk-' + riskLevel.toLowerCase();
  $('aiRiskBar').style.width = riskScore + '%';
  $('aiRiskBar').className = 'progress-bar bg-' + riskColor(riskLevel);
  $('aiRiskScore').textContent = 'AI Risk Score: ' + riskScore + '/100';

  // Features
  renderFeatureGrid('featureGrid', data.stylometric_features || {});

  // AI signals
  const sig = data.ai_signals || {};
  const sigDisplay = {
    burstiness_score:          sig.burstiness_score,
    ai_phrase_density:         sig.ai_phrase_density,
    paragraph_uniformity_cv:   sig.paragraph_uniformity_cv,
    ai_risk_score:             sig.ai_risk_score,
  };
  renderFeatureGrid('aiSignalGrid', sigDisplay, true);

  // AI phrases list
  if (sig.matched_ai_phrases?.length) {
    const cell = document.createElement('div');
    cell.className = 'feature-cell';
    cell.style.gridColumn = '1 / -1';
    cell.innerHTML = `<div class="feature-label">Matched AI Phrases</div>
      <div class="feature-value small text-muted">${sig.matched_ai_phrases.map(p => `"${escapeHtml(p)}"`).join(', ')}</div>`;
    $('aiSignalGrid').appendChild(cell);
  }

  // Narrative
  $('aiAnalysisText').innerHTML = renderMarkdown(data.ai_analysis || '');
}

function renderFeatureGrid(containerId, features, highlight = false) {
  const container = $(containerId);
  container.innerHTML = '';
  Object.entries(features).forEach(([k, v]) => {
    if (v === null || v === undefined) return;
    const cell = document.createElement('div');
    cell.className = 'feature-cell';
    const label = k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const display = typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(v);
    cell.innerHTML = `<div class="feature-label">${label}</div><div class="feature-value">${display}</div>`;
    container.appendChild(cell);
  });
}

function riskColor(level) {
  return { Low: 'success', Medium: 'warning', High: 'orange', Critical: 'danger' }[level] || 'secondary';
}

/* ══════════════════════════════════════════════════════════
   SIMILARITY TAB
══════════════════════════════════════════════════════════ */
$('similarityBtn').addEventListener('click', async () => {
  const textA = $('sim-text-a').value.trim();
  const textB = $('sim-text-b').value.trim();
  if (!textA || !textB) { alert('Both submissions are required.'); return; }

  showLoading('Comparing submissions…');
  try {
    const res = await fetch('/api/similarity', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text_a:  textA,
        text_b:  textB,
        label_a: $('sim-label-a').value.trim() || 'Submission A',
        label_b: $('sim-label-b').value.trim() || 'Submission B',
      }),
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    renderSimilarityResults(data);
  } catch (err) {
    alert('Error: ' + err.message);
  } finally {
    hideLoading();
  }
});

function renderSimilarityResults(data) {
  const score = data.similarity_score ?? 0;
  const pct = Math.round(score * 100);
  const level = data.risk_level || 'Low';

  $('simResults').style.display = 'block';
  $('simScoreNum').textContent = pct + '%';
  $('simScoreCircle').style.borderColor = riskHex(level);
  $('simScoreCircle').style.color = riskHex(level);
  $('simScoreCircle').style.background = riskHex(level, .12);

  const badge = $('simRiskBadge');
  badge.textContent = level;
  badge.className = 'badge badge-risk badge-' + level;

  const bar = $('simBar');
  bar.style.width = pct + '%';
  bar.style.background = riskHex(level);

  $('simAssessment').innerHTML = renderMarkdown(data.ai_assessment || '');
}

function riskHex(level, alpha = 1) {
  const map = { Low: '#16a34a', Medium: '#ca8a04', High: '#dc6803', Critical: '#dc2626' };
  const hex = map[level] || '#57606a';
  if (alpha < 1) {
    const r = parseInt(hex.slice(1,3),16);
    const g = parseInt(hex.slice(3,5),16);
    const b = parseInt(hex.slice(5,7),16);
    return `rgba(${r},${g},${b},${alpha})`;
  }
  return hex;
}

/* ══════════════════════════════════════════════════════════
   PROFILE TAB
══════════════════════════════════════════════════════════ */
$('addSubmissionBtn').addEventListener('click', () => {
  const wrapper = document.createElement('div');
  wrapper.className = 'mb-2 position-relative';
  const count = document.querySelectorAll('.prof-submission').length + 1;
  wrapper.innerHTML = `
    <textarea class="form-control mono-text prof-submission" rows="4"
      placeholder="Submission ${count} — paste verified text…"></textarea>
    <button class="btn btn-xs btn-ghost position-absolute top-0 end-0 mt-1 me-1 remove-sub-btn"
      title="Remove">
      <i class="bi bi-x"></i>
    </button>`;
  wrapper.querySelector('.remove-sub-btn').addEventListener('click', () => wrapper.remove());
  $('submissionInputs').appendChild(wrapper);
});

$('profileBtn').addEventListener('click', async () => {
  const name = $('prof-name').value.trim() || 'Anonymous';
  const texts = [...document.querySelectorAll('.prof-submission')]
    .map(t => t.value.trim()).filter(Boolean);
  if (!texts.length) { alert('Add at least one submission.'); return; }

  showLoading('Building student profile…');
  try {
    const res = await fetch('/api/profile', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ student_name: name, submissions: texts }),
    });
    const data = await res.json();
    if (data.error) { alert(data.error); return; }
    renderProfileResults(data);
    state.stats.profiles++;
    updateStats();
  } catch (err) {
    alert('Error: ' + err.message);
  } finally {
    hideLoading();
  }
});

function renderProfileResults(data) {
  $('profilePlaceholder').style.display = 'none';
  $('profileResults').style.display = 'block';

  // Flatten baseline for display
  const flat = {};
  for (const [k, v] of Object.entries(data.baseline || {})) {
    flat[k + ' (mean)'] = v.mean;
    flat[k + ' (range)'] = `${v.min} – ${v.max}`;
  }
  renderFeatureGrid('baselineGrid', flat);
  $('profileText').innerHTML = renderMarkdown(data.ai_profile || '');
}

/* ══════════════════════════════════════════════════════════
   DASHBOARD
══════════════════════════════════════════════════════════ */
function logEntry(data) {
  const level  = data.ai_risk_level || 'Low';
  const name   = data.student_name  || 'Anonymous';
  const assign = data.assignment_name || 'Untitled';
  const ts     = new Date().toLocaleTimeString();

  state.log.unshift({ level, name, assign, ts });
  state.riskCounts[level] = (state.riskCounts[level] || 0) + 1;
  state.stats.analysed++;
  if (level === 'High' || level === 'Critical') state.stats.flagged++;
  else state.stats.clear++;
  updateStats();
  updateLog();
  drawRiskChart();
}

function updateStats() {
  $('stat-analysed').textContent = state.stats.analysed;
  $('stat-flagged').textContent  = state.stats.flagged;
  $('stat-clear').textContent    = state.stats.clear;
  $('stat-profiles').textContent = state.stats.profiles;
}

function updateLog() {
  const container = $('analysisLog');
  if (!state.log.length) return;
  container.innerHTML = state.log.slice(0, 20).map(e => `
    <div class="log-entry">
      <div class="log-icon" style="background:${riskHex(e.level,.15)};color:${riskHex(e.level)}">
        <i class="bi bi-${e.level === 'Low' ? 'check-circle' : 'exclamation-triangle'}"></i>
      </div>
      <div class="flex-grow-1">
        <strong>${escapeHtml(e.name)}</strong>
        <span class="text-muted ms-1">— ${escapeHtml(e.assign)}</span>
      </div>
      <span class="badge badge-risk badge-${e.level}">${e.level}</span>
      <span class="text-muted small ms-2">${e.ts}</span>
    </div>`).join('');
}

/* ── Mini SVG bar chart for risk distribution ─────────── */
function drawRiskChart() {
  const svg  = $('riskSvg');
  const levels = ['Low','Medium','High','Critical'];
  const colors = ['#16a34a','#ca8a04','#dc6803','#dc2626'];
  const counts = levels.map(l => state.riskCounts[l] || 0);
  const max = Math.max(...counts, 1);

  const W = 200, H = 120, barW = 30, gap = 10, padL = 20, padB = 30, padT = 10;
  const chartH = H - padB - padT;
  const startX = (W - levels.length * (barW + gap) + gap) / 2;

  let bars = '';
  levels.forEach((l, i) => {
    const x = startX + i * (barW + gap);
    const barH = Math.round((counts[i] / max) * chartH);
    const y = padT + chartH - barH;
    bars += `
      <rect x="${x}" y="${y}" width="${barW}" height="${barH}" fill="${colors[i]}" rx="3" opacity=".85"/>
      <text x="${x + barW/2}" y="${H - padB + 14}" text-anchor="middle"
        font-size="9" fill="var(--muted)" font-family="system-ui">${l}</text>
      <text x="${x + barW/2}" y="${y - 3}" text-anchor="middle"
        font-size="9" fill="${colors[i]}" font-weight="600">${counts[i]}</text>`;
  });

  svg.innerHTML = bars;
}

function refreshDashboard() {
  updateStats();
  updateLog();
  drawRiskChart();
  fetchHealth();
}

async function fetchHealth() {
  try {
    const res = await fetch('/api/health');
    const d   = await res.json();
    const yn  = v => v ? '<span class="badge bg-success">Yes</span>' : '<span class="badge bg-warning">No</span>';
    $('ss-model').textContent   = d.model || '—';
    $('ss-nltk').innerHTML      = yn(d.nltk);
    $('ss-sklearn').innerHTML   = yn(d.sklearn);
    $('statusPill').innerHTML   = '<i class="bi bi-circle-fill pulse-dot"></i> Agent Online';
  } catch (e) {
    $('statusPill').innerHTML = '<i class="bi bi-circle-fill" style="color:#f87171"></i> Offline';
  }
}

/* ══════════════════════════════════════════════════════════
   UTILS
══════════════════════════════════════════════════════════ */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Init ───────────────────────────────────────────────── */
fetchHealth();
