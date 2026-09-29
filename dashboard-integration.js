/**
 * Dashboard Frontend Integration Module
 * Wires sihfrontend.html to the FastAPI backend (api_server.py)
 *
 * This module handles:
 * - Page navigation and routing
 * - API calls to backend endpoints
 * - Form submission (FIR registration)
 * - Chart rendering with live data
 * - Chat interface for AI Assistant
 * - Investigation page sub-tabs
 * - Report Analysis page + FIR PDF upload/extraction
 * - Toast notifications
 */

// ============================================================================
// CONFIGURATION
// ============================================================================
const API_BASE = window.location.origin + '/api';

// Small inline image icon (data URI) used next to Suspicious Activity alert
// titles in the Structural Alerts / Statistical Alerts panels.
const ALERT_ICON_SRC = 'data:image/png;base64,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';

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Show a toast notification
 */
function showToast(message, type = 'success') {
  const toast = document.querySelector('.toast') || createToast();
  toast.textContent = message;
  toast.className = `toast ${type}`;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}

function createToast() {
  const toast = document.createElement('div');
  toast.className = 'toast';
  document.body.appendChild(toast);
  return toast;
}

/**
 * Make API call (wrapper around fetch).
 *
 * PERFORMANCE: GET responses are cached for API_CACHE_TTL_MS and identical
 * requests that are already in flight share one network call. The Overview
 * and Network Analysis tabs both need /network, the Timeline tab and the map
 * both need /case-locations, and the Report page re-requests its config on
 * every visit -- previously each of those hit the server (and re-ran its
 * pandas/networkx work) every single time. Any write (POST/PUT/DELETE) or an
 * explicit clearApiCache() empties the cache so new FIRs show up immediately.
 */
const API_CACHE_TTL_MS = 20000;
const _apiCache = new Map();      // endpoint -> { t, data }
const _apiInflight = new Map();   // endpoint -> Promise

function clearApiCache() { _apiCache.clear(); _apiInflight.clear(); }

async function apiCall(endpoint, method = 'GET', data = null) {
  const isGet = method === 'GET';

  if (isGet) {
    const hit = _apiCache.get(endpoint);
    if (hit && Date.now() - hit.t < API_CACHE_TTL_MS) return hit.data;
    if (_apiInflight.has(endpoint)) return _apiInflight.get(endpoint);
  }

  const run = (async () => {
    try {
      const options = { method };
      if (!isGet) options.headers = { 'Content-Type': 'application/json' };
      if (data) options.body = JSON.stringify(data);

      const response = await fetch(`${API_BASE}${endpoint}`, options);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const json = await response.json();
      if (isGet) _apiCache.set(endpoint, { t: Date.now(), data: json });
      else clearApiCache();
      return json;
    } catch (error) {
      console.error(`API Error [${endpoint}]:`, error);
      showToast('Error communicating with server', 'error');
      return null;
    } finally {
      if (isGet) _apiInflight.delete(endpoint);
    }
  })();

  if (isGet) _apiInflight.set(endpoint, run);
  return run;
}

/**
 * Navigate to a page
 */
function navigateToPage(pageName) {
  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Show target page
  const page = document.getElementById(`page-${pageName}`);
  const navItem = document.querySelector(`[data-page="${pageName}"]`);

  if (page) {
    page.classList.add('active');
  }
  if (navItem) {
    navItem.classList.add('active');
  }

  // Load page-specific data
  loadPageData(pageName);
}

/**
 * Load page-specific data from API
 */
async function loadPageData(pageName) {
  switch (pageName) {
    case 'dashboard':
      loadDashboardData();
      break;
    case 'investigation':
      loadInvestigationData();
      break;
    case 'reg-fir':
      loadFIRFormData();
      break;
    case 'report':
      loadReportData();
      break;
    case 'casebasket':
      initializeCaseBasketPage();
      break;
  }
}

// ============================================================================
// DASHBOARD PAGE
// ============================================================================

let lastOverviewSig = null;

async function loadDashboardData() {
  const data = await apiCall('/overview');
  if (!data) return;

  // Coming back to the Dashboard with unchanged data used to destroy and
  // rebuild all four charts and the whole Leaflet marker layer every time.
  // Only redraw when the numbers actually changed.
  const sig = JSON.stringify(data);
  if (sig === lastOverviewSig) {
    if (typeof caseLocationMapInstance !== 'undefined' && caseLocationMapInstance) {
      setTimeout(() => caseLocationMapInstance.invalidateSize(), 50);   // map was display:none while away
    }
    return;
  }
  lastOverviewSig = sig;

  // NOTE: the original 4 stat cards (Missing Persons / UIDB / UIFP /
  // Preventive Actions) are CCTNS categories the synthetic FIR pipeline
  // does not generate — there's no real data for them, so they're left at
  // their static placeholder values in the HTML rather than faked here.
  // These are the numbers the pipeline actually produces, shown instead:
  document.getElementById('statTotalFir') && (document.getElementById('statTotalFir').textContent = data.stats?.total_fir ?? 0);
  document.getElementById('statTotalEntities') && (document.getElementById('statTotalEntities').textContent = data.stats?.total_entities ?? 0);
  document.getElementById('statTotalLinks') && (document.getElementById('statTotalLinks').textContent = data.stats?.total_links ?? 0);
  document.getElementById('statCriticalBridges') && (document.getElementById('statCriticalBridges').textContent = data.stats?.critical_bridges ?? 0);

  // Pending Tasks: the synthetic FIR pipeline doesn't generate a real
  // task queue, so /api/overview always returns pending_tasks: []. This
  // used to blindly overwrite pendingTasksBody with that empty array,
  // wiping out the (correct, matches the reference design) hardcoded rows
  // that sihfrontendtest.py's own renderPendingTasks() already draws on
  // load. Only overwrite with API data if the API actually returned rows;
  // per the design brief this table is fine hardcoded for now.
  const pendingBody = document.getElementById('pendingTasksBody');
  if (pendingBody && Array.isArray(data.pending_tasks) && data.pending_tasks.length) {
    pendingBody.innerHTML = data.pending_tasks.map(task => `
      <tr>
        <td>${task.task_name}</td>
        <td>${task.reg_date}</td>
        <td>${task.complaint_no}</td>
        <td><span class="badge">${task.status}</span></td>
      </tr>
    `).join('');
  }

  // Initialize charts
  initializeDonutCharts(data.crime_against_women, data.crime_against_children, data.crime_against_elders, data.stats?.total_fir || 0);
  initializeCaseCategoryChart(data.crime_category_breakdown || {});

  // Case Location + Cross-Jurisdictional Links map (replaces the old Crime
  // Trend chart) — defined in sihfrontendtest.py's inline <script>.
  if (typeof initCaseLocationMap === 'function') {
    initCaseLocationMap();
  }
}

// NOTE ON COLORS: Chart.js hands these strings straight to the Canvas 2D
// API's fillStyle, which -- unlike CSS on an actual DOM element -- cannot
// resolve custom properties like 'var(--purple-700)'. The browser silently
// drops the invalid color, which is why these charts rendered colorless.
// Using resolved hex values (matching the :root palette in sihfrontendtest.py)
// fixes this everywhere below.
const THEME = {
  purple: '#5a3a92', purple2: '#8a63b8',
  pink: '#c22a72', pink2: '#e37fab', pink3: '#f3b6cf',
  blue: '#2f8fd1', blue2: '#6cb3e0', blue3: '#a8d3ee',
  orange: '#e98a4e', orange2: '#f0ae82', orange3: '#f7d3ba',
  green: '#3fa66b', red: '#d1495b', muted: '#786f92', line: '#e4defa',
};
const CATEGORY_COLORS = {
  'Women/Children': THEME.pink, 'Violent': THEME.red, 'Property': THEME.orange,
  'Financial': '#8b5cf6', 'Cyber': THEME.blue, 'Organized': '#f97316',
  'State/Terror': '#7f1d1d', 'Other': THEME.muted,
};
// CCTNS / NCRB-equivalent display names for the case category labels.
// Keys stay as the short internal labels (used for data lookup + colors);
// only the on-screen text shown on the chart changes.
const CATEGORY_DISPLAY_NAMES = {
  'Organized': 'Organized Crime',
  'Property': 'Offences Against Property',
  'State/Terror': 'Offences Against State & Public Tranquility',
  'Women/Children': 'Crimes Against Women & Children',
  'Cyber': 'Cyber Crime & IT Act Offences',
  'Violent': 'Violent Crime / Offences Against Body',
};

// Chart instances are tracked and destroyed before being redrawn.
// Previously nothing destroyed the old instance, so every time
// loadDashboardData() ran again (e.g. navigating back to the dashboard)
// Chart.js stacked a new chart on the same <canvas>, which is what made
// these charts appear to keep growing/collapsing on reload.
let donutWomenChartInstance, donutChildrenChartInstance,
    donutEldersChartInstance, caseCategoryChartInstance;

/**
 * Crime Against Women / Children / Elders donuts. Pink for women, blue for
 * children, orange for elders -- matching the same three theme families
 * used everywhere else in this dashboard (--pink / --blue / --orange).
 *
 * FIX: these used to divide each category's case COUNT against a hardcoded
 * denominator of 100 (as if `cases` were already a percentage), e.g.
 * `100 - (womenData?.cases || 0)`. The backend (_build_overview() in
 * sihfrontendtest.py) actually returns a raw count out of the total FIRs
 * in the dataset -- and by default the synthetic pipeline only generates
 * 20 total cases (PIPELINE_NUM_CASES). So a real, sizeable share like
 * "3 of 20 cases" rendered as "3 of 100", making every donut look almost
 * empty regardless of how significant that category actually was. Each
 * donut now uses the real total FIR count as its denominator, so the
 * filled portion reflects each category's true share of all cases.
 */
function initializeDonutCharts(womenData, childrenData, eldersData, totalCases) {
  const canvasWomen = document.getElementById('donutWomen');
  const canvasChildren = document.getElementById('donutChildren');
  const canvasElders = document.getElementById('donutElders');
  const total = totalCases || 0;

  function donutData(count) {
    // Guard against a zero/undefined total so the donut doesn't render as
    // fully "remaining" (or NaN) when there's no data yet.
    const c = count || 0;
    const remaining = total > 0 ? Math.max(0, total - c) : 0;
    return [c, remaining];
  }

  if (canvasWomen) {
    if (donutWomenChartInstance) donutWomenChartInstance.destroy();
    donutWomenChartInstance = new Chart(canvasWomen, {
      type: 'doughnut',
      data: {
        labels: ['Reported', 'Remaining'],
        datasets: [{
          data: donutData(womenData?.cases),
          backgroundColor: [THEME.pink, THEME.pink3],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '68%',
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true, callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed}` } },
        },
      },
    });
  }

  if (canvasChildren) {
    if (donutChildrenChartInstance) donutChildrenChartInstance.destroy();
    donutChildrenChartInstance = new Chart(canvasChildren, {
      type: 'doughnut',
      data: {
        labels: ['Reported', 'Remaining'],
        datasets: [{
          data: donutData(childrenData?.cases),
          backgroundColor: [THEME.blue, THEME.blue3],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '68%',
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true, callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed}` } },
        },
      },
    });
  }

  if (canvasElders) {
    if (donutEldersChartInstance) donutEldersChartInstance.destroy();
    donutEldersChartInstance = new Chart(canvasElders, {
      type: 'doughnut',
      data: {
        labels: ['Reported', 'Remaining'],
        datasets: [{
          data: donutData(eldersData?.cases),
          backgroundColor: [THEME.orange, THEME.orange3],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '68%',
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true, callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed}` } },
        },
      },
    });
  }
}

/**
 * Case Category Breakdown -- ported from sihdashboard.py's Analytics page
 * (same CATEGORY_COLORS palette), shown under the Case Distribution donuts.
 */
function initializeCaseCategoryChart(categoryCounts) {
  const canvas = document.getElementById('caseCategoryChart');
  if (!canvas) return;

  const keys = Object.keys(categoryCounts);
  const displayLabels = keys.map(k => CATEGORY_DISPLAY_NAMES[k] || k);
  if (caseCategoryChartInstance) caseCategoryChartInstance.destroy();
  caseCategoryChartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: displayLabels,
      datasets: [{
        data: keys.map(k => categoryCounts[k]),
        backgroundColor: keys.map(k => CATEGORY_COLORS[k] || '#818cf8'),
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { enabled: true, callbacks: { label: (ctx) => `${ctx.label}: ${ctx.parsed.y} cases` } },
      },
      scales: {
        y: { beginAtZero: true, grid: { color: THEME.line } },
        x: {
          grid: { display: false },
          ticks: {
            autoSkip: false,
            maxRotation: 40,
            minRotation: 0,
            font: { size: 10 },
          },
        },
      },
    },
  });
}

// NOTE: the calendar (renderCalendar / calPrev / calNext) lives ONLY in the
// inline <script> of sihfrontendtest.py. This file used to define a second
// renderCalendar(year, month) with the same name. Being loaded later it
// silently REPLACED the inline one, so the inline setLang() -> renderCalendar()
// call (no arguments) produced "Invalid Date" and an empty grid, and every
// dashboard visit stacked another pair of prev/next click listeners.

// ============================================================================
// INVESTIGATION PAGE (with sub-tabs)
// ============================================================================

async function loadInvestigationData() {
  // Wire up the Overview / Network Analysis / Timeline / Suspicious
  // Activity / Persons & Witnesses submenu-tab buttons once.
  setupInvestigationSubTabs();

  // The "Overview" tab (Case Count / District Breakdown / Network Nodes /
  // Network Edges stats + the Network Overview and District Distribution
  // charts) is active by default, so populate it right away.
  loadInvestigationOverview();
}

/**
 * Wires clicks on the Investigation page's .submenu-tab buttons to show
 * the matching .page-tab-content panel (#inv-tab-<name>). Only attaches
 * the listeners once, since loadInvestigationData() runs every time the
 * Investigation page is opened.
 *
 * BUG FIXED: this used to only load data for the 'overview' tab -- clicking
 * Network Analysis / Timeline / Suspicious Activity / Persons & Witnesses
 * correctly switched which panel was visible, but never fetched anything,
 * so those tabs always looked empty/broken. Every tab now has a loader.
 */
function setupInvestigationSubTabs() {
  const page = document.getElementById('page-investigation');
  if (!page || page.dataset.subtabsWired) return;
  page.dataset.subtabsWired = 'true';

  page.querySelectorAll('.submenu-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      page.querySelectorAll('.submenu-tab').forEach(b => b.classList.remove('active'));
      page.querySelectorAll('.page-tab-content').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      document.getElementById(`inv-tab-${btn.dataset.tab}`)?.classList.add('active');

      loadInvestigationTabData(btn.dataset.tab);
    });
  });
}

function loadInvestigationTabData(tabName) {
  switch (tabName) {
    case 'overview': loadInvestigationOverview(); break;
    case 'network': loadInvestigationNetworkTab(); break;
    case 'timeline': loadInvestigationTimelineTab(); break;
    case 'alerts': loadInvestigationAlertsTab(); break;
    case 'persons': loadInvestigationPersonsTab(); break;
  }
}

// ----------------------------------------------------------------------
// Overview tab: stat cards + Network Overview (degree centrality) +
// District Distribution charts. Mirrors sihdashboard.py's Analytics page
// (Degree Centrality bar chart / District Distribution donut), recolored
// for this app's light theme and rendered with Chart.js instead of Plotly.
// ----------------------------------------------------------------------
let networkOverviewChartInstance, districtChartInstance;

// Same 9-district palette family as the app's own donut charts
// (var(--purple-700), var(--pink), var(--blue), var(--orange), ...),
// just extended to cover every CCTNS district.
const DISTRICT_CHART_COLORS = [
  '#5a3a92', '#c22a72', '#2f8fd1', '#e98a4e', '#3fa66b',
  '#d1495b', '#8a63b8', '#e3a6c6', '#786f92',
];

async function loadInvestigationOverview() {
  const data = await apiCall('/network');
  if (!data) return;

  const summary = data.summary || {};
  const districtCounts = data.district_counts || {};

  document.getElementById('statInvCaseCount') &&
    (document.getElementById('statInvCaseCount').textContent =
      Object.values(districtCounts).reduce((a, b) => a + b, 0));
  document.getElementById('statInvDistrictCount') &&
    (document.getElementById('statInvDistrictCount').textContent = Object.keys(districtCounts).length);
  document.getElementById('statInvNetworkNodes') &&
    (document.getElementById('statInvNetworkNodes').textContent = summary.total_nodes ?? 0);
  document.getElementById('statInvNetworkEdges') &&
    (document.getElementById('statInvNetworkEdges').textContent = summary.total_edges ?? 0);

  renderNetworkOverviewChart(data.top_suspects || []);
  renderDistrictDistributionChart(districtCounts);
}

/** "Network Overview" card -- degree centrality of the top ranked entities. */
function renderNetworkOverviewChart(topSuspects) {
  const canvas = document.getElementById('networkOverviewChart');
  if (!canvas) return;

  const top = topSuspects.slice(0, 15);
  const labels = top.map(s => s.label ?? s.name ?? s.id ?? '');
  const values = top.map(s => s.degree ?? s.score ?? 0);

  if (networkOverviewChartInstance) networkOverviewChartInstance.destroy();
  networkOverviewChartInstance = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Degree Centrality',
        data: values,
        backgroundColor: '#5a3a92',
        borderRadius: 4,
        maxBarThickness: 28,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, grid: { color: '#e4defa' }, ticks: { color: '#786f92' } },
        x: { grid: { display: false }, ticks: { color: '#786f92', font: { size: 9 }, maxRotation: 45, minRotation: 45 } },
      },
    },
  });
}

/** "District Distribution" card -- reported case count per district. */
function renderDistrictDistributionChart(districtCounts) {
  const canvas = document.getElementById('districtChart');
  if (!canvas) return;

  const labels = Object.keys(districtCounts);
  const values = Object.values(districtCounts);

  if (districtChartInstance) districtChartInstance.destroy();
  districtChartInstance = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: labels.map((_, i) => DISTRICT_CHART_COLORS[i % DISTRICT_CHART_COLORS.length]),
        borderWidth: 2,
        borderColor: '#ffffff',
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '55%',
      plugins: {
        legend: { display: true, position: 'right', labels: { color: '#241a38', boxWidth: 12, font: { size: 10 } } },
      },
    },
  });
}

function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}

// ----------------------------------------------------------------------
// Network Analysis tab: #topSuspectsTable, #bridgesList,
// plus the Pattern Intelligence Engine panel (#patternIntelList), ported
// from sihdashboard.py's "Pattern Intelligence Engine -- Statistical
// Anomaly Alerts" section and placed next to Top Suspects as requested.
// #networkMapFrame is a plain <iframe src="/api/network/map">, so it needs
// no JS wiring here -- the backend serves that page directly.
// ----------------------------------------------------------------------
async function loadInvestigationNetworkTab() {
  // The pyvis network map is heavy; it is only fetched once the tab is opened.
  const mapFrame = document.getElementById('networkMapFrame');
  if (mapFrame && !mapFrame.getAttribute('src') && mapFrame.dataset.src) {
    mapFrame.src = mapFrame.dataset.src;
  }
  const [network, alerts] = await Promise.all([apiCall('/network'), apiCall('/alerts')]);

  if (network) {
    // Toll plaza entities (e.g. "TP-0102 / Vashi Toll Plaza") are camera
    // infrastructure nodes, not persons -- they can't be suspects, so
    // they're filtered out of the ranked list before it's rendered.
    const isTollPlaza = s => /toll plaza/i.test(s.label || '') || /^tp-\d/i.test(s.label || '') || /^tp-\d/i.test(s.id || '');
    const suspects = (network.top_suspects || []).filter(s => !isTollPlaza(s));
    const tbody = document.getElementById('topSuspectsTable');
    if (tbody) {
      tbody.innerHTML = suspects.slice(0, 10).map((s, i) => `
        <tr>
          <td>${i + 1}</td>
          <td>${escapeHtml(s.label)}</td>
          <td>${(s.composite_score ?? s.score ?? 0)}</td>
          <td>${s.case_count ?? '—'}</td>
        </tr>
      `).join('') || '<tr><td colspan="4">No ranked suspects in this batch yet.</td></tr>';
    }

    const bridges = network.critical_bridges || [];
    const bridgesEl = document.getElementById('bridgesList');
    if (bridgesEl) {
      bridgesEl.innerHTML = bridges.slice(0, 8).map(b => `
        <div class="pi-alert sev-medium">
          <div class="pi-title">${escapeHtml(b.source_label ?? b.source)} ↔ ${escapeHtml(b.target_label ?? b.target)}</div>
          <div class="pi-text">Structural bridge -- removing this link splits the network.</div>
        </div>
      `).join('') || '<p style="font-size:12.5px;color:var(--muted);">No critical bridges detected.</p>';
    }
  }

  const piEl = document.getElementById('patternIntelList');
  if (piEl) {
    const statistical = (alerts && alerts.statistical) || [];
    piEl.innerHTML = statistical.length
      ? statistical.slice(0, 12).map(a => {
          const sev = String(a.severity || '').toLowerCase();
          return `
            <div class="pi-alert sev-${sev}">
              <div class="pi-title">[${(a.severity || '').toUpperCase()}] ${escapeHtml(a.type)} · score ${a.score ?? '—'}</div>
              <div class="pi-text">${escapeHtml(a.details)}${(a.entities && a.entities.length) ? '<br>Entities: ' + escapeHtml(a.entities.slice(0, 5).join(', ')) : ''}</div>
            </div>
          `;
        }).join('')
      : '<p style="font-size:12.5px;color:var(--muted);">No statistical pattern anomalies detected in this batch.</p>';
  }
}

// ----------------------------------------------------------------------
// Timeline tab: #timelineFirSelect + #timelineContainer
//
// sihtimeline.py's TimelineCorrelationEngine.build_case_timeline() already
// supports scoping to one FIR (selected_case_id) and /api/timeline already
// accepts ?case_id=..., but this tab used to call it with no case_id at
// all, so every FIR's events came back mixed together with no way to pick
// one. It now mirrors the Case Location map's own "select a FIR" pattern:
// a dropdown (populated from the same /api/case-locations list) drives a
// case_id-scoped fetch, and the event cards below carry the same fields
// sihtimeline.py builds per event (Person, Location, Source, Risk Score),
// styled as this app's own cards instead of a Streamlit/Plotly chart.
// ----------------------------------------------------------------------

// Matches sihtimeline.py's TimelineCorrelationEngine.EVENT_COLOR_MAP.
const TIMELINE_EVENT_COLORS = {
  'Occurrence': '#EF4444',
  'FIR Report': '#F59E0B',
  'Call': '#3B82F6',
  'FASTag / Vehicle': '#10B981',
  'Bank Transaction': '#8B5CF6',
  'Crypto': '#EC4899',
  'Anomaly Alert': '#DC2626',
};

let timelineFirOptionsLoaded = false;
let chronologyChartInstance = null;

// ----------------------------------------------------------------------
// Interactive Multi-Event Chronology Chart -- ported from sihtimeline.py's
// render_timeline_page(): a Plotly px.scatter with x=DateTime, y=Person,
// color=Event Type, size=Risk Score. Rebuilt as a Chart.js bubble chart
// (this app has no Plotly runtime), fed by the same event list the Event
// Timeline cards below already fetch, so the two stay in sync.
// ----------------------------------------------------------------------
function renderChronologyChart(events) {
  const canvas = document.getElementById('chronologyChart');
  const emptyEl = document.getElementById('chronologyChartEmpty');
  const legendEl = document.getElementById('chronologyChartLegend');
  if (!canvas) return;

  if (chronologyChartInstance) { chronologyChartInstance.destroy(); chronologyChartInstance = null; }

  if (!events.length) {
    canvas.style.display = 'none';
    if (emptyEl) emptyEl.style.display = 'block';
    if (legendEl) legendEl.innerHTML = '';
    return;
  }
  canvas.style.display = 'block';
  if (emptyEl) emptyEl.style.display = 'none';

  // Person / entity list drives the category (y) axis, in first-seen
  // chronological order -- matches how Plotly lays out a categorical axis
  // from row order in sihtimeline.py's DataFrame.
  const persons = [];
  events.forEach(e => { const p = e.person || 'Unknown'; if (!persons.includes(p)) persons.push(p); });

  // One Chart.js dataset per Event Type == one colored series in the
  // Plotly chart's legend/color axis (color_discrete_map=EVENT_COLOR_MAP).
  const byType = {};
  events.forEach(e => {
    const type = e.type || 'Other';
    (byType[type] = byType[type] || []).push(e);
  });

  const datasets = Object.keys(byType).map(type => ({
    label: type,
    backgroundColor: (TIMELINE_EVENT_COLORS[type] || '#5a3a92') + 'cc',
    borderColor: '#2b2140',
    borderWidth: 1,
    data: byType[type].map(e => {
      const risk = Number(e.risk_score) || 0;
      return {
        x: new Date(String(e.timestamp).replace(' ', 'T')).getTime(),
        y: e.person || 'Unknown',
        r: 4 + (Math.min(Math.max(risk, 0), 100) / 100) * 14, // Risk Score -> bubble size, same role as Plotly's size="Risk Score"
        _event: e,
      };
    }),
  }));

  if (legendEl) {
    legendEl.innerHTML = `<span style="width:100%;font-weight:600;color:var(--ink);">Event Type</span>` +
      Object.keys(byType).map(type => {
        const color = TIMELINE_EVENT_COLORS[type] || '#5a3a92';
        return `<span style="display:inline-flex;align-items:center;gap:4px;"><span style="width:9px;height:9px;border-radius:50%;background:${color};display:inline-block;"></span>${escapeHtml(type)}</span>`;
      }).join('');
  }

  chronologyChartInstance = new Chart(canvas, {
    type: 'bubble',
    data: { datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }, // custom legend above (chronologyChartLegend) mirrors the Case Location map's own legend pattern
        // Zoom/pan, from chartjs-plugin-zoom (vendored locally, see
        // ensure_chartjs_zoom_asset() in sihfrontendtest.py). If the plugin
        // script never loaded (no internet access to fetch it), Chart.js
        // just ignores this unknown plugin option block and the chart still
        // renders normally, minus scroll/drag zoom -- the on-screen +/−
        // buttons then also no-op via the same typeof check in
        // zoomChronologyChart()/resetChronologyChartZoom() below.
        zoom: {
          pan: { enabled: true, mode: 'x', modifierKey: null },
          zoom: {
            wheel: { enabled: true, speed: 0.08 },
            pinch: { enabled: true },
            drag: { enabled: false },
            mode: 'x',
          },
          limits: { x: { min: 'original', max: 'original' } },
        },
        tooltip: {
          callbacks: {
            title: (items) => items[0]?.raw?._event?.type || '',
            label: (item) => {
              const e = item.raw._event;
              const lines = [
                (e.person || 'Unknown') + ' — ' + (e.timestamp || ''),
                e.description || '',
              ];
              if (e.location) lines.push('Location: ' + e.location);
              if (e.case_id) lines.push('Case: ' + e.case_id);
              if (e.source) lines.push('Source: ' + e.source);
              lines.push('Risk Score: ' + (e.risk_score ?? '—') + '/100');
              return lines;
            },
          },
        },
      },
      scales: {
        x: {
          type: 'linear',
          title: { display: true, text: 'Timeline (Occurrence → Reporting → Events)', color: '#786f92', font: { size: 11 } },
          grid: { color: '#e4defa' },
          ticks: {
            color: '#786f92',
            font: { size: 9 },
            callback: (val) => {
              const d = new Date(val);
              return isNaN(d) ? '' : d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            },
          },
        },
        y: {
          type: 'category',
          labels: persons,
          title: { display: true, text: 'Entity / Involved Person / Vehicle', color: '#786f92', font: { size: 11 } },
          grid: { color: '#e4defa' },
          ticks: { color: '#786f92', font: { size: 9.5 } },
        },
      },
    },
  });
}

// Zoom in/out/reset controls for chronologyChartInstance. Guarded with
// typeof checks because the underlying chart.zoom()/resetZoom() methods
// only exist once chartjs-plugin-zoom has actually registered itself
// (i.e. the vendored script under /static/js/ loaded successfully).
function zoomChronologyChart(factor) {
  if (chronologyChartInstance && typeof chronologyChartInstance.zoom === 'function') {
    chronologyChartInstance.zoom(factor);
  }
}

function resetChronologyChartZoom() {
  if (chronologyChartInstance && typeof chronologyChartInstance.resetZoom === 'function') {
    chronologyChartInstance.resetZoom();
  }
}

async function loadInvestigationTimelineTab() {
  const container = document.getElementById('timelineContainer');
  const sel = document.getElementById('timelineFirSelect');
  if (!container) return;

  // Populate the FIR dropdown once (same case list as the Case Location
  // map), then keep whatever the user has selected on every later call --
  // repopulating on each change would just reset their selection.
  if (sel && !timelineFirOptionsLoaded) {
    const locData = await apiCall('/case-locations');
    const cases = (locData && locData.cases) || [];
    sel.innerHTML = cases.map(c => `<option value="${c.fir_no}">${c.fir_no}</option>`).join('');
    timelineFirOptionsLoaded = true;
  }

  const firNo = sel && sel.value;
  if (!firNo) {
    container.innerHTML = '<p style="text-align:center;color:var(--muted);font-size:12.5px;">No FIRs available yet.</p>';
    renderChronologyChart([]);
    return;
  }

  const data = await apiCall('/timeline?case_id=' + encodeURIComponent(firNo));
  const events = (data && data.events) || [];
  renderChronologyChart(events);
  container.innerHTML = events.length
    ? events.map(e => {
        const color = TIMELINE_EVENT_COLORS[e.type] || '#5a3a92';
        return `
          <div style="padding:12px;margin-bottom:8px;border-left:3px solid ${color};background:var(--purple-050);border-radius:4px;">
            <div style="display:flex;justify-content:space-between;align-items:baseline;gap:8px;flex-wrap:wrap;">
              <div style="font-weight:600;color:var(--ink);font-size:12.5px;">${escapeHtml(e.type)}</div>
              <span class="badge" style="background:${color}22;color:${color};">Risk ${e.risk_score ?? '—'}</span>
            </div>
            <div style="font-size:11px;color:var(--muted);margin-top:2px;">
              ${escapeHtml(e.timestamp)}${e.location ? ' · ' + escapeHtml(e.location) : ''}${e.person ? ' · ' + escapeHtml(e.person) : ''}
            </div>
            <div style="margin-top:4px;color:var(--ink);font-size:12.5px;">${escapeHtml(e.description)}</div>
            <div style="margin-top:4px;font-size:10.5px;color:var(--muted);">${escapeHtml(e.case_id)} — ${escapeHtml(e.source)}</div>
          </div>
        `;
      }).join('')
    : `<p style="text-align:center;color:var(--muted);font-size:12.5px;">No events recorded for ${escapeHtml(firNo)}.</p>`;
}

// ----------------------------------------------------------------------
// Suspicious Activity tab: #structuralAlertsList, #statisticalAlertsList
// ----------------------------------------------------------------------
async function loadInvestigationAlertsTab() {
  const data = await apiCall('/alerts');
  if (!data) return;

  const structEl = document.getElementById('structuralAlertsList');
  if (structEl) {
    structEl.innerHTML = (data.structural || []).map(a => `
      <div class="pi-alert sev-high">
        <div class="pi-title"><span>${escapeHtml(a.type)}</span><img class="pi-alert-icon" src="${ALERT_ICON_SRC}" alt="" width="26" height="26"></div>
        <div class="pi-text">${escapeHtml(a.details)}</div>
      </div>
    `).join('') || '<p style="font-size:12.5px;color:var(--muted);">No structural network alerts.</p>';
  }

  const statEl = document.getElementById('statisticalAlertsList');
  if (statEl) {
    statEl.innerHTML = (data.statistical || []).map(a => {
      const sev = String(a.severity || '').toLowerCase();
      return `
        <div class="pi-alert sev-${sev}">
          <div class="pi-title"><span>[${(a.severity || '').toUpperCase()}] ${escapeHtml(a.type)}</span><img class="pi-alert-icon" src="${ALERT_ICON_SRC}" alt="" width="26" height="26"></div>
          <div class="pi-text">${escapeHtml(a.details)}</div>
        </div>
      `;
    }).join('') || '<p style="font-size:12.5px;color:var(--muted);">No statistical alerts.</p>';
  }
}

// ----------------------------------------------------------------------
// Persons & Witnesses tab: #personsByRoleTable, #entityTypesList,
// #personsTable, #duplicatesList
// (ported from sihdashboard.py's "Persons and Witnesses" page, which has
// three sub-tabs: Persons / Entities by Type / Possible Same Person -- all
// three are surfaced here from the one /api/persons payload.)
// ----------------------------------------------------------------------

// Same 9-district-ish palette reused for entity-type counts.
const ENTITY_TYPE_COLORS = {
  PERSON: '#818cf8', PHONE: '#38bdf8', VEHICLE: '#f59e0b',
  ACCOUNT: '#a855f7', LOCATION: '#10b981', CASE: '#ef4444',
};

let personsByRoleData = [];

function renderPersonsByRoleTable() {
  const tbody = document.getElementById('personsByRoleTable');
  if (!tbody) return;
  const roleF = document.getElementById('personsRoleFilter')?.value || '';
  const rows = roleF ? personsByRoleData.filter(p => p.role === roleF) : personsByRoleData;
  tbody.innerHTML = rows.map(p => `
    <tr>
      <td>${escapeHtml(p.name)}</td>
      <td>${escapeHtml(p.role)}</td>
      <td>${escapeHtml(p.case_id)}</td>
      <td>${escapeHtml(p.district)}</td>
      <td>${p.connections ?? 0}</td>
    </tr>
  `).join('') || '<tr><td colspan="5" style="text-align:center;color:var(--muted);">No persons available in the current batch.</td></tr>';
}

async function loadInvestigationPersonsTab() {
  const data = await apiCall('/persons');
  if (!data) return;

  personsByRoleData = data.by_role || [];
  renderPersonsByRoleTable();

  const typesEl = document.getElementById('entityTypesList');
  if (typesEl) {
    const types = data.entity_types || [];
    const maxCount = Math.max(1, ...types.map(t => t.count));
    typesEl.innerHTML = types.map(t => {
      const color = ENTITY_TYPE_COLORS[t.type] || '#94a3b8';
      const pct = Math.round((t.count / maxCount) * 100);
      return `
        <div style="margin-bottom:10px;">
          <div style="display:flex;justify-content:space-between;font-size:12.5px;color:var(--ink);margin-bottom:3px;">
            <span>${escapeHtml(t.type)}</span><span style="color:var(--muted);">${t.count}</span>
          </div>
          <div style="background:var(--purple-050);border-radius:4px;height:6px;overflow:hidden;">
            <div style="width:${pct}%;height:100%;background:${color};"></div>
          </div>
        </div>
      `;
    }).join('') || '<p style="font-size:12.5px;color:var(--muted);">No entities in the graph yet.</p>';
  }

  const tbody = document.getElementById('personsTable');
  if (tbody) {
    tbody.innerHTML = (data.confirmed_merges || []).map(m => `
      <tr>
        <td>${escapeHtml(m.canonical_id)}</td>
        <td>${(m.aliases || []).map(escapeHtml).join(', ') || '—'}</td>
        <td>${typeof m.confidence === 'number' ? m.confidence.toFixed(2) : (m.confidence ?? '—')}</td>
      </tr>
    `).join('') || '<tr><td colspan="3" style="text-align:center;color:var(--muted);">No confirmed alias merges in the current batch.</td></tr>';
  }

  const dupEl = document.getElementById('duplicatesList');
  if (dupEl) {
    dupEl.innerHTML = (data.review_queue || []).map(p => `
      <div class="pi-alert sev-medium">
        <div class="pi-title">${escapeHtml(p.person_a)} ⇄ ${escapeHtml(p.person_b)}</div>
        <div class="pi-text">Match score: ${typeof p.score === 'number' ? p.score.toFixed(2) : (p.score ?? '—')}</div>
      </div>
    `).join('') || '<p style="font-size:12.5px;color:var(--muted);">No possible duplicates flagged.</p>';
  }
}

// ============================================================================
// FIR REGISTRATION (7-step merged form)
// ============================================================================

async function loadFIRFormData() {
  // wires the Manual Registration / Upload FIR (PDF) sub-tabs (once)
  setupFirTabs();

  // Load dropdown data
  const districts = await apiCall('/districts');
  if (districts?.districts) {
    const districtSelect = document.getElementById('fir-district');
    if (districtSelect) {
      districtSelect.innerHTML = '<option value="">Select District</option>' +
        districts.districts.map(d => `<option value="${d}">${d}</option>`).join('');
    }
  }
}

// ============================================================================
// REPORT ANALYSIS PAGE
// ----------------------------------------------------------------------------
// Port of sihdashboard.py's "Report Analysis" page: pick a case -> Case File
// -> Medical / Financial / Non-Media / Multimedia tabs (each with Reports +
// Analysis sub-tabs) -> Full Unified Investigation Report.
// Connectivity is deliberately not shown anywhere on this page.
// Data comes from the /api/reports/* routes in sihfrontendtest.py.
// ============================================================================
const RPT = {
  cfg: null,        // /api/reports/config
  caseId: null,
  uploads: {},      // "case||tab||module" -> [{name, size, uploaded_at}]  (session only)
  files: {},        // same key -> File, kept so "Run Analysis" can still send it
  tables: {},       // id -> rows, used by the chat message filter
  tableSeq: 0,
};

const RPT_FORENSIC_TABS = [
  { name: 'Medical Forensic',
    caption: 'All Medico-Legal & Forensic Reports generated for this case (MLC, post-mortem, toxicology, DNA, SAFE, odontology, skeletal, psychiatric).' },
  { name: 'Financial Forensic',
    caption: 'Financial & Banking Intelligence, Cryptocurrency Intelligence, and Corporate & Tax Intelligence reports for this case.' },
  { name: 'Non-Media Forensic',
    caption: 'Non-media digital forensic findings for this case — Telecom Intelligence and Vehicle & Location Intelligence are live; the remaining digital-forensics artifact categories below are under construction.' },
  { name: 'Multimedia Digital Forensic',
    caption: 'Multimedia & digital media analysis for this case — chats, audio, video, and image forensics. This tab is entirely under construction until evidence is uploaded via Analysis.' },
];

const RPT_LIVE_NOTES = {
  'Chats Analysis': 'BASIC tier: .db / .sqlite / .json / .xml are parsed now. .crypt14, .crypt15 and .ufdr are HEAVY-tier formats not yet built — uploading one returns a clear message instead of a crash.',
  'Video Analysis': 'BASIC tier: Extracts container metadata, detects scene cuts as a tampering heuristic, and generates frame thumbnails. Does NOT include PRNU fingerprinting, optical-flow analysis, or deepfake detection (those are HEAVY-tier features).',
  'Audio Analysis': 'BASIC tier: Extracts audio metadata (duration, sample rate, channels), detects speech vs. silence segments via energy thresholds, generates a mel-scale spectrogram visualization, and computes MFCC feature statistics. Does NOT include speaker diarization, speaker verification, or forensic voice comparison (those are HEAVY-tier features requiring explicit legal disclaimer).',
  'Image Analysis': 'BASIC tier: Extracts EXIF metadata (GPS coordinates, capture timestamp, camera make/model, software tag), detects software-editing indicators, and performs Error Level Analysis (ELA) on JPEG files to highlight potential editing regions. ELA is not applicable to PNG/HEIC/RAW formats. Does NOT include PRNU sensor-fingerprint matching or DCT compression-variance analysis (those are HEAVY-tier features).',
};
const RPT_SAMPLE_HINTS = {
  'Chats Analysis': "Run analysis on a synthetic chat log generated from this case's own FIR data (informant/victim/accused names & numbers).",
  'Video Analysis': 'Run analysis on a synthetic video generated for this case. Shows how the analyzer handles scene cuts.',
  'Audio Analysis': 'Run analysis on a synthetic audio file (silence + speech-like tones).',
  'Image Analysis': 'Run analysis on a synthetic image generated for this case.',
};

const rptById = id => document.getElementById(id);
const rptEnc = encodeURIComponent;

function rptNow() {
  const d = new Date(), p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function rptAlert(kind, html) { return `<div class="rpt-alert ${kind}">${html}</div>`; }
function rptCurrentCase() {
  return (rptById('rptCaseTyped')?.value.trim()) || rptById('rptCaseSelect')?.value || '';
}

/**
 * Called by loadPageData() every time the Report page is opened. Builds the
 * static skeleton once, then refreshes the case list + layout each visit
 * (new FIRs / freshly generated CSVs show up without a page reload).
 */
async function loadReportData() {
  const root = rptById('reportRoot');
  if (!root) return;

  if (!root.dataset.built) {
    root.dataset.built = '1';
    root.innerHTML = `
      <div class="rpt-info">Select a Case / FIR number to open its case file, shown below. Then work through the 4 forensic tabs —
        <b>Medical Forensic</b>, <b>Financial Forensic</b>, <b>Non-Media Forensic</b>, and <b>Multimedia Digital Forensic</b> — each split
        into a <b>Reports</b> sub-tab (everything generated or uploaded for this case) and an <b>Analysis</b> sub-tab (upload raw evidence
        per module). The <b>Full Unified Investigation Report</b> sits at the bottom. Modules still on the roadmap are clearly marked
        <span class="rpt-uc-label">Under Construction</span> instead of showing broken or empty reports.</div>
      <div class="card">
        <div class="rpt-case-row">
          <div class="field"><label>Select Case / FIR No.</label><select id="rptCaseSelect"></select></div>
          <div class="field"><label>…or type a Case / FIR No. directly (overrides the dropdown)</label>
            <input id="rptCaseTyped" placeholder="e.g. FIR/2026/0007"></div>
        </div>
      </div>
      <div id="rptCaseBody"></div>`;

    rptById('rptCaseSelect').addEventListener('change', () => { rptById('rptCaseTyped').value = ''; rptRenderCase(); });
    rptById('rptCaseTyped').addEventListener('change', rptRenderCase);

    // one set of delegated listeners for everything rendered under #reportRoot
    root.addEventListener('click', rptOnClick);
    root.addEventListener('change', e => {
      const inp = e.target.closest('[data-rpt-upload]');
      if (inp) rptAttachFile(inp.dataset.rptUpload, inp);
    });
    root.addEventListener('toggle', e => {          // toggle doesn't bubble -> capture
      const d = e.target;
      if (d.open && d.matches?.('[data-rpt-mod][data-live="1"]')) rptLoadRuns(d.dataset.rptMod);
    }, true);

    // modal close bits (the modal itself lives in the page template)
    rptById('rptModalClose').addEventListener('click', rptCloseModal);
    rptById('rptModalBack').addEventListener('click', e => { if (e.target.id === 'rptModalBack') rptCloseModal(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape') rptCloseModal(); });
  }

  const [cfg, cases] = await Promise.all([apiCall('/reports/config'), apiCall('/reports/cases')]);
  if (!cfg || !cases) {
    rptById('rptCaseBody').innerHTML = rptAlert('err', 'Could not load the report catalog from the server. Check the server log.');
    return;
  }
  RPT.cfg = cfg;

  // Re-opening the Report tab used to tear down and rebuild the entire case
  // body (and reset the user's open sub-tabs) even when nothing had changed.
  const sig = JSON.stringify(cfg) + '|' + cases.cases.join(',');
  const body = rptById('rptCaseBody');
  if (sig === RPT.sig && RPT.caseId && RPT.caseId === rptCurrentCase() && body && body.children.length) return;
  RPT.sig = sig;

  const sel = rptById('rptCaseSelect');
  const prev = sel.value;
  sel.innerHTML = cases.cases.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
  if (prev && cases.cases.includes(prev)) sel.value = prev;

  await rptRenderCase();
}

async function rptRenderCase() {
  const body = rptById('rptCaseBody');
  const caseId = rptCurrentCase();
  if (!caseId) {
    body.innerHTML = rptAlert('warn', 'No FIR dataset is loaded yet — restart the server (or register a FIR) so the pipeline can generate it.');
    return;
  }
  const info = await apiCall(`/reports/case?case_id=${rptEnc(caseId)}`);
  if (!info?.found) {
    body.innerHTML = rptAlert('err', `No case found for '${escapeHtml(caseId)}'. Check the Case / FIR number and try again.`);
    return;
  }
  RPT.caseId = caseId;

  const metric = (k, v) => `<div class="rpt-metric"><div class="k">${k}</div><div class="v">${escapeHtml(v || '—')}</div></div>`;
  const tabBar = RPT_FORENSIC_TABS.map((t, i) =>
    `<div class="tab${i === 0 ? ' active' : ''}" data-target="rptTab-${i}">${t.name}</div>`).join('');
  const panels = RPT_FORENSIC_TABS.map((t, i) => `
    <div class="rpt-panel" id="rptTab-${i}"${i === 0 ? '' : ' style="display:none;"'}>
      <div class="rpt-tabgroup">
        <div class="tabs" data-tabgroup>
          <div class="tab active" data-target="rptSub-${i}-r">Reports</div>
          <div class="tab" data-target="rptSub-${i}-a">Analysis</div>
        </div>
        <div class="rpt-panel" id="rptSub-${i}-r">
          <div class="rpt-caption">${escapeHtml(t.caption)}</div>
          ${rptSectionsHtml(t.name)}
          <div data-rpt-uploaded="${escapeHtml(t.name)}"></div>
        </div>
        <div class="rpt-panel" id="rptSub-${i}-a" style="display:none;">${rptAnalysisHtml(t.name, i)}</div>
      </div>
    </div>`).join('');

  body.innerHTML = `
    <div class="rpt-metrics">
      ${metric('District', info.district)}${metric('Case Type', info.case_type)}${metric('Vulnerability', info.vulnerability)}
    </div>
    <hr class="rpt-hr">
    <div class="rpt-title" style="margin-top:0;">Case File</div>
    <div class="rpt-caption">FIR master record for the selected case.</div>
    ${rptSectionsHtml('Case File')}
    <hr class="rpt-hr">
    <div class="rpt-tabgroup"><div class="tabs" data-tabgroup>${tabBar}</div>${panels}</div>
    <hr class="rpt-hr">
    <div class="rpt-title" style="margin-top:0;">Full Unified Investigation Report</div>
    <div id="rptUnified"></div>
    <div id="rptAllUploads"></div>`;

  rptWireTabs(body);
  rptRestoreAttachments();
  rptRefreshUploads();
  rptLoadUnified(caseId);
}

function rptWireTabs(scope) {
  scope.querySelectorAll('.tabs[data-tabgroup]').forEach(bar => {
    bar.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
      bar.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t === tab));
      bar.parentElement.querySelectorAll(':scope > .rpt-panel').forEach(p => {
        p.style.display = p.id === tab.dataset.target ? '' : 'none';
      });
    }));
  });
}

// ---- Reports sub-tab: report buttons + "under construction" placeholders ----
function rptSectionsHtml(tabName) {
  const tab = RPT.cfg?.tabs?.[tabName];
  if (!tab) return '';
  const sections = tab.sections.map(sec => `
    <div class="rpt-title">${escapeHtml(sec.category)}</div>
    <div class="rpt-grid">${sec.reports.map(r => r.exists
      ? `<button class="btn rpt-btn" data-rpt-file="${escapeHtml(r.file)}" data-rpt-name="${escapeHtml(r.name)}">${escapeHtml(r.name)}</button>`
      : `<button class="btn rpt-btn" disabled>${escapeHtml(r.name)} (not generated)</button>`).join('')}
    </div>`).join('');
  return sections + rptUnderConstructionHtml(tabName, tab.under_construction);
}

function rptUnderConstructionHtml(tabName, mods) {
  if (!mods || !mods.length) return '';
  return `
    <div class="rpt-title rpt-uc-label">Additional ${escapeHtml(tabName)} Modules (Under Construction)</div>
    <div class="rpt-grid">${mods.map(m => `<button class="btn rpt-btn rpt-uc-btn" disabled>${escapeHtml(m)} — Under Construction</button>`).join('')}</div>
    <div class="rpt-caption">These forensic modules are planned but not yet wired to a data source in this build.</div>`;
}

// ---- Analysis sub-tab: one expander per module -----------------------------
function rptAnalysisHtml(tabName, tabIdx) {
  const mods = RPT.cfg?.modules?.[tabName] || [];
  if (!mods.length) return rptAlert('info', 'No analysis modules configured for this tab yet.');
  return mods.map((m, mi) => {
    const id = `${tabIdx}-${mi}`;
    const exts = m.extensions.map(e => '.' + e);
    const off = m.live && m.unavailable;
    const uc = "Under construction — automated analysis for this module isn't wired up yet.";
    return `
    <details class="rpt-module" data-rpt-mod="${id}" data-tab="${escapeHtml(tabName)}" data-name="${escapeHtml(m.name)}" data-live="${m.live && !off ? 1 : 0}">
      <summary>${m.icon} ${escapeHtml(m.name)}</summary>
      <div class="rpt-module-body">
        <div class="rpt-caption">Accepted file types: ${exts.join(', ')}</div>
        ${m.live ? `<div class="rpt-caption">${escapeHtml(RPT_LIVE_NOTES[m.name] || '')}</div>` : ''}
        ${off ? rptAlert('warn', `${escapeHtml(m.name)} isn't available: ${escapeHtml(m.unavailable)}`) : ''}
        <input type="file" data-rpt-upload="${id}" accept="${exts.join(',')}">
        <div data-rpt-status="${id}"></div>
        <div class="rpt-actions"${m.live ? '' : ' style="grid-template-columns:repeat(2,1fr);"'}>
          <button class="btn" data-rpt-run="${id}" disabled title="${m.live ? 'Upload a file above first.' : uc}">Run Analysis</button>
          ${m.live ? `<button class="btn" data-rpt-sample="${id}" ${off ? 'disabled' : ''} title="${escapeHtml(RPT_SAMPLE_HINTS[m.name] || '')}">Use Sample Evidence</button>` : ''}
          <button class="btn" disabled title="Under construction — AI-assisted review for this module isn't wired up yet.">Connect to AI</button>
        </div>
        <div data-rpt-result="${id}"></div>
        <div data-rpt-runs="${id}"></div>
      </div>
    </details>`;
  }).join('');
}

function rptModCtx(id) {
  const el = document.querySelector(`[data-rpt-mod="${id}"]`);
  if (!el) return null;
  return { el, tab: el.dataset.tab, name: el.dataset.name, live: el.dataset.live === '1',
           key: `${RPT.caseId}||${el.dataset.tab}||${el.dataset.name}` };
}

function rptAttachFile(id, input) {
  const ctx = rptModCtx(id);
  if (!ctx) return;
  const status = ctx.el.querySelector(`[data-rpt-status="${id}"]`);
  const runBtn = ctx.el.querySelector(`[data-rpt-run="${id}"]`);
  const f = input.files[0];
  if (!f) {
    delete RPT.files[ctx.key];
    status.innerHTML = '';
    runBtn.disabled = true;
    return;
  }
  RPT.files[ctx.key] = f;
  const list = (RPT.uploads[ctx.key] = RPT.uploads[ctx.key] || []);
  if (!list.some(x => x.name === f.name && x.size === f.size)) {
    list.push({ name: f.name, size: f.size, uploaded_at: rptNow() });
  }
  status.innerHTML = rptAlert('ok', `'${escapeHtml(f.name)}' attached to this case. It now appears under this tab's Reports sub-tab and in the evidence list below.`);
  runBtn.disabled = !ctx.live;
  rptRefreshUploads();
}

// after the case body is rebuilt the <input>s are empty, but the File objects
// are still in RPT.files -- so re-enable Run for anything already attached
function rptRestoreAttachments() {
  document.querySelectorAll('[data-rpt-mod]').forEach(el => {
    const ctx = rptModCtx(el.dataset.rptMod);
    const f = RPT.files[ctx.key];
    if (!f) return;
    el.querySelector(`[data-rpt-status="${el.dataset.rptMod}"]`).innerHTML =
      rptAlert('ok', `'${escapeHtml(f.name)}' is attached (re-select it if you want to change it).`);
    el.querySelector(`[data-rpt-run="${el.dataset.rptMod}"]`).disabled = !ctx.live;
  });
}

function rptRefreshUploads() {
  const fileLine = f => `<li><code>${escapeHtml(f.name)}</code> — ${(f.size / 1024).toFixed(1)} KB — uploaded ${escapeHtml(f.uploaded_at)}</li>`;
  const mine = Object.entries(RPT.uploads).filter(([k, files]) => k.startsWith(`${RPT.caseId}||`) && files.length);

  document.querySelectorAll('[data-rpt-uploaded]').forEach(el => {
    const tab = el.dataset.rptUploaded;
    const rows = mine.filter(([k]) => k.split('||')[1] === tab);
    el.innerHTML = rows.length
      ? `<div class="rpt-title">Uploaded Evidence Files (this session)</div>` +
        rows.map(([k, files]) => `<div class="rpt-caption"><b>${escapeHtml(k.split('||')[2])}</b></div><ul style="margin:0 0 8px 18px;font-size:12.5px;">${files.map(fileLine).join('')}</ul>`).join('')
      : '';
  });

  const all = rptById('rptAllUploads');
  if (all) {
    all.innerHTML = mine.length
      ? `<details class="rpt-module" style="margin-top:12px;"><summary>Evidence files uploaded this session (all tabs)</summary><div class="rpt-module-body"><ul style="margin:0 0 0 18px;font-size:12.5px;">` +
        mine.map(([k, files]) => files.map(f =>
          `<li><b>${escapeHtml(k.split('||')[1])} — ${escapeHtml(k.split('||')[2])}</b> — <code>${escapeHtml(f.name)}</code> (${(f.size / 1024).toFixed(1)} KB, ${escapeHtml(f.uploaded_at)})</li>`).join('')).join('') +
        `</ul></div></details>`
      : '';
  }
}

// ---- click handling ---------------------------------------------------------
function rptOnClick(e) {
  const rep = e.target.closest('[data-rpt-file]');
  if (rep && !rep.disabled) { rptOpenReport(rep.dataset.rptName, rep.dataset.rptFile); return; }
  const run = e.target.closest('[data-rpt-run]');
  if (run && !run.disabled) { rptRunModule(run.dataset.rptRun, false); return; }
  const sample = e.target.closest('[data-rpt-sample]');
  if (sample && !sample.disabled) { rptRunModule(sample.dataset.rptSample, true); }
}

// ---- report viewer modal (replaces Streamlit's st.dialog) -------------------
function rptCloseModal() { rptById('rptModalBack')?.classList.remove('show'); }

function rptToCsv(columns, rows) {
  const q = v => {
    if (v === null || v === undefined) return '';
    const s = typeof v === 'object' ? JSON.stringify(v) : String(v);
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  };
  return [columns.map(q).join(','), ...rows.map(r => columns.map(c => q(r[c])).join(','))].join('\r\n');
}

async function rptOpenReport(name, file) {
  const caseId = RPT.caseId;
  rptById('rptModalTitle').textContent = name;
  const body = rptById('rptModalBody');
  body.innerHTML = '<p class="rpt-caption">Loading…</p>';
  rptById('rptModalBack').classList.add('show');

  const d = await apiCall(`/reports/table?case_id=${rptEnc(caseId)}&file=${rptEnc(file)}`);
  if (!d) { body.innerHTML = rptAlert('err', 'Could not load this report.'); return; }
  if (!d.exists) {
    body.innerHTML = rptAlert('warn', `<code>${escapeHtml(file)}</code> hasn't been generated yet in the server's working directory.`);
    return;
  }
  const head = `<div class="rpt-caption">Source file: <code>${escapeHtml(file)}</code> • ${d.count} record(s) matched for <b>${escapeHtml(caseId)}</b></div>`;
  if (!d.count) { body.innerHTML = head + rptAlert('info', `No ${escapeHtml(name)} records exist for case ${escapeHtml(caseId)}.`); return; }

  body.innerHTML = head + `<div class="rpt-scroll">${rptTableInner(d.rows, 1000, d.columns)}</div>
    <button class="btn solid" id="rptCsvBtn" style="margin-top:10px;width:100%;">Download this table (CSV)</button>`;
  rptById('rptCsvBtn').addEventListener('click', () => {
    const blob = new Blob(['\ufeff' + rptToCsv(d.columns, d.rows)], { type: 'text/csv;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${caseId.replace(/\//g, '_')}__${file}`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
}

// ---- generic table / value renderers (used by modal + analysis results) -----
function rptColumns(rows) {
  const cols = [];
  rows.slice(0, 50).forEach(r => Object.keys(r).forEach(k => { if (!cols.includes(k)) cols.push(k); }));
  return cols;
}

function rptCell(v) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'string' && v.startsWith('data:image')) return `<img class="rpt-img" style="max-height:60px;" src="${v}" alt="">`;
  return escapeHtml(typeof v === 'object' ? JSON.stringify(v) : v);
}

function rptTableInner(rows, limit = 300, columns = null) {
  const cols = columns || rptColumns(rows);
  const shown = rows.slice(0, limit);
  return `<table><thead><tr>${cols.map(c => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead><tbody>` +
    shown.map(r => `<tr>${cols.map(c => `<td>${rptCell(r[c])}</td>`).join('')}</tr>`).join('') +
    `</tbody></table>` +
    (rows.length > limit ? `<div class="rpt-caption" style="padding:6px 8px;">Showing the first ${limit} of ${rows.length} rows${columns ? ' — the CSV download has all of them' : ''}.</div>` : '');
}

function rptTableHtml(rows) {
  const id = 't' + (++RPT.tableSeq);
  RPT.tables[id] = rows;
  return `<div class="rpt-scroll" data-rpt-table="${id}">${rptTableInner(rows)}</div>`;
}

function rptValueHtml(v) {
  if (v === null || v === undefined || v === '') return '<span style="color:var(--muted);">—</span>';
  if (typeof v === 'string') return v.startsWith('data:image') ? `<img class="rpt-img" src="${v}" alt="">` : escapeHtml(v);
  if (typeof v !== 'object') return escapeHtml(String(v));
  if (Array.isArray(v)) {
    if (!v.length) return '<span style="color:var(--muted);">(none)</span>';
    if (v.every(x => x && typeof x === 'object' && !Array.isArray(x))) return rptTableHtml(v);
    if (v.every(x => x === null || typeof x !== 'object')) {
      if (v.some(x => typeof x === 'string' && x.startsWith('data:image'))) return v.map(rptValueHtml).join('');
      return escapeHtml(v.slice(0, 200).join(', ')) + (v.length > 200 ? ` … (+${v.length - 200} more)` : '');
    }
    return v.map(x => `<div class="rpt-nest">${rptValueHtml(x)}</div>`).join('');
  }
  return `<div class="rpt-kv">${Object.entries(v).map(([k, x]) =>
    `<div class="k">${escapeHtml(k)}</div><div>${rptValueHtml(x)}</div>`).join('')}</div>`;
}

function rptResultHtml(result) {
  if (!result || typeof result !== 'object') return rptAlert('warn', 'The analyzer returned nothing.');
  const { status, ...rest } = result;
  if (status && status !== 'ok') {
    const msg = result.message || result.parse_error || result.error || result.reason || '';
    return rptAlert('warn', `Analysis status: <b>${escapeHtml(status)}</b>${msg ? ' — ' + escapeHtml(msg) : ''}`);
  }
  return rptAlert('ok', 'Analysis complete') + rptValueHtml(rest);
}

// keyword search + date-range filter over the biggest table in a chat result
// (stands in for sihchatsanalysis.render_message_filter, which is Streamlit-only)
function rptAttachMessageFilter(container) {
  const holders = [...container.querySelectorAll('[data-rpt-table]')];
  if (!holders.length) return;
  const size = h => RPT.tables[h.dataset.rptTable].length;
  const holder = holders.reduce((a, b) => (size(b) > size(a) ? b : a));
  const rows = RPT.tables[holder.dataset.rptTable];
  const cols = rptColumns(rows);
  const dateCol = cols.find(c => /date|time/i.test(c));

  const bar = document.createElement('div');
  bar.className = 'rpt-filter';
  bar.innerHTML = `<input type="search" data-f="q" placeholder="Keyword search…" style="min-width:220px;">` +
    (dateCol ? `<label class="rpt-caption" style="margin:0;">From <input type="date" data-f="from"></label>
                <label class="rpt-caption" style="margin:0;">To <input type="date" data-f="to"></label>` : '');
  holder.before(bar);

  const day = x => {                      // "2026-01-05 10:22" / ISO -> "2026-01-05"
    const s = String(x ?? '');
    if (/^\d{4}-\d{2}-\d{2}/.test(s)) return s.slice(0, 10);
    const t = new Date(s);
    return isNaN(t) ? '' : `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`;
  };
  const apply = () => {
    const q = bar.querySelector('[data-f="q"]').value.trim().toLowerCase();
    const from = bar.querySelector('[data-f="from"]')?.value;
    const to = bar.querySelector('[data-f="to"]')?.value;
    const out = rows.filter(r => {
      if (q && !cols.some(c => String(r[c] ?? '').toLowerCase().includes(q))) return false;
      if (dateCol && (from || to)) {
        const d = day(r[dateCol]);
        if (!d || (from && d < from) || (to && d > to)) return false;
      }
      return true;
    });
    holder.innerHTML = rptTableInner(out, 300, cols) + `<div class="rpt-caption" style="padding:6px 8px;">${out.length} of ${rows.length} row(s) match.</div>`;
  };
  let _t; bar.addEventListener('input', () => { clearTimeout(_t); _t = setTimeout(apply, 150); });
}

// ---- run an analyzer --------------------------------------------------------
async function rptRunModule(id, sample) {
  const ctx = rptModCtx(id);
  if (!ctx) return;
  const file = RPT.files[ctx.key];
  if (!sample && !file) return;

  const out = ctx.el.querySelector(`[data-rpt-result="${id}"]`);
  const btns = ctx.el.querySelectorAll('.rpt-actions button');
  const wasDisabled = [...btns].map(b => b.disabled);
  btns.forEach(b => { b.disabled = true; });
  out.innerHTML = rptAlert('info', sample ? `Analyzing synthetic sample for ${escapeHtml(ctx.name)}…` : `Analyzing <code>${escapeHtml(file.name)}</code>…`);

  try {
    const qs = new URLSearchParams({ case_id: RPT.caseId, module: ctx.name, sample: sample ? 'true' : 'false', filename: sample ? '' : file.name });
    const res = await fetch(`${API_BASE}/reports/analyze?${qs}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/octet-stream' },
      body: sample ? undefined : file,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      out.innerHTML = rptAlert(res.status === 404 ? 'warn' : 'err', escapeHtml(data.message || `Server error (HTTP ${res.status})`));
      return;
    }
    out.innerHTML = `<div class="rpt-caption">Run finished ${escapeHtml(data.uploaded_at)} — <code>${escapeHtml(data.filename)}</code></div>` + rptResultHtml(data.result);
    if (ctx.name === 'Chats Analysis' && data.result?.status === 'ok') rptAttachMessageFilter(out);
    rptLoadRuns(id);
  } catch (err) {
    console.error('analysis failed', err);
    out.innerHTML = rptAlert('err', 'Could not reach the server for this analysis.');
  } finally {
    btns.forEach((b, i) => { b.disabled = wasDisabled[i]; });
  }
}

async function rptLoadRuns(id) {
  const ctx = rptModCtx(id);
  if (!ctx) return;
  const holder = ctx.el.querySelector(`[data-rpt-runs="${id}"]`);
  const data = await apiCall(`/reports/runs?case_id=${rptEnc(RPT.caseId)}&module=${rptEnc(ctx.name)}`);
  const runs = data?.runs || [];
  if (!runs.length) { holder.innerHTML = ''; return; }
  holder.innerHTML = `<details class="rpt-module" style="margin-top:10px;"><summary>Previous ${escapeHtml(ctx.name)} runs for this case (${runs.length})</summary>
    <div class="rpt-module-body">` +
    runs.slice().reverse().map((r, i) =>
      `<div class="rpt-caption"><b>Run ${runs.length - i} — ${escapeHtml(r.uploaded_at || 'n/a')}</b>${r.filename ? ' · ' + escapeHtml(r.filename) : ''}${r.sample ? ' · sample' : ''}</div>` + rptResultHtml(r.result)
    ).join('<hr class="rpt-hr">') + `</div></details>`;
}

// ---- Full Unified Investigation Report ---------------------------------------
async function rptLoadUnified(caseId) {
  const el = rptById('rptUnified');
  const d = await apiCall(`/reports/unified?case_id=${rptEnc(caseId)}`);
  if (!el || caseId !== RPT.caseId) return;          // user switched cases meanwhile
  if (!d?.exists) { el.innerHTML = rptAlert('info', "The unified report hasn't been generated yet."); return; }
  el.innerHTML = `
    <details class="rpt-module"><summary>${escapeHtml(d.label)}</summary>
      <div class="rpt-module-body"><pre class="rpt-pre">${escapeHtml(d.preview)}</pre></div></details>
    <a class="btn solid" href="${API_BASE}/reports/unified/download" download style="display:inline-block;text-decoration:none;margin:10px 0;">Download full unified report (.txt)</a>
    <details class="rpt-module"><summary class="rpt-uc-label">Modules marked Under Construction in this report</summary>
      <div class="rpt-module-body">
        <div class="rpt-caption">The Full Unified Investigation Report includes a section for these modules, labeled UNDER CONSTRUCTION, since they are not yet wired to a real data source:</div>
        <ul class="rpt-uc-label" style="margin:0 0 0 18px;font-size:12.5px;">${(d.under_construction || []).map(m => `<li>${escapeHtml(m)}</li>`).join('')}</ul>
      </div></details>`;
}

// ============================================================================
// FIR REGISTRATION -> "Upload FIR (PDF)" sub-tab
// ----------------------------------------------------------------------------
// PDF -> POST /api/fir/extract (regex + OCR + Groq, same pipeline as
// sihdashboard.py) -> editable review form -> POST /api/fir/register.
// ============================================================================
const FIRPDF = { status: null };

function setupFirTabs() {
  const bar = rptById('firTabs');
  if (!bar || bar.dataset.wired) return;
  bar.dataset.wired = '1';

  bar.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
    bar.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t === tab));
    const which = tab.dataset.firTab;
    rptById('firTabManual').style.display = which === 'manual' ? '' : 'none';
    rptById('firTabUpload').style.display = which === 'upload' ? '' : 'none';
    if (which === 'upload') firPdfInit();
  }));

  rptById('firPdfInput').addEventListener('change', e => {
    rptById('firPdfExtractBtn').disabled = !e.target.files[0] || !!FIRPDF.status?.pdf_error;
  });
  rptById('firPdfExtractBtn').addEventListener('click', firPdfExtract);
  rptById('firPdfSubmit').addEventListener('click', firPdfSubmit);

  // little "auto default" behaviour, same as the Streamlit form: the police
  // station / acts fields follow district / case type until the officer edits them
  rptById('fp-ps').addEventListener('input', e => { e.target.dataset.auto = '0'; });
  rptById('fp-acts').addEventListener('input', e => { e.target.dataset.auto = '0'; });
  rptById('fp-district').addEventListener('change', e => {
    const ps = rptById('fp-ps');
    if (ps.dataset.auto === '1') ps.value = `${e.target.value} PS`;
  });
  rptById('fp-case-type').addEventListener('change', e => {
    const acts = rptById('fp-acts');
    if (acts.dataset.auto === '1') acts.value = FIRPDF.status?.case_types?.[e.target.value] || '';
  });
  document.querySelectorAll('input[name="fpAccKnown"]').forEach(r => r.addEventListener('change', () => {
    const name = rptById('fp-acc-name');
    if (r.checked && r.value === 'unknown') name.value = 'Unknown Accused';
    else if (r.checked && name.value === 'Unknown Accused') name.value = '';
  }));
}

async function firPdfInit() {
  if (FIRPDF.status) return;
  const box = rptById('firPdfStatus');
  const st = await apiCall('/fir/extract/status');
  if (!st) { box.textContent = 'Could not check PDF extraction support on the server.'; return; }
  FIRPDF.status = st;

  rptById('fp-district').innerHTML = st.districts.map(d => `<option>${escapeHtml(d)}</option>`).join('');
  rptById('fp-case-type').innerHTML = Object.keys(st.case_types).map(c => `<option>${escapeHtml(c)}</option>`).join('');

  if (st.pdf_error) {
    box.innerHTML = `PDF reading isn't available: ${escapeHtml(st.pdf_error)}`;
    rptById('firPdfInput').disabled = true;
  } else if (st.groq_error) {
    box.innerHTML = `Groq translation/classification is off (${escapeHtml(st.groq_error)}). Regex-extracted fields (name, phone, address, narrative) will still work — set the GROQ_API_KEY environment variable to also get auto-translation and Case_Type classification.`;
  } else {
    box.innerHTML = `Translation/classification runs on the free Groq API (<code>${escapeHtml(st.groq_model)}</code>). Name/phone/address/narrative are read locally by regex — only short field snippets and the narrative text are sent to Groq.`;
  }
}

function firNowStr() {
  const d = new Date(), p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}

function firPdfFillForm(f) {
  const set = (id, v) => { rptById(id).value = v ?? ''; };
  const st = FIRPDF.status;

  const district = st.districts.includes(f.District) ? f.District : st.districts[0];
  set('fp-district', district);
  set('fp-ps', f.Police_Station || `${district} PS`);
  rptById('fp-ps').dataset.auto = f.Police_Station ? '0' : '1';
  set('fp-state', f.State_UT || 'Maharashtra');
  set('fp-fir-no', '');
  set('fp-dt', firNowStr());

  const caseType = f.Case_Type in st.case_types ? f.Case_Type : Object.keys(st.case_types)[0];
  set('fp-case-type', caseType);
  set('fp-acts', f.Acts_Sections || st.case_types[caseType] || '');
  rptById('fp-acts').dataset.auto = f.Acts_Sections ? '0' : '1';
  set('fp-place', f.Place_of_Occurrence);

  set('fp-inf-name', f.Informant_Name);
  set('fp-inf-contact', f.Informant_Contact);
  set('fp-inf-addr', f.Informant_Address);

  set('fp-vic-name', f.Victim_Name);
  set('fp-vic-age', 25);
  set('fp-vic-gender', 'Male');
  set('fp-vic-contact', f.Victim_Contact);

  const acc = f.Accused_Name_Alias || '';
  const known = !!acc && !/unknown/i.test(acc);
  document.querySelector(`input[name="fpAccKnown"][value="${known ? 'known' : 'unknown'}"]`).checked = true;
  set('fp-acc-name', known ? acc : 'Unknown Accused');
  set('fp-acc-contact', f.Accused_Contact);
  set('fp-acc-addr', f.Accused_Address);

  set('fp-io', 'Inspector (Unassigned)');
  set('fp-narrative', f.FIR_Narrative_Statement);
}

async function firPdfExtract() {
  const file = rptById('firPdfInput').files[0];
  if (!file) return;
  const btn = rptById('firPdfExtractBtn'), msg = rptById('firPdfMsg');
  const model = FIRPDF.status && !FIRPDF.status.groq_error ? ` with ${FIRPDF.status.groq_model}` : '';
  btn.disabled = true;
  msg.style.color = '';
  msg.textContent = `Reading PDF and extracting fields${model}…`;

  try {
    const res = await fetch(`${API_BASE}/fir/extract`, {
      method: 'POST', headers: { 'Content-Type': 'application/pdf' }, body: file,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.status !== 'success') {
      msg.style.color = '#9c2434';
      msg.textContent = data.message || `Extraction failed (HTTP ${res.status}).`;
      return;
    }
    firPdfFillForm(data.fields || {});
    rptById('firPdfReview').style.display = '';
    msg.textContent = Object.keys(data.fields || {}).length
      ? 'Fields extracted — review and correct them below before registering.'
      : "Nothing could be matched in this PDF's layout — fill the form in by hand below.";
    rptById('firPdfReview').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (err) {
    console.error('FIR extract failed', err);
    msg.style.color = '#9c2434';
    msg.textContent = 'Could not reach the server.';
  } finally {
    btn.disabled = false;
  }
}

async function firPdfSubmit() {
  const v = id => (rptById(id)?.value || '').trim();
  if (!v('fp-inf-name')) { showToast('Please enter the Informant Name.', 'error'); return; }
  if (!v('fp-vic-name')) { showToast('Please enter the Victim Name.', 'error'); return; }

  const age = parseInt(v('fp-vic-age'), 10);
  // keys line up with FIR_FORM_FIELD_MAP in sihfrontendtest.py
  const payload = {
    district: v('fp-district'), police_station: v('fp-ps'), state: v('fp-state'),
    fir_number: v('fp-fir-no'), reporting_datetime: v('fp-dt'),
    case_type: v('fp-case-type'), acts_sections: v('fp-acts'), place_of_occurrence: v('fp-place'),
    complainant_name: v('fp-inf-name'), complainant_mobile: v('fp-inf-contact'), complainant_address: v('fp-inf-addr'),
    victim_name: v('fp-vic-name'), victim_age: Number.isNaN(age) ? null : age,
    victim_gender: v('fp-vic-gender'), victim_contact: v('fp-vic-contact'),
    accused_known: document.querySelector('input[name="fpAccKnown"]:checked')?.value === 'known',
    accused_name: v('fp-acc-name'), accused_mobile: v('fp-acc-contact'), accused_address: v('fp-acc-addr'),
    investigating_officer: v('fp-io'), narrative: rptById('fp-narrative').value.trim(),
  };

  const btn = rptById('firPdfSubmit');
  btn.disabled = true;
  const origLabel = btn.textContent;
  btn.textContent = 'Registering…';
  try {
    const res = await fetch(`${API_BASE}/fir/register`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.status === 'success') {
      clearApiCache();          // new case -> overview / reports / persons must refetch
      lastOverviewSig = null;
      RPT.sig = null;
      showToast(`FIR registered: ${data.fir_number}`, 'success');
      rptById('firPdfReview').style.display = 'none';
      rptById('firPdfInput').value = '';
      rptById('firPdfExtractBtn').disabled = true;
      rptById('firPdfMsg').textContent = '';
    } else {
      showToast(data.message || 'Failed to register FIR', 'error');
    }
  } catch (err) {
    console.error('FIR register failed', err);
    showToast('Error communicating with server', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = origLabel;
  }
}

async function submitFIRForm() {
  // Collect form data from all steps
  const formData = {
    fir_type: document.getElementById('fir-type')?.value || '',
    fir_filter: document.getElementById('fir-filter')?.value || '',
    police_station: document.getElementById('fir-station')?.value || '',
    linked_gd: document.getElementById('fir-linked-gd')?.value || '',

    district: document.getElementById('fir-district')?.value || '',
    state: 'Maharashtra',
    case_type: document.getElementById('fir-case-type')?.value || '',
    place_of_occurrence: document.getElementById('fir-place')?.value || '',
    incident_date: document.getElementById('fir-incident-date')?.value || '',
    incident_time: document.getElementById('fir-incident-time')?.value || '',
    beat: document.getElementById('fir-beat')?.value || '',
    location_category: document.getElementById('fir-location-category')?.value || '',

    complainant_name: document.getElementById('fir-complainant-name')?.value || '',
    complainant_mobile: document.getElementById('fir-complainant-mobile')?.value || '',
    complainant_address: document.getElementById('fir-complainant-address')?.value || '',
    complainant_address_type: document.getElementById('fir-address-type')?.value || '',

    victim_name: document.getElementById('fir-victim-name')?.value || '',
    victim_age: parseInt(document.getElementById('fir-victim-age')?.value) || null,
    victim_gender: document.getElementById('fir-victim-gender')?.value || '',
    victim_contact: document.getElementById('fir-victim-contact')?.value || '',

    accused_known: document.querySelector('input[name="accused-known"]:checked')?.value === 'yes',
    accused_name: document.getElementById('fir-accused-name')?.value || '',
    accused_alias: document.getElementById('fir-accused-alias')?.value || '',
    accused_mobile: document.getElementById('fir-accused-mobile')?.value || '',
    accused_address: document.getElementById('fir-accused-address')?.value || '',
    video_recorded: document.getElementById('fir-video-recorded')?.checked || false,
    delay_reason: document.getElementById('fir-delay-reason')?.value || '',

    zero_fir: document.getElementById('fir-zero-fir')?.checked || false,
    reregistration: document.getElementById('fir-reregistration')?.checked || false,
    cross_case_reference: document.getElementById('fir-cross-case')?.value || '',
    court_copy_required: document.getElementById('fir-court-copy')?.checked || false,
    investigating_officer: document.getElementById('fir-investigating-officer')?.value || '',
    narrative: document.getElementById('fir-narrative')?.value || '',
  };

  // Call API
  const result = await apiCall('/fir/register', 'POST', formData);

  if (result?.status === 'success') {
    showToast(`FIR registered: ${result.fir_number}`, 'success');
    // Reset form or navigate away
    document.getElementById('fir-form')?.reset();
  } else {
    showToast(result?.message || 'Failed to register FIR', 'error');
  }
}

// ============================================================================
// CASE BASKET PAGE (FIR selector + Checklist / AI Assistant / AI Insights)
// ============================================================================
//
// Layout: pick an FIR -> three sub-tabs scoped to it.
//   - Checklist   : the main feature. What's been done on the case and what's
//                   still pending (FIR, Accused, Arrest Memo/PO, Property,
//                   Case Diary, General Diary, IF-II, Section Amendment,
//                   Court e-Signature). Real case-level facts (district,
//                   case type) come from /api/reports/case; the per-item
//                   done/pending state and counts (CD count, GD count, IF-II
//                   date, etc.) are generated with a seeded pseudo-random
//                   function (_cbHash) keyed on the FIR number, so the same
//                   FIR always looks the same across visits/languages. Swap
//                   generateCaseBasketChecklistData() for a real
//                   /api/case-basket?fir_no=... endpoint once that logic
//                   exists on the backend -- the rendering below doesn't
//                   need to change, only where the numbers come from.
//   - AI Assistant: the existing SOP/legal chat UI (unchanged behaviour).
//   - AI Investigation Insights: intentionally a "coming soon" placeholder.

let caseBasketFirOptionsLoaded = false;
let caseBasketCurrentFir = null;

async function initializeCaseBasketPage() {
  await populateCaseBasketFirSelect();
  setupCaseBasketSubTabs();
  initializeChatUI();
  // Re-select whatever FIR was already chosen (e.g. returning to the page,
  // or a language switch) instead of resetting to the empty state.
  if (caseBasketCurrentFir) {
    renderCaseBasketForFir(caseBasketCurrentFir);
  }
}

async function populateCaseBasketFirSelect() {
  const sel = document.getElementById('caseBasketFirSelect');
  if (!sel || caseBasketFirOptionsLoaded) return;

  const locData = await apiCall('/case-locations');
  const cases = (locData && locData.cases) || [];
  sel.innerHTML = `<option value="">${t('cbSelectFirPlaceholder')}</option>` +
    cases.map(c => `<option value="${c.fir_no}">${c.fir_no}</option>`).join('');
  caseBasketFirOptionsLoaded = true;
}

function setupCaseBasketSubTabs() {
  const body = document.getElementById('caseBasketBody');
  if (!body || body.dataset.subtabsWired) return;
  body.dataset.subtabsWired = 'true';

  body.querySelectorAll('.submenu-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      body.querySelectorAll('.submenu-tab').forEach(b => b.classList.remove('active'));
      body.querySelectorAll('.page-tab-content').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`cb-tab-${btn.dataset.cbtab}`)?.classList.add('active');
    });
  });
}

async function onCaseBasketFirChange() {
  const sel = document.getElementById('caseBasketFirSelect');
  const firNo = sel ? sel.value : '';
  caseBasketCurrentFir = firNo || null;
  await renderCaseBasketForFir(firNo);
}

async function renderCaseBasketForFir(firNo) {
  const emptyState = document.getElementById('caseBasketEmptyState');
  const body = document.getElementById('caseBasketBody');
  const metaEl = document.getElementById('caseBasketFirMeta');

  if (!firNo) {
    if (emptyState) emptyState.style.display = '';
    if (body) body.style.display = 'none';
    if (metaEl) metaEl.textContent = '';
    return;
  }

  if (emptyState) emptyState.style.display = 'none';
  if (body) body.style.display = '';

  const caseInfo = await apiCall('/reports/case?case_id=' + encodeURIComponent(firNo));
  if (metaEl) {
    metaEl.textContent = (caseInfo && caseInfo.found)
      ? t('cbFirMetaLine').replace('{district}', caseInfo.district).replace('{type}', caseInfo.case_type)
      : '';
  }

  renderCaseBasketChecklist(firNo, caseInfo);
}

/** Small seeded hash so the same FIR always produces the same mock state. */
function _cbHash(str) {
  let h = 0;
  for (let i = 0; i < String(str).length; i++) {
    h = (h * 31 + String(str).charCodeAt(i)) >>> 0;
  }
  return h;
}

function generateCaseBasketChecklistData(firNo, caseInfo) {
  const h = _cbHash(firNo);
  const pick = (n, mod) => (h >> n) % mod;

  const accusedCount = pick(1, 5);           // 0-4
  const cdCount = pick(3, 9);                 // 0-8
  const gdCount = pick(5, 4);                 // 0-3
  const propertyCount = pick(7, 6);           // 0-5
  const propertyValue = (pick(9, 90) + 5) * 1000;
  const isPO = pick(11, 2) === 0;
  const sectionsAdded = pick(13, 3);          // 0-2
  const pendingEsign = pick(15, 4);           // 0-3

  const day = 1 + pick(17, 27);
  const month = 1 + pick(19, 12);
  const isoDate = `2026-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
  const displayDate = new Date(isoDate).toLocaleDateString(currentLang === 'hi' ? 'hi-IN' : 'en-IN', { day: 'numeric', month: 'short', year: 'numeric' });

  return {
    fir: { done: true },
    accused: { done: accusedCount > 0, count: accusedCount },
    arrest: { done: pick(21, 3) !== 0, isPO, date: displayDate },
    property: { done: propertyCount > 0, count: propertyCount, value: propertyValue.toLocaleString(currentLang === 'hi' ? 'hi-IN' : 'en-IN') },
    cd: { done: cdCount > 0, count: cdCount },
    gd: { done: gdCount > 0, count: gdCount },
    if2: { done: pick(23, 3) !== 0, date: displayDate },
    section: { done: sectionsAdded > 0, sectionsAdded },
    esign: { done: pendingEsign === 0, pending: pendingEsign },
  };
}

function _cbItem(key, titleKey, done, subText, opts) {
  opts = opts || {};
  const checkSvg = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>`;
  const dotSvg = `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="4"/></svg>`;
  const link = opts.link ? `<div class="ci-sub" style="margin-top:6px;"><a href="javascript:void(0)" onclick="${opts.link}" style="color:var(--purple-700);font-weight:600;">${t('cbViewLink')}</a></div>` : '';
  return `
    <div class="checklist-item ${done ? 'done' : ''}">
      <div class="ci-icon">${done ? checkSvg : dotSvg}</div>
      <div class="ci-body">
        <div class="ci-title">${t(titleKey)}</div>
        <div class="ci-sub">${subText}</div>
        ${link}
      </div>
      <div class="ci-status">${done ? t('cbStatusDone') : t('cbStatusPending')}</div>
    </div>`;
}

function renderCaseBasketChecklist(firNo, caseInfo) {
  const list = document.getElementById('cbChecklistList');
  if (!list) return;

  const d = generateCaseBasketChecklistData(firNo, caseInfo);
  const items = [];

  items.push(_cbItem('fir', 'cbItemFirTitle', true, t('cbFirSubDone')));

  items.push(_cbItem('accused', 'cbItemAccusedTitle', d.accused.done,
    d.accused.done ? t('cbAccusedSubDone').replace('{n}', d.accused.count) : t('cbAccusedSubPending'),
    { link: `navigateToPage('reg-fir')` }));

  const arrestAction = d.arrest.isPO ? t('cbArrestActionPO') : t('cbArrestActionMemo');
  items.push(_cbItem('arrest', 'cbItemArrestTitle', d.arrest.done,
    d.arrest.done ? t('cbArrestSubDone').replace('{action}', arrestAction).replace('{date}', d.arrest.date) : t('cbArrestSubPending')));

  items.push(_cbItem('property', 'cbItemPropertyTitle', d.property.done,
    d.property.done ? t('cbPropertySubDone').replace('{n}', d.property.count).replace('{value}', d.property.value) : t('cbPropertySubPending'),
    { link: `navigateToPage('reg-property')` }));

  items.push(_cbItem('cd', 'cbItemCdTitle', d.cd.done,
    d.cd.done ? t('cbCdSubDone').replace('{n}', d.cd.count) : t('cbCdSubPending'),
    d.cd.done ? { link: `showToast('${t('cbItemCdTitle')}: ${d.cd.count}')` } : {}));

  items.push(_cbItem('gd', 'cbItemGdTitle', d.gd.done,
    d.gd.done ? t('cbGdSubDone').replace('{n}', d.gd.count) : t('cbGdSubPending'),
    d.gd.done ? { link: `navigateToPage('gd-view')` } : {}));

  items.push(_cbItem('if2', 'cbItemIf2Title', d.if2.done,
    d.if2.done ? t('cbIf2SubDone').replace('{date}', d.if2.date) : t('cbIf2SubPending')));

  items.push(_cbItem('section', 'cbItemSectionTitle', d.section.done,
    d.section.done ? t('cbSectionSubDone').replace('{detail}', '+' + d.section.sectionsAdded) : t('cbSectionSubPending')));

  items.push(_cbItem('esign', 'cbItemEsignTitle', d.esign.done,
    d.esign.done ? t('cbEsignSubDone') : t('cbEsignSubPending').replace('{n}', d.esign.pending)));

  list.innerHTML = items.join('');

  const doneCount = [d.fir, d.accused, d.arrest, d.property, d.cd, d.gd, d.if2, d.section, d.esign].filter(x => x.done).length;
  const total = 9;
  const fill = document.getElementById('cbProgressFill');
  const label = document.getElementById('cbProgressLabel');
  if (fill) fill.style.width = Math.round((doneCount / total) * 100) + '%';
  if (label) label.textContent = `${doneCount}/${total}`;
}

// ============================================================================
// AI ASSISTANT / CHAT UI
// ============================================================================

async function initializeChatUI() {
  // Markup for #chatMessages / #chatInput now lives statically in the
  // Case Basket page's "AI Assistant" sub-tab (sihfrontendtest.py), so
  // this only needs to wire the Enter-to-send listener, once.
  const chatInput = document.getElementById('chatInput');
  if (chatInput && !chatInput.dataset.wired) {
    chatInput.dataset.wired = '1';
    chatInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') sendChatMessage();
    });
  }
}

let chatBusy = false;

async function sendChatMessage() {
  const input = document.getElementById('chatInput');
  const messagesDiv = document.getElementById('chatMessages');
  const message = input?.value?.trim();

  if (!message || chatBusy) return;
  chatBusy = true;

  // everything user- or model-supplied is escaped before it touches innerHTML
  const safe = txt => escapeHtml(txt).replace(/\n/g, '<br>');
  const add = html => messagesDiv.insertAdjacentHTML('beforeend', html);
  const bubble = (inner, mine) => mine
    ? `<div style="text-align:right;margin-left:40px;"><div style="background:var(--purple-700);color:#fff;padding:8px 12px;border-radius:8px;display:inline-block;text-align:left;">${inner}</div></div>`
    : `<div style="text-align:left;margin-right:40px;"><div style="background:var(--bg);color:var(--ink);padding:8px 12px;border-radius:8px;border:1px solid var(--line);">${inner}</div></div>`;

  add(bubble(safe(message), true));
  input.value = '';
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  add(`<div id="chatPending" style="text-align:left;margin-right:40px;color:var(--muted);font-size:12px;">Thinking…</div>`);
  messagesDiv.scrollTop = messagesDiv.scrollHeight;

  let response;
  try {
    response = await apiCall('/assistant/ask', 'POST', { query: message });
  } finally {
    document.getElementById('chatPending')?.remove();
    chatBusy = false;
  }

  if (response?.answer) {
    let inner = safe(response.answer);
    if (response.sources && response.sources.length > 0) {
      inner += `<div style="font-size:11px;color:var(--muted);margin-top:8px;padding-top:8px;border-top:1px solid var(--line);">
        <strong>Sources:</strong><br>
        ${response.sources.map(s => escapeHtml(s.page ? `${s.title} (${s.page})` : s.title)).join('<br>')}
      </div>`;
    }
    add(bubble(inner, false));
  } else if (response?.error === 'service_unavailable') {
    add(bubble(`<span style="color:var(--muted);">${safe(response.message || 'Assistant is currently unavailable.')}</span>`, false));
  } else {
    add(bubble('<span style="color:var(--muted);">Error: Unable to process your request.</span>', false));
  }

  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// ============================================================================
// PAGE NAVIGATION INITIALIZATION
// ============================================================================

// NOTE: Click-wiring for [data-page], [data-toggle], and .submenu a used to
// live here too (duplicating the inline <script> in sihfrontendtest.py's
// HTML_TEMPLATE, which defines showPage() and attaches the same listeners).
// Two listeners on the same element meant every click ran
// classList.toggle('open') TWICE, so the class flipped and flipped right
// back -- the Registration and General Diary submenus looked stuck/broken.
// showPage() in the inline script is now the single owner of navigation and
// calls loadPageData() itself after switching pages, so this file only
// needs to run the initial load.

// ============================================================================
// INITIALIZATION ON PAGE LOAD
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  // Load initial dashboard data
  loadPageData('dashboard');
});