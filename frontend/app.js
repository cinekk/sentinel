const API = '';  // same origin

// ── Tab-aware layer rules ─────────────────────────────────────────────────────
// show: enable these layers when the tab becomes active
// hide: disable these layers when the tab becomes active (and re-enable on leave)
const TAB_LAYER_RULES = {
  flood: {
    show: ['hospitals-status', 'gauges', 'flood_zones', 'events'],
    hide: ['hospitals'],
  },
  // Leaving flood tab restores the base hospitals layer
};

function applyTabLayerRules(tab) {
  // Hide layers owned by OTHER tabs (restore base layer when leaving flood)
  Object.entries(TAB_LAYER_RULES).forEach(([ruleTab, rules]) => {
    if (ruleTab === tab) return;
    (rules.hide || []).forEach(id => {
      // These were hidden by the other tab — restore them
      if (!(id in layerEnabled)) return;
      layerEnabled[id] = true;
      const group = layerGroups[id];
      if (group && !map.hasLayer(group)) group.addTo(map);
      const cb = document.getElementById(`toggle-${id}`);
      if (cb) cb.checked = true;
      // Restore transfer lines with hospitals-status when leaving flood tab
      if (id === 'hospitals-status' && _transferLinesLayer) {
        const showEvacRoutes = (layerConfig['hospitals-status'] || {}).showEvacRoutes !== false;
        if (showEvacRoutes && !map.hasLayer(_transferLinesLayer)) _transferLinesLayer.addTo(map);
      }
    });
  });

  const rules = TAB_LAYER_RULES[tab];
  if (!rules) return;

  // Hide conflicting layers
  (rules.hide || []).forEach(id => {
    layerEnabled[id] = false;
    const group = layerGroups[id];
    if (group && map.hasLayer(group)) map.removeLayer(group);
    const cb = document.getElementById(`toggle-${id}`);
    if (cb) cb.checked = false;
    // Transfer lines are coupled to hospitals-status
    if (id === 'hospitals-status' && _transferLinesLayer && map.hasLayer(_transferLinesLayer)) {
      map.removeLayer(_transferLinesLayer);
    }
  });

  // Enable flood-context layers (show-only — not hidden when leaving tab)
  (rules.show || []).forEach(id => {
    if (layerEnabled[id]) return;  // already on
    layerEnabled[id] = true;
    const group = layerGroups[id];
    if (group && !map.hasLayer(group)) group.addTo(map);
    const cb = document.getElementById(`toggle-${id}`);
    if (cb) cb.checked = true;
    // Transfer lines are coupled to hospitals-status
    if (id === 'hospitals-status' && _transferLinesLayer) {
      const showEvacRoutes = (layerConfig['hospitals-status'] || {}).showEvacRoutes !== false;
      if (showEvacRoutes && !map.hasLayer(_transferLinesLayer)) _transferLinesLayer.addTo(map);
    }
  });
}

// ── Sidebar tabs ──────────────────────────────────────────────────────────────

document.querySelectorAll('.stab').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.stab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.querySelector(`.tab-panel[data-panel="${tab}"]`).classList.add('active');
    applyTabLayerRules(tab);
  });
});

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
const _layerGeoJSON  = {};    // layer_id → raw GeoJSON FeatureCollection (for in-tab reads)
let _fireCrisisId    = null;  // tracks active fire crisis_id for fire tab panel
let allEvents = [];

// ── Change-detection state ────────────────────────────────────────────────────
let _knownEventIds         = null;  // null = first load, skip toasts
let _knownHospitalStatuses = {};    // hospital_id → status string
let _lastFloodTick         = -1;
let _renderedLayerIds      = null;  // CSV of layer_ids from last full panel render
const _eventMarkers        = new Map();  // event id → L.Marker

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
  hospital:       '🏥',
  school:         '🏫',
  social:         '🏠',
  fire_station:   '🚒',
  transport_unit: '🚑',
};

const BEARING_LABELS = { 0:'N', 45:'NE', 90:'E', 135:'SE', 180:'S', 225:'SW', 270:'W', 315:'NW' };

const LAYER_TYPE_CLASS = {
  resources:       'resources',
  events:          'events',
  boundary:        'boundary',
  simulation:      'simulation',
  air_quality:     'air_quality',
  flood_zone:      'flood_zone',
  hospital_status: 'hospital_status',
  gauge:           'gauge',
};

const LAYER_TYPE_COLOR = {
  events:          '#ef4444',  // red
  simulation:      '#f97316',  // orange
  air_quality:     '#10b981',  // emerald
  resources:       '#a855f7',  // purple (fallback)
  flood_zone:      '#0ea5e9',  // sky blue
  boundary:        '#6b7280',  // gray
  threat_zone:     '#f59e0b',  // amber
  hospital_status: '#ef4444',  // rose — flood status
  gauge:           '#38bdf8',  // light blue — river gauges
};

// Per-layer overrides (take priority over data_type color above)
const LAYER_ID_COLOR = {
  hospitals:    '#f43f5e',  // rose   – medical
  schools:      '#eab308',  // yellow – education
  social:       '#14b8a6',  // teal   – social care
  fire_stations:'#f97316',  // orange – fire/rescue
};

const DEFAULT_CLUSTER_COLOR = '#3b82f6';

function clusterColor(layerId, dataType) {
  return LAYER_ID_COLOR[layerId] ?? LAYER_TYPE_COLOR[dataType] ?? DEFAULT_CLUSTER_COLOR;
}

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
  const skip = new Set(['id', 'type', 'sub_schools', 'sub_count']);
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

function hospitalStatusPopupHtml(props, allowedKeys, labelMap) {
  const base = popupHtml(props, allowedKeys, labelMap);
  const hid  = props?.id   || '';
  const name = props?.name || '';
  const gen  = props?.generator_state || 'ok';
  const pct  = props?.personnel_pct  ?? 85;
  return base + `<div style="margin-top:8px;padding-top:6px;border-top:1px solid rgba(255,255,255,.1)">
    <button class="popup-override-btn sim-btn primary"
      data-hid="${escapeHtml(hid)}"
      data-name="${escapeHtml(name)}"
      data-gen="${escapeHtml(gen)}"
      data-pct="${pct}"
      style="width:100%;font-size:.65rem;padding:4px 8px">
      ✏ Override operatora
    </button>
  </div>`;
}

function schoolPopupHtml(props, allowedKeys, labelMap) {
  const base = popupHtml(props, allowedKeys, labelMap);
  if (!props?.sub_schools?.length) return base;
  const items = props.sub_schools
    .map((s) => `<li>${escapeHtml(s.name)}</li>`)
    .join('');
  return `${base}
    <details style="margin-top:6px;font-size:.75rem;opacity:.8">
      <summary style="cursor:pointer">+${props.sub_count} szkół w kompleksie</summary>
      <ul style="margin:4px 0 0 12px;padding:0">${items}</ul>
    </details>`;
}

// ── Override modal ────────────────────────────────────────────────────────────

let _overrideHospitalId = null;

function openOverrideModal(hid, name, gen, pct) {
  _overrideHospitalId = hid;
  document.getElementById('override-modal-name').textContent = name;
  document.getElementById('om-gen').value  = gen || 'ok';
  document.getElementById('om-pct').value  = pct ?? 85;
  document.getElementById('om-road').checked = false;
  document.getElementById('override-modal').style.display = 'flex';
}

function closeOverrideModal() {
  document.getElementById('override-modal').style.display = 'none';
  _overrideHospitalId = null;
}

document.getElementById('override-modal-close').addEventListener('click', closeOverrideModal);
document.getElementById('override-modal-cancel').addEventListener('click', closeOverrideModal);
document.getElementById('override-modal').addEventListener('click', e => {
  if (e.target === e.currentTarget) closeOverrideModal();
});

document.getElementById('override-modal-apply').addEventListener('click', async () => {
  if (!_overrideHospitalId) return;
  const gen  = document.getElementById('om-gen').value;
  const pct  = parseInt(document.getElementById('om-pct').value ?? '85');
  const road = document.getElementById('om-road').checked;
  const btn  = document.getElementById('override-modal-apply');
  btn.disabled = true; btn.textContent = '…';
  try {
    const res = await fetch(`${API}/api/hospitals/${_overrideHospitalId}/override`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ generator_state: gen, personnel_pct: pct, road_cut: road }),
    });
    if (res.ok) {
      showToast(`Override zastosowany: ${document.getElementById('override-modal-name').textContent}`, 'success', '🏥 Operator');
      closeOverrideModal();
      map.closePopup();
      await refresh();
    } else {
      showToast('Błąd zapisu override', 'warning', '🏥 Operator');
    }
  } catch (e) {
    showToast('Błąd połączenia', 'warning', '🏥 Operator');
  } finally {
    btn.disabled = false; btn.textContent = 'Zastosuj';
  }
});

// Attach override button handler when any popup opens
map.on('popupopen', e => {
  const btn = e.popup.getElement()?.querySelector('.popup-override-btn');
  if (!btn) return;
  btn.addEventListener('click', () => {
    openOverrideModal(btn.dataset.hid, btn.dataset.name, btn.dataset.gen, +btn.dataset.pct);
  });
});

// ── Cluster icon factory ──────────────────────────────────────────────────────

function makeClusterIconFactory(color) {
  const c = color || DEFAULT_CLUSTER_COLOR;
  return function(cluster) {
    const count = cluster.getChildCount();
    const size  = count < 10 ? 32 : count < 100 ? 38 : 44;
    return L.divIcon({
      html: `<div class="cluster-icon" style="width:${size}px;height:${size}px;--cc:${c};box-shadow:0 0 10px ${c}66,inset 0 0 6px ${c}20">${count}</div>`,
      className: '',
      iconSize: L.point(size, size),
      iconAnchor: L.point(size / 2, size / 2),
    });
  };
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

  // Hospital flood status markers — colored circle with 🏥
  if (type === 'hospital_status') {
    const color = feature.properties?.marker_color || '#6b7280';
    const pulse = feature.properties?.status === 'evacuate';
    const markerClass = `map-marker-wrap${pulse ? ' marker-pulse' : ''}`;
    return L.marker(latlng, {
      icon: L.divIcon({
        html: `<div class="${markerClass}" style="background:${color}33;border:2.5px solid ${color};border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;font-size:1.15rem;box-shadow:0 0 10px ${color}66,0 2px 8px rgba(0,0,0,.9)">🏥</div>`,
        iconSize: [36, 36], iconAnchor: [18, 18], className: '',
      }),
    });
  }

  // River gauge markers — colored dot
  if (type === 'gauge') {
    const color = feature.properties?.marker_color || '#38bdf8';
    const pulse = feature.properties?.alert_level === 'alarm';
    const markerClass = `map-marker-wrap${pulse ? ' marker-pulse' : ''}`;
    return L.marker(latlng, {
      icon: L.divIcon({
        html: `<div class="${markerClass}" style="background:${color};border:2px solid ${color}aa;border-radius:50%;width:14px;height:14px;box-shadow:0 0 8px ${color}88"></div>`,
        iconSize: [14, 14], iconAnchor: [7, 7], className: '',
      }),
    });
  }

  const resourceIcon = RESOURCE_ICON[type];
  if (resourceIcon) {
    const cfg = layerId ? (layerConfig[layerId] || {}) : {};
    const propVal = cfg.mainProp != null ? feature.properties?.[cfg.mainProp] : null;
    const bgColor = getColorForValue(propVal, cfg.thresholds);
    const pulse   = bgColor && isLowestBucket(propVal, cfg.thresholds);
    const circleStyle = bgColor
      ? `background:${bgColor};border-radius:50%;width:30px;height:30px;display:flex;align-items:center;justify-content:center;${pulse ? '' : `box-shadow:0 0 8px ${bgColor}88;`}`
      : 'width:30px;height:30px;display:flex;align-items:center;justify-content:center;';
    const markerClass = `map-marker-wrap${pulse ? ' marker-pulse' : ''}`;
    return L.marker(latlng, {
      icon: L.divIcon({
        html: `<div class="${markerClass}" style="${circleStyle}font-size:1.15rem;filter:drop-shadow(0 2px 5px rgba(0,0,0,.9))">${resourceIcon}</div>`,
        iconSize: [30, 30], iconAnchor: [15, 15], className: '',
      }),
    });
  }

  const color = SEVERITY_COLOR[severity] || '#6e92b4';
  const icon  = CATEGORY_ICON[category] || '⚠️';

  // 112 call: investigating = dark red pulsing border; active = severity color ring
  if (type === 'event') {
    const props = feature.properties ?? {};
    const isNoResponse = props.status === 'investigating';
    const ringColor = isNoResponse ? '#ef4444' : (SEVERITY_COLOR[severity] || '#6e92b4');
    const pulse = isNoResponse || severity === 'critical';
    const markerClass = `map-marker-wrap${pulse ? ' marker-pulse' : ''}`;
    const border = `2.5px solid ${ringColor}`;
    return L.marker(latlng, {
      icon: L.divIcon({
        html: `<div class="${markerClass}" style="background:${ringColor}28;border:${border};border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;box-shadow:0 0 8px ${ringColor}55,0 2px 6px rgba(0,0,0,.9)">${icon}</div>`,
        iconSize: [32, 32], iconAnchor: [16, 16], className: '',
      }),
    });
  }

  return L.marker(latlng, {
    icon: L.divIcon({
      html: `<div class="map-marker-wrap" style="width:30px;height:30px;display:flex;align-items:center;justify-content:center;font-size:1.2rem;filter:drop-shadow(0 2px 5px rgba(0,0,0,.9))">${icon}</div>`,
      iconSize: [30, 30], iconAnchor: [15, 15], className: '',
    }),
  });
}

async function fetchAndRenderLayer(id) {
  try {
    const res = await fetch(`${API}/api/layers/${id}/geojson`);
    if (!res.ok) return;
    const data = await res.json();

    const geojson = data;
    _layerGeoJSON[id] = geojson;

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

    const features      = geojson.features ?? [];
    const pointFeatures = features.filter(f => f.geometry?.type === 'Point');
    const otherFeatures = features.filter(f => f.geometry?.type !== 'Point');
    const shouldCluster = pointFeatures.length > 0;

    if (layerGroups[id]) {
      layerGroups[id].clearLayers();
    } else {
      layerGroups[id] = shouldCluster
        ? L.markerClusterGroup({
            chunkedLoading: true,
            maxClusterRadius: 60,
            showCoverageOnHover: false,
            iconCreateFunction: makeClusterIconFactory(clusterColor(id, layerMeta[id]?.data_type)),
          })
        : L.layerGroup();
    }

    if (shouldCluster) {
      // Add each point marker directly so the cluster engine can group them
      for (const feature of pointFeatures) {
        const [lon, lat] = feature.geometry.coordinates;
        const marker = pointToLayer(feature, L.latLng(lat, lon), id);
        if (!marker) continue;
        const cfg     = layerConfig[id] || {};
        const allowed = cfg.popupProps?.length ? cfg.popupProps : null;
        const isHosp  = layerMeta[id]?.data_type === 'hospital_status';
        const isSchool = feature.properties?.type === 'school';
        const html    = isHosp
          ? hospitalStatusPopupHtml(feature.properties, allowed, layerLabelMaps[id])
          : isSchool
            ? schoolPopupHtml(feature.properties, allowed, layerLabelMaps[id])
            : popupHtml(feature.properties, allowed, layerLabelMaps[id]);
        marker.bindPopup(html, { maxWidth: 300 });
        if (feature.properties?.type === 'powiat') {
          marker.on('click', () => filterEventsByPowiat(feature.properties.name));
        }
        layerGroups[id].addLayer(marker);
      }
      // Polygons/lines from the same layer go into a plain geoJSON sub-layer
      if (otherFeatures.length > 0) {
        const geoLayer = L.geoJSON({ ...geojson, features: otherFeatures }, {
          style: styleForFeature,
          onEachFeature(feature, layer) {
            const cfg     = layerConfig[id] || {};
            const allowed = cfg.popupProps?.length ? cfg.popupProps : null;
            layer.bindPopup(popupHtml(feature.properties, allowed, layerLabelMaps[id]), { maxWidth: 300 });
          },
        });
        layerGroups[id].addLayer(geoLayer);
      }
    } else {
      const geoLayer = L.geoJSON(geojson, {
        style: styleForFeature,
        pointToLayer: (feature, latlng) => pointToLayer(feature, latlng, id),
        onEachFeature(feature, layer) {
          const cfg     = layerConfig[id] || {};
          const allowed = cfg.popupProps?.length ? cfg.popupProps : null;
          const isHosp  = layerMeta[id]?.data_type === 'hospital_status';
          const isSchool = feature.properties?.type === 'school';
          const html    = isHosp
            ? hospitalStatusPopupHtml(feature.properties, allowed, layerLabelMaps[id])
            : isSchool
              ? schoolPopupHtml(feature.properties, allowed, layerLabelMaps[id])
              : popupHtml(feature.properties, allowed, layerLabelMaps[id]);
          layer.bindPopup(html, { maxWidth: 300 });
          if (feature.properties?.type === 'powiat') {
            layer.on('click', () => filterEventsByPowiat(feature.properties.name));
          }
        },
      });
      layerGroups[id].addLayer(geoLayer);
    }

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
    _renderedLayerIds = '';
    return;
  }

  // If layers haven't changed, just sync checkbox states — don't nuke open config panels
  const newKey = layers.map(l => l.layer_id).join(',');
  if (_renderedLayerIds === newKey) {
    layers.forEach(l => {
      const cb = document.getElementById(`toggle-${l.layer_id}`);
      if (cb) cb.checked = !!layerEnabled[l.layer_id];
    });
    return;
  }
  _renderedLayerIds = newKey;

  list.innerHTML = layers.map(layer => {
    const dotClass  = LAYER_TYPE_CLASS[layer.data_type] || 'boundary';
    const hasConfig = layer.data_type === 'resources' || layer.data_type === 'hospital_status';
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
      // Transfer lines are coupled to the hospitals-status layer
      if (layer.layer_id === 'hospitals-status' && _transferLinesLayer) {
        const showEvacRoutes = (layerConfig['hospitals-status'] || {}).showEvacRoutes !== false;
        if (e.target.checked && showEvacRoutes) { if (!map.hasLayer(_transferLinesLayer)) _transferLinesLayer.addTo(map); }
        else { if (map.hasLayer(_transferLinesLayer)) map.removeLayer(_transferLinesLayer); }
      }
    });

    if (layer.data_type === 'resources' || layer.data_type === 'hospital_status') {
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
    ${id === 'hospitals-status' ? `
    <div class="cfg-section">
      <label class="cfg-prop-check">
        <input type="checkbox" class="cfg-evac-routes" ${cfg.showEvacRoutes !== false ? 'checked' : ''}>
        Pokaż trasy ewakuacyjne na mapie
      </label>
    </div>` : ''}
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

  const newCfg = { mainProp, thresholds, popupProps };
  if (id === 'hospitals-status') {
    newCfg.showEvacRoutes = panelEl.querySelector('.cfg-evac-routes')?.checked ?? true;
    // Apply evacuation routes visibility immediately
    if (_transferLinesLayer) {
      const hostsEnabled = layerEnabled['hospitals-status'] !== false;
      if (hostsEnabled && newCfg.showEvacRoutes) {
        if (!map.hasLayer(_transferLinesLayer)) _transferLinesLayer.addTo(map);
      } else {
        if (map.hasLayer(_transferLinesLayer)) map.removeLayer(_transferLinesLayer);
      }
    }
  }
  saveLayerConfig(id, newCfg);
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
    <div class="event-card severity-${ev.severity}" data-lat="${ev.latitude}" data-lon="${ev.longitude}" data-id="${ev.id}">
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
      const id  = parseInt(card.dataset.id);
      if (!lat || !lon) return;
      const marker = _eventMarkers.get(id);
      if (marker && layerGroups['__events__']) {
        layerGroups['__events__'].zoomToShowLayer(marker, () => marker.openPopup());
      } else {
        map.setView([lat, lon], 13);
      }
    });
  });
}

function filterEventsByPowiat(name) {
  console.log('Filter by powiat:', name);
}

// ── Popup helpers ─────────────────────────────────────────────────────────────

// Find a marker in a layer group by approximate lat/lon and open its popup.
// Uses MarkerClusterGroup.zoomToShowLayer so it unspiderfies clusters first.
function openLayerMarkerPopup(layerId, lat, lon, zoom = 13) {
  const group = layerGroups[layerId];
  if (!group) { map.setView([lat, lon], zoom); return; }

  map.setView([lat, lon], zoom);

  // Short delay to let the map pan settle before looking up layers
  setTimeout(() => {
    const layers = typeof group.getLayers === 'function' ? group.getLayers() : [];
    // For MarkerClusterGroup, getLayers() returns all child layers recursively
    const allLayers = [];
    const collect = (l) => {
      if (typeof l.getLayers === 'function') l.getLayers().forEach(collect);
      else allLayers.push(l);
    };
    layers.forEach(collect);

    let best = null;
    let bestDist = Infinity;
    for (const layer of allLayers) {
      if (!layer.getLatLng) continue;
      const ll = layer.getLatLng();
      const d  = Math.abs(ll.lat - lat) + Math.abs(ll.lng - lon);
      if (d < bestDist) { bestDist = d; best = layer; }
    }

    if (best && bestDist < 0.01) {
      if (typeof group.zoomToShowLayer === 'function') {
        group.zoomToShowLayer(best, () => best.openPopup());
      } else {
        best.openPopup();
      }
    }
  }, 280);
}

function renderEventMarkers(events, newIds = new Set()) {
  if (!layerGroups['__events__']) {
    layerGroups['__events__'] = L.markerClusterGroup({
      chunkedLoading: true,
      maxClusterRadius: 50,
      showCoverageOnHover: false,
      iconCreateFunction: makeClusterIconFactory(LAYER_TYPE_COLOR.events),
    }).addTo(map);
  }

  // Incremental update: remove stale, add new only (avoids flicker on every poll)
  const currentIds = new Set(
    events.filter(e => e.latitude && e.longitude).map(e => e.id)
  );

  for (const [id, marker] of _eventMarkers) {
    if (!currentIds.has(id)) {
      layerGroups['__events__'].removeLayer(marker);
      _eventMarkers.delete(id);
    }
  }

  for (const ev of events) {
    if (!ev.latitude || !ev.longitude) continue;
    if (_eventMarkers.has(ev.id)) continue;  // already on map

    const icon  = CATEGORY_ICON[ev.category] || '⚠️';
    const color = SEVERITY_COLOR[ev.severity] || '#6e92b4';
    const isNew = newIds.has(ev.id);
    const isCrit = ev.severity === 'critical' || ev.severity === 'high';
    const animClass = isNew ? (isCrit ? ' marker-new-ring' : ' marker-new') : '';

    const marker = L.marker([ev.latitude, ev.longitude], {
      icon: L.divIcon({
        html: `<div class="map-marker-wrap${animClass}" style="background:${color}28;border:2px solid ${color};border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-size:1.1rem;box-shadow:0 0 8px ${color}44,0 1px 6px rgba(0,0,0,.9)">${icon}</div>`,
        iconSize: [32, 32], iconAnchor: [16, 16], className: '',
      }),
    })
      .bindPopup(`
        <div class="popup-title">${icon} ${ev.description}</div>
        <div class="popup-row">Kategoria <span>${ev.category}</span></div>
        <div class="popup-row">Powaga <span style="color:${color}">${ev.severity}</span></div>
        <div class="popup-row">Status <span>${ev.status}</span></div>
        <div class="popup-row">Czas <span>${formatTime(ev.time)}</span></div>
        <div class="popup-row">Źródło <span>${ev.source}</span></div>
      `);

    layerGroups['__events__'].addLayer(marker);
    _eventMarkers.set(ev.id, marker);
  }
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

// ── Toast notification system ─────────────────────────────────────────────────

const TOAST_MAX      = 4;
const TOAST_DURATION = 5500;

function showToast(message, type = 'info', title = null, duration = TOAST_DURATION) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  // Drop oldest toast when at cap
  while (container.children.length >= TOAST_MAX) {
    const oldest = container.firstChild;
    if (oldest) { clearTimeout(oldest._toastTimer); oldest.remove(); }
    else break;
  }

  const iconMap = { info: 'ℹ', warning: '⚠', critical: '⚡', success: '✓' };
  const icon = iconMap[type] || 'ℹ';

  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.innerHTML =
    `<span class="toast-icon">${icon}</span>` +
    `<div class="toast-content">` +
      (title ? `<div class="toast-title">${escapeHtml(title)}</div>` : '') +
      `<div class="toast-msg">${escapeHtml(message)}</div>` +
    `</div>` +
    `<button class="toast-close" title="Zamknij">✕</button>`;

  el.querySelector('.toast-close').addEventListener('click', () => dismissToast(el));
  container.appendChild(el);
  el._toastTimer = setTimeout(() => dismissToast(el), duration);
}

function dismissToast(el) {
  if (!el || !el.parentNode) return;
  clearTimeout(el._toastTimer);
  el.classList.add('toast--out');
  setTimeout(() => el.remove(), 220);
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
      const freshEvents = await eventsRes.json();

      // Detect newly-arrived events (skip on first load to avoid mass toasts)
      let newIds = new Set();
      if (_knownEventIds !== null) {
        newIds = new Set(freshEvents.filter(e => !_knownEventIds.has(e.id)).map(e => e.id));
        const newOnes = freshEvents.filter(e => newIds.has(e.id));
        const toShow  = newOnes.slice(0, 3);
        for (const ev of toShow) {
          const icon = CATEGORY_ICON[ev.category] || '⚠️';
          const t    = ev.severity === 'critical' ? 'critical'
                     : ev.severity === 'high'     ? 'warning' : 'info';
          showToast(ev.description, t, `${icon} Nowe zgłoszenie`);
        }
        if (newOnes.length > 3) {
          showToast(`…i ${newOnes.length - 3} więcej nowych zdarzeń`, 'info');
        }
      }
      _knownEventIds = new Set(freshEvents.map(e => e.id));
      allEvents = freshEvents;
      renderEvents(allEvents);
      renderEventMarkers(allEvents, newIds);
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
    const narrativeEl = document.getElementById('sim-narrative-time');

    const simTabBadge = document.getElementById('sim-tab-badge');
    if (state.running) {
      dot.className      = 'running';
      label.textContent  = 'AKTYWNA';
      label.className    = 'sim-status-label running';
      if (simTabBadge) simTabBadge.style.display = '';
    } else {
      dot.className      = '';
      label.textContent  = state.tick > 0 ? 'ZATRZYMANA' : 'GOTOWA';
      label.className    = 'sim-status-label';
      if (simTabBadge) simTabBadge.style.display = 'none';
    }

    if (narrativeEl) {
      if (state.tick > 0) {
        const min = state.narrative_time_min ?? 0;
        narrativeEl.textContent = `T+${Math.round(min)} min`;
        narrativeEl.style.display = '';
      } else {
        narrativeEl.style.display = 'none';
      }
    }

    _fireCrisisId = state.crisis_id ?? null;
    renderFireImpacts(_fireCrisisId);
    renderFireSensors();
  } catch (e) {
    console.warn('Sim state fetch failed:', e);
  }
}

function renderFireImpacts(crisisId) {
  const list     = document.getElementById('fire-impact-list');
  const evacEl   = document.getElementById('fire-evac-count');
  const warnEl   = document.getElementById('fire-warn-count');
  if (!list) return;

  if (!crisisId) {
    list.innerHTML = '<div class="empty-state">Symulacja nieaktywna</div>';
    if (evacEl) evacEl.style.display = 'none';
    if (warnEl) warnEl.style.display = 'none';
    return;
  }

  const fireImpacts = (_lastAlerts || []).filter(a => a.crisis_id === crisisId);
  if (!fireImpacts.length) {
    list.innerHTML = '<div class="empty-state">Brak obiektów w strefie</div>';
    if (evacEl) evacEl.style.display = 'none';
    if (warnEl) warnEl.style.display = 'none';
    return;
  }

  const evac = fireImpacts.filter(a => a.level === 'inside');
  const warn = fireImpacts.filter(a => a.level === 'approaching');

  if (evacEl) {
    evacEl.textContent = evac.length;
    evacEl.style.display = evac.length ? '' : 'none';
  }
  if (warnEl) {
    warnEl.textContent = warn.length;
    warnEl.style.display = warn.length ? '' : 'none';
  }

  const sorted = [...evac, ...warn];
  list.innerHTML = sorted.map(a => {
    const icon      = resourceTypeIcon(a.resource_name);
    const levelCls  = a.level === 'inside' ? 'fire-impact--evac' : 'fire-impact--warn';
    const tag       = a.level === 'inside' ? 'EWAKUACJA' : 'ZAGROŻENIE';
    const dist      = a.distance_km != null ? `${a.distance_km.toFixed(1)} km` : '';
    return `
      <div class="fire-impact-row ${levelCls}">
        <span class="fire-impact-icon">${icon}</span>
        <span class="fire-impact-name">${a.resource_name}</span>
        <span class="fire-impact-tag">${tag}</span>
        <span class="fire-impact-dist">${dist}</span>
      </div>`;
  }).join('');
}

function renderFireSensors() {
  const table = document.getElementById('fire-sensor-table');
  if (!table) return;

  const layer = _layerGeoJSON?.simulation_threat;
  const sensors = layer?.features?.filter(f => f.properties?.type === 'sensor') ?? [];

  if (!sensors.length) {
    table.innerHTML = '<div class="empty-state">Symulacja nieaktywna</div>';
    return;
  }

  table.innerHTML = sensors.map(f => {
    const p    = f.properties;
    const val  = p.pm25 ?? 0;
    const cls  = val > 250 ? 'pm-crit' : val > 150 ? 'pm-high' : val > 50 ? 'pm-med' : 'pm-ok';
    const bars = val > 250 ? '████' : val > 150 ? '███' : val > 50 ? '██' : '█';
    return `
      <div class="fire-sensor-row">
        <span class="fire-sensor-name">${p.name}</span>
        <span class="fire-sensor-val ${cls}">${Math.round(val)}</span>
        <span class="fire-sensor-bar ${cls}">${bars}</span>
      </div>`;
  }).join('');
}

async function pollAlerts() {
  try {
    const res = await fetch(`${API}/api/v1/crisis/affected`);
    if (!res.ok) return;
    const alerts = await res.json();
    renderAlertHud(alerts);
    renderFireImpacts(_fireCrisisId);
  } catch (e) {
    console.warn('Alert poll failed:', e);
  }
}

document.getElementById('btn-clear-events').addEventListener('click', async () => {
  await fetch(`${API}/api/events`, { method: 'DELETE' });
  allEvents = [];
  _knownEventIds = new Set();
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

// ── Flood Dashboard (Zestaw A) ─────────────────────────────────────────────────

const FLOOD_STATUS_LABEL = { operational: 'Sprawny', at_risk: 'Zagrożony', evacuate: 'Ewakuacja' };
const FLOOD_STATUS_COLOR = { operational: '#22c55e', at_risk: '#f59e0b', evacuate: '#ef4444' };
const GAUGE_ALERT_COLOR  = { normal: '#22c55e', warning: '#f59e0b', alarm: '#ef4444', unknown: '#6b7280' };
const GAUGE_ALERT_LABEL  = { normal: 'Normal', warning: 'Ostrzeżenie', alarm: 'ALARM', unknown: '—' };

let _floodHospitals = [];
let _transferLinesLayer = null;

function _lineBearing(lat1, lon1, lat2, lon2) {
  const toRad = d => d * Math.PI / 180;
  const dLon = toRad(lon2 - lon1);
  const y = Math.sin(dLon) * Math.cos(toRad(lat2));
  const x = Math.cos(toRad(lat1)) * Math.sin(toRad(lat2))
          - Math.sin(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.cos(dLon);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

async function loadTransferLines() {
  try {
    const res = await fetch(`${API}/api/flood/transfer-recommendations`);
    if (!res.ok) return;
    const recs = await res.json();

    if (_transferLinesLayer) {
      _transferLinesLayer.clearLayers();
    } else {
      _transferLinesLayer = L.layerGroup();
    }

    for (const rec of recs) {
      for (const tgt of rec.targets) {
        // Animated dashed line (CSS handles the flow animation via className)
        const line = L.polyline(
          [[rec.from_lat, rec.from_lon], [tgt.lat, tgt.lon]],
          { color: '#f59e0b', weight: 2, dashArray: '8 6', opacity: 0.85,
            className: 'transfer-animated-line' }
        );
        const sorTag = tgt.has_sor ? ' · SOR' : '';
        line.bindTooltip(
          `→ ${tgt.short_name} · ${tgt.distance_km} km · ${tgt.available_beds} łóżek${sorTag}`,
          { sticky: true, className: 'transfer-tooltip' }
        );
        _transferLinesLayer.addLayer(line);

        // Direction arrowhead at midpoint, rotated to bearing
        const midLat = (rec.from_lat + tgt.lat) / 2;
        const midLon = (rec.from_lon + tgt.lon) / 2;
        const b = _lineBearing(rec.from_lat, rec.from_lon, tgt.lat, tgt.lon);
        const arrowIcon = L.divIcon({
          html: `<div style="transform:rotate(${b - 90}deg);transform-origin:center;font-size:11px;color:#f59e0b;line-height:1;text-shadow:0 0 4px #0008">▶</div>`,
          className: '',
          iconSize: [12, 12],
          iconAnchor: [6, 6],
        });
        _transferLinesLayer.addLayer(
          L.marker([midLat, midLon], { icon: arrowIcon, interactive: false })
        );
      }
    }

    // Only show if hospitals-status layer is currently active and evac routes are enabled in config
    const hostsEnabled  = layerEnabled['hospitals-status'] !== false;
    const showEvacRoutes = (layerConfig['hospitals-status'] || {}).showEvacRoutes !== false;
    if (hostsEnabled && showEvacRoutes) {
      if (!map.hasLayer(_transferLinesLayer)) _transferLinesLayer.addTo(map);
    } else {
      if (map.hasLayer(_transferLinesLayer)) map.removeLayer(_transferLinesLayer);
    }
  } catch (e) {
    console.warn('Transfer lines load failed:', e);
  }
}

async function loadFloodAssessment() {
  try {
    const [assessRes, transferRes] = await Promise.all([
      fetch(`${API}/api/flood/assessment`),
      fetch(`${API}/api/flood/transfer-recommendations`),
    ]);
    if (!assessRes.ok) return;
    _floodHospitals = await assessRes.json();

    // Merge transfer targets into each hospital object for the table
    if (transferRes.ok) {
      const recs = await transferRes.json();
      const recMap = {};
      for (const r of recs) recMap[r.from_hospital_id] = r.targets;
      for (const h of _floodHospitals) {
        h.transfer_targets = recMap[h.hospital_id] || [];
      }
    }

    renderHospitalStatusTable(_floodHospitals);
    updateFloodBadge(_floodHospitals);
  } catch (e) {
    console.warn('Flood assessment failed:', e);
  }
}

async function loadGauges() {
  try {
    const res = await fetch(`${API}/api/layers/gauges/geojson`);
    if (!res.ok) return;
    const fc = await res.json();
    const gauges = (fc.features || []).map(f => ({
      id: f.properties.id,
      name: f.properties.station_name,
      river: f.properties.river,
      alert_level: f.properties.alert_level,
      level_cm: f.properties.level_cm,
      warning_cm: f.properties.warning_cm,
      alarm_cm: f.properties.alarm_cm,
      overridden: f.properties.overridden,
    }));
    renderGaugePanel(gauges);
  } catch (e) {
    console.warn('Gauges load failed:', e);
  }
}

async function loadFloodSummary() {
  const spinner = document.getElementById('flood-summary-spinner');
  const narrative = document.getElementById('flood-ai-narrative');
  const lists = document.getElementById('flood-ai-lists');
  if (spinner) spinner.style.display = '';
  try {
    const res = await fetch(`${API}/api/flood/summary`);
    if (!res.ok) { narrative.textContent = 'Błąd pobierania oceny AI.'; return; }
    const data = await res.json();
    narrative.textContent = data.narrative || '—';

    const sections = [
      { key: 'evacuate',   label: 'Do ewakuacji',       color: '#ef4444' },
      { key: 'at_risk',    label: 'Zagrożone',           color: '#f59e0b' },
      { key: 'redirect_to',label: 'Przyjmują pacjentów', color: '#22c55e' },
    ];
    lists.innerHTML = sections.map(s => {
      const items = data[s.key] || [];
      if (!items.length) return '';
      return `<div class="flood-ai-section">
        <div class="flood-ai-label" style="color:${s.color}">${s.label}</div>
        <ul class="flood-ai-ul">${items.map(i => `<li>${escapeHtml(i)}</li>`).join('')}</ul>
      </div>`;
    }).join('');
  } catch (e) {
    narrative.textContent = 'Brak połączenia z AI.';
    console.warn('Flood summary failed:', e);
  } finally {
    if (spinner) spinner.style.display = 'none';
  }
}

function renderHospitalStatusTable(hospitals) {
  const el = document.getElementById('flood-hospital-table');
  const counts = document.getElementById('flood-hosp-counts');
  if (!el) return;

  // Detect status changes and fire toasts
  for (const h of hospitals) {
    const prev = _knownHospitalStatuses[h.hospital_id];
    if (prev !== undefined && prev !== h.status) {
      if (h.status === 'evacuate') {
        showToast(`${h.name} — zarządzono ewakuację pacjentów`, 'critical', '🏥 Zmiana statusu szpitala', 8000);
      } else if (h.status === 'at_risk') {
        showToast(`${h.name} — szpital w strefie zagrożenia`, 'warning', '🏥 Zmiana statusu szpitala');
      } else if (h.status === 'operational') {
        showToast(`${h.name} — status przywrócony`, 'success', '🏥 Zmiana statusu szpitala');
      }
    }
    _knownHospitalStatuses[h.hospital_id] = h.status;
  }

  const evac = hospitals.filter(h => h.status === 'evacuate').length;
  const risk = hospitals.filter(h => h.status === 'at_risk').length;
  const ok   = hospitals.filter(h => h.status === 'operational').length;
  if (counts) counts.innerHTML =
    `<span style="color:#ef4444">${evac} ewakuacja</span> · ` +
    `<span style="color:#f59e0b">${risk} zagrożone</span> · ` +
    `<span style="color:#22c55e">${ok} sprawne</span>`;

  if (!hospitals.length) { el.innerHTML = '<div class="empty-state">Brak danych</div>'; return; }

  // Sort: evacuate first, then at_risk, then operational; within same status by name
  const sorted = [...hospitals].sort((a, b) => {
    const order = { evacuate: 0, at_risk: 1, operational: 2 };
    const od = (order[a.status] ?? 3) - (order[b.status] ?? 3);
    return od !== 0 ? od : a.name.localeCompare(b.name, 'pl');
  });

  el.innerHTML = sorted.map(h => {
    const color = FLOOD_STATUS_COLOR[h.status] || '#6b7280';
    const label = FLOOD_STATUS_LABEL[h.status] || h.status;
    const genIcon = { ok: '⚡', degraded: '⚠️', offline: '🔴' }[h.generator_state] || '';
    const sorTag = h.sor ? '<span class="flood-tag">SOR</span>' : '';
    const receiveTag = h.can_receive ? '<span class="flood-tag flood-tag--green">Przyjmuje</span>' : '';
    const gaugeInfo = h.nearest_gauge_level
      ? `<span style="color:${GAUGE_ALERT_COLOR[h.nearest_gauge_level] || '#6b7280'};font-size:.65rem">${GAUGE_ALERT_LABEL[h.nearest_gauge_level]}</span>`
      : '';
    const factors = (h.risk_factors || []).length
      ? `<div class="flood-risk-factors">${h.risk_factors.map(f => `<span class="flood-factor">${escapeHtml(f)}</span>`).join('')}</div>`
      : '';
    // Small capacity warning: flag hospitals with very few beds — critical for patient routing
    const isSmallCapacity = h.beds != null && h.beds < 80;
    const bedsColor = isSmallCapacity ? '#f59e0b' : 'inherit';
    const bedsTitle = isSmallCapacity ? ' title="Mała pojemność — ograniczone możliwości przyjęcia pacjentów"' : '';
    const transferRow = (h.transfer_targets && h.transfer_targets.length)
      ? `<div class="flood-transfer-row">
           <span class="flood-transfer-label">↪ Przekieruj do:</span>
           ${h.transfer_targets.map(t => `<span class="flood-tag flood-tag--amber">${escapeHtml(t.short_name)}</span>`).join('')}
         </div>`
      : '';
    return `
      <div class="flood-hosp-row" data-lat="${h.lat}" data-lon="${h.lon}" data-id="${h.hospital_id}">
        <div class="flood-hosp-top">
          <span class="flood-status-badge" style="--badge-color:${color}">${label}</span>
          <span class="flood-hosp-name">${escapeHtml(h.name)}</span>
        </div>
        <div class="flood-hosp-meta">
          ${sorTag}${receiveTag}
          <span class="flood-meta-item">${genIcon} gen: ${h.generator_state}</span>
          <span class="flood-meta-item">👤 ${h.personnel_pct}%</span>
          <span class="flood-meta-item" style="color:${bedsColor}"${bedsTitle}>🛏 ${h.beds}${isSmallCapacity ? ' ⚠' : ''}</span>
          ${h.demand_112 ? `<span class="flood-meta-item">🚑 112: ${h.demand_112}</span>` : ''}
          ${gaugeInfo}
        </div>
        ${factors}
        ${transferRow}
      </div>
    `;
  }).join('');

  el.querySelectorAll('.flood-hosp-row').forEach(row => {
    row.addEventListener('click', () => {
      const lat = parseFloat(row.dataset.lat);
      const lon = parseFloat(row.dataset.lon);
      if (!lat || !lon) return;
      openLayerMarkerPopup('hospitals-status', lat, lon, 14);
    });
  });
}

function renderGaugePanel(gauges) {
  const el = document.getElementById('flood-gauge-list');
  const badge = document.getElementById('flood-gauge-alarm-count');
  if (!el) return;

  const alarmCount = gauges.filter(g => g.alert_level === 'alarm').length;
  const warnCount  = gauges.filter(g => g.alert_level === 'warning').length;
  if (badge) badge.textContent = alarmCount > 0 ? `${alarmCount} alarm` : (warnCount > 0 ? `${warnCount} ostrzeż.` : '—');
  if (badge) badge.style.background = alarmCount > 0 ? '#ef4444' : (warnCount > 0 ? '#f59e0b' : '#22c55e');

  // Show top 8: alarm first, then warning, then normal
  const sorted = [...gauges].sort((a, b) => {
    const order = { alarm: 0, warning: 1, normal: 2, unknown: 3 };
    return (order[a.alert_level] ?? 4) - (order[b.alert_level] ?? 4);
  }).slice(0, 8);

  if (!sorted.length) { el.innerHTML = '<div class="empty-state">Brak danych o poziomach rzek</div>'; return; }

  el.innerHTML = sorted.map(g => {
    const color = GAUGE_ALERT_COLOR[g.alert_level] || '#6b7280';
    const label = GAUGE_ALERT_LABEL[g.alert_level] || '—';
    const pct = (g.alarm_cm && g.level_cm != null)
      ? Math.min(100, Math.round((g.level_cm / g.alarm_cm) * 100))
      : null;
    const overTag = g.overridden ? ' <span class="flood-tag" style="color:#f59e0b">[demo]</span>' : '';
    return `
      <div class="flood-gauge-row">
        <div class="flood-gauge-top">
          <span class="flood-gauge-dot" style="background:${color};box-shadow:0 0 6px ${color}"></span>
          <span class="flood-gauge-name">${escapeHtml(g.name)}${overTag}</span>
          <span class="flood-gauge-river">${escapeHtml(g.river)}</span>
          <span class="flood-gauge-level" style="color:${color}">${label}</span>
        </div>
        ${pct != null ? `<div class="flood-gauge-bar-bg"><div class="flood-gauge-bar" style="width:${pct}%;background:${color}"></div></div>` : ''}
      </div>
    `;
  }).join('');
}

function updateFloodBadge(hospitals) {
  const badge = document.getElementById('flood-evac-badge');
  if (!badge) return;
  const evac = hospitals.filter(h => h.status === 'evacuate').length;
  if (evac > 0) {
    badge.textContent = evac;
    badge.style.display = '';
    badge.style.background = '#ef4444';
  } else {
    const risk = hospitals.filter(h => h.status === 'at_risk').length;
    if (risk > 0) {
      badge.textContent = risk;
      badge.style.display = '';
      badge.style.background = '#f59e0b';
    } else {
      badge.style.display = 'none';
    }
  }
}


// ── Flood scenario simulation ─────────────────────────────────────────────────

let _floodSimRunning = false;
let _floodSimInterval = null;

async function fetchFloodScenarioState() {
  try {
    const res = await fetch(`${API}/api/flood-scenario/state`);
    if (!res.ok) return null;
    return await res.json();
  } catch { return null; }
}

function updateFloodSimUI(state) {
  if (!state) return;
  const running = state.running;
  _floodSimRunning = running;

  _lastFloodTick = running ? state.tick : -1;

  const startBtn  = document.getElementById('flood-sim-start');
  const stopBtn   = document.getElementById('flood-sim-stop');
  const timeEl    = document.getElementById('flood-sim-time');
  const progressEl = document.getElementById('flood-sim-progress');
  const barEl     = document.getElementById('flood-sim-bar');
  const tickLabel = document.getElementById('flood-sim-tick-label');

  if (startBtn) startBtn.style.display = running ? 'none' : '';
  if (stopBtn)  stopBtn.style.display  = running ? ''     : 'none';

  if (running) {
    if (timeEl)  { timeEl.textContent = state.narrative_label; timeEl.style.display = ''; }
    if (progressEl) progressEl.style.display = '';
    if (barEl)   barEl.style.width = `${Math.round((state.tick / state.max_tick) * 100)}%`;
    if (tickLabel) tickLabel.textContent = `Tick ${state.tick} / ${state.max_tick}`;
  } else {
    if (timeEl)  timeEl.style.display = 'none';
    if (progressEl) { progressEl.style.display = state.tick > 0 ? '' : 'none'; }
    if (barEl && state.tick > 0) barEl.style.width = `${Math.round((state.tick / state.max_tick) * 100)}%`;
    if (tickLabel && state.tick > 0) tickLabel.textContent = `Tick ${state.tick} / ${state.max_tick}`;
  }
}

async function pollFloodScenario() {
  const state = await fetchFloodScenarioState();
  updateFloodSimUI(state);
  if (state?.running) {
    await refreshFloodTab();
  }
}

function startFloodSimInterval() {
  if (_floodSimInterval) return;
  _floodSimInterval = setInterval(pollFloodScenario, 15_000);
}

function stopFloodSimInterval() {
  if (_floodSimInterval) { clearInterval(_floodSimInterval); _floodSimInterval = null; }
}

function initFloodDashboard() {
  const refreshBtn = document.getElementById('flood-summary-refresh');
  if (refreshBtn) refreshBtn.addEventListener('click', async () => {
    await loadFloodAssessment();
    await loadGauges();
    await loadFloodSummary();
  });

  // Scenario control buttons
  const startBtn = document.getElementById('flood-sim-start');
  if (startBtn) startBtn.addEventListener('click', async () => {
    const interval = parseInt(document.getElementById('flood-sim-interval')?.value ?? '15');
    await fetch(`${API}/api/flood-scenario/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tick_interval_seconds: interval }),
    });
    startFloodSimInterval();
    const state = await fetchFloodScenarioState();
    updateFloodSimUI(state);
    await refreshFloodTab();
  });

  const stopBtn = document.getElementById('flood-sim-stop');
  if (stopBtn) stopBtn.addEventListener('click', async () => {
    await fetch(`${API}/api/flood-scenario/stop`, { method: 'POST' });
    stopFloodSimInterval();
    const state = await fetchFloodScenarioState();
    updateFloodSimUI(state);
    await refreshFloodTab();
  });

  const resetBtn = document.getElementById('flood-sim-reset');
  if (resetBtn) resetBtn.addEventListener('click', async () => {
    await fetch(`${API}/api/flood-scenario/reset`, { method: 'POST' });
    stopFloodSimInterval();
    const state = await fetchFloodScenarioState();
    updateFloodSimUI(state);
    await refreshFloodTab();
  });

}

// ── Evacuation dispatch ───────────────────────────────────────────────────────

const EVAC_PRIORITY_COLOR = {
  NATYCHMIASTOWE: 'var(--red)',
  PILNE:          'var(--amber)',
  PLANOWE:        'var(--blue)',
};

const EVAC_TYPE_LABEL = {
  S: 'Specjalistyczny ZRM',
  N: 'Neonatologiczny',
  P: 'Podstawowy ZRM',
  T: 'Transport san.',
};

const EVAC_CATEGORY_LABEL = {
  icu:        'OIT / OIOM',
  ward:       'Oddział ogólny',
  ambulatory: 'Ambulatoryjni',
};

function renderEvacUnitRow(unit) {
  const statusClass = `evac-unit-status--${unit.status}`;
  const typeLabel   = EVAC_TYPE_LABEL[unit.unit_type] || unit.unit_type;
  return `
    <div class="evac-unit-row" title="${escapeHtml(typeLabel)}">
      <span class="evac-type-badge evac-type-${unit.unit_type}">${unit.unit_type}</span>
      <span class="evac-unit-status ${statusClass}"></span>
      <span class="evac-unit-callsign">${escapeHtml(unit.call_sign)}</span>
      <span class="evac-unit-dist">${unit.distance_km} km</span>
      <span class="evac-unit-eta">~${unit.eta_minutes} min</span>
    </div>`;
}

function renderEvacCard(order) {
  const prioClass = `evac-priority--${order.priority}`;
  const transferHtml = order.transfer_target
    ? `<span class="evac-transfer-target">↪ ${escapeHtml(order.transfer_target)}</span>`
    : '';

  const patientRows = order.patient_groups.map(g => `
    <tr>
      <td>${escapeHtml(EVAC_CATEGORY_LABEL[g.category] || g.category)}</td>
      <td style="text-align:right">${g.count}</td>
      <td style="text-align:center"><span class="evac-type-badge evac-type-${g.required_unit_type}">${g.required_unit_type}</span></td>
      <td style="text-align:right">${g.units_needed} jedn.</td>
    </tr>`).join('');

  const unitRows = order.assigned_units.slice(0, 8).map(renderEvacUnitRow).join('');
  const moreUnits = order.assigned_units.length > 8
    ? `<div class="evac-unit-row" style="color:var(--text-mid)">…+${order.assigned_units.length - 8} więcej</div>` : '';

  const deficitHtml = order.deficit > 0
    ? `<div class="evac-deficit">⚠ Niedobór: brakuje <strong>${order.deficit}</strong> jednostek</div>` : '';

  return `
    <div class="evac-card">
      <div class="evac-card-header">
        <span class="evac-priority ${prioClass}">${escapeHtml(order.priority)}</span>
        <span class="evac-hosp-name">${escapeHtml(order.name)}</span>
        ${transferHtml}
      </div>
      <div class="evac-body">
        <table class="evac-patient-table">
          <thead><tr>
            <th>Kategoria</th><th style="text-align:right">Pacjenci</th>
            <th style="text-align:center">Typ</th><th style="text-align:right">Jedn.</th>
          </tr></thead>
          <tbody>${patientRows}</tbody>
        </table>
        ${order.assigned_units.length ? `
        <div>
          <div class="evac-units-header">Przydzielone jednostki (${order.units_available}/${order.units_needed})</div>
          <div class="evac-units-list">${unitRows}${moreUnits}</div>
        </div>` : ''}
        ${deficitHtml}
      </div>
    </div>`;
}

async function loadEvacuationDispatch() {
  const el    = document.getElementById('flood-evac-list');
  const badge = document.getElementById('flood-evac-unit-count');
  if (!el) return;

  try {
    const res    = await fetch(`${API}/api/flood/evacuation-dispatch`);
    const orders = await res.json();

    if (!orders.length) {
      el.innerHTML = '<div class="empty-state">Brak szpitali wymagających ewakuacji</div>';
      if (badge) badge.textContent = '';
      return;
    }

    el.innerHTML = orders.map(renderEvacCard).join('');

    const totalPatients = orders.reduce((s, o) =>
      s + o.patient_groups.reduce((ps, g) => ps + g.count, 0), 0);
    const totalDeficit  = orders.reduce((s, o) => s + o.deficit, 0);
    if (badge) {
      badge.textContent = `${orders.length} szp. · ${totalPatients} pac.` +
        (totalDeficit > 0 ? ` · ⚠ ${totalDeficit} brak` : '');
    }
  } catch (e) {
    console.warn('Evacuation dispatch load failed:', e);
  }
}

async function refreshFloodTab() {
  await loadFloodAssessment();
  await loadGauges();
  await loadTransferLines();
  await fetchAndRenderLayer('hospitals-status');
  await loadEvacuationDispatch();
}

// ── Demo controller ───────────────────────────────────────────────────────────

const DemoController = (() => {
  const STEPS = [
    // { delay_ms, fn }  — delays are relative to previous step
    { delay: 0,    fn: '_switchToFlood'   },
    { delay: 500,  fn: '_startSim'        },
    { delay: 800,  fn: '_speakAlert1'     },
    { delay: 1500, fn: '_panMap'          },
    { delay: 6000, fn: '_calloutGauges'   },
    { delay: 10000,fn: '_calloutHospitals'},
    { delay: 10000,fn: '_calloutEvac'     },
    { delay: 12000,fn: '_finish'          },
  ];

  let _timers = [];
  let _active  = false;
  let _countdownTimer = null;
  let _highlightEl = null;

  function _schedule(steps) {
    let elapsed = 0;
    for (const s of steps) {
      elapsed += s.delay;
      _timers.push(setTimeout(() => { if (_active) _ctrl[s.fn]?.(); }, elapsed));
    }
  }

  function _clearAll() {
    _timers.forEach(clearTimeout);
    _timers = [];
    if (_countdownTimer) { clearInterval(_countdownTimer); _countdownTimer = null; }
    _clearHighlight();
    _hideCallout();
  }

  function _clearHighlight() {
    if (_highlightEl) { _highlightEl.classList.remove('demo-highlight'); _highlightEl = null; }
  }

  function _highlight(selector) {
    _clearHighlight();
    const el = document.querySelector(selector);
    if (el) { el.classList.add('demo-highlight'); _highlightEl = el; }
  }

  function _showCallout(label, text) {
    const c  = document.getElementById('demo-callout');
    const lb = document.getElementById('demo-callout-label');
    const tx = document.getElementById('demo-callout-text');
    if (!c) return;
    lb.textContent = label;
    tx.textContent = text;
    c.style.display = 'block';
    // Re-trigger animation
    c.style.animation = 'none';
    c.offsetHeight; // reflow
    c.style.animation = '';
  }

  function _hideCallout() {
    const c = document.getElementById('demo-callout');
    if (c) c.style.display = 'none';
  }

  async function _speak(text) {
    try {
      const res = await fetch(`${API}/api/voice/speak`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) return;
      const { audio_base64 } = await res.json();
      if (!audio_base64) return;
      const bin   = atob(audio_base64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      const url   = URL.createObjectURL(new Blob([bytes], { type: 'audio/mpeg' }));
      new Audio(url).play();
    } catch { /* demo continues silently if TTS fails */ }
  }

  const _ctrl = {
    _switchToFlood() {
      document.querySelector('.stab[data-tab="flood"]')?.click();
    },
    _startSim() {
      fetch(`${API}/api/flood-scenario/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interval_seconds: 8 }),
      }).catch(() => {});
    },
    _speakAlert1() {
      _speak('Uwaga! Poziom wody na Wieprzu przekroczył stan alarmowy. Uruchamiam procedurę monitorowania zagrożenia powodziowego w województwie lubelskim.');
    },
    _panMap() {
      map.flyTo([51.42, 21.97], 10, { animate: true, duration: 2 });
    },
    _calloutGauges() {
      _highlight('#flood-gauge-list');
      _showCallout('Rzeki — poziomy alarmowe',
        'Czujniki IMGW monitorują poziomy wód w czasie rzeczywistym. Kolor czerwony oznacza przekroczenie stanu alarmowego.');
    },
    _calloutHospitals() {
      _speak('Wykryto krytyczne zagrożenie. Szpitale w strefie powodzi wymagają natychmiastowej ewakuacji. Uruchamiam procedurę transportu sanitarnego.');
      _highlight('#flood-hospital-table');
      _showCallout('Status szpitali',
        'Ocena każdego szpitala na podstawie stref ISOK, poziomów rzek i zdarzeń 112. Czerwony = ewakuacja wymagana.');
    },
    _calloutEvac() {
      _speak('Inicjuję protokół ewakuacji medycznej. Przydział jednostek transportu sanitarnego w toku. Oczekiwany czas ewakuacji — czterdzieści pięć minut.');
      _highlight('#flood-evac-list');
      _showCallout('Ewakuacja medyczna',
        'Panel dowodzenia ewakuacją — przydział jednostek T / P / S / N do każdego szpitala z czasem dojazdu i analizą niedoborów.');
    },
    _finish() {
      _clearHighlight();
      _hideCallout();
      _active = false;
      showToast('Demo zakończone — eksploruj aplikację samodzielnie', 'success', '⚡ SENTINEL');
    },
  };

  function showCountdown() {
    if (new URLSearchParams(location.search).has('nodemo')) return;
    const overlay = document.getElementById('demo-overlay');
    const numEl   = document.getElementById('demo-countdown-num');
    if (!overlay || !numEl) return;

    let n = 8;
    numEl.textContent = n;
    overlay.style.display = 'flex';

    _countdownTimer = setInterval(() => {
      n--;
      numEl.textContent = n;
      if (n <= 0) {
        clearInterval(_countdownTimer);
        _countdownTimer = null;
        overlay.style.display = 'none';
        start();
      }
    }, 1000);
  }

  function start() {
    _active = true;
    document.getElementById('demo-overlay').style.display = 'none';
    _schedule(STEPS);
  }

  function skip() {
    _active = false;
    _clearAll();
    document.getElementById('demo-overlay').style.display = 'none';
  }

  // Bind skip button
  document.getElementById('demo-skip-btn')?.addEventListener('click', skip);

  // Auto-trigger
  const params = new URLSearchParams(location.search);
  if (!params.has('nodemo')) {
    if (params.has('demo')) {
      window.addEventListener('load', () => start());
    } else {
      window.addEventListener('load', () => setTimeout(showCountdown, 3000));
    }
  }

  return { start, skip, showCountdown };
})();

// ── Boot ──────────────────────────────────────────────────────────────────────

fetchLayerSchemas();
initChat();
initBriefing();
initFloodDashboard();
refresh();
updateSimState();
update112State();
pollAlerts();
refreshFloodTab();
loadFloodSummary();
// Sync scenario state on load (handles page refresh mid-simulation)
fetchFloodScenarioState().then(state => {
  updateFloodSimUI(state);
  if (state?.running) startFloodSimInterval();
});
setInterval(refresh, 30_000);
setInterval(updateSimState, 10_000);
setInterval(update112State, 15_000);
setInterval(pollAlerts, 5_000);
setInterval(refreshFloodTab, 60_000);
