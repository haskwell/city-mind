/* ═══════════════════════════════════════════════════
   CityMind — Frontend Logic
   ═══════════════════════════════════════════════════ */

// ── App State ──────────────────────────────────────
const state = {
  grid:       null,   // { size, cells[] }
  roads:      null,   // { edges[], path1, path2, ... }
  ambulance:  null,   // { placements[], ... }
};

// ── Canvas config ──────────────────────────────────
const CELL  = 62;
const PAD   = 3;

const COLORS = {
  EMPTY:            '#0d1117',
  RESIDENTIAL:      '#166534',
  HOSPITAL:         '#7f1d1d',
  PRIMARY_HOSPITAL: '#450a0a',
  SCHOOL:           '#1e3a5f',
  INDUSTRIAL:       '#431407',
  POWER_PLANT:      '#3b0764',
  AMBULANCE_DEPOT:  '#083344',
};

const FILL_COLORS = {
  EMPTY:            '#111827',
  RESIDENTIAL:      '#22c55e',
  HOSPITAL:         '#ef4444',
  PRIMARY_HOSPITAL: '#991b1b',
  SCHOOL:           '#3b82f6',
  INDUSTRIAL:       '#f97316',
  POWER_PLANT:      '#a855f7',
  AMBULANCE_DEPOT:  '#06b6d4',
};

const LABELS = {
  RESIDENTIAL: 'R', HOSPITAL: 'H', PRIMARY_HOSPITAL: 'H',
  SCHOOL: 'S', INDUSTRIAL: 'I', POWER_PLANT: 'P', AMBULANCE_DEPOT: 'A',
};

// ── Helpers ────────────────────────────────────────
function $(id) { return document.getElementById(id); }

function setDot(id, state) {
  const el = $(id);
  el.className = 'dot dot-' + state;
}

function setStatus(dotId, textId, dotState, text) {
  setDot(dotId, dotState);
  $(textId).textContent = text;
}

function setGlobal(dotState, text) {
  const dot = $('global_dot');
  dot.className = 'status-dot ' + (dotState === 'idle' ? '' : dotState);
  $('global_status_text').textContent = text;
}

function cellCentre(row, col) {
  const x = col * CELL + (col + 1) * PAD + CELL / 2;
  const y = row * CELL + (row + 1) * PAD + CELL / 2;
  return [x, y];
}

// ── Total / capacity update ────────────────────────
function updateTotal() {
  const size = parseInt($('grid_size').value) || 5;
  const capacity = size * size;
  const types = ['RESIDENTIAL','HOSPITAL','SCHOOL','INDUSTRIAL','POWER_PLANT','AMBULANCE_DEPOT'];
  let total = 0;
  for (const t of types) {
    total += parseInt($('count_' + t).value) || 0;
  }
  const pct = Math.min(total / capacity, 1) * 100;
  const over = total > capacity;

  $('total_text').textContent = `${total} / ${capacity}`;
  const fill = $('capacity_fill');
  fill.style.width = pct + '%';
  fill.classList.toggle('over', over);

  const btn = $('btn_csp');
  btn.disabled = over;
}

function adjustValue(id, delta, min, max) {
  const el = $(id);
  const val = Math.min(max, Math.max(min, (parseInt(el.value) || 0) + delta));
  el.value = val;
  updateTotal();
}

function adjustCount(type, delta) {
  adjustValue('count_' + type, delta, 0, 200);
}

// ── Canvas Render ──────────────────────────────────
function getCanvas() { return $('city_canvas'); }

function renderAll() {
  const canvas = getCanvas();
  if (!state.grid) { canvas.style.display = 'none'; return; }

  const { size } = state.grid;
  const canvasSize = size * CELL + (size + 1) * PAD;
  canvas.width  = canvasSize;
  canvas.height = canvasSize;
  canvas.style.display = 'block';
  $('canvas_placeholder').classList.add('hidden');

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvasSize, canvasSize);

  // Background
  ctx.fillStyle = '#080b12';
  ctx.fillRect(0, 0, canvasSize, canvasSize);

  drawGrid(ctx, size);
  if (state.roads)     drawRoads(ctx);
  if (state.ambulance) drawAmbulances(ctx);
  if (state.roads)     redrawLabels(ctx, size);
  if (!state.roads)    drawLabels(ctx, size);
}

function drawGrid(ctx, size) {
  for (const cell of state.grid.cells) {
    const { row, col, type } = cell;
    const x1 = col * CELL + (col + 1) * PAD;
    const y1 = row * CELL + (row + 1) * PAD;

    // Shadow/glow for non-empty
    if (type !== 'EMPTY') {
      ctx.shadowColor = FILL_COLORS[type] || '#fff';
      ctx.shadowBlur  = 6;
    }

    ctx.fillStyle = FILL_COLORS[type] || '#1a1f2e';
    roundRect(ctx, x1, y1, CELL, CELL, 6);
    ctx.fill();

    ctx.shadowBlur = 0;

    // Subtle inner border
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    roundRect(ctx, x1 + 0.5, y1 + 0.5, CELL - 1, CELL - 1, 6);
    ctx.stroke();
  }
}

function drawLabels(ctx, size) {
  for (const cell of state.grid.cells) {
    const label = LABELS[cell.type];
    if (!label) continue;
    const [cx, cy] = cellCentre(cell.row, cell.col);
    ctx.font = `bold ${Math.round(CELL * 0.32)}px 'Space Mono', monospace`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = 'rgba(255,255,255,0.9)';
    ctx.shadowColor = 'rgba(0,0,0,0.6)';
    ctx.shadowBlur  = 4;
    ctx.fillText(label, cx, cy);
    ctx.shadowBlur = 0;
  }
}

function redrawLabels(ctx, size) {
  drawLabels(ctx, size);
}

function drawRoads(ctx) {
  const { edges, path1, path2 } = state.roads;

  // Build sets for quick lookup
  const path1Set = new Set();
  const path2Set = new Set();
  if (path1) for (let i = 0; i < path1.length - 1; i++) path1Set.add(edgeKey(path1[i], path1[i+1]));
  if (path2) for (let i = 0; i < path2.length - 1; i++) path2Set.add(edgeKey(path2[i], path2[i+1]));

  // Normal roads first
  for (const e of edges) {
    const key = edgeKey(e.u, e.v);
    if (path1Set.has(key) || path2Set.has(key)) continue;

    const [ux, uy] = cellCentre(e.u[0], e.u[1]);
    const [vx, vy] = cellCentre(e.v[0], e.v[1]);

    ctx.strokeStyle = e.blocked ? '#ef4444' : 'rgba(200,210,230,0.5)';
    ctx.lineWidth = 2;
    ctx.setLineDash([]);
    ctx.shadowBlur = 0;

    ctx.beginPath();
    ctx.moveTo(ux, uy);
    ctx.lineTo(vx, vy);
    ctx.stroke();
  }

  // Path 2 (backup – dashed teal)
  if (path2) {
    ctx.strokeStyle = '#14b8a6';
    ctx.lineWidth   = 3;
    ctx.setLineDash([6, 4]);
    ctx.shadowColor = '#14b8a6';
    ctx.shadowBlur  = 8;
    for (let i = 0; i < path2.length - 1; i++) {
      const [ux, uy] = cellCentre(path2[i][0], path2[i][1]);
      const [vx, vy] = cellCentre(path2[i+1][0], path2[i+1][1]);
      ctx.beginPath();
      ctx.moveTo(ux, uy);
      ctx.lineTo(vx, vy);
      ctx.stroke();
    }
    ctx.setLineDash([]);
    ctx.shadowBlur = 0;
  }

  // Path 1 (primary – amber)
  if (path1) {
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth   = 4;
    ctx.shadowColor = '#f59e0b';
    ctx.shadowBlur  = 10;
    for (let i = 0; i < path1.length - 1; i++) {
      const [ux, uy] = cellCentre(path1[i][0], path1[i][1]);
      const [vx, vy] = cellCentre(path1[i+1][0], path1[i+1][1]);
      ctx.beginPath();
      ctx.moveTo(ux, uy);
      ctx.lineTo(vx, vy);
      ctx.stroke();
    }
    ctx.shadowBlur = 0;
  }
}

function drawAmbulances(ctx) {
  const r = Math.round(CELL * 0.2);
  for (const [row, col] of state.ambulance.placements) {
    const [cx, cy] = cellCentre(row, col);

    // Glow ring
    ctx.strokeStyle = '#ff4081';
    ctx.lineWidth   = 2;
    ctx.shadowColor = '#ff4081';
    ctx.shadowBlur  = 16;
    ctx.beginPath();
    ctx.arc(cx, cy, r + 3, 0, Math.PI * 2);
    ctx.stroke();

    // Filled circle
    ctx.fillStyle   = '#ff4081';
    ctx.shadowColor = '#ff4081';
    ctx.shadowBlur  = 12;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur  = 0;

    // Emoji
    ctx.font         = `${Math.round(r * 1.1)}px serif`;
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText('🚑', cx, cy);
  }
}

// ── Utilities ──────────────────────────────────────
function edgeKey(a, b) {
  const [ar, ac] = a, [br, bc] = b;
  if (ar < br || (ar === br && ac < bc)) return `${ar},${ac}-${br},${bc}`;
  return `${br},${bc}-${ar},${ac}`;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y,     x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x,     y + h, r);
  ctx.arcTo(x,     y + h, x,     y,     r);
  ctx.arcTo(x,     y,     x + w, y,     r);
  ctx.closePath();
}

// ── API Calls ──────────────────────────────────────
async function runCSP() {
  const types = ['RESIDENTIAL','HOSPITAL','SCHOOL','INDUSTRIAL','POWER_PLANT','AMBULANCE_DEPOT'];
  const counts = {};
  for (const t of types) counts[t] = parseInt($('count_' + t).value) || 0;

  setGlobal('running', 'Running CSP…');
  setStatus('dot_c1', 'text_c1', 'running', 'Solving…');
  $('btn_csp').disabled = true;
  $('btn_roads').disabled = true;
  $('btn_ambulance').disabled = true;
  $('btn_save').disabled = true;

  try {
    const res = await fetch('/api/run_csp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grid_size: parseInt($('grid_size').value), counts }),
    });
    const data = await res.json();

    if (data.success) {
      state.grid      = data.grid;
      state.roads     = null;
      state.ambulance = null;

      renderAll();
      resetRoadsUI();
      resetAmbulanceUI();

      const v = data.violations;
      if (v > 0) {
        setStatus('dot_c1', 'text_c1', 'warn', `Done — ${v} violation(s)`);
        setGlobal('ok', 'Layout complete');
      } else {
        setStatus('dot_c1', 'text_c1', 'ok', `Solved ✓  (${data.steps} steps)`);
        setGlobal('ok', 'Layout solved');
      }
      $('csp_steps').textContent = data.steps;
      $('btn_roads').disabled = false;
      $('btn_save').disabled  = false;
    } else {
      setStatus('dot_c1', 'text_c1', 'err', 'Error: ' + data.error);
      setGlobal('err', 'CSP failed');
    }
  } catch (e) {
    setStatus('dot_c1', 'text_c1', 'err', 'Network error');
    setGlobal('err', 'Request failed');
  }

  $('btn_csp').disabled = false;
}

async function saveGrid() {
  try {
    const res = await fetch('/api/save_grid', { method: 'POST' });
    const data = await res.json();
    if (data.success) setStatus('dot_c1', 'text_c1', 'ok', 'Grid saved ✓');
    else              setStatus('dot_c1', 'text_c1', 'err', data.error);
  } catch (e) {
    setStatus('dot_c1', 'text_c1', 'err', 'Save failed');
  }
}

async function loadGrid() {
  try {
    const res  = await fetch('/api/load_grid');
    const data = await res.json();
    if (data.success) {
      state.grid      = data.grid;
      state.roads     = null;
      state.ambulance = null;
      renderAll();
      resetRoadsUI();
      resetAmbulanceUI();
      setStatus('dot_c1', 'text_c1', 'ok', 'Grid loaded ✓');
      setGlobal('ok', 'Grid loaded');
      $('btn_roads').disabled   = false;
      $('btn_save').disabled    = false;
      $('btn_ambulance').disabled = true;
    } else {
      setStatus('dot_c1', 'text_c1', 'err', data.error);
    }
  } catch (e) {
    setStatus('dot_c1', 'text_c1', 'err', 'Load failed');
  }
}

async function runRoads() {
  setGlobal('running', 'Building roads…');
  setStatus('dot_c2', 'text_c2', 'running', 'Building…');
  $('btn_roads').disabled     = true;
  $('btn_csp').disabled       = true;
  $('btn_ambulance').disabled = true;

  try {
    const res  = await fetch('/api/run_roads', { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      state.roads     = data;
      state.ambulance = null;

      renderAll();
      resetAmbulanceUI();

      setStatus('dot_c2', 'text_c2', 'ok', 'Road network built ✓');
      setGlobal('ok', 'Roads complete');
      $('c2_nodes').textContent = data.nodes;
      $('c2_mst').textContent   = data.mst_edges;
      $('c2_extra').textContent = data.extra_edges;
      $('c2_path1').textContent = '—';
      $('c2_path2').textContent = `${data.extra_edges} bridge edges`;

      $('btn_ambulance').disabled = false;
    } else {
      setStatus('dot_c2', 'text_c2', 'err', 'Error: ' + data.error);
      setGlobal('err', 'Roads failed');
    }
  } catch (e) {
    setStatus('dot_c2', 'text_c2', 'err', 'Network error');
    setGlobal('err', 'Request failed');
  }

  $('btn_roads').disabled = false;
  $('btn_csp').disabled   = false;
}

async function runAmbulance() {
  setGlobal('running', 'Running GA…');
  setStatus('dot_c3', 'text_c3', 'running', 'Optimising…');
  $('btn_ambulance').disabled = true;
  $('btn_roads').disabled     = true;
  $('btn_csp').disabled       = true;

  try {
    const res  = await fetch('/api/run_ambulance', { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      state.ambulance = data;
      renderAll();

      setStatus('dot_c3', 'text_c3', 'ok', 'Ambulances placed ✓');
      setGlobal('ok', 'GA complete');
      $('c3_placements').textContent = data.placements.length;
      $('c3_worst').textContent      = data.worst_case_distance != null ? data.worst_case_distance : '∞';
      $('c3_coverage').textContent   = `${data.covered} / ${data.total_citizens}`;
    } else {
      setStatus('dot_c3', 'text_c3', 'err', 'Error: ' + data.error);
      setGlobal('err', 'GA failed');
    }
  } catch (e) {
    setStatus('dot_c3', 'text_c3', 'err', 'Network error');
    setGlobal('err', 'Request failed');
  }

  $('btn_ambulance').disabled = false;
  $('btn_roads').disabled     = false;
  $('btn_csp').disabled       = false;
}

// ── UI Resets ──────────────────────────────────────
function resetRoadsUI() {
  setStatus('dot_c2', 'text_c2', 'idle', 'Ready');
  $('c2_nodes').textContent = '—';
  $('c2_mst').textContent   = '—';
  $('c2_extra').textContent = '—';
  $('c2_path1').textContent = '—';
  $('c2_path2').textContent = '—';
}

function resetAmbulanceUI() {
  setStatus('dot_c3', 'text_c3', 'idle', 'Run C2 first');
  $('c3_placements').textContent = '—';
  $('c3_worst').textContent      = '—';
  $('c3_coverage').textContent   = '—';
  $('btn_ambulance').disabled    = true;
}

// ── Init ───────────────────────────────────────────
updateTotal();