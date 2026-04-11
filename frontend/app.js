const API = '';  // same origin

// ── Map init ──────────────────────────────────────────────────────────────────

const map = L.map('map', { center: [51.25, 22.57], zoom: 8, zoomControl: false });

L.control.zoom({ position: 'bottomright' }).addTo(map);

// Prevent scroll events on overlays from reaching Leaflet (would zoom the map)
L.DomEvent.disableScrollPropagation(document.getElementById('alert-modal'));
L.DomEvent.disableScrollPropagation(document.getElementById('alert-hud'));

// Dark CartoDB tiles — ops-center aesthetic
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '© <a href="https://openstreetmap.org">OSM</a> contributors, © <a href="https://carto.com">CARTO</a>',
  subdomains: 'abcd',
  maxZoom: 20,
}).addTo(map);

// ── State ─────────────────────────────────────────────────────────────────────

const layerGroups  = {};   // layer_id → L.LayerGroup
const layerEnabled = {};   // layer_id → bool
const layerMeta    = {};   // layer_id → meta object
let allEvents = [];

const layerConfig       = {};  // layer_id → {mainProp, thresholds, popupProps}
const layerNumericProps = {};  // layer_id → string[]  (numeric property names)
const layerAllProps     = {};  // layer_id → string[]  (all property names)
const layerLabelMaps    = {};  // layer_id → {attr_key: "Human Label"}

// ── Layer config persistence ──────────────────────────────────────────────────

function loadLayerConfig(id) {
  try {
    const raw = localStorage.getItem(`sentinel_layer_config_${id}`);
    return raw ? JSON.parse(raw) : { mainProp: null, thresholds: [], popupProps: null };
  } catch { return { mainProp: null, thresholds: [], popupProps: null }; }
}

function saveLayerConfig(id, cfg) {
  layerConfig[id] = cfg;
  localStorage.setItem(`sentinel_layer_config_${id}`, JSON.stringify(cfg));
}

// ── Constants ─────────────────────────────────────────────────────────────────

const SEVERITY_COLOR = {
  critical: '#ef4444',
  high:     '#f97316',
  medium:   '#eab308',
  low:      '#10b981',
};

const CATEGORY_ICON = {
  fire:           '🔥',
  flood:          '🌊',
  medical:        '🏥',
  hazmat:         '☢️',
  security:       '🚨',
  infrastructure: '⚡',
  other:          '⚠️',
};

const RESOURCE_ICON = {
  hospital:     '🏥',
  school:       '🏫',
  social:       '🏠',
  fire_station: '🚒',
};

const BEARING_LABELS = { 0:'N', 45:'NE', 90:'E', 135:'SE', 180:'S', 225:'SW', 270:'W', 315:'NW' };

const LAYER_TYPE_CLASS = {
  resources:   'resources',
  events:      'events',
  boundary:    'boundary',
  simulation:  'simulation',
  air_quality: 'air_quality',
  flood_zone:  'flood_zone',
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
}

function bearingLabel(deg) {
  const nearest = Object.keys(BEARING_LABELS).reduce((a, b) =>
    Math.abs(b - deg) < Math.abs(a - deg) ? b : a
  );
  return `${deg}° (${BEARING_LABELS[nearest] || '—'})`;
}

function getColorForValue(value, thresholds) {
  if (!thresholds?.length || value == null || isNaN(Number(value))) return null;
  const num = Number(value);
  for (const t of thresholds) {
    if (t.value == null) return t.color;  // catch-all
    if (num < t.value)   return t.color;
  }
  return thresholds[thresholds.length - 1].color;
}

function isLowestBucket(value, thresholds) {
  if (!thresholds?.length || value == null || isNaN(Number(value))) return false;
  const first = thresholds.find(t => t.value != null);
  return first != null && Number(value) < first.value;
}

function defaultThresholds() {
  return [
    { value: 10,  color: '#ef4444' },
    { value: 50,  color: '#f97316' },
    { color: '#10b981' },
  ];
}

function popupHtml(props, allowedKeys, labelMap) {
  if (!props) return '<div class="popup-title">Brak danych</div>';
  const skip = new Set(['id', 'type']);
  const labels = labelMap || {};
  const rows = Object.entries(props)
    .filter(([k]) => {
      if (skip.has(k) || props[k] == null || props[k] === '') return false;
      return !allowedKeys?.length || allowedKeys.includes(k);
    })
    .map(([k, v]) => {
      const displayKey = labels[k] || k;
      const displayVal = typeof v === 'boolean' ? (v ? 'Tak' : 'Nie') : v;
      return `<div class="popup-row">${displayKey}<span>${displayVal}</span></div>`;
    })
    .join('');
  return `<div class="popup-title">${props.name || props.description || 'Obiekt'}</div>${rows}`;
}

// ── Layer rendering ───────────────────────────────────────────────────────────

function styleForFeature(feature) {
  const { type, severity } = feature.properties ?? {};
  if (type === 'voivodeship') return { color: '#1e3d5e', weight: 1.5, fillColor: '#0b1426', fillOpacity: 0.35 };
  if (type === 'threat_zone') return { color: '#ef4444', weight: 2, fillColor: '#ef4444', fillOpacity: 0.12, dashArray: '6 4' };
  if (type === 'flood_zone')  return { color: '#0ea5e9', weight: 1, fillColor: '#38bdf8', fillOpacity: 0.30 };
  const color = SEVERITY_COLOR[severity] || '#3b82f6';
  return { color, weight: 1.5, fillColor: color, fillOpacity: 0.18 };
}

function pointToLayer(feature, latlng, layerId) {
  const { type, severity, category } = feature.properties ?? {};

  if (type === 'powiat') {
    return L.circleMarker(latlng, {
      radius: 2.5,
      color: '#1e3d5e',
      fillColor: '#1e3d5e',
      fillOpacity: 0.8,
      weight: 1,
    });
  }

  const resourceIcon = RESOURCE_ICON[type];
  if (resourceIcon) {
    const cfg = layerId ? (layerConfig[layerId] || {}) : {};
    const propVal = cfg.mainProp != null ? feature.properties?.[cfg.mainProp] : null;
    const bgColor = getColorForValue(propVal, cfg.thresholds);
    const pulse   = bgColor && isLowestBucket(propVal, cfg.thresholds);
    const circleStyle = bgColor
      ? `background:${bgColor};border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;${pulse ? '' : `box-shadow:0 0 6px ${bgColor}88;`}`
      : '';
    const markerClass = `map-marker-wrap${pulse ? ' marker-pulse' : ''}`;
    return L.marker(latlng, {
      icon: L.divIcon({
        html: `<div class="${markerClass}" style="${circleStyle}font-size:1rem;filter:drop-shadow(0 1px 3px rgba(0,0,0,.9))">${resourceIcon}</div>`,
        iconSize: [22, 22], iconAnchor: [11, 11], className: '',
      }),
    });
  }

  const color = SEVERITY_COLOR[severity] || '#6e92b4';
  const icon  = CATEGORY_ICON[category] || '⚠️';

  // 112 call: investigating = dark red pulsing border; active = severity color ring
  if (type === 'event') {
    const props = feature.properties ?? {};
    const isNoResponse = props.status === 'investigating';
    const ringColor = isNoResponse ? '#7f1d1d' : (SEVERITY_COLOR[severity] || '#6e92b4');
    const pulse = isNoResponse || severity === 'critical';
    const markerClass = `map-marker-wrap${pulse ? ' marker-pulse' : ''}`;
    const border = `2px solid ${ringColor}`;
    return L.marker(latlng, {
      icon: L.divIcon({
        html: `<div class="${markerClass}" style="background:${ringColor}22;border:${border};border-radius:50%;width:24px;height:24px;display:flex;align-items:center;justify-content:center;font-size:1rem;filter:drop-shadow(0 1px 4px rgba(0,0,0,.9))">${icon}</div>`,
        iconSize: [24, 24], iconAnchor: [12, 12], className: '',
      }),
    });
  }

  return L.marker(latlng, {
    icon: L.divIcon({
      html: `<div class="map-marker-wrap" style="font-size:1.4rem;filter:drop-shadow(0 1px 4px rgba(0,0,0,.9))">${icon}</div>`,
      iconSize: [24, 24], iconAnchor: [12, 12], className: '',
    }),
  });
}

async function fetchAndRenderLayer(id) {
  try {
    const res = await fetch(`${API}/api/layers/${id}/geojson`);
    if (!res.ok) return;
    const data = await res.json();

    const geojson = data;

    // Discover property names and types from GeoJSON features
    const numericProps = new Set();
    const allPropsSet  = new Set();
    for (const feat of geojson.features ?? []) {
      const props = feat.properties;
      if (!props) continue;
      for (const [k, v] of Object.entries(props)) {
        allPropsSet.add(k);
        if (k !== 'id' && (typeof v === 'number' || (typeof v === 'string' && v !== '' && !isNaN(Number(v))))) {
          numericProps.add(k);
        }
      }
    }
    layerNumericProps[id] = [...numericProps];
    layerAllProps[id]     = [...allPropsSet];

    if (layerGroups[id]) {
      layerGroups[id].clearLayers();
    } else {
      layerGroups[id] = L.layerGroup();
    }

    const geoLayer = L.geoJSON(geojson, {
      style: styleForFeature,
      pointToLayer: (feature, latlng) => pointToLayer(feature, latlng, id),
      onEachFeature(feature, layer) {
        const cfg     = layerConfig[id] || {};
        const allowed = cfg.popupProps?.length ? cfg.popupProps : null;
        layer.bindPopup(popupHtml(feature.properties, allowed, layerLabelMaps[id]), { maxWidth: 300 });
        if (feature.properties?.type === 'powiat') {
          layer.on('click', () => filterEventsByPowiat(feature.properties.name));
        }
      },
    });

    layerGroups[id].addLayer(geoLayer);
    if (layerEnabled[id] && !map.hasLayer(layerGroups[id])) {
      layerGroups[id].addTo(map);
    }
  } catch (e) {
    console.warn(`Failed to fetch layer ${id}:`, e);
  }
}

// ── Layer panel ───────────────────────────────────────────────────────────────

function renderLayerPanel(layers) {
  const list = document.getElementById('layer-list');
  const countEl = document.getElementById('layer-count');
  countEl.textContent = layers.length;

  if (!layers.length) {
    list.innerHTML = '<div class="empty-state">Brak warstw</div>';
    return;
  }

  list.innerHTML = layers.map(layer => {
    const dotClass  = LAYER_TYPE_CLASS[layer.data_type] || 'boundary';
    const hasConfig = layer.data_type === 'resources';
    return `
      <div class="layer-entry" data-layer-id="${layer.layer_id}">
        <label class="layer-item">
          <input type="checkbox" id="toggle-${layer.layer_id}" ${layerEnabled[layer.layer_id] ? 'checked' : ''} />
          <span class="layer-dot ${dotClass}"></span>
          <span class="layer-name">${layer.name}</span>
          ${hasConfig ? `<button class="layer-cfg-btn" data-layer-id="${layer.layer_id}" title="Konfiguracja warstwy">⚙</button>` : ''}
        </label>
        ${hasConfig ? `<div class="layer-cfg-panel" id="cfg-panel-${layer.layer_id}" style="display:none"></div>` : ''}
      </div>
    `;
  }).join('');

  layers.forEach(layer => {
    document.getElementById(`toggle-${layer.layer_id}`).addEventListener('change', e => {
      layerEnabled[layer.layer_id] = e.target.checked;
      const group = layerGroups[layer.layer_id];
      if (!group) return;
      if (e.target.checked) {
        group.addTo(map);
      } else {
        map.removeLayer(group);
      }
    });

    if (layer.data_type === 'resources') {
      document.querySelector(`.layer-cfg-btn[data-layer-id="${layer.layer_id}"]`)
        ?.addEventListener('click', e => { e.stopPropagation(); toggleConfigPanel(layer.layer_id); });
    }
  });
}

// ── Layer config panel ────────────────────────────────────────────────────────

function toggleConfigPanel(id) {
  const panel = document.getElementById(`cfg-panel-${id}`);
  if (!panel) return;
  if (panel.style.display !== 'none') { panel.style.display = 'none'; return; }
  renderConfigPanel(id, panel);
  panel.style.display = 'block';
}

function renderConfigPanel(id, panelEl) {
  const cfg            = layerConfig[id] || { mainProp: null, thresholds: [], popupProps: null };
  const numericProps   = layerNumericProps[id] || [];
  const allProps       = (layerAllProps[id] || []).filter(p => p !== 'id' && p !== 'type');
  const activeThresh   = (cfg.mainProp && cfg.thresholds.length) ? cfg.thresholds : (cfg.mainProp ? defaultThresholds() : []);

  panelEl.innerHTML = `
    <div class="cfg-section">
      <div class="cfg-label">Właściwość główna</div>
      <select class="cfg-main-prop">
        <option value="">— brak —</option>
        ${numericProps.map(p => {
          const lbl = (layerLabelMaps[id] || {})[p] || p;
          return `<option value="${p}" ${cfg.mainProp === p ? 'selected' : ''}>${lbl}</option>`;
        }).join('')}
      </select>
    </div>
    ${cfg.mainProp ? `
    <div class="cfg-section">
      <div class="cfg-label">Progi kolorów <button class="cfg-thresh-add">+ dodaj</button></div>
      <div class="cfg-threshold-list">
        ${activeThresh.map(t => `
          <div class="cfg-threshold-row">
            <input class="cfg-thresh-val" type="number" placeholder="max wartość" value="${t.value ?? ''}" />
            <input class="cfg-thresh-color" type="color" value="${t.color || '#10b981'}" />
            <button class="cfg-thresh-del">✕</button>
          </div>`).join('')}
      </div>
    </div>` : ''}
    <div class="cfg-section">
      <div class="cfg-label">
        Właściwości w popupie
        <button class="cfg-props-all">wszystkie</button>
        <button class="cfg-props-none">żadne</button>
      </div>
      <input class="cfg-prop-filter" type="text" placeholder="szukaj…" />
      <div class="cfg-prop-list">
        ${allProps.map(p => {
          const checked = !cfg.popupProps?.length || cfg.popupProps.includes(p) ? 'checked' : '';
          const lbl = (layerLabelMaps[id] || {})[p] || p;
          return `<label class="cfg-prop-check"><input type="checkbox" value="${p}" ${checked}> ${lbl}</label>`;
        }).join('')}
      </div>
    </div>
    <div class="cfg-section">
      <button class="cfg-apply-btn">Zastosuj</button>
    </div>
  `;

  panelEl.querySelector('.cfg-apply-btn').addEventListener('click', () => applyConfigPanel(id, panelEl));
  panelEl.querySelector('.cfg-thresh-add')?.addEventListener('click', () => addThresholdRow(panelEl));
  panelEl.querySelectorAll('.cfg-thresh-del').forEach(b =>
    b.addEventListener('click', e => e.target.closest('.cfg-threshold-row').remove())
  );
  panelEl.querySelector('.cfg-main-prop').addEventListener('change', () => {
    layerConfig[id] = { ...(layerConfig[id] || {}), mainProp: panelEl.querySelector('.cfg-main-prop').value || null };
    renderConfigPanel(id, panelEl);
  });
  panelEl.querySelector('.cfg-props-all')?.addEventListener('click', () => {
    panelEl.querySelectorAll('.cfg-prop-list input').forEach(cb => cb.checked = true);
  });
  panelEl.querySelector('.cfg-props-none')?.addEventListener('click', () => {
    panelEl.querySelectorAll('.cfg-prop-list input').forEach(cb => cb.checked = false);
  });
  panelEl.querySelector('.cfg-prop-filter')?.addEventListener('input', e => {
    const q = e.target.value.toLowerCase();
    panelEl.querySelectorAll('.cfg-prop-check').forEach(el => {
      el.style.display = el.textContent.trim().toLowerCase().includes(q) ? '' : 'none';
    });
  });
}

function applyConfigPanel(id, panelEl) {
  const mainProp   = panelEl.querySelector('.cfg-main-prop')?.value || null;
  const thresholds = [];
  panelEl.querySelectorAll('.cfg-threshold-row').forEach(row => {
    const val   = parseFloat(row.querySelector('.cfg-thresh-val').value);
    const color = row.querySelector('.cfg-thresh-color').value;
    thresholds.push(isNaN(val) ? { color } : { value: val, color });
  });
  thresholds.sort((a, b) => (a.value == null ? 1 : b.value == null ? -1 : a.value - b.value));

  const allProps   = (layerAllProps[id] || []).filter(p => p !== 'id' && p !== 'type');
  const checked    = [...panelEl.querySelectorAll('.cfg-prop-list input:checked')].map(el => el.value);
  const popupProps = checked.length === allProps.length ? null : checked;

  saveLayerConfig(id, { mainProp, thresholds, popupProps });
  fetchAndRenderLayer(id);

  const btn = panelEl.querySelector('.cfg-apply-btn');
  btn.textContent = 'Zastosowano ✓';
  setTimeout(() => { btn.textContent = 'Zastosuj'; }, 1500);
}

function addThresholdRow(panelEl) {
  const list = panelEl.querySelector('.cfg-threshold-list');
  const row  = document.createElement('div');
  row.className = 'cfg-threshold-row';
  row.innerHTML = `<input class="cfg-thresh-val" type="number" placeholder="max wartość" /><input class="cfg-thresh-color" type="color" value="#10b981" /><button class="cfg-thresh-del">✕</button>`;
  row.querySelector('.cfg-thresh-del').addEventListener('click', () => row.remove());
  list.appendChild(row);
}

// ── Events panel ──────────────────────────────────────────────────────────────

function renderEvents(events) {
  const list     = document.getElementById('event-list');
  const badge    = document.getElementById('events-count-badge');
  const countEl  = document.getElementById('event-count');

  badge.textContent  = events.length;
  countEl.textContent = `${events.length} zdarzeń`;

  if (!events.length) {
    list.innerHTML = '<div class="empty-state">Brak zdarzeń</div>';
    return;
  }

  // Show newest first, cap at 50
  const shown = [...events].reverse().slice(0, 50);

  list.innerHTML = shown.map(ev => `
    <div class="event-card severity-${ev.severity}" data-lat="${ev.latitude}" data-lon="${ev.longitude}">
      <div class="event-title">${CATEGORY_ICON[ev.category] || '⚠️'} ${ev.description}</div>
      <div class="event-meta">
        <span>${ev.category}</span>
        <span class="event-severity ${ev.severity}">${ev.severity}</span>
        <span>${formatTime(ev.time)}</span>
      </div>
    </div>
  `).join('');

  list.querySelectorAll('.event-card').forEach(card => {
    card.addEventListener('click', () => {
      const lat = parseFloat(card.dataset.lat);
      const lon = parseFloat(card.dataset.lon);
      if (lat && lon) map.setView([lat, lon], 12);
    });
  });
}

function filterEventsByPowiat(name) {
  console.log('Filter by powiat:', name);
}

function renderEventMarkers(events) {
  if (!layerGroups['__events__']) {
    layerGroups['__events__'] = L.layerGroup().addTo(map);
  }
  layerGroups['__events__'].clearLayers();

  events.forEach(ev => {
    if (!ev.latitude || !ev.longitude) return;
    const icon  = CATEGORY_ICON[ev.category] || '⚠️';
    const color = SEVERITY_COLOR[ev.severity] || '#6e92b4';
    L.marker([ev.latitude, ev.longitude], {
      icon: L.divIcon({
        html: `<div class="map-marker-wrap" style="font-size:1.5rem;filter:drop-shadow(0 1px 4px rgba(0,0,0,.9))">${icon}</div>`,
        iconSize: [28, 28], iconAnchor: [14, 14], className: '',
      }),
    })
      .bindPopup(`
        <div class="popup-title">${icon} ${ev.description}</div>
        <div class="popup-row">Kategoria <span>${ev.category}</span></div>
        <div class="popup-row">Powaga <span style="color:${color}">${ev.severity}</span></div>
        <div class="popup-row">Status <span>${ev.status}</span></div>
        <div class="popup-row">Czas <span>${formatTime(ev.time)}</span></div>
        <div class="popup-row">Źródło <span>${ev.source}</span></div>
      `)
      .addTo(layerGroups['__events__']);
  });
}

// ── Alert modal ───────────────────────────────────────────────────────────────

let _lastAlerts = [];

document.getElementById('hud-toggle').addEventListener('click', () => {
  if (!_lastAlerts.length) return;
  openAlertModal(_lastAlerts);
});

document.getElementById('alert-modal-close').addEventListener('click', closeAlertModal);
document.getElementById('alert-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeAlertModal();
});

function openAlertModal(alerts) {
  const modal     = document.getElementById('alert-modal');
  const panel     = modal.querySelector('.alert-modal-panel');
  const body      = document.getElementById('alert-modal-body');
  const sub       = document.getElementById('modal-sub');
  const hasCrit   = alerts.some(a => a.level === 'inside');

  panel.className = 'alert-modal-panel' + (hasCrit ? ' has-critical' : '');
  modal.classList.add('open');

  const inside     = alerts.filter(a => a.level === 'inside').length;
  const approaching = alerts.filter(a => a.level === 'approaching').length;
  sub.textContent = `${inside} w strefie · ${approaching} blisko · ${alerts.length} łącznie`;

  body.innerHTML = alerts.map((a, i) => {
    const icon = resourceTypeIcon(a.resource_name);
    const tag  = a.level === 'inside' ? 'W STREFIE' : 'BLISKO';
    return `
      <div class="modal-alert-card level-${a.level}" style="animation-delay:${i * 0.04}s">
        <div class="modal-card-top">
          <span class="modal-card-icon">${icon}</span>
          <span class="modal-card-name">${a.resource_name}</span>
          <span class="modal-card-tag">${tag}</span>
        </div>
        <div class="modal-card-action">${a.action}</div>
      </div>
    `;
  }).join('');
}

function closeAlertModal() {
  document.getElementById('alert-modal').classList.remove('open');
}

// ── Alert HUD ─────────────────────────────────────────────────────────────────

function resourceTypeIcon(name = '') {
  const n = name.toLowerCase();
  if (n.includes('szpital') || n.includes('klinik') || n.includes('hospita')) return '🏥';
  if (n.includes('szkoł') || n.includes('liceum') || n.includes('gimn') || n.includes('sp nr') || n.includes('zespół szkół')) return '🏫';
  if (n.includes('dps') || n.includes('dom pomocy') || n.includes('opieki')) return '🏠';
  if (n.includes('psp') || n.includes('osp') || n.includes('straż')) return '🚒';
  return '📍';
}

function renderAlertHud(alerts) {
  const hud       = document.getElementById('alert-hud');
  const list      = document.getElementById('hud-alert-list');
  const countEl   = document.getElementById('hud-count');

  _lastAlerts = alerts || [];

  if (!alerts || !alerts.length) {
    hud.style.display = 'none';
    closeAlertModal();
    return;
  }

  const hasCritical = alerts.some(a => a.level === 'inside');

  hud.style.display = 'flex';
  hud.className = hasCritical ? 'has-critical' : '';

  countEl.textContent = `${alerts.length} obiekt${alerts.length === 1 ? '' : 'ów'}`;

  list.innerHTML = alerts.map((a, i) => {
    const icon = resourceTypeIcon(a.resource_name);
    const tag  = a.level === 'inside' ? 'STREFA' : 'BLISKO';
    return `
      <div class="hud-alert-item level-${a.level}" style="animation-delay:${i * 0.06}s">
        <div class="alert-resource">
          <span class="alert-icon">${icon}</span>
          <span class="alert-name">${a.resource_name}</span>
          <span class="alert-level-tag">${tag}</span>
        </div>
        <div class="alert-action">${a.action}</div>
      </div>
    `;
  }).join('');
}

// ── Main refresh ──────────────────────────────────────────────────────────────

async function refresh() {
  try {
    const layersRes = await fetch(`${API}/api/layers`);
    if (layersRes.ok) {
      const layers = await layersRes.json();
      layers.forEach(l => {
        if (!(l.layer_id in layerEnabled)) layerEnabled[l.layer_id] = true;
        if (!(l.layer_id in layerConfig))  layerConfig[l.layer_id]  = loadLayerConfig(l.layer_id);
        layerMeta[l.layer_id] = l;
      });
      renderLayerPanel(layers);
      await Promise.all(layers.map(l => fetchAndRenderLayer(l.layer_id)));
    }

    const eventsRes = await fetch(`${API}/api/events`);
    if (eventsRes.ok) {
      allEvents = await eventsRes.json();
      renderEvents(allEvents);
      renderEventMarkers(allEvents);
    }

    document.getElementById('last-updated').textContent = new Date().toLocaleTimeString('pl-PL');
    const dot = document.getElementById('status-dot');
    dot.className = '';
    dot.style.background = 'var(--green)';
    dot.style.boxShadow  = '0 0 6px var(--green)';
  } catch (e) {
    console.error('Refresh failed:', e);
    const dot = document.getElementById('status-dot');
    dot.className = 'dead';
  }
}

// ── Simulation panel ──────────────────────────────────────────────────────────

document.getElementById('rng-wind').addEventListener('input', e => {
  document.getElementById('val-wind').textContent = e.target.value;
});
document.getElementById('rng-dir').addEventListener('input', e => {
  document.getElementById('val-dir').textContent = bearingLabel(+e.target.value);
});
document.getElementById('rng-int').addEventListener('input', e => {
  document.getElementById('val-int').textContent = (+e.target.value).toFixed(1);
});

function buildSimConfig() {
  return {
    source_lat: 51.4158,
    source_lon: 21.9698,
    wind_speed_kmh:       +document.getElementById('rng-wind').value,
    wind_direction_deg:   +document.getElementById('rng-dir').value,
    fire_intensity:       +document.getElementById('rng-int').value,
    tick_interval_seconds: 10,
  };
}

document.getElementById('btn-start').addEventListener('click', async () => {
  await fetch(`${API}/api/simulation/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildSimConfig()),
  });
  await updateSimState();
  await refresh();
});

document.getElementById('btn-stop').addEventListener('click', async () => {
  await fetch(`${API}/api/simulation/stop`, { method: 'POST' });
  await updateSimState();
});

document.getElementById('btn-reset').addEventListener('click', async () => {
  await fetch(`${API}/api/simulation/reset`, { method: 'POST' });
  await updateSimState();
  await refresh();
});

async function updateSimState() {
  try {
    const res = await fetch(`${API}/api/simulation/state`);
    if (!res.ok) return;
    const state = await res.json();

    const dot   = document.getElementById('sim-dot');
    const label = document.getElementById('sim-label');
    const tick  = document.getElementById('sim-tick');

    if (state.running) {
      dot.className      = 'running';
      label.textContent  = 'AKTYWNA';
      label.className    = 'running';
    } else {
      dot.className      = '';
      label.textContent  = state.tick > 0 ? 'ZATRZYMANA' : 'GOTOWA';
      label.className    = '';
    }

    tick.textContent = state.tick > 0 ? `T+${state.tick}` : '';
  } catch (e) {
    console.warn('Sim state fetch failed:', e);
  }
}

async function pollAlerts() {
  try {
    const res = await fetch(`${API}/api/v1/crisis/affected`);
    if (!res.ok) return;
    const alerts = await res.json();
    renderAlertHud(alerts);
  } catch (e) {
    console.warn('Alert poll failed:', e);
  }
}

document.getElementById('btn-clear-events').addEventListener('click', async () => {
  await fetch(`${API}/api/events`, { method: 'DELETE' });
  allEvents = [];
  renderEvents([]);
  renderEventMarkers([]);
  document.getElementById('event-count').textContent = '0 zdarzeń';
  document.getElementById('events-count-badge').textContent = '0';
});

// ── Layer schemas (human-friendly labels) ─────────────────────────────────

async function fetchLayerSchemas() {
  try {
    const res = await fetch(`${API}/api/assistant/layer-schemas`);
    if (!res.ok) return;
    const schemas = await res.json();
    for (const s of schemas) {
      const lmap = {};
      for (const a of s.attributes || []) lmap[a.key] = a.label;
      layerLabelMaps[s.layer_id] = lmap;
    }
  } catch (e) {
    console.warn('Failed to fetch layer schemas:', e);
  }
}

// ── AI Assistant ──────────────────────────────────────────────────────────

let assistantBusy = false;

function applyViewConfig(cfg) {
  if (!cfg) return;

  for (const id of (cfg.layers_visible || [])) {
    layerEnabled[id] = true;
    const group = layerGroups[id];
    if (group && !map.hasLayer(group)) group.addTo(map);
  }
  for (const id of (cfg.layers_hidden || [])) {
    layerEnabled[id] = false;
    const group = layerGroups[id];
    if (group && map.hasLayer(group)) map.removeLayer(group);
  }

  for (const [id, attrs] of Object.entries(cfg.popup_attributes || {})) {
    const existing = layerConfig[id] || { mainProp: null, thresholds: [], popupProps: null };
    existing.popupProps = attrs;
    saveLayerConfig(id, existing);
  }

  const crit = cfg.critical_attribute;
  if (crit && crit.layer_id && crit.attribute) {
    const existing = layerConfig[crit.layer_id] || { mainProp: null, thresholds: [], popupProps: null };
    existing.mainProp = crit.attribute;
    existing.thresholds = crit.thresholds || defaultThresholds();
    saveLayerConfig(crit.layer_id, existing);
    fetchAndRenderLayer(crit.layer_id);
  }

  document.querySelectorAll('#layer-list input[type="checkbox"]').forEach(cb => {
    const id = cb.id.replace('toggle-', '');
    cb.checked = !!layerEnabled[id];
  });

  for (const id of (cfg.layers_visible || [])) fetchAndRenderLayer(id);
}

async function sendAssistantQuery(query) {
  if (assistantBusy || !query.trim()) return;
  assistantBusy = true;

  const chatMessages = document.getElementById('chat-messages');
  chatMessages.innerHTML += `<div class="chat-msg user">${escapeHtml(query)}</div>`;

  const indicator = document.createElement('div');
  indicator.className = 'chat-msg assistant typing';
  indicator.textContent = 'Analizuję…';
  chatMessages.appendChild(indicator);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await fetch(`${API}/api/assistant/configure-view`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });

    if (!res.ok) {
      const err = await res.text();
      indicator.textContent = `Błąd: ${err}`;
      indicator.classList.remove('typing');
      indicator.classList.add('error');
      return;
    }

    const cfg = await res.json();
    indicator.remove();

    const explanation = cfg.explanation || 'Widok zaktualizowany.';
    const model = cfg.model || '';
    const modelTag = model && model !== 'fallback'
      ? ` <span class="chat-model">${model}</span>` : '';
    chatMessages.innerHTML +=
      `<div class="chat-msg assistant">${escapeHtml(explanation)}${modelTag}</div>`;
    chatMessages.scrollTop = chatMessages.scrollHeight;

    applyViewConfig(cfg);
  } catch (e) {
    indicator.textContent = 'Błąd połączenia z asystentem.';
    indicator.classList.remove('typing');
    indicator.classList.add('error');
    console.error('Assistant error:', e);
  } finally {
    assistantBusy = false;
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function initChat() {
  const input = document.getElementById('chat-input');
  const btn   = document.getElementById('chat-send');
  if (!input || !btn) return;

  const submit = () => {
    const q = input.value.trim();
    if (q) { sendAssistantQuery(q); input.value = ''; }
  };

  btn.addEventListener('click', submit);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); }
  });
}

// ── Voice Briefing (karaoke) ──────────────────────────────────────────────────

let briefingAudio = null;
let briefingWords = [];
let briefingWordEls = [];
let briefingBusy = false;
let briefingTimer = null;   // fallback interval when no audio
let briefingStartTs = 0;    // performance.now() at play start
let briefingDuration = 0;
let briefingPausedAt = 0;   // elapsed seconds when paused
let briefingHasAudio = false;

function fmtTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

function briefingCurrentTime() {
  if (briefingHasAudio && briefingAudio) return briefingAudio.currentTime;
  return briefingPausedAt + (performance.now() - briefingStartTs) / 1000;
}

function briefingSyncLoop() {
  const playing = briefingHasAudio
    ? (briefingAudio && !briefingAudio.paused)
    : (briefingTimer !== null);
  if (!playing) return;

  const t = briefingCurrentTime();
  const dur = briefingDuration || 1;

  for (let i = 0; i < briefingWords.length; i++) {
    const w = briefingWords[i];
    const el = briefingWordEls[i];
    if (!el) continue;
    if (t >= w.start && t <= w.end) {
      el.className = 'briefing-word speaking';
    } else if (t > w.end) {
      el.className = 'briefing-word spoken';
    } else {
      el.className = 'briefing-word';
    }
  }

  const bar = document.getElementById('briefing-bar');
  const time = document.getElementById('briefing-time');
  if (bar) bar.style.width = `${Math.min((t / dur) * 100, 100)}%`;
  if (time) time.textContent = `${fmtTime(Math.min(t, dur))} / ${fmtTime(dur)}`;

  if (t >= dur) {
    stopBriefingTimer();
    document.getElementById('briefing-play').textContent = '▶';
    return;
  }
  requestAnimationFrame(briefingSyncLoop);
}

function stopBriefingTimer() {
  if (briefingTimer !== null) { clearInterval(briefingTimer); briefingTimer = null; }
}

function renderBriefingWords(words) {
  const container = document.getElementById('briefing-text');
  container.innerHTML = '';
  briefingWordEls = [];
  for (const w of words) {
    const span = document.createElement('span');
    span.className = 'briefing-word';
    span.textContent = w.word + ' ';
    container.appendChild(span);
    briefingWordEls.push(span);
  }
}

function showBriefingWidget() {
  document.getElementById('briefing-widget').classList.remove('hidden');
}

function hideBriefingWidget() {
  document.getElementById('briefing-widget').classList.add('hidden');
  if (briefingAudio) { briefingAudio.pause(); briefingAudio = null; }
  stopBriefingTimer();
  briefingWords = [];
  briefingWordEls = [];
  briefingPausedAt = 0;
  briefingHasAudio = false;
  const bar = document.getElementById('briefing-bar');
  if (bar) bar.style.width = '0%';
  document.getElementById('briefing-time').textContent = '0:00 / 0:00';
  document.getElementById('briefing-play').textContent = '▶';
}

async function requestBriefing() {
  if (briefingBusy) return;
  briefingBusy = true;

  const btn = document.getElementById('briefing-btn');
  btn.disabled = true;
  btn.textContent = '⏳';

  try {
    const res = await fetch(`${API}/api/voice/briefing`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.text();
      alert(`Briefing error: ${err}`);
      return;
    }
    const data = await res.json();
    briefingWords = data.words;
    briefingDuration = data.duration_seconds;
    briefingPausedAt = 0;
    renderBriefingWords(data.words);
    showBriefingWidget();

    if (data.audio_base64) {
      briefingHasAudio = true;
      const raw = atob(data.audio_base64);
      const bytes = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      const blob = new Blob([bytes], { type: 'audio/mpeg' });
      const blobUrl = URL.createObjectURL(blob);
      briefingAudio = new Audio(blobUrl);
      briefingAudio.addEventListener('ended', () => {
        document.getElementById('briefing-play').textContent = '▶';
        URL.revokeObjectURL(blobUrl);
      });
      try {
        await briefingAudio.play();
        document.getElementById('briefing-play').textContent = '⏸';
        requestAnimationFrame(briefingSyncLoop);
      } catch (e) {
        console.warn('[BRIEFING] autoplay blocked, click ▶:', e);
      }
    } else {
      briefingHasAudio = false;
      briefingAudio = null;
      // Text-only: auto-start timer animation
      briefingStartTs = performance.now();
      briefingPausedAt = 0;
      briefingTimer = setInterval(() => {}, 50);
      document.getElementById('briefing-play').textContent = '⏸';
      requestAnimationFrame(briefingSyncLoop);
    }
  } catch (e) {
    console.error('Briefing fetch failed:', e);
    alert('Nie udało się wygenerować briefingu.');
  } finally {
    btn.disabled = false;
    btn.textContent = '📢';
    briefingBusy = false;
  }
}

function toggleBriefingPlay() {
  const btn = document.getElementById('briefing-play');

  if (briefingHasAudio && briefingAudio) {
    if (briefingAudio.paused) {
      briefingAudio.play();
      btn.textContent = '⏸';
      requestAnimationFrame(briefingSyncLoop);
    } else {
      briefingAudio.pause();
      btn.textContent = '▶';
    }
  } else {
    if (briefingTimer !== null) {
      briefingPausedAt = briefingCurrentTime();
      stopBriefingTimer();
      btn.textContent = '▶';
    } else {
      briefingStartTs = performance.now();
      briefingTimer = setInterval(() => {}, 50);
      btn.textContent = '⏸';
      requestAnimationFrame(briefingSyncLoop);
    }
  }
}

function initBriefing() {
  const btn = document.getElementById('briefing-btn');
  if (btn) btn.addEventListener('click', requestBriefing);

  const playBtn = document.getElementById('briefing-play');
  if (playBtn) playBtn.addEventListener('click', toggleBriefingPlay);

  const closeBtn = document.getElementById('briefing-close');
  if (closeBtn) closeBtn.addEventListener('click', hideBriefingWidget);
}

// ── 112 Emergency call generator panel ───────────────────────────────────────

let _e112Running = false;

document.getElementById('btn-e112-start').addEventListener('click', async () => {
  await fetch(`${API}/api/emergency/start`, { method: 'POST' });
  await update112State();
  await refresh();
});

document.getElementById('btn-e112-pause').addEventListener('click', async () => {
  const action = _e112Running ? 'pause' : 'resume';
  await fetch(`${API}/api/emergency/${action}`, { method: 'POST' });
  await update112State();
});

document.getElementById('btn-e112-reset').addEventListener('click', async () => {
  await fetch(`${API}/api/emergency/reset`, { method: 'POST' });
  await update112State();
  await refresh();
});

async function update112State() {
  try {
    const res = await fetch(`${API}/api/layers/events/geojson`);
    if (!res.ok) return;
    const geojson = await res.json();
    const simCalls = (geojson.features ?? []).filter(f => f.properties?.source === 'simulation');
    const count = simCalls.length;
    const noResponse = simCalls.filter(f => f.properties?.status === 'investigating').length;

    document.getElementById('e112-count').textContent = count;

    const dot   = document.getElementById('e112-dot');
    const label = document.getElementById('e112-label');

    if (_e112Running) {
      dot.className     = 'running';
      label.textContent = noResponse > 0 ? `AKTYWNA · ${noResponse} bez ZRM` : 'AKTYWNA';
      label.className   = 'running';
      document.getElementById('btn-e112-pause').textContent = '⏸ PAUZA';
    } else {
      dot.className     = '';
      label.textContent = count > 0 ? 'ZATRZYMANA' : 'GOTOWA';
      label.className   = '';
      document.getElementById('btn-e112-pause').textContent = '▶ WZNÓW';
    }
  } catch (e) {
    console.warn('112 state fetch failed:', e);
  }
}

document.getElementById('btn-e112-start').addEventListener('click', () => { _e112Running = true; }, true);
document.getElementById('btn-e112-reset').addEventListener('click', () => { _e112Running = false; }, true);
document.getElementById('btn-e112-pause').addEventListener('click', () => { _e112Running = !_e112Running; }, true);

// ── Boot ──────────────────────────────────────────────────────────────────────

fetchLayerSchemas();
initChat();
initBriefing();
refresh();
updateSimState();
update112State();
pollAlerts();
setInterval(refresh, 30_000);
setInterval(updateSimState, 10_000);
setInterval(update112State, 15_000);
setInterval(pollAlerts, 5_000);
