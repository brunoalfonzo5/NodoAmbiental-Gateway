'use strict';

/*
 * Nodo Ambiental · Interfaz v0.1
 * El frontend consume un contrato JSON estable. La fuente puede ser:
 *   DEMO → ./data/nodos.json
 *   API  → http://127.0.0.1:8000/api/nodos
 * Cuando integremos Python, solo tendremos que implementar ese endpoint.
 */
const CONFIG = Object.freeze({
  demoUrl: './data/nodos.json',
  apiUrl: 'http://127.0.0.1:8000/api/nodos',
  refreshMs: 15000,
});

const state = { mode: 'demo', data: null, selectedId: null, map: null, markers: null, busy: false };
const el = (id) => document.getElementById(id);
const set = (id, value) => { el(id).textContent = String(value); };
const validNumber = (value) => typeof value === 'number' && Number.isFinite(value);
const number = (value, digits = 1) => validNumber(value) ? value.toLocaleString('es-AR', { maximumFractionDigits: digits, minimumFractionDigits: 0 }) : '—';
const dateTime = (value) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('es-AR', { dateStyle: 'short', timeStyle: 'short' });
};
const time = (value) => {
  if (!value) return '—';
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
};
function escapeHTML(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[char]));
}

function showNotice(message, isError = false) {
  const n = el('notice');
  n.textContent = message;
  n.classList.add('show');
  n.classList.toggle('error', isError);
}

function renderPlaceholder() {
  ['temperature','humidity','wind','current-node-name','last-update','nodes-total','nodes-active','gw-status','latest-frame','rssi','snr','node-count','gateway-id'].forEach((id) => set(id, '—'));
  set('risk', 'PENDIENTE'); set('risk-description', 'Índice todavía no implementado');
  set('gateway-text', 'Sin conexión'); set('wind-direction', '—');
  el('gateway-dot').className = 'dot dot-bad';
  el('chart').innerHTML = '<p class="empty-copy">Sin datos para mostrar.</p>';
  el('nodes-body').innerHTML = '<tr><td colspan="5" class="table-placeholder">Sin datos disponibles.</td></tr>';
  if (state.markers) state.markers.clearLayers();
}

function render() {
  if (!state.data) { renderPlaceholder(); return; }
  const { gateway = {}, nodos = [], actualizado } = state.data;
  const selectedNode = nodos.find((n) => n.id === state.selectedId) || nodos[0];
  state.selectedId = selectedNode?.id ?? null;

  set('last-update', `Última actualización: ${dateTime(actualizado)}`);
  set('gateway-id', gateway.id || '—');
  set('gateway-text', gateway.estado === 'online' ? 'Gateway conectado' : 'Gateway sin conexión');
  el('gateway-dot').className = `dot ${gateway.estado === 'online' ? 'dot-good' : 'dot-bad'}`;
  set('nodes-total', nodos.length);
  set('nodes-active', nodos.filter((n) => n.estado === 'online').length);
  set('node-count', `${nodos.length} nodo${nodos.length === 1 ? '' : 's'}`);
  set('gw-status', gateway.estado === 'online' ? 'CONECTADO' : 'DESCONECTADO');
  set('latest-frame', time(gateway.ultima_trama));

  const m = selectedNode?.mediciones || {};
  const stale = selectedNode?.estado !== 'online';
  set('current-node-name', selectedNode?.nombre ?? '—');
  // Una lectura offline es histórica; no se presenta como medición actual.
  set('temperature', stale ? '—' : number(m.temperatura_c));
  set('humidity', stale ? '—' : number(m.humedad_pct, 0));
  set('wind', stale ? '—' : number(m.viento_kmh));
  set('wind-direction', stale ? '—' : (m.direccion_viento || '—'));
  set('rssi', selectedNode && validNumber(selectedNode.radio?.rssi_dbm) ? `${number(selectedNode.radio.rssi_dbm, 0)} dBm` : '—');
  set('snr', selectedNode && validNumber(selectedNode.radio?.snr_db) ? `${number(selectedNode.radio.snr_db)} dB` : '—');
  set('risk', (typeof m.riesgo_incendio === 'string' && m.riesgo_incendio.trim()) ? m.riesgo_incendio : 'PENDIENTE');
  set('risk-description', m.riesgo_incendio ? 'Valor aportado por el backend' : 'Cálculo por definir con el proyecto');

  renderTable(nodos);
  renderChart(selectedNode?.historial || []);
  renderMap(nodos);
}

function renderTable(nodos) {
  const tbody = el('nodes-body');
  if (!nodos.length) { tbody.innerHTML = '<tr><td colspan="5" class="table-placeholder">No hay nodos registrados.</td></tr>'; return; }
  tbody.innerHTML = nodos.map((node) => {
    const on = node.estado === 'online';
    const battery = validNumber(node.bateria_pct) ? `${number(node.bateria_pct,0)}%` : '—';
    return `<tr class="${node.id === state.selectedId ? 'selected' : ''}">
      <td>${escapeHTML(node.id)}<div class="node-label">${escapeHTML(node.nombre || 'Sin nombre')}</div></td>
      <td><span class="status-pill ${on ? '' : 'offline'}"><span class="dot ${on ? 'dot-good' : 'dot-bad'}"></span>${on ? 'En línea' : 'Sin conexión'}</span></td>
      <td>${escapeHTML(time(node.ultima_lectura))}</td>
      <td class="${validNumber(node.bateria_pct) && node.bateria_pct < 25 ? 'battery-low' : 'battery-good'}">${battery}</td>
      <td><button type="button" class="node-button" data-node-id="${escapeHTML(node.id)}" aria-label="Ver ${escapeHTML(node.nombre || node.id)}">Ver datos →</button></td>
    </tr>`;
  }).join('');
}

// Cada serie posee su escala, para no confundir °C con km/h.
function renderChart(history) {
  const data = history.filter((entry) => validNumber(entry.temperatura_c) && validNumber(entry.viento_kmh));
  if (data.length < 2) {
    el('chart').innerHTML = '<p class="empty-copy">No hay historial disponible para este nodo.</p>';
    return;
  }
  const width=650,height=184,x1=15,x2=630,y1=14,y2=153;
  const createPath = (key) => {
    const values = data.map((d) => d[key]);
    let min = Math.min(...values), max = Math.max(...values);
    const padding = Math.max((max - min) * 0.22, 1);
    min -= padding; max += padding;
    return values.map((value, i) => `${i===0?'M':'L'}${(x1+i*(x2-x1)/(values.length-1)).toFixed(1)} ${(y2-(value-min)/(max-min)*(y2-y1)).toFixed(1)}`).join(' ');
  };
  const lines = [0,1,2,3].map((i) => `<line x1="${x1}" y1="${y1+i*(y2-y1)/3}" x2="${x2}" y2="${y1+i*(y2-y1)/3}" stroke="#344555" stroke-width="1" stroke-dasharray="3 5"/>`).join('');
  const ticks = [0,Math.floor((data.length-1)/2),data.length-1].map((i)=>`<text x="${x1+i*(x2-x1)/(data.length-1)}" y="177" fill="#839bab" font-size="10" text-anchor="middle">${escapeHTML(data[i].hora||'')}</text>`).join('');
  el('chart').innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-label="Evolución de temperatura y viento"><title>Temperatura y viento durante las últimas muestras</title>${lines}<path d="${createPath('temperatura_c')}" fill="none" stroke="#ff9f55" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/><path d="${createPath('viento_kmh')}" fill="none" stroke="#51cfb5" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/>${ticks}</svg>`;
}

function renderMap(nodos) {
  const mapEl = el('map');
  if (!window.L) {
    mapEl.textContent = 'No se pudo cargar el mapa. Revisá tu conexión a internet.';
    mapEl.style.display='grid'; mapEl.style.placeItems='center'; mapEl.style.padding='20px';
    return;
  }
  if (!state.map) {
    state.map = L.map(mapEl,{scrollWheelZoom:false}).setView([-38.942,-69.235],12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution:'&copy; OpenStreetMap contributors', maxZoom:18,
    }).addTo(state.map);
    state.markers = L.layerGroup().addTo(state.map);
  }
  state.markers.clearLayers();
  const points = [];
  nodos.forEach((node) => {
    if (!validNumber(node.lat) || !validNumber(node.lon) || Math.abs(node.lat)>90 || Math.abs(node.lon)>180) return;
    const color = node.estado === 'online' ? '#5fd1b1' : '#e58b83';
    const marker = L.circleMarker([node.lat,node.lon],{
      radius: node.id === state.selectedId ? 10 : 7, color:'#0b1b24',weight:2,fillColor:color,fillOpacity:1,
    }).addTo(state.markers);
    marker.bindPopup(`<strong>${escapeHTML(node.nombre || node.id)}</strong><br>${escapeHTML(node.id)}<br>${node.estado==='online'?'En línea':'Sin conexión'}`);
    marker.on('click', () => {state.selectedId=node.id;render();});
    points.push([node.lat,node.lon]);
  });
  if (points.length) state.map.fitBounds(L.latLngBounds(points).pad(0.35),{maxZoom:13});
  setTimeout(() => state.map?.invalidateSize(), 80);
}

async function loadData() {
  if (state.busy) return;
  state.busy=true;
  const button=el('refresh-button');
  button.disabled=true;
  const url=state.mode==='demo'?CONFIG.demoUrl:CONFIG.apiUrl;
  try {
    const res=await fetch(url,{cache:'no-store'});
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const payload=await res.json();
    if (!payload || !Array.isArray(payload.nodos)) throw new Error('El JSON debe contener el arreglo "nodos"');
    state.data=payload;
    if (!payload.nodos.some(n=>n.id===state.selectedId)) state.selectedId=payload.nodos[0]?.id??null;
    render();
    showNotice(state.mode==='demo'
      ? 'MODO DEMO · Los valores son ejemplos simulados. Podés elegir un nodo y explorar el panel.'
      : 'API PYTHON · Datos recibidos desde el servidor.');
  } catch (err) {
    console.error('Error al obtener datos:',err);
    state.data=null;
    render();
    showNotice(state.mode==='demo'
      ? 'No se pudo abrir data/nodos.json. Abrí la carpeta web con Live Server o un servidor HTTP local.'
      : `No se pudo conectar con ${CONFIG.apiUrl}. Verificá la API Python y su configuración CORS. (${err.message})`,true);
  } finally {state.busy=false;button.disabled=false;}
}

function start() {
  const select=el('source-select');
  select.addEventListener('change', () => {
    state.mode=select.value;
    const demo=state.mode==='demo';
    el('mode-badge').innerHTML=demo?'<span class="dot dot-demo"></span> DEMOSTRACIÓN':'<span class="dot dot-good"></span> API PYTHON';
    loadData();
  });
  el('refresh-button').addEventListener('click',loadData);
  el('nodes-body').addEventListener('click', (ev) => {
    const btn=ev.target.closest('[data-node-id]');
    if (!btn) return;
    state.selectedId=btn.getAttribute('data-node-id');
    render();
    document.getElementById('panel').scrollIntoView({behavior:'smooth'});
  });
  function tickClock() {set('clock',new Date().toLocaleString('es-AR',{weekday:'short',hour:'2-digit',minute:'2-digit'}));}
  tickClock();setInterval(tickClock,60000);
  loadData();
  setInterval(loadData,CONFIG.refreshMs);
}
start();
