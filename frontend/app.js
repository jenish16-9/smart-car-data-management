import { api, tokenStore } from './api.js';

const app = document.querySelector('#app');

const state = { page: location.hash.replace('#/', '') || 'dashboard', user: null, userName: 'Admin', vehicle: 'CAR-1024', deviceId: null, alertId: null, mapVehicle: 'All Vehicles', filters: { vehicle: 'All Vehicles', type: 'All Types', range: '' }, loading: false, notice: '' };

const icons = { dashboard: '▦', map: '⌖', alerts: '♧', car: '▱', analytics: '▥', user: '●', audio: '▥', clock: '◷', check: '✓', bell: '♧' };

function svgIcon(type) {
  const paths = {
    car: '<path d="M5 17h14l1-5-2-5H6L4 12l1 5Z"/><path d="M7 17v2M17 17v2M4 12h16M8 8l1.5-3h5L16 8"/><circle cx="8" cy="14" r="1"/><circle cx="16" cy="14" r="1"/>',
    audio: '<path d="M4 12h2M8 8v8M12 5v14M16 8v8M20 10v4"/>',
    detection: '<rect x="5" y="4" width="14" height="16" rx="2"/><path d="M8 9h8M8 13h8M8 17h5"/>',
    alert: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/>'
  };
  return `<span class="metric-icon"><svg viewBox="0 0 24 24" aria-hidden="true">${paths[type]}</svg></span>`;
}

function navIcon(type) {
  const paths = {
    dashboard: '<rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/>',
    map: '<path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
    alerts: '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/>',
    car: '<path d="M5 16h14l-1-6H6l-1 6Z"/><path d="M7 10l2-4h6l2 4M7 16v2M17 16v2"/><circle cx="8" cy="14" r="1"/><circle cx="16" cy="14" r="1"/>',
    analytics: '<path d="M5 19V9M12 19V5M19 19v-7"/>'
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[type]}</svg>`;
}

function carIllustration() { return `<svg viewBox="0 0 300 190" role="img" aria-label="Top view of CAR-1024"><ellipse cx="150" cy="96" rx="112" ry="76" fill="#eaf2fb" stroke="#5f7897" stroke-width="8"/><path d="M91 59c8-17 24-28 42-31h34c18 3 34 14 42 31l13 31v30l-13 31c-8 17-24 28-42 31h-34c-18-3-34-14-42-31l-13-31V90l13-31Z" fill="#fdfefe" stroke="#b8cadd" stroke-width="5"/><path d="M112 64c7-14 18-20 32-22h12c14 2 25 8 32 22l7 16h-90l7-16Z" fill="#2e4c70" stroke="#8ca6c2" stroke-width="4"/><path d="M105 85h90v29h-90Z" fill="#bdd0e3" stroke="#8ca6c2" stroke-width="4"/><path d="M112 125h76l-7 14c-7 12-17 18-31 20h-0c-14-2-24-8-31-20l-7-14Z" fill="#2e4c70" stroke="#8ca6c2" stroke-width="4"/><rect x="65" y="70" width="25" height="47" rx="9" fill="#2f4967"/><rect x="210" y="70" width="25" height="47" rx="9" fill="#2f4967"/><path d="M112 48h76M112 144h76" stroke="#ffffff" stroke-width="4" stroke-linecap="round"/></svg>`; }

function brandMark() { return `<div class="brand-mark" aria-label="AudioGuard logo"><span></span><span></span><span></span><span></span><span></span></div>`; }
function nav() { const items = [['dashboard','Dashboard'],['fleet','Vehicles & Devices'],['map','Live Map'],['alerts','Alert Details'],['car','Car Monitoring & Control'],['analytics','Analytics']]; return `<aside class="sidebar"><div class="side-brand">${brandMark()}<div>Smart Car<br/>Data Management</div></div><nav class="nav">${items.map(([id,label]) => `<button class="nav-btn ${state.page===id?'active':''}" data-page="${id}"><span class="nav-icon">${navIcon(id === 'fleet' ? 'car' : id)}</span><span>${label}</span></button>`).join('')}</nav></aside>`; }
// ---------------------------------------------------------------------------
// Data layer. `data` starts as the built-in sample data (the original static UI) and is
// replaced by live backend data whenever the API is reachable. If the backend is down,
// the sample data is kept so no page is ever blank.
// ---------------------------------------------------------------------------
const pad = (n) => String(n).padStart(2, '0');
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const cap = (value) => String(value ?? '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
const fmtDateTime = (iso) => { const d = new Date(iso); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`; };
const fmtTime = (iso) => new Date(iso).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
const fmtLong = (iso) => new Date(iso).toLocaleString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).replace(/(\d{4}),/, '$1');
const percent = (n) => `${Math.round(n)}%`;

function ago(iso) {
  if (!iso) return 'Never';
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return hours < 48 ? `${hours} hr ago` : `${Math.round(hours / 24)} days ago`;
}

function duration(iso) {
  const minutes = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 60000));
  const days = Math.floor(minutes / 1440); const hours = Math.floor((minutes % 1440) / 60);
  if (days) return `${days} day${days > 1 ? 's' : ''} ${hours} hour${hours === 1 ? '' : 's'}`;
  if (hours) return `${hours} hour${hours === 1 ? '' : 's'} ${minutes % 60} min`;
  return `${minutes} min`;
}

const TYPE_TONE = { emergency_vehicle_siren: 'amber', glass_breaking: 'red', screaming: 'red', gunshot: 'red', crash: 'red', tire_skidding: 'amber', abnormal_engine_noise: 'blue', normal: 'green' };
const SEVERITY_TONE = { critical: 'red', high: 'red', medium: 'amber', low: 'blue' };
const ALERT_LABEL = { open: 'Unread', acknowledged: 'Acknowledged', resolved: 'Resolved' };
const STATUS_TONE = { online: 'green', healthy: 'green', locked: 'green', warning: 'amber' };
const toneOf = (value) => STATUS_TONE[String(value).toLowerCase()] || 'red';
const DONUT_COLORS = ['#ef6868', '#549bf1', '#72d18f', '#a694ee'];
const MARKER_COLORS = ['blue', 'green', 'orange'];

function sampleVehicle(code, type, pos, label, color) {
  return { code, type, connected: true, microphone: 'Online', engine: 'Healthy', gps: 'Locked', lastSeen: '2 min ago', sync: '2 minutes ago', uptime: '2 days 6 hours', registered: '—', mapStatus: 'In Transit', mode: 'continuous', capture: true, recording: false, pos: { ...pos, label }, color };
}

function sampleData() {
  return {
    live: false,
    summary: { vehicles: 12, uploads: 342, detections: 86, alerts: 5, events: '1,248', critical: 87, confidence: '92%', resolution: '96%' },
    events: [['CAR-1024', 'Glass Break', '2024-05-01 14:23:11', '96%', 'Alert', 'red'], ['CAR-1024', 'Engine Noise', '2024-05-01 12:17:03', '87%', 'Reviewing', 'amber'], ['CAR-1024', 'Normal Cabin', '2024-05-01 10:05:21', '78%', 'Completed', 'green'], ['CAR-1024', 'Glass Break', '2024-04-30 16:45:12', '93%', 'Alert', 'red'], ['CAR-1024', 'Engine Noise', '2024-04-30 14:11:09', '88%', 'Reviewing', 'amber']],
    weekly: [20, 35, 50, 43, 68, 39, 29].map((h, i) => ({ h, label: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i] })),
    vehicles: [
      sampleVehicle('CAR-1024', 'Sedan', { x: 45, y: 42 }, { x: 42, y: 34 }, 'blue'),
      sampleVehicle('CAR-1025', 'SUV', { x: 20, y: 64 }, { x: 17, y: 55 }, 'green'),
      sampleVehicle('CAR-1026', 'Sedan', { x: 78, y: 51 }, { x: 75, y: 42 }, 'orange'),
    ],
    vehicleRecords: [],
    devices: [],
    heartbeats: [],
    alertList: [],
    alert: { id: null, title: 'Glass Break Detected', severity: 'High Severity', tone: 'red', vehicle: 'CAR-1024', time: '10:24 AM', confidence: '94% Confidence', location: 'Front Right', status: 'Unread', model: 'v2.3.1', ms: '320 ms', audio: 'AUD-20240218-102435-7F3A', reviewed: '-' },
    overTime: [15, 22, 30, 18, 25, 33, 46, 35, 18, 20, 29, 42, 58, 37].map((h, i) => ({ h, label: i % 3 === 0 ? `Apr ${i + 1}` : '' })),
    byType: [{ name: 'Glass Breaking', key: 'glass_breaking', tone: 'red', count: 168, conf: '94%', last: 'Apr 30, 2024 14:32:18' }, { name: 'Abnormal Engine Noise', key: 'abnormal_engine_noise', tone: 'blue', count: 302, conf: '91%', last: 'Apr 30, 2024 13:17:05' }, { name: 'Emergency Vehicle Siren', key: 'emergency_vehicle_siren', tone: 'amber', count: 118, conf: '89%', last: 'Apr 30, 2024 12:54:41' }],
    activity: [['2024-06-24 10:18:32', 'Audio Capture Started', 'Microphone activated'], ['2024-06-24 10:15:21', 'Monitoring Mode Changed', 'Mode set to Continuous'], ['2024-06-24 10:12:03', 'Device Status Check', 'All systems normal'], ['2024-06-24 10:08:17', 'Connection Established', 'Vehicle connected to server']],
    ranges: ['Apr 1, 2024 - Apr 30, 2024', 'Last 7 days'],
  };
}

// Live mode starts empty (never flash sample numbers to a signed-in user) and fills in per page.
function emptyLiveData() {
  return { ...sampleData(), live: true, summary: { vehicles: 0, uploads: 0, detections: 0, alerts: 0, events: '0', critical: 0, confidence: '0%', resolution: '0%' }, events: [], weekly: [], vehicles: [], vehicleRecords: [], devices: [], heartbeats: [], alertList: [], alert: null, overTime: [], byType: [], activity: [] };
}

let data = sampleData();
const NO_VEHICLE = { code: '—', type: '—', connected: false, microphone: 'Offline', engine: 'Unknown', gps: 'No Signal', lastSeen: 'Never', sync: 'Never', uptime: '—', registered: '—', mapStatus: 'Unknown', mode: 'continuous', capture: false, recording: false };
const currentVehicle = () => data.vehicles.find((v) => v.code === state.vehicle) || data.vehicles[0] || NO_VEHICLE;
const connectedPill = (v) => (v.status === 'maintenance' ? '<span class="status-pill amber">Maintenance</span>' : `<span class="status-pill ${v.connected ? 'green' : 'red'}">${v.connected ? 'Connected' : 'Disconnected'}</span>`);
const statePill = (value) => `<span class="status-pill ${toneOf(value)}">${esc(value)}</span>`;

// ----- Mapping backend responses to the view model -----
function toVehicle(v, latest) {
  const d = v.device || {};
  const moving = latest && latest.speed > 1;
  const connected = v.status === 'connected';
  const mapStatus = v.status === 'maintenance' ? 'In Maintenance' : !connected ? 'Offline' : moving ? 'In Transit' : 'Parked';
  const uptime = connected && d.online_since ? duration(d.online_since) : v.status === 'maintenance' ? 'In maintenance' : connected ? '—' : 'Offline';
  const state_ = v.status;
  return { code: v.vehicle_code, type: v.vehicle_type, connected, status: state_, microphone: cap(v.audio_device_state || 'offline'), engine: cap(d.engine_status || 'unknown'), gps: cap(d.gps_status || 'no_signal'), lastSeen: ago(v.last_seen_at || d.last_sync_at), sync: ago(d.last_sync_at), uptime, mapStatus, mode: d.monitoring_mode || 'continuous', capture: d.audio_capture_enabled !== false, recording: Boolean(d.recording), latest: latest || null };
}

function placeMarkers(vehicles) {
  const located = vehicles.filter((v) => v.latest && v.latest.location);
  const lats = located.map((v) => v.latest.location.latitude);
  const lngs = located.map((v) => v.latest.location.longitude);
  const spanLat = Math.max(...lats) - Math.min(...lats);
  const spanLng = Math.max(...lngs) - Math.min(...lngs);
  located.forEach((v, i) => {
    const x = spanLng ? 12 + ((v.latest.location.longitude - Math.min(...lngs)) / spanLng) * 76 : 50;
    const y = spanLat ? 12 + ((Math.max(...lats) - v.latest.location.latitude) / spanLat) * 70 : 50;
    v.pos = { x, y, label: { x: x - 3, y: y - 8 } };
    v.color = v.status === 'maintenance' ? 'orange' : v.status === 'disconnected' ? 'gray' : MARKER_COLORS[i % 2];
  });
}

function toEventRow(audio) {
  const analysis = audio.analysis;
  if (!analysis) return [audio.vehicle_code, 'Pending analysis', fmtDateTime(audio.uploaded_at), '—', cap(audio.processing_status), audio.processing_status === 'failed' ? 'red' : 'amber'];
  const flagged = analysis.predicted_class !== 'normal';
  const [label, tone] = !flagged ? ['Completed', 'green'] : analysis.confidence >= 0.8 ? ['Alert', 'red'] : ['Reviewing', 'amber'];
  return [audio.vehicle_code, cap(analysis.predicted_class), fmtDateTime(audio.uploaded_at), percent(analysis.confidence * 100), label, tone];
}

function weeklyUploads(audioList) {
  const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() - (6 - i)); return d; });
  const counts = days.map((day) => audioList.filter((a) => new Date(a.uploaded_at).toDateString() === day.toDateString()).length);
  const max = Math.max(...counts, 1);
  return days.map((day, i) => ({ h: Math.max(2, (counts[i] / max) * 100), label: day.toLocaleDateString('en-US', { weekday: 'short' }) }));
}

function toAlertView(alert) {
  const analysis = alert.analysis;
  return { id: alert.id, title: `${cap(alert.event_type)} Detected`, severity: `${cap(alert.severity)} Severity`, tone: SEVERITY_TONE[alert.severity] || 'red', vehicle: alert.vehicle_code, time: fmtTime(alert.detected_at), confidence: `${Math.round(alert.confidence * 100)}% Confidence`, location: alert.location || 'Unknown', status: ALERT_LABEL[alert.status] || cap(alert.status), model: analysis ? analysis.model_version : '—', ms: analysis ? `${analysis.processing_time_ms} ms` : '—', audio: alert.audio_record_id || alert.simulation_event_id || '—', audioId: alert.audio_record_id, isSimulation: Boolean(alert.is_simulation), reviewed: alert.reviewed_at ? fmtTime(alert.reviewed_at) : '-' };
}

function daysFor(range) { return /7/.test(range) ? 7 : /90/.test(range) ? 90 : 30; }

function toAnalytics(summary, over, byType, days) {
  const counts = new Map(over.map((p) => [p.date, p.count]));
  const dates = Array.from({ length: days }, (_, i) => new Date(Date.now() - (days - 1 - i) * 864e5).toISOString().slice(0, 10));
  const max = Math.max(...counts.values(), 1);
  const step = days > 14 ? 5 : days > 7 ? 3 : 1;
  const dayLabel = (d) => new Date(`${d}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
  return {
    summary: { events: summary.total_events.toLocaleString(), critical: summary.critical_events, confidence: percent(summary.average_confidence), resolution: percent(summary.resolution_rate) },
    overTime: dates.map((d, i) => ({ h: Math.max(2, ((counts.get(d) || 0) / max) * 100), label: (days - 1 - i) % step === 0 ? dayLabel(d) : '', tip: `${dayLabel(d)}: ${counts.get(d) || 0} events` })),
    byType: byType.map((t) => ({ name: cap(t.event_type), key: t.event_type, tone: TYPE_TONE[t.event_type] || 'blue', count: t.count, conf: percent(t.average_confidence), last: t.last_detected ? fmtLong(t.last_detected) : '—' })),
  };
}

// ----- Page loaders (live mode only) -----
async function loadVehicles(withLocation = false) {
  const list = await api.vehicles();
  data.vehicleRecords = list;
  const latest = withLocation ? await Promise.all(list.map((v) => api.latestTelemetry(v.vehicle_code).catch((e) => (e.status === 404 ? null : Promise.reject(e))))) : [];
  data.vehicles = list.map((v, i) => toVehicle(v, latest[i]));
  if (withLocation) placeMarkers(data.vehicles);
  if (!data.vehicles.some((v) => v.code === state.vehicle) && data.vehicles.length) state.vehicle = data.vehicles[0].code;
}

const loaders = {
  async dashboard() {
    await loadVehicles();
    const code = currentVehicle().code;
    const [summary, audio] = await Promise.all([api.analytics(), code === NO_VEHICLE.code ? [] : api.audio({ limit: 500, vehicle_id: code })]);
    data.summary = { ...data.summary, vehicles: summary.vehicle_count, uploads: summary.audio_upload_count, detections: summary.detection_count, alerts: summary.active_alert_count };
    data.events = audio.slice(0, 5).map(toEventRow);
    data.weekly = weeklyUploads(audio);
  },
  async map() { await loadVehicles(true); },
  async fleet() {
    await loadVehicles();
    const code = currentVehicle().code;
    data.devices = code === NO_VEHICLE.code ? [] : await api.vehicleDevices(code);
    if (!data.devices.some((device) => device.id === state.deviceId)) state.deviceId = data.devices[0]?.id || null;
    data.heartbeats = state.deviceId ? await api.deviceHeartbeats(state.deviceId, { limit: 20 }) : [];
  },
  async alerts() {
    await loadVehicles();
    const code = currentVehicle().code;
    const list = code === NO_VEHICLE.code ? [] : await api.alerts({ vehicle_id: code, limit: 50 });
    data.alertList = list.map((a) => ({ id: a.id, label: `${cap(a.event_type)} · ${fmtDateTime(a.detected_at)} · ${ALERT_LABEL[a.status] || a.status}` }));
    const pick = list.find((a) => a.id === state.alertId) || list.find((a) => a.status !== 'resolved') || list[0];
    state.alertId = pick ? pick.id : null;
    data.alert = pick ? toAlertView(await api.alert(pick.id)) : null;
  },
  async car() {
    await loadVehicles();
    const code = currentVehicle().code;
    if (code === NO_VEHICLE.code) { data.activity = []; return; }
    const [logs, history] = await Promise.all([api.deviceLogs(code, { limit: 10 }), api.telemetry(code, { limit: 5 })]);
    const rows = [
      ...logs.map((l) => ({ at: l.timestamp, row: [fmtDateTime(l.timestamp), cap(l.event_type), l.message] })),
      ...history.map((t) => ({ at: t.timestamp, row: [fmtDateTime(t.timestamp), 'Telemetry Received', [t.speed != null && `Speed ${t.speed} km/h`, t.engine_temperature != null && `Engine ${t.engine_temperature}°C`, t.battery_level != null && `Battery ${t.battery_level}%`].filter(Boolean).join(' · ') || 'Location update'] })),
    ];
    data.activity = rows.sort((x, y) => new Date(y.at) - new Date(x.at)).slice(0, 8).map((r) => r.row);
  },
  async analytics() {
    await loadVehicles();
    const params = { vehicle_id: state.filters.vehicle === 'All Vehicles' ? '' : state.filters.vehicle };
    const days = daysFor(state.filters.range);
    const [summary, over, byType] = await Promise.all([api.analytics(params), api.eventsOverTime({ ...params, days }), api.eventsByType(params)]);
    Object.assign(data, toAnalytics(summary, over, byType, days));
    data.ranges = ['Last 30 days', 'Last 7 days', 'Last 90 days'];
  },
};

async function loadData() {
  if (!api.hasToken()) return; // offline demo session: keep sample data
  try {
    if (!data.live) data = emptyLiveData();
    await (loaders[state.page] || loaders.analytics)();
    state.notice = '';
  } catch (err) {
    if (err.status === 401) { await endSession('Your session has expired. Please sign in again.'); return; }
    data = sampleData();
    state.notice = err.unreachable ? 'Backend unavailable — showing sample data.' : `Could not load data (${err.message}) — showing sample data.`;
  }
}

// ---------------------------------------------------------------------------
// Views (markup unchanged from the original static design)
// ---------------------------------------------------------------------------
function topbar() { return `<header class="topbar"><div class="top-brand">${brandMark()}<span>Smart Car Data Management</span></div><div class="top-actions"><select class="select-control vehicle-select" id="vehicleTop">${data.vehicles.map((v) => `<option ${v.code === state.vehicle ? 'selected' : ''}>${esc(v.code)}</option>`).join('')}</select><div class="profile-wrap"><button class="profile" id="profileMenuBtn" aria-expanded="false"><span class="avatar">●</span><span>${esc(state.userName)}</span><span>⌄</span></button><div class="account-menu" id="accountMenu" hidden><button class="logout-btn" id="logoutBtn">↪&nbsp; Logout</button></div></div></div></header>`; }
function banner() { return state.notice ? `<div class="notice" role="status">${esc(state.notice)}</div>` : ''; }
function shell(content) { return `<div class="app-shell">${nav()}<main class="main">${topbar()}<section class="content">${banner()}${content}</section></main></div>`; }
function metric(icon, label, value) { return `<article class="metric-card"><div><small>${label}</small><strong>${value}</strong></div>${icon}</article>`; }
const emptyRow = (cols, text) => `<tr><td colspan="${cols}">${text}</td></tr>`;

function dashboard() {
  const s = data.summary; const v = currentVehicle();
  const shownCode = (r) => (data.live ? r[0] : state.vehicle);
  const rows = data.events.length ? data.events.map((r) => `<tr>${[shownCode(r), ...r.slice(1, 4)].map((x) => `<td>${esc(x)}</td>`).join('')}<td><span class="status-pill ${r[5]}">${esc(r[4])}</span></td></tr>`).join('') : emptyRow(5, `No audio events recorded for ${esc(state.vehicle)}`);
  return shell(`<h1 class="page-title">Dashboard</h1><div class="grid metrics">${metric(svgIcon('car'), 'Registered Vehicles', s.vehicles)}${metric(svgIcon('audio'), 'Audio Uploads', s.uploads)}${metric(svgIcon('detection'), 'Detections', s.detections)}${metric(svgIcon('alert'), 'Active Alerts', s.alerts)}</div><div class="grid dashboard-grid"><div class="panel"><h2 class="section-title">Recent Audio Events</h2><div class="table-wrap"><table><thead><tr><th>Vehicle ID</th><th>Event Type</th><th>Timestamp</th><th>Confidence</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div></div><div class="panel"><h2 class="section-title">Vehicle Status</h2><div class="detail-list"><div class="detail-row">${connectedPill(v)}</div><div class="detail-row">♩ <strong>Microphone ${esc(v.microphone)}</strong></div><div class="detail-row">◷ <strong>Last Sync:</strong> ${esc(v.lastSeen)}</div></div><h2 class="section-title">Uploads This Week</h2><div class="bar-chart">${data.weekly.map((b) => `<div class="bar" style="height:${b.h}%"><span>${esc(b.label)}</span></div>`).join('')}</div></div></div>`);
}

function mapPage() {
  const shown = data.vehicles.filter((v) => state.mapVehicle === 'All Vehicles' || v.code === state.mapVehicle);
  const markers = shown.filter((v) => v.pos).map((v) => `<span class="map-label" style="left:${v.pos.label.x}%;top:${v.pos.label.y}%">${esc(v.code)}</span><span class="marker ${v.color}" style="left:${v.pos.x}%;top:${v.pos.y}%">▱</span>`).join('');
  const empty = data.live && !markers ? '<span class="map-label" style="left:40%;top:45%">No location data yet</span>' : '';
  const v = data.vehicles.find((x) => x.code === state.mapVehicle) || currentVehicle();
  return shell(`<h1 class="page-title">Live Vehicle Map</h1><div class="grid map-layout"><div class="panel"><div class="filter"><label>Vehicle</label><select class="select-control" id="mapFilter"><option>All Vehicles</option>${data.vehicles.map((x) => `<option ${x.code === state.mapVehicle ? 'selected' : ''}>${esc(x.code)}</option>`).join('')}</select></div><div class="map-box" style="margin-top:18px">${markers}${empty}</div></div><div class="panel vehicle-card"><h2>${esc(v.code)}</h2><div class="detail-list"><div class="detail-row">${connectedPill(v)}</div><div class="detail-row">♩ <strong>Audio Device ${esc(v.microphone)}</strong></div><div class="detail-row">◷ Last Sync: ${esc(v.lastSeen)}</div><div class="detail-row">➤ Current Status: ${esc(v.mapStatus)}</div></div><button class="primary-btn" data-page="car" data-vehicle="${esc(v.code)}">View Details</button><button class="secondary-btn" data-page="alerts" data-vehicle="${esc(v.code)}">Open Alerts</button></div></div>`);
}

function alertPage() {
  const a = data.alert;
  const picker = data.live && data.alertList.length ? `<div class="filter" style="margin-bottom:18px"><label>Alert (${esc(state.vehicle)})</label><select class="select-control" id="alertPick">${data.alertList.map((x) => `<option value="${esc(x.id)}" ${x.id === state.alertId ? 'selected' : ''}>${esc(x.label)}</option>`).join('')}</select></div>` : '';
  if (!a) return shell(`<h1 class="page-title">Alert Details</h1><div class="panel"><p>No alerts have been raised for ${esc(state.vehicle)}.</p></div>`);
  return shell(`<h1 class="page-title">Alert Details</h1>${picker}<div class="panel"><div class="alert-hero"><div class="alert-symbol">!</div><div><h2>${esc(a.title)}</h2><span class="status-pill ${a.tone}">${esc(a.severity)}</span>${a.isSimulation ? '<span class="status-pill amber">Simulation</span>' : ''}<div class="alert-meta" style="margin-top:18px"><span>▱ ${esc(data.live ? a.vehicle : state.vehicle)}</span><span>◷ ${esc(a.time)}</span><span>♩ ${esc(a.confidence)}</span><span>⌖ ${esc(a.location)}</span><span class="status-pill ${a.status === 'Resolved' ? 'green' : 'red'}">${esc(a.status)}</span></div></div></div><div class="action-row"><button class="primary-btn" id="ackBtn">✓ ${a.status === 'Resolved' ? 'Resolved' : 'Acknowledge Alert'}</button><button class="secondary-btn" id="resolveBtn">✓ Mark as Resolved</button><button class="secondary-btn" id="audioBtn">♩ View Audio Record</button></div></div><div class="grid two-col"><div class="panel"><h2 class="section-title">Detection Information</h2><div class="detail-list"><div class="detail-row">▣ <span>Model Version</span><strong>${esc(a.model)}</strong></div><div class="detail-row">◷ <span>Processing Time</span><strong>${esc(a.ms)}</strong></div><div class="detail-row">▤ <span>${a.isSimulation ? 'Simulation Event ID' : 'Audio Record ID'}</span><strong>${esc(a.audio)}</strong></div><div class="detail-row">ⓘ <span>Recommended Action</span><strong>Check vehicle surroundings and verify vehicle status.</strong></div></div></div><div class="panel"><h2 class="section-title">Alert Timeline</h2><div class="timeline"><div class="timeline-item"><span class="timeline-dot active"></span><div><strong>Detected</strong><div>${esc(a.time)}</div></div></div><div class="timeline-item"><span class="timeline-dot"></span><div><strong>Reviewed</strong><div>${esc(a.reviewed)}</div></div></div><div class="timeline-item"><span class="timeline-dot"></span><div><strong>Notification Sent</strong><div>-</div></div></div></div></div></div>`);
}

function carPage() {
  const v = currentVehicle();
  const rows = data.activity.length ? data.activity.map((r) => `<tr><td>${esc(r[0])}</td><td>${esc(r[1])}</td><td>${esc(r[2])}</td><td><span class="status-pill green">Success</span></td></tr>`).join('') : emptyRow(4, 'No device activity recorded yet');
  return shell(`<h1 class="page-title">Car Monitoring &amp; Control</h1><div class="grid two-col"><div class="panel car-panel"><div class="car-header"><div><h2>${esc(v.code)} ${connectedPill(v)}</h2><div class="car-subtitle">▱ &nbsp; ${esc(v.type)}</div></div></div><div class="car-meta"><span>◷ &nbsp; Last Seen: ${esc(v.lastSeen)}</span><span>|</span><span>◷ &nbsp; Uptime: ${esc(v.uptime)}</span></div><div class="vehicle-overview"><div class="vehicle-overview-title"><span class="vehicle-badge">${svgIcon('car')}</span><span>Vehicle Overview</span></div><div class="vehicle-status-grid"><div class="vehicle-status-card"><small>Engine</small><strong>${statePill(v.engine)}</strong></div><div class="vehicle-status-card"><small>Cabin Audio</small><strong>${statePill(v.microphone)}</strong></div><div class="vehicle-status-card"><small>GPS Location</small><strong>${statePill(v.gps)}</strong></div><div class="vehicle-status-card"><small>Latest Sync</small><strong>${esc(v.sync)}</strong></div></div></div></div><div class="panel"><h2 class="section-title">Device Controls</h2><div class="control-list"><div class="control-item"><span class="control-label">♩ Microphone ${statePill(v.microphone)}</span></div><div class="control-item"><span class="control-label">▥ Audio Capture</span><button class="toggle ${v.capture ? 'on' : ''}" id="captureToggle" aria-pressed="${v.capture}" aria-label="Toggle audio capture"></button><span>${v.capture ? 'Enabled' : 'Disabled'}</span></div><div class="control-item"><span class="control-label">⚙ Monitoring Mode</span><select class="select-control" style="width:150px" id="modeSelect">${[['continuous', 'Continuous'], ['motion_triggered', 'Motion Triggered'], ['paused', 'Paused']].map(([value, label]) => `<option value="${value}" ${v.mode === value ? 'selected' : ''}>${label}</option>`).join('')}</select></div><button class="primary-btn" id="recordBtn">◉ ${v.recording ? 'Stop Recording' : 'Start Recording'}</button><button class="secondary-btn" id="pauseBtn">Ⅱ ${v.mode === 'paused' ? 'Resume Monitoring' : 'Pause Monitoring'}</button><button class="secondary-btn" id="refreshBtn">⟳ Refresh Status</button></div></div></div><div class="panel activity"><h2 class="section-title">Recent Device Activity</h2><div class="table-wrap"><table><thead><tr><th>Time</th><th>Event</th><th>Details</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div></div>`);
}

function analytics() {
  const s = data.summary;
  const shownTypes = data.byType.filter((t) => state.filters.type === 'All Types' || t.name === state.filters.type);
  const total = shownTypes.reduce((sum, t) => sum + t.count, 0);
  let acc = 0;
  const stops = shownTypes.slice(0, 4).map((t, i) => { const from = (acc / total) * 100; acc += t.count; return `${DONUT_COLORS[i]} ${from}% ${(acc / total) * 100}%`; });
  const donut = data.live && total ? `style="background:conic-gradient(${stops.join(',')});--donut-label:'${total.toLocaleString()}\\A total events'"` : data.live ? 'style="background:#eaf2fb;--donut-label:\'0\\A total events\'"' : '';
  const typeNames = ['Glass Break', 'Engine Noise', 'Cabin Noise', 'Horn', 'Crash', 'Normal'];
  const dot = { red: '🔴', blue: '🔵', green: '🟢', amber: '🟠' };
  const option = (value, selected) => `<option ${value === selected ? 'selected' : ''}>${esc(value)}</option>`;
  const ranges = data.ranges.map((r) => option(r, state.filters.range || data.ranges[0])).join('');
  const rows = shownTypes.length ? shownTypes.map((t) => `<tr><td>${dot[t.tone] || '🔵'} ${esc(t.name)}</td><td>${t.count}</td><td>${esc(t.conf)}</td><td>${esc(t.last)}</td></tr>`).join('') : emptyRow(4, 'No events recorded yet');
  return shell(`<h1 class="page-title">Audio Event Analytics</h1><div class="panel"><div class="grid filters"><div class="filter"><label>Vehicle</label><select class="select-control" id="fVehicle"><option>All Vehicles</option>${data.vehicles.map((v) => option(v.code, state.filters.vehicle)).join('')}</select></div><div class="filter"><label>Date Range</label><select class="select-control" id="fRange">${ranges}</select></div><div class="filter"><label>Event Type</label><select class="select-control" id="fType"><option>All Types</option>${typeNames.map((t) => option(t, state.filters.type)).join('')}</select></div><button class="primary-btn" id="applyFilters">Apply Filters</button></div></div><div class="grid metrics" style="margin-top:18px">${metric(svgIcon('audio'), 'Total Events', s.events)}${metric(svgIcon('alert'), 'Critical Events', s.critical)}${metric(svgIcon('detection'), 'Average Confidence', s.confidence)}${metric(svgIcon('car'), 'Resolution Rate', s.resolution)}</div><div class="grid two-col" style="margin-top:18px"><div class="panel events-chart"><h2 class="section-title">Events Over Time</h2><div class="bar-chart" style="height:240px"><div class="bar-chart-inner">${data.overTime.map((b) => `<div class="bar" style="height:${b.h}%" title="${esc(b.tip || '')}"><span>${esc(b.label)}</span></div>`).join('')}</div></div></div><div class="panel"><h2 class="section-title">Events by Type</h2><div class="donut" ${donut}></div><div class="detail-list">${shownTypes.slice(0, 3).map((t) => `<div class="detail-row"><span class="status-pill ${t.tone}">${esc(t.name)}</span><strong>${t.count}</strong></div>`).join('')}</div></div></div><div class="panel" style="margin-top:18px"><h2 class="section-title">Top Detected Events</h2><div class="table-wrap"><table><thead><tr><th>Event Type</th><th>Count</th><th>Average Confidence</th><th>Last Detected</th></tr></thead><tbody>${rows}</tbody></table></div></div>`);
}

function fleetPage() {
  const vehicle = data.vehicleRecords.find((item) => item.vehicle_code === state.vehicle);
  const device = data.devices.find((item) => item.id === state.deviceId);
  const deviceRows = data.devices.map((item) => `<button class="record-card ${item.id === state.deviceId ? 'selected-record' : ''}" data-device-id="${esc(item.id)}"><span><strong>${esc(item.name)}</strong><small>${esc(item.hardware_id)}</small></span><span><small>Last heartbeat</small><strong>${item.last_heartbeat_at ? esc(ago(item.last_heartbeat_at)) : 'Never'}</strong></span>${statePill(item.state)}</button>`).join('');
  const history = data.heartbeats.map((item) => `<tr><td>${esc(fmtDateTime(item.received_at))}</td><td>${esc(item.health)}</td><td>${esc(JSON.stringify(item.metrics))}</td></tr>`).join('');
  const vehicleSettings = vehicle ? `<form class="panel data-form" id="vehicleUpdateForm"><h2 class="section-title">Selected vehicle</h2><label>Vehicle code<input value="${esc(vehicle.vehicle_code)}" disabled></label><label>Vehicle type<input name="vehicle_type" value="${esc(vehicle.vehicle_type)}" required></label><label>VIN<input name="vin" value="${esc(vehicle.vin || '')}" minlength="17" maxlength="17" pattern="[A-HJ-NPR-Z0-9]{17}" required></label><label>License plate<input name="license_plate" value="${esc(vehicle.license_plate || '')}" maxlength="20" required></label><label>Status<select name="status" class="select-control"><option value="connected" ${vehicle.status === 'connected' ? 'selected' : ''}>Connected</option><option value="disconnected" ${vehicle.status === 'disconnected' ? 'selected' : ''}>Disconnected</option><option value="maintenance" ${vehicle.status === 'maintenance' ? 'selected' : ''}>Maintenance</option></select></label><button class="primary-btn">Save vehicle</button><button class="danger-btn" type="button" id="removeVehicleBtn">Remove vehicle</button></form>` : '<section class="panel empty-state">Register a vehicle to begin.</section>';
  const deviceRegistration = vehicle ? `<form class="panel data-form" id="deviceCreateForm"><h2 class="section-title">Register IoT device</h2><label>Name<input name="name" required maxlength="100"></label><label>Hardware ID<input name="hardware_id" required minlength="3" maxlength="100"></label><label>Firmware version<input name="firmware_version" maxlength="50"></label><button class="primary-btn">Register device</button></form>` : '';
  const deviceSettings = device ? `<div class="management-grid activity"><form class="panel data-form" id="deviceUpdateForm"><h2 class="section-title">Device details</h2><label>Name<input name="name" value="${esc(device.name)}" required></label><label>Firmware version<input name="firmware_version" value="${esc(device.firmware_version || '')}"></label><button class="primary-btn" ${device.state === 'RETIRED' ? 'disabled' : ''}>Save details</button></form><form class="panel data-form" id="deviceConfigurationForm"><h2 class="section-title">Device settings</h2><label class="check"><input name="captureEnabled" type="checkbox" ${device.configuration.captureEnabled ? 'checked' : ''}> Capture enabled</label><label>Monitoring mode<select name="monitoringMode" class="select-control"><option value="event" ${device.configuration.monitoringMode === 'event' ? 'selected' : ''}>Event triggered</option><option value="continuous" ${device.configuration.monitoringMode === 'continuous' ? 'selected' : ''}>Continuous</option><option value="paused" ${device.configuration.monitoringMode === 'paused' ? 'selected' : ''}>Paused</option></select></label><label>Heartbeat interval (seconds)<input name="heartbeatIntervalSeconds" type="number" min="5" max="3600" value="${esc(device.configuration.heartbeatIntervalSeconds || 30)}"></label><button class="primary-btn" ${device.state === 'RETIRED' ? 'disabled' : ''}>Save settings</button></form></div><div class="management-grid activity"><form class="panel data-form" id="audioSimulationForm"><h2 class="section-title">Simulate audio event</h2><label>PCM WAV file<input name="audio" type="file" accept=".wav,audio/wav" required></label><label>Location (optional)<input name="location" maxlength="200" placeholder="Parking garage"></label><button class="primary-btn" ${['DISABLED','RETIRED'].includes(device.state) ? 'disabled' : ''}>Classify audio</button><p class="help-text">Uses the configured demo model; results are marked as simulations.</p></form><form class="panel data-form" id="heartbeatForm"><h2 class="section-title">Send test heartbeat</h2><label>Health<select name="health" class="select-control"><option>HEALTHY</option><option>WARNING</option></select></label><div class="form-row"><label>Battery %<input name="batteryPercent" type="number" min="0" max="100"></label><label>Temperature °C<input name="temperatureCelsius" type="number"></label></div><button class="primary-btn" ${device.state === 'RETIRED' ? 'disabled' : ''}>Send heartbeat</button></form><section class="panel"><h2 class="section-title">Lifecycle</h2><div class="action-stack"><button class="secondary-btn" id="disableDeviceBtn" ${['DISABLED','RETIRED'].includes(device.state) ? 'disabled' : ''}>Disable</button><button class="danger-btn" id="retireDeviceBtn" ${device.state === 'RETIRED' ? 'disabled' : ''}>Retire permanently</button><button class="danger-btn" id="removeDeviceBtn">Remove from inventory</button></div><p class="help-text">Removal preserves the PostgreSQL record and MongoDB heartbeat history.</p></section></div><section class="panel activity"><h2 class="section-title">Heartbeat history</h2><div class="table-wrap"><table><thead><tr><th>Received</th><th>Health</th><th>Metrics</th></tr></thead><tbody>${history || emptyRow(3, 'No heartbeat history.')}</tbody></table></div></section>` : '';
  return shell(`<h1 class="page-title">Vehicles &amp; IoT Devices</h1><div class="management-grid"><form class="panel data-form" id="vehicleCreateForm"><h2 class="section-title">Register vehicle</h2><label>Vehicle code<input name="vehicle_code" placeholder="CAR-1024" required></label><label>Vehicle type<input name="vehicle_type" placeholder="Sedan" required></label><label>VIN<input name="vin" placeholder="1HGCM82633A004352" minlength="17" maxlength="17" pattern="[A-HJ-NPR-Z0-9]{17}" required></label><label>License plate<input name="license_plate" placeholder="8ABC123" maxlength="20" required></label><button class="primary-btn">Register vehicle</button></form>${vehicleSettings}</div><div class="management-grid activity">${deviceRegistration}<section class="panel"><h2 class="section-title">Devices for ${esc(state.vehicle)}</h2><div class="record-list">${deviceRows || '<div class="empty-state">No active devices registered.</div>'}</div></section></div>${deviceSettings}`);
}

function login(register = false) { return `<main class="auth-shell ${register ? 'register-shell' : ''}"><div class="auth-card">${brandMark()}<h1>Smart Car Data Management</h1><p class="sub">${register ? 'Create your account' : 'Sign in to monitor your vehicle audio system'}</p>${register ? `<div class="form-field"><label>Full Name</label><input id="fullName" placeholder="Enter your full name" autocomplete="name" /></div>` : ''}<div class="form-field"><label>Email Address</label><input id="email" type="email" placeholder="you@example.com" autocomplete="email" /></div><div class="form-field"><label>Password</label><input id="password" type="password" placeholder="Enter your password" autocomplete="${register ? 'new-password' : 'current-password'}" /></div>${register ? `<div class="form-field"><label>Confirm Password</label><input id="confirmPassword" type="password" placeholder="Confirm your password" autocomplete="new-password" /></div>` : ''}<p class="form-error" id="authError" role="alert" hidden></p><div class="auth-actions"><label class="check"><input id="remember" type="checkbox" checked /> ${register ? 'I agree to the Terms and Conditions' : 'Remember me'}</label>${!register ? '<span class="link" id="forgot" role="button" tabindex="0">Forgot password?</span>' : ''}</div><button class="primary-btn full" id="authBtn">${register ? 'Create Account' : 'Sign In'}</button><div class="auth-switch">${register ? 'Already have an account?' : 'Don’t have an account?'} <span class="link" id="switchAuth">${register ? 'Sign In' : 'Create an account'}</span></div></div></main>`; }

// ---------------------------------------------------------------------------
// Rendering, navigation and actions
// ---------------------------------------------------------------------------
const pages = { dashboard, fleet: fleetPage, map: mapPage, alerts: alertPage, car: carPage };

function render() {
  if (!state.user) { app.innerHTML = login(false); bind(); return; }
  if (state.loading) { app.innerHTML = shell('<h1 class="page-title">Loading…</h1>'); bind(); return; }
  app.innerHTML = (pages[state.page] || analytics)();
  bind();
}

async function show() {
  if (api.hasToken()) { state.loading = true; render(); await loadData(); state.loading = false; }
  render();
}

async function navigate(page) { state.notice = ''; state.page = page; location.hash = '/' + page; await show(); }

async function endSession(message = '') {
  try { await api.logout(); } catch { /* token is cleared regardless */ }
  tokenStore.clear();
  state.user = null; state.page = 'dashboard'; state.loading = false; state.notice = ''; data = sampleData();
  location.hash = '';
  render();
  if (message) showAuthError(message);
}

function showAuthError(message) {
  const el = document.querySelector('#authError');
  if (!el) return;
  el.textContent = message; el.hidden = false;
}

const field = (selector) => document.querySelector(selector)?.value.trim() ?? '';

async function startSession(user) {
  state.user = user; state.userName = user.name; data = sampleData(); state.notice = '';
  await show();
}

async function signIn(register) {
  const button = document.querySelector('#authBtn');
  const email = field('#email'); const password = document.querySelector('#password')?.value ?? '';
  const remember = document.querySelector('#remember')?.checked ?? false;
  if (register) {
    const name = field('#fullName');
    if (!name || !email) return showAuthError('Please enter your name and email address.');
    if (!document.querySelector('#remember')?.checked) return showAuthError('Please accept the Terms and Conditions.');
    if (password.length < 8) return showAuthError('Password must be at least 8 characters.');
    if (password !== document.querySelector('#confirmPassword')?.value) return showAuthError('Passwords do not match.');
  } else if (!email || !password) {
    return showAuthError('Please enter your email and password.');
  }
  button.disabled = true;
  try {
    if (register) await api.register(field('#fullName'), email, password);
    const result = await api.login(email, password, register ? false : remember);
    await startSession(result.user);
  } catch (err) {
    button.disabled = false;
    if (err.unreachable) return showAuthError('Cannot reach the server. Please make sure the backend is running, then try again.');
    showAuthError(err.status === 422 && !register ? 'Please enter a valid email and password.' : err.message);
  }
}

// Re-fetch the current page's data and repaint without the "Loading…" flash.
async function reload() { await loadData(); render(); }

function applySampleControls(v, patch) {
  const next = { mode: v.mode, capture: v.capture, recording: v.recording, ...patch };
  if (next.mode === 'paused' || !next.capture) next.recording = patch.recording === true ? true : false;
  if (patch.recording === true && !next.capture) { state.notice = 'Enable audio capture before starting a recording.'; return; }
  if (patch.recording === true && next.mode === 'paused') { state.notice = 'Resume monitoring before starting a recording.'; return; }
  Object.assign(v, next); state.notice = 'Backend unavailable — showing sample data.';
}

async function setControls(patch) {
  const v = currentVehicle();
  if (v === NO_VEHICLE) return;
  if (!data.live) {
    applySampleControls(v, { ...('monitoring_mode' in patch && { mode: patch.monitoring_mode }), ...('audio_capture_enabled' in patch && { capture: patch.audio_capture_enabled }), ...('recording' in patch && { recording: patch.recording }) });
    return render();
  }
  try {
    await api.updateControls(v.code, patch);
    await reload();
  } catch (err) {
    if (err.status === 401) return endSession('Your session has expired. Please sign in again.');
    state.notice = err.message; render();
  }
}

async function viewAudio() {
  const a = data.alert;
  if (!a) return;
  if (!data.live) state.notice = 'Sample data: no audio record is available.';
  else if (!a.audioId) state.notice = 'This alert was created manually and has no linked audio record.';
  else {
    try {
      const r = await api.audioRecord(a.audioId);
      const result = r.analysis ? ` · ${cap(r.analysis.predicted_class)} (${percent(r.analysis.confidence * 100)})` : '';
      state.notice = `Audio record: ${r.file_name} · ${cap(r.processing_status)}${result} · ${r.storage_url}`;
    } catch (err) { state.notice = err.message; }
  }
  render();
}

async function alertAction(kind) {
  const a = data.alert;
  if (!a) return;
  if (!data.live || !a.id) { a.status = kind === 'resolve' ? 'Resolved' : 'Acknowledged'; render(); return; }
  try {
    await (kind === 'resolve' ? api.resolveAlert(a.id) : api.acknowledgeAlert(a.id));
    state.notice = '';
    await reload();
  } catch (err) {
    if (err.status === 401) return endSession('Your session has expired. Please sign in again.');
    state.notice = err.message; render();
  }
}

async function fleetAction(action, successMessage = '') {
  try {
    await action();
    await loadData();
    state.notice = successMessage;
    render();
  } catch (err) {
    if (err.status === 401) return endSession('Your session has expired. Please sign in again.');
    state.notice = err.message;
    render();
  }
}

function formObject(form) { return Object.fromEntries(new FormData(form)); }

function bindFleet() {
  document.querySelectorAll('[data-device-id]').forEach((button) => button.addEventListener('click', async () => { state.deviceId = button.dataset.deviceId; await show(); }));
  document.querySelector('#vehicleCreateForm')?.addEventListener('submit', (event) => { event.preventDefault(); const values = formObject(event.currentTarget); values.vin = values.vin.toUpperCase(); values.license_plate = values.license_plate.toUpperCase(); fleetAction(async () => { const created = await api.createVehicle({ ...values, status: 'disconnected' }); state.vehicle = created.vehicle_code; state.deviceId = null; }, 'Vehicle registered.'); });
  document.querySelector('#vehicleUpdateForm')?.addEventListener('submit', (event) => { event.preventDefault(); const values = formObject(event.currentTarget); values.vin = values.vin.toUpperCase(); values.license_plate = values.license_plate.toUpperCase(); fleetAction(() => api.updateVehicle(state.vehicle, values), 'Vehicle updated.'); });
  document.querySelector('#removeVehicleBtn')?.addEventListener('click', () => { if (confirm('Remove this vehicle? Associated devices will be detached and retired.')) fleetAction(async () => { await api.removeVehicle(state.vehicle); state.deviceId = null; }, 'Vehicle removed; device history was retained.'); });
  document.querySelector('#deviceCreateForm')?.addEventListener('submit', (event) => { event.preventDefault(); const values = formObject(event.currentTarget); if (!values.firmware_version) values.firmware_version = null; fleetAction(async () => { const created = await api.createDevice(state.vehicle, values); state.deviceId = created.id; }, 'Device registered in PENDING state.'); });
  document.querySelector('#deviceUpdateForm')?.addEventListener('submit', (event) => { event.preventDefault(); const values = formObject(event.currentTarget); if (!values.firmware_version) values.firmware_version = null; fleetAction(() => api.updateDevice(state.deviceId, values), 'Device updated.'); });
  document.querySelector('#deviceConfigurationForm')?.addEventListener('submit', (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const configuration = { captureEnabled: form.has('captureEnabled'), monitoringMode: form.get('monitoringMode'), heartbeatIntervalSeconds: Number(form.get('heartbeatIntervalSeconds')) }; fleetAction(() => api.updateDeviceConfiguration(state.deviceId, configuration), 'Device settings updated.'); });
  document.querySelector('#heartbeatForm')?.addEventListener('submit', (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const metrics = {}; if (form.get('batteryPercent')) metrics.batteryPercent = Number(form.get('batteryPercent')); if (form.get('temperatureCelsius')) metrics.temperatureCelsius = Number(form.get('temperatureCelsius')); fleetAction(() => api.heartbeat(state.deviceId, { health: form.get('health'), metrics }), 'Heartbeat received.'); });
  document.querySelector('#audioSimulationForm')?.addEventListener('submit', async (event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const audio = form.get('audio'); if (!(audio instanceof File) || !audio.size) { state.notice = 'Choose a WAV file first.'; return render(); } try { const result = await api.classifyDeviceAudio(state.deviceId, audio, String(form.get('location') || '').trim()); await loadData(); const alert = result.alertId ? ' · simulated alert created' : ' · no alert (normal or below threshold)'; state.notice = `${cap(result.eventType)} · ${percent(result.confidence * 100)} confidence · ${result.modelVersion}${alert}`; render(); } catch (err) { if (err.status === 401) return endSession('Your session has expired. Please sign in again.'); state.notice = err.message; render(); } });
  document.querySelector('#disableDeviceBtn')?.addEventListener('click', () => { if (confirm('Disable this device? Heartbeats will not reactivate it.')) fleetAction(() => api.updateDevice(state.deviceId, { state: 'DISABLED' }), 'Device disabled.'); });
  document.querySelector('#retireDeviceBtn')?.addEventListener('click', () => { if (confirm('Retire this device permanently?')) fleetAction(() => api.updateDevice(state.deviceId, { state: 'RETIRED' }), 'Device retired.'); });
  document.querySelector('#removeDeviceBtn')?.addEventListener('click', () => { if (confirm('Remove this device from active inventory while preserving history?')) fleetAction(async () => { await api.removeDevice(state.deviceId); state.deviceId = null; }, 'Device removed; heartbeat history was retained.'); });
}

function bind() {
  document.querySelectorAll('[data-page]').forEach((b) => b.addEventListener('click', () => { if (b.dataset.vehicle) { state.vehicle = b.dataset.vehicle; state.alertId = null; } navigate(b.dataset.page); }));
  const top = document.querySelector('#vehicleTop');
  if (top) top.addEventListener('change', (e) => { state.vehicle = e.target.value; state.deviceId = null; state.alertId = null; state.notice = ''; show(); });
  const profileBtn = document.querySelector('#profileMenuBtn'); const accountMenu = document.querySelector('#accountMenu');
  if (profileBtn && accountMenu) profileBtn.addEventListener('click', (e) => { e.stopPropagation(); const isOpen = !accountMenu.hasAttribute('hidden'); if (isOpen) { accountMenu.setAttribute('hidden', ''); } else { accountMenu.removeAttribute('hidden'); } profileBtn.setAttribute('aria-expanded', String(!isOpen)); });
  document.querySelector('#logoutBtn')?.addEventListener('click', () => endSession());
  document.addEventListener('click', () => { if (accountMenu && !accountMenu.hasAttribute('hidden')) { accountMenu.setAttribute('hidden', ''); profileBtn?.setAttribute('aria-expanded', 'false'); } }, { once: true });
  document.querySelector('#authBtn')?.addEventListener('click', () => signIn(Boolean(document.querySelector('#fullName'))));
  document.querySelectorAll('.auth-card input').forEach((input) => input.addEventListener('keydown', (e) => { if (e.key === 'Enter') document.querySelector('#authBtn').click(); }));
  document.querySelector('#switchAuth')?.addEventListener('click', () => { const register = !document.querySelector('#fullName'); app.innerHTML = login(register); bind(); });
  document.querySelector('#ackBtn')?.addEventListener('click', () => alertAction('acknowledge'));
  document.querySelector('#resolveBtn')?.addEventListener('click', () => alertAction('resolve'));
  document.querySelector('#recordBtn')?.addEventListener('click', () => setControls({ recording: !currentVehicle().recording }));
  document.querySelector('#pauseBtn')?.addEventListener('click', () => setControls({ monitoring_mode: currentVehicle().mode === 'paused' ? 'continuous' : 'paused' }));
  document.querySelector('#captureToggle')?.addEventListener('click', () => setControls({ audio_capture_enabled: !currentVehicle().capture }));
  document.querySelector('#modeSelect')?.addEventListener('change', (e) => setControls({ monitoring_mode: e.target.value }));
  document.querySelector('#audioBtn')?.addEventListener('click', viewAudio);
  document.querySelector('#alertPick')?.addEventListener('change', (e) => { state.alertId = e.target.value; reload(); });
  document.querySelector('#forgot')?.addEventListener('click', () => showAuthError('Password reset is not available yet. Please ask an administrator to reset your password.'));
  document.querySelector('#refreshBtn')?.addEventListener('click', async () => { await reload(); if (!state.notice && data.live) state.notice = 'Status refreshed.'; render(); });
  document.querySelector('#mapFilter')?.addEventListener('change', (e) => { state.mapVehicle = e.target.value; if (state.mapVehicle !== 'All Vehicles') state.vehicle = state.mapVehicle; render(); });
  document.querySelector('#applyFilters')?.addEventListener('click', () => { state.filters = { vehicle: field('#fVehicle'), range: field('#fRange'), type: field('#fType') }; show(); });
  bindFleet();
}

window.addEventListener('hashchange', () => { const page = location.hash.replace('#/', '') || 'dashboard'; if (state.user && page !== state.page) { state.page = page; show(); } });

async function restoreSession() {
  if (!api.hasToken()) return;
  try {
    await startSession(await api.me());
  } catch (err) {
    if (err.status === 401) tokenStore.clear();
  }
}

render();
restoreSession();
