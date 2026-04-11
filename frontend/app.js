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

function popupHtml(props) {
  if (!props) return '<div class="popup-title">Brak danych</div>';
  const skip = new Set(['id', 'type']);
  const rows = Object.entries(props)
    .filter(([k]) => !skip.has(k) && props[k] != null && props[k] !== '')
    .map(([k, v]) => `<div class="popup-row">${k}<span>${v}</span></div>`)
    .join('');
  return `<div class="popup-title">${props.name || props.description || 'Obiekt'}</div>${rows}`;
}

// ── Layer rendering ───────────────────────────────────────────────────────────

function styleForFeature(feature) {
  const { type, severity } = feature.properties ?? {};
  if (type === 'voivodeship') return { color: '#1e3d5e', weight: 1.5, fillColor: '#0b1426', fillOpacity: 0.35 };
  if (type === 'threat_zone') return { color: '#ef4444', weight: 2, fillColor: '#ef4444', fillOpacity: 0.12, dashArray: '6 4' };
  const color = SEVERITY_COLOR[severity] || '#3b82f6';
  return { color, weight: 1.5, fillColor: color, fillOpacity: 0.18 };
}

function pointToLayer(feature, latlng) {
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
    return L.marker(latlng, {
      icon: L.divIcon({
        html: `<div class="map-marker-wrap" style="font-size:1rem;filter:drop-shadow(0 1px 3px rgba(0,0,0,.9))">${resourceIcon}</div>`,
        iconSize: [20, 20], iconAnchor: [10, 10], className: '',
      }),
    });
  }

  const color = SEVERITY_COLOR[severity] || '#6e92b4';
  const icon  = CATEGORY_ICON[category] || '⚠️';
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
    const geojson = await res.json();

    if (layerGroups[id]) {
      layerGroups[id].clearLayers();
    } else {
      layerGroups[id] = L.layerGroup();
    }

    const geoLayer = L.geoJSON(geojson, {
      style: styleForFeature,
      pointToLayer,
      onEachFeature(feature, layer) {
        layer.bindPopup(popupHtml(feature.properties), { maxWidth: 300 });
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
    const dotClass = LAYER_TYPE_CLASS[layer.data_type] || 'boundary';
    return `
      <label class="layer-item">
        <input type="checkbox" id="toggle-${layer.layer_id}" ${layerEnabled[layer.layer_id] ? 'checked' : ''} />
        <span class="layer-dot ${dotClass}"></span>
        <span class="layer-name">${layer.name}</span>
      </label>
    `;
  }).join('');

  layers.forEach(layer => {
    document.getElementById(`toggle-${layer.layer_id}`).addEventListener('change', e => {
      layerEnabled[layer.layer_id] = e.target.checked;
      const group = layerGroups[layer.layer_id];
      if (!group) return;
      e.target.checked ? group.addTo(map) : map.removeLayer(group);
    });
  });
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

    renderAlertHud(state.alerts || []);
  } catch (e) {
    console.warn('Sim state fetch failed:', e);
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

// ── Boot ──────────────────────────────────────────────────────────────────────

refresh();
updateSimState();
setInterval(refresh, 30_000);
setInterval(updateSimState, 10_000);
