const API = '';  // same origin

// ── Map init ──────────────────────────────────────────────────────────────────

const map = L.map('map', { center: [51.25, 22.57], zoom: 8 });

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© OpenStreetMap contributors',
  maxZoom: 18,
}).addTo(map);

// ── State ─────────────────────────────────────────────────────────────────────

const layerGroups = {};   // layer_id → L.LayerGroup
const layerEnabled = {};  // layer_id → bool
const layerMeta    = {};  // layer_id → meta object
let allEvents = [];

// ── Constants ─────────────────────────────────────────────────────────────────

const SEVERITY_COLOR = {
  critical: '#e74c3c',
  high:     '#e67e22',
  medium:   '#f1c40f',
  low:      '#27ae60',
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

const BEARING_LABELS = { 0:'N', 45:'NE', 90:'E', 135:'SE', 180:'S', 225:'SW', 270:'W', 315:'NW' };

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
}

function popupHtml(props) {
  if (!props) return '<div class="popup-title">Brak danych</div>';
  const rows = Object.entries(props)
    .map(([k, v]) => `<div class="popup-row">${k}: <span>${v}</span></div>`)
    .join('');
  return `<div class="popup-title">${props.name || props.description || 'Obiekt'}</div>${rows}`;
}

function bearingLabel(deg) {
  const nearest = Object.keys(BEARING_LABELS).reduce((a, b) =>
    Math.abs(b - deg) < Math.abs(a - deg) ? b : a
  );
  return `${deg} (${BEARING_LABELS[nearest] || '—'})`;
}

// ── Layer rendering ───────────────────────────────────────────────────────────

function styleForFeature(feature) {
  const { type, severity } = feature.properties ?? {};
  if (type === 'voivodeship') return { color: '#2980b9', weight: 2, fillColor: '#1a3a5c', fillOpacity: 0.08 };
  if (type === 'threat_zone') return { color: '#e74c3c', weight: 2, fillColor: '#e74c3c', fillOpacity: 0.15 };
  const color = SEVERITY_COLOR[severity] || '#5d7a9a';
  return { color, weight: 2, fillColor: color, fillOpacity: 0.2 };
}

function pointToLayer(feature, latlng) {
  const { type, severity, category } = feature.properties ?? {};

  if (type === 'powiat') {
    return L.circleMarker(latlng, { radius: 3, color: '#2980b9', fillColor: '#2980b9', fillOpacity: 0.6, weight: 1 });
  }

  const color = SEVERITY_COLOR[severity] || '#5d7a9a';
  const icon  = CATEGORY_ICON[category]  || '📍';
  return L.marker(latlng, {
    icon: L.divIcon({
      html: `<div style="font-size:1.4rem;line-height:1;filter:drop-shadow(0 1px 3px rgba(0,0,0,.7))">${icon}</div>`,
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
        layer.bindPopup(popupHtml(feature.properties), { maxWidth: 280 });
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
  if (!layers.length) {
    list.innerHTML = '<div class="empty-state">Brak warstw</div>';
    return;
  }

  list.innerHTML = layers.map(layer => `
    <label class="layer-item">
      <input type="checkbox" id="toggle-${layer.layer_id}" ${layerEnabled[layer.layer_id] ? 'checked' : ''} />
      <span>${layer.name}</span>
      <span class="layer-badge">${layer.data_type}</span>
    </label>
  `).join('');

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
  const list = document.getElementById('event-list');
  if (!events.length) {
    list.innerHTML = '<div class="empty-state">Brak zdarzeń</div>';
    return;
  }

  list.innerHTML = events.map(ev => `
    <div class="event-card severity-${ev.severity}" data-lat="${ev.latitude}" data-lon="${ev.longitude}">
      <div class="event-title">${CATEGORY_ICON[ev.category] || '⚠️'} ${ev.description}</div>
      <div class="event-meta">${ev.category} · ${ev.severity} · ${formatTime(ev.time)}</div>
    </div>
  `).join('');

  list.querySelectorAll('.event-card').forEach(card => {
    card.addEventListener('click', () => {
      const lat = parseFloat(card.dataset.lat);
      const lon = parseFloat(card.dataset.lon);
      if (lat && lon) map.setView([lat, lon], 12);
    });
  });

  document.getElementById('event-count').textContent = `${events.length} zdarzeń`;
}

function filterEventsByPowiat(name) {
  // Placeholder — Phase 5
  console.log('Filter by powiat:', name);
}

function renderEventMarkers(events) {
  if (!layerGroups['__events__']) {
    layerGroups['__events__'] = L.layerGroup().addTo(map);
  }
  layerGroups['__events__'].clearLayers();

  events.forEach(ev => {
    if (!ev.latitude || !ev.longitude) return;
    const icon  = CATEGORY_ICON[ev.category]  || '⚠️';
    const color = SEVERITY_COLOR[ev.severity] || '#5d7a9a';
    L.marker([ev.latitude, ev.longitude], {
      icon: L.divIcon({
        html: `<div style="font-size:1.6rem;filter:drop-shadow(0 1px 4px rgba(0,0,0,.8))">${icon}</div>`,
        iconSize: [28, 28], iconAnchor: [14, 14], className: '',
      }),
    })
      .bindPopup(`
        <div class="popup-title">${icon} ${ev.description}</div>
        <div class="popup-row">Kategoria: <span>${ev.category}</span></div>
        <div class="popup-row">Powaga: <span style="color:${color}">${ev.severity}</span></div>
        <div class="popup-row">Status: <span>${ev.status}</span></div>
        <div class="popup-row">Czas: <span>${formatTime(ev.time)}</span></div>
        <div class="popup-row">Źródło: <span>${ev.source}</span></div>
      `)
      .addTo(layerGroups['__events__']);
  });
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

    document.getElementById('last-updated').textContent = `aktualizacja: ${new Date().toLocaleTimeString('pl-PL')}`;
    document.getElementById('status-dot').style.background = '#27ae60';
  } catch (e) {
    console.error('Refresh failed:', e);
    document.getElementById('status-dot').style.background = '#e74c3c';
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
    wind_speed_kmh:      +document.getElementById('rng-wind').value,
    wind_direction_deg:  +document.getElementById('rng-dir').value,
    fire_intensity:      +document.getElementById('rng-int').value,
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

    const dot       = document.getElementById('sim-dot');
    const label     = document.getElementById('sim-label');
    const tickEl    = document.getElementById('sim-tick');
    const alertList = document.getElementById('alert-list');

    if (state.running) {
      dot.className      = 'running';
      label.textContent  = 'AKTYWNA';
      label.style.color  = '#e74c3c';
    } else {
      dot.className      = '';
      label.textContent  = state.tick > 0 ? 'Zatrzymana' : 'Gotowa';
      label.style.color  = '#5d7a9a';
    }

    tickEl.textContent = state.tick > 0 ? `tick ${state.tick}` : '';

    if (state.alerts?.length) {
      alertList.innerHTML = state.alerts.map(a => `
        <div class="alert-item ${a.level}">
          <strong>${a.resource_name}</strong><br/>${a.action}
        </div>
      `).join('');
    } else {
      alertList.innerHTML = state.running
        ? '<div style="font-size:0.65rem;color:#3a4f6a">Brak zagrożonych obiektów</div>'
        : '';
    }
  } catch (e) {
    console.warn('Sim state fetch failed:', e);
  }
}

// ── Boot ──────────────────────────────────────────────────────────────────────

refresh();
updateSimState();
setInterval(refresh, 30_000);
setInterval(updateSimState, 10_000);
