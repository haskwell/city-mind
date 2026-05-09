const GRAPH_FILL_COLORS = {
  EMPTY:            '#111827',
  RESIDENTIAL:      '#22c55e',
  HOSPITAL:         '#ef4444',
  PRIMARY_HOSPITAL: '#991b1b',
  SCHOOL:           '#3b82f6',
  INDUSTRIAL:       '#f97316',
  POWER_PLANT:      '#a855f7',
  AMBULANCE_DEPOT:  '#06b6d4',
};

const RISK_BORDER = {
  High:   '#ef4444',
  Medium: '#f59e0b',
  Low:    '#22c55e',
};

const NODE_SPACING = 120;
const NODE_SIZE    = 54;

let cy = null;
let currentView = 'grid';

// C4 routing state
let selectedCivilians = new Set();   // "r_c" string keys
let selectingCivilians = false;      // true when C4 is ready for selection
let currentPathEdgeIds = [];         // edge ids currently highlighted as active path

function switchView(view) {
  currentView = view;

  const canvas    = document.getElementById('city_canvas');
  const graphCont = document.getElementById('graph_container');
  const tabGrid   = document.getElementById('tab_grid');
  const tabGraph  = document.getElementById('tab_graph');
  const placeholder = document.getElementById('canvas_placeholder');

  if (view === 'grid') {
    if (state.grid) {
      canvas.style.display = 'block';
      placeholder.classList.add('hidden');
    } else {
      canvas.style.display = 'none';
      placeholder.classList.remove('hidden');
    }
    graphCont.style.display = 'none';
    tabGrid.classList.add('active');
    tabGraph.classList.remove('active');
  } else {
    canvas.style.display = 'none';
    placeholder.classList.add('hidden');
    graphCont.style.display = 'block';
    tabGrid.classList.remove('active');
    tabGraph.classList.add('active');
    document.getElementById('graph_placeholder').style.display = state.roads ? 'none' : 'block';
    if (cy) cy.resize();
  }

  closeInspectPanel();
}

function graphViewReady() {
  document.getElementById('tab_graph').disabled = false;
  buildGraph();
}

function graphViewUpdate() {
  if (cy) buildGraph();
}

function buildGraph() {
  if (!state.grid || !state.roads) return;

  const elements = [];

  for (const cell of state.grid.cells) {
    if (cell.type === 'EMPTY') continue;

    const key      = `[${cell.row}, ${cell.col}]`;
    const risk     = state.crime?.risk_levels?.[key]  ?? null;
    const cluster  = state.crime?.cluster_labels?.[key] ?? null;

    elements.push({
      group: 'nodes',
      data: {
        id:                 `${cell.row}_${cell.col}`,
        row:                cell.row,
        col:                cell.col,
        label:              cell.type.charAt(0),
        type:               cell.type,
        population_density: cell.population_density,
        risk_index:         cell.risk_index,
        risk:               risk,
        cluster:            cluster,
        accessible:         true,
      },
      position: {
        x: cell.col * NODE_SPACING,
        y: cell.row * NODE_SPACING,
      },
    });
  }

  for (const edge of state.roads.edges) {
    const [ur, uc] = edge.u;
    const [vr, vc] = edge.v;
    const srcId = `${ur}_${uc}`;
    const tgtId = `${vr}_${vc}`;
    elements.push({
      group: 'edges',
      data: {
        id:             `e_${srcId}_${tgtId}`,
        source:         srcId,
        target:         tgtId,
        blocked:        edge.blocked,
        redundancy:     edge.redundancy,
        base_cost:      edge.base_cost      ?? null,
        effective_cost: edge.effective_cost ?? null,
      },
    });
  }

  if (cy) {
    cy.destroy();
    cy = null;
  }

  cy = cytoscape({
    container: document.getElementById('cy'),
    elements,
    style: buildCyStyle(),
    layout: { name: 'preset' },
    userZoomingEnabled:    true,
    userPanningEnabled:    true,
    boxSelectionEnabled:   false,
    autoungrabify:         false,
    minZoom: 0.2,
    maxZoom: 4,
  });

  cy.fit(cy.elements(), 48);

  cy.on('tap', 'node', function(evt) {
    const data = evt.target.data();
    // C4 civilian selection
    if (selectingCivilians && data.type !== 'AMBULANCE_DEPOT' && data.type !== 'EMPTY') {
      const key = `${data.row}_${data.col}`;
      if (selectedCivilians.has(key)) {
        selectedCivilians.delete(key);
        evt.target.removeClass('civilian');
      } else {
        selectedCivilians.add(key);
        evt.target.addClass('civilian');
      }
      updateCivilianCount();
      return;
    }
    showNodeInspect(data);
  });

  cy.on('tap', 'edge', function(evt) {
    showEdgeInspect(evt.target.data());
  });

  cy.on('tap', function(evt) {
    if (evt.target === cy) closeInspectPanel();
  });
  document.getElementById('graph_placeholder').style.display = 'none';

}

function buildCyStyle() {
  const nodeStyles = Object.entries(GRAPH_FILL_COLORS).map(([type, color]) => ({
    selector: `node[type="${type}"]`,
    style: { 'background-color': color },
  }));

  const riskStyles = Object.entries(RISK_BORDER).map(([risk, color]) => ({
    selector: `node[risk="${risk}"]`,
    style: {
      'border-color': color,
      'border-width':  4,
    },
  }));

  return [
    {
      selector: 'node',
      style: {
        'width':              NODE_SIZE,
        'height':             NODE_SIZE,
        'shape':              'round-rectangle',
        'label':              'data(label)',
        'color':              'rgba(255,255,255,0.9)',
        'font-family':        'Space Mono, monospace',
        'font-size':          16,
        'font-weight':        700,
        'text-valign':        'center',
        'text-halign':        'center',
        'border-width':       0,
        'border-color':       'transparent',
        'text-outline-width': 2,
        'text-outline-color': 'rgba(0,0,0,0.5)',
        'transition-property': 'border-color, border-width',
        'transition-duration': '0.2s',
      },
    },
    ...nodeStyles,
    ...riskStyles,
    {
      selector: 'node:selected',
      style: {
        'border-width': 3,
        'border-color': '#e8edf7',
        'overlay-color': '#ffffff',
        'overlay-opacity': 0.06,
        'overlay-padding': 6,
      },
    },
    {
      selector: 'edge',
      style: {
        'width':              2,
        'line-color':         'rgba(200,210,230,0.35)',
        'curve-style':        'straight',
        'opacity':            1,
      },
    },
    {
      selector: 'edge[?redundancy]',
      style: {
        'line-color':   '#14b8a6',
        'line-style':   'dashed',
        'line-dash-pattern': [8, 5],
        'width':         2,
        'opacity':       0.7,
      },
    },
    {
      selector: 'edge[?blocked]',
      style: {
        'line-color': '#ef4444',
        'width':       3,
        'opacity':     0.9,
      },
    },
    {
      selector: 'edge:selected',
      style: {
        'line-color':    '#f59e0b',
        'width':          4,
        'overlay-color':  '#f59e0b',
        'overlay-opacity': 0.15,
        'overlay-padding': 4,
      },
    },
    // C4: civilian selection style
    {
      selector: 'node.civilian',
      style: {
        'border-color': '#f59e0b',
        'border-width':  5,
        'width':         NODE_SIZE * 1.15,
        'height':        NODE_SIZE * 1.15,
      },
    },
    // C4: medic marker
    {
      selector: 'node[type="MEDIC"]',
      style: {
        'background-color': '#ffffff',
        'color':             '#000000',
        'font-size':         20,
        'font-weight':       700,
        'width':             NODE_SIZE * 1.1,
        'height':            NODE_SIZE * 1.1,
        'shape':             'ellipse',
        'border-color':      '#fde047',
        'border-width':       4,
        'z-index':            999,
        'text-outline-width': 0,
      },
    },
    // C4: active path highlighting
    {
      selector: 'edge.active-path',
      style: {
        'line-color': '#fde047',
        'width':       4,
        'opacity':     1,
        'z-index':     100,
      },
    },
  ];
}

function showNodeInspect(data) {
  const panel = document.getElementById('inspect_panel');
  const body  = document.getElementById('inspect_body');
  const title = document.getElementById('inspect_title');
  const badge = document.getElementById('inspect_badge');

  title.textContent = 'Node Inspector';

  const color = GRAPH_FILL_COLORS[data.type] || '#5a6680';
  badge.textContent  = data.type.replace(/_/g, ' ');
  badge.style.background = color + '22';
  badge.style.color      = color;
  badge.style.border     = `1px solid ${color}44`;

  let html = '';

  html += section('Location', [
    row('Row',    data.row),
    row('Column', data.col),
    row('Type',   data.type.replace(/_/g, ' ')),
  ]);

  html += section('Attributes', [
    row('Population Density', data.population_density ?? '—'),
    row('Risk Index',         typeof data.risk_index === 'number' ? data.risk_index.toFixed(2) : '—'),
    row('Accessible',         data.accessible ? valClass('Yes', 'ok') : valClass('No', 'blocked')),
  ]);

  if (data.risk || data.cluster !== null) {
    const riskClass = data.risk ? data.risk.toLowerCase() : '';
    html += section('Crime Analysis (C5)', [
      row('Risk Level', data.risk ? valClass(data.risk, riskClass) : noData()),
      row('Cluster',    data.cluster !== null ? data.cluster : noData()),
    ]);

    const key = `[${data.row}, ${data.col}]`;
    const exp = state.crime?.explanations?.[key];
    if (exp) {
      html += `<div class="inspect-section">
        <div class="inspect-section-label">Explanation</div>
        <div class="inspect-explanation">
          ${exp.split(' | ').map(s => `<span>• ${s}</span>`).join('')}
        </div>
      </div>`;
    }
  } else {
    html += `<div class="inspect-section">
      <div class="inspect-section-label">Crime Analysis (C5)</div>
      <div class="inspect-no-data">Run C5 to see risk data</div>
    </div>`;
  }

  body.innerHTML = html;
  panel.classList.add('open');
}

function showEdgeInspect(data) {
  const panel = document.getElementById('inspect_panel');
  const body  = document.getElementById('inspect_body');
  const title = document.getElementById('inspect_title');
  const badge = document.getElementById('inspect_badge');

  title.textContent = 'Edge Inspector';

  let edgeLabel = data.blocked ? 'BLOCKED' : data.redundancy ? 'BACKUP' : 'MST';
  let edgeColor = data.blocked ? '#ef4444' : data.redundancy ? '#14b8a6' : 'rgba(200,210,230,0.5)';
  badge.textContent  = edgeLabel;
  badge.style.background = edgeColor + '22';
  badge.style.color      = edgeColor;
  badge.style.border     = `1px solid ${edgeColor}44`;

  const [ur, uc] = data.source.split('_').map(Number);
  const [vr, vc] = data.target.split('_').map(Number);

  const srcCell = state.grid?.cells.find(c => c.row === ur && c.col === uc);
  const tgtCell = state.grid?.cells.find(c => c.row === vr && c.col === vc);

  const srcColor = GRAPH_FILL_COLORS[srcCell?.type] ?? '#5a6680';
  const tgtColor = GRAPH_FILL_COLORS[tgtCell?.type] ?? '#5a6680';

  const srcLabel = `<span class="edge-endpoint"><span class="edge-dot" style="background:${srcColor}"></span>(${ur},${uc}) ${srcCell?.type?.replace(/_/g,' ') ?? ''}</span>`;
  const tgtLabel = `<span class="edge-endpoint"><span class="edge-dot" style="background:${tgtColor}"></span>(${vr},${vc}) ${tgtCell?.type?.replace(/_/g,' ') ?? ''}</span>`;

  let html = '';

  html += section('Endpoints', [
    row('From', srcLabel),
    row('To',   tgtLabel),
  ]);

  const base = data.base_cost;
  const eff  = data.effective_cost;
  let costRows = [];

  if (base !== null && base !== undefined) {
    costRows.push(row('Base Cost', base.toFixed(3)));
  } else {
    costRows.push(row('Base Cost', noData()));
  }

  if (eff !== null && eff !== undefined) {
    let effDisplay = eff.toFixed(3);
    if (base !== null && base !== undefined) {
      const delta = ((eff - base) / base) * 100;
      const deltaClass = delta > 0.01 ? 'up' : 'same';
      const deltaStr   = delta > 0.01 ? `+${delta.toFixed(1)}%` : '±0%';
      effDisplay = `<span class="cost-delta">${eff.toFixed(3)} <span class="delta-tag ${deltaClass}">${deltaStr}</span></span>`;
    }
    costRows.push(row('Effective Cost', effDisplay));
  } else {
    costRows.push(row('Effective Cost', noData()));
  }

  html += section('Costs', costRows);

  html += section('Status', [
    row('Road Type', data.redundancy ? 'Backup (redundant)' : 'MST (primary)'),
    row('Blocked',   data.blocked ? valClass('Yes — impassable', 'blocked') : valClass('No', 'ok')),
  ]);

  // C4: Block Road button
  const alreadyBlocked = data.blocked;
  html += `<div class="inspect-section">
    <button
      class="btn btn-ghost"
      style="width:100%;margin-top:4px;${alreadyBlocked ? 'opacity:0.4;cursor:not-allowed' : ''}"
      onclick="${alreadyBlocked ? '' : `blockRoad('${data.source}','${data.target}')`}"
      ${alreadyBlocked ? 'disabled' : ''}>
      🚧 ${alreadyBlocked ? 'Already Blocked' : 'Block Road'}
    </button>
  </div>`;

  body.innerHTML = html;
  panel.classList.add('open');
}

function section(label, rows) {
  return `<div class="inspect-section">
    <div class="inspect-section-label">${label}</div>
    ${rows.join('')}
  </div>`;
}

function row(key, val) {
  return `<div class="inspect-row">
    <span class="inspect-key">${key}</span>
    <span class="inspect-val">${val}</span>
  </div>`;
}

function valClass(text, cls) {
  return `<span class="inspect-val ${cls}">${text}</span>`;
}

function noData() {
  return `<span style="color:#2a3347;font-style:italic">—</span>`;
}

function closeInspectPanel() {
  document.getElementById('inspect_panel').classList.remove('open');
  if (cy) cy.$(':selected').unselect();
}
// ── C4: Civilian helpers ───────────────────────────────────────────────────

function enableCivilianSelection() {
  selectingCivilians = true;
}

function disableCivilianSelection() {
  selectingCivilians = false;
}

function updateCivilianCount() {
  const el = document.getElementById('c4_civilian_count');
  if (el) el.textContent = selectedCivilians.size;
  const clearBtn = document.getElementById('btn_clear_civilians');
  if (clearBtn) clearBtn.disabled = selectedCivilians.size === 0;
  const startBtn = document.getElementById('btn_start_routing');
  if (startBtn) startBtn.disabled = !(state.ambulance && selectedCivilians.size > 0);
}

function clearCivilians() {
  if (cy) {
    cy.nodes('.civilian').removeClass('civilian');
  }
  selectedCivilians.clear();
  updateCivilianCount();
}

function getCivilianList() {
  // Returns array of [row, col] from the "r_c" keys
  return Array.from(selectedCivilians).map(key => {
    const [r, c] = key.split('_').map(Number);
    return [r, c];
  });
}

// ── C4: Block road ─────────────────────────────────────────────────────────

async function blockRoad(srcId, tgtId) {
  const [ur, uc] = srcId.split('_').map(Number);
  const [vr, vc] = tgtId.split('_').map(Number);

  try {
    const res = await fetch('/api/routing/block_road', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ u: [ur, uc], v: [vr, vc] }),
    });
    const data = await res.json();
    if (data.success) {
      // Update Cytoscape edge data immediately
      const edgeId = `e_${srcId}_${tgtId}`;
      const altEdgeId = `e_${tgtId}_${srcId}`;
      const edge = cy.$(`#${edgeId}`).length ? cy.$(`#${edgeId}`) : cy.$(`#${altEdgeId}`);
      if (edge.length) {
        edge.data('blocked', true);
      }
      // Update state.roads.edges for consistency
      if (state.roads && state.roads.edges) {
        for (const e of state.roads.edges) {
          if ((e.u[0] === ur && e.u[1] === uc && e.v[0] === vr && e.v[1] === vc) ||
              (e.u[0] === vr && e.u[1] === vc && e.v[0] === ur && e.v[1] === uc)) {
            e.blocked = true;
          }
        }
      }
      closeInspectPanel();
    }
  } catch (err) {
    console.error('blockRoad failed', err);
  }
}

// ── C4: Medic marker ───────────────────────────────────────────────────────

function addMedicMarker(row, col) {
  if (!cy) return;
  removeMedicMarker();
  cy.add({
    group: 'nodes',
    data: { id: 'medic', type: 'MEDIC', label: '✚' },
    position: { x: col * NODE_SPACING, y: row * NODE_SPACING },
  });
}

function moveMedicMarker(row, col) {
  if (!cy) return;
  const medic = cy.$('#medic');
  if (medic.length) {
    medic.position({ x: col * NODE_SPACING, y: row * NODE_SPACING });
  }
}

function removeMedicMarker() {
  if (!cy) return;
  cy.$('#medic').remove();
}

// ── C4: Path highlighting ──────────────────────────────────────────────────

function highlightPath(pathNodes) {
  if (!cy) return;
  // Clear old
  for (const eid of currentPathEdgeIds) {
    cy.$(`#${eid}`).removeClass('active-path');
  }
  currentPathEdgeIds = [];

  if (!pathNodes || pathNodes.length < 2) return;

  for (let i = 0; i < pathNodes.length - 1; i++) {
    const [ar, ac] = pathNodes[i];
    const [br, bc] = pathNodes[i + 1];
    const srcId = `${ar}_${ac}`;
    const tgtId = `${br}_${bc}`;
    const edgeId  = `e_${srcId}_${tgtId}`;
    const edgeId2 = `e_${tgtId}_${srcId}`;
    const edge = cy.$(`#${edgeId}`).length ? cy.$(`#${edgeId}`) : cy.$(`#${edgeId2}`);
    if (edge.length) {
      edge.addClass('active-path');
      currentPathEdgeIds.push(edge.id());
    }
  }
}

function clearPathHighlight() {
  for (const eid of currentPathEdgeIds) {
    if (cy) cy.$(`#${eid}`).removeClass('active-path');
  }
  currentPathEdgeIds = [];
}

// ── C4: Extend buildCyStyle with civilian, medic, active-path styles ───────
// Called automatically by buildGraph() via a monkey-patch approach:
// We override the style array after the fact.

const _origBuildCyStyle = buildCyStyle;
// (We extend at the bottom of the file, after buildCyStyle is defined)
