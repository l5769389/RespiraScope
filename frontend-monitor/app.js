import { createChartModule } from "./modules/chart.js?v=monitor-scan-20260525-11";
import { createRecordModule } from "./modules/record.js?v=monitor-scan-20260525-11";
import { createSocketModule } from "./modules/socket.js?v=monitor-scan-20260525-11";
import { createStatusModule } from "./modules/status.js?v=monitor-scan-20260525-11";

const runtimeConfig = window.CT_BREATH_RUNTIME_CONFIG || {};
function isLoopbackHost(host) {
  return ["localhost", "127.0.0.1", "::1", "[::1]"].includes(String(host || "").toLowerCase());
}

function resolveBackendHost(configHost) {
  const pageHost = window.location.hostname;
  const host = configHost || pageHost || "127.0.0.1";
  if (isLoopbackHost(host) && pageHost && !isLoopbackHost(pageHost)) {
    return pageHost;
  }
  return host;
}

const backendHost = resolveBackendHost(runtimeConfig.backendHost);
const backendPort = runtimeConfig.backendPort || 8000;
const API_BASE = `http://${backendHost}:${backendPort}`;
const SOCKET_URL = `${API_BASE}/breath`;
const LANGUAGE_KEY = "RespiraScope-language";
const MAX_POINTS = 30000;
const RECORD_MAX_POINTS = 180000;
const DISPLAY_WINDOW = 1500;
const LIVE_POINT_RATIO = 0.86;
const FILTER_STARTUP_POINTS = 300;
const FILTER_MARKER_WARMUP_POINTS = 75;
const INITIAL_DATA_TIMEOUT_MS = 4000;
const NO_DATA_WARNING_MS = 6000;
const NO_DATA_CHECK_MS = 2000;
const recordRuntimeConfig = runtimeConfig.record || {};
const RECORD_PRE_POINTS = Math.max(0, Math.floor(Number(recordRuntimeConfig.prePoints ?? recordRuntimeConfig.pre_points ?? 100) || 0));
const RECORD_POST_POINTS = Math.max(0, Math.floor(Number(recordRuntimeConfig.postPoints ?? recordRuntimeConfig.post_points ?? 100) || 0));
const POST_RECORD_TIMEOUT_MS = 8000;
const CONFIRMATION_DELAY_POINTS = Math.max(0, Math.floor(Number(runtimeConfig.confirmationDelayPoints ?? 12) || 0));
const DATA_GAP_RESET_POINTS = Math.max(1, Math.floor(Number(runtimeConfig.dataGapResetPoints ?? 25) || 0));
const LIVE_RIGHT_PADDING_RATIO = 1 - LIVE_POINT_RATIO;
const Y_AXIS_PADDING_RATIO = 0.12;
const Y_AXIS_MIN_SPAN = 80;
const RECORD_RANGE_ACTIVE_COLOR = "rgba(245, 158, 11, 0.16)";
const RECORD_RANGE_DONE_COLOR = "rgba(20, 184, 166, 0.12)";
const SCAN_RANGE_ACTIVE_COLOR = "rgba(37, 99, 235, 0.2)";
const SCAN_RANGE_DONE_COLOR = "rgba(37, 99, 235, 0.14)";
const TRANSLATIONS = {
  zh: {
    "monitor.title": "呼吸监测",
    "language.label": "语言",
    "button.startMonitoring": "开始监测",
    "button.recordStart": "开始记录",
    "button.scanStart": "开始扫描",
    "button.scanEnd": "结束扫描",
    "button.recordEnd": "结束记录",
    "button.saveRecord": "保存记录",
    "button.loadRecord": "加载记录",
    "button.pauseView": "暂停视图",
    "button.resumeView": "恢复视图",
    "button.reset": "重置",
    "follow.live": "实时跟随",
    "follow.review": "回看模式",
    "chart.realtimeTitle": "实时波形",
    "chart.realtimeSubtitle": "后端实时发送的原始、滤波、波峰与波谷信号",
    "field.smoothing": "平滑",
    "field.confirmPeaks": "延迟确认峰谷",
    "smoothing.auto": "自动",
    "smoothing.off": "关闭",
    "smoothing.light": "轻度",
    "smoothing.medium": "中等",
    "smoothing.strong": "强",
    "legend.raw": "原始",
    "legend.filtered": "滤波",
    "legend.peak": "波峰",
    "legend.valley": "波谷",
    "legend.recorded": "记录区间",
    "legend.scan": "扫描区间",
    "statusPanel.status": "状态",
    "statusPanel.stability": "稳定性",
    "statusPanel.intervalCv": "间隔 CV",
    "statusPanel.rawPoints": "原始点数",
    "statusPanel.filteredPoints": "滤波点数",
    "details.signalWindow": "信号窗口",
    "details.recordFile": "记录文件",
    "details.recordFileHint": "保存或加载一段记录",
    "details.lastUpdate": "最后更新",
    "record.title": "记录片段",
    "connection.disconnected": "未连接",
    "connection.connected": "已连接",
    "connection.error": "连接错误",
    "connection.waiting": "等待数据",
    "connection.receiving": "正在接收数据",
    "connection.startBackendUnreachable": "启动失败：后端不可达",
    "connection.startHttp": "启动失败：HTTP {status}",
    "connection.startSensorNotConnected": "启动失败：传感器未连接{detail}",
    "connection.sensorDisconnected": "传感器已断开{detail}",
    "connection.startNoData": "启动失败：没有呼吸数据",
    "connection.noData": "没有呼吸数据",
    "connection.noRecentData": "近期没有呼吸数据",
    "connection.filterUpdateFailed": "滤波参数更新失败",
    "quality.stable": "稳定",
    "quality.variable": "波动",
    "quality.irregular": "不规则",
    "quality.insufficient": "数据不足",
    "hint.waitingEnoughBreaths": "等待足够呼吸周期",
    "hint.intervalVariation": "呼吸间隔的变化程度",
    "hint.regular": "呼吸节律规律",
    "hint.someVariation": "节律存在一定波动",
    "hint.irregular": "检测到不规则节律",
    "hint.needsTwoPeaks": "至少需要两个已检测波峰",
    "hint.stableCv": "稳定：呼吸间隔变化低于 15%",
    "hint.variableCv": "波动：呼吸间隔变化在 15%-35%",
    "hint.irregularCv": "不规则：呼吸间隔变化高于 35%",
    "window.samples": "{start} - {end} 点",
    "window.review": "回看模式",
    "chart.value": "值",
    "series.raw": "原始",
    "series.filtered": "滤波",
    "series.peak": "波峰",
    "series.valley": "波谷",
    "record.status.idle": "空闲",
    "record.status.recording": "记录中",
    "record.status.postCapture": "后置采集中",
    "record.status.filtering": "滤波中",
    "record.status.tooShort": "数据过短",
    "record.status.liveCapture": "实时采集",
    "record.status.localRecord": "本地记录",
    "record.status.offlineFiltered": "离线滤波完成",
    "record.status.loadedFile": "已加载文件",
    "record.status.loadFailed": "加载失败",
    "record.status.recorded": "已记录",
    "record.file.none": "无已加载文件",
    "record.index.empty": "索引 -",
    "record.index.range": "记录 {start} - {end}",
    "record.index.rangeWithFile": "记录 {start} - {end} / 文件 {fileStart} - {fileEnd}",
    "record.scans.empty": "扫描 -",
    "record.scans.count": "{count} 次扫描",
    "record.scans.detail": "{count} 次扫描：{ranges}",
    "record.time.empty": "时间 -",
    "record.time.range": "时间 {start} - {end}",
    "record.points": "{count} 点",
    "record.pointsWithPadding": "{count} 点（前置 {pre} / 后置 {post}）",
    "record.error.noWaveform": "文件中没有波形数据",
    "record.range.recording": "记录中",
    "record.range.postCapture": "后置采集中",
    "record.range.recorded": "已记录",
    "record.range.scan": "扫描 #{index}",
    "record.range.scanActive": "扫描 #{index} 中",
    "duration.seconds": "{seconds}s",
    "duration.minutesSeconds": "{minutes}m {seconds}s",
  },
  en: {
    "monitor.title": "Breath Monitor",
    "language.label": "Language",
    "button.startMonitoring": "Start Monitoring",
    "button.recordStart": "Record Start",
    "button.scanStart": "Scan Start",
    "button.scanEnd": "Scan End",
    "button.recordEnd": "Record End",
    "button.saveRecord": "Save Record",
    "button.loadRecord": "Load Record",
    "button.pauseView": "Pause View",
    "button.resumeView": "Resume View",
    "button.reset": "Reset",
    "follow.live": "Live Follow",
    "follow.review": "Review Mode",
    "chart.realtimeTitle": "Realtime Waveform",
    "chart.realtimeSubtitle": "Live raw, filtered, peak, and valley signals",
    "field.smoothing": "Smoothing",
    "field.confirmPeaks": "Confirm Peaks",
    "smoothing.auto": "Auto",
    "smoothing.off": "Off",
    "smoothing.light": "Light",
    "smoothing.medium": "Medium",
    "smoothing.strong": "Strong",
    "legend.raw": "Raw",
    "legend.filtered": "Filtered",
    "legend.peak": "Peak",
    "legend.valley": "Valley",
    "legend.recorded": "Recorded range",
    "legend.scan": "Scan range",
    "statusPanel.status": "Status",
    "statusPanel.stability": "Stability",
    "statusPanel.intervalCv": "Interval CV",
    "statusPanel.rawPoints": "Raw Points",
    "statusPanel.filteredPoints": "Filtered Points",
    "details.signalWindow": "Signal Window",
    "details.recordFile": "Record File",
    "details.recordFileHint": "save or load a recorded segment",
    "details.lastUpdate": "Last Update",
    "record.title": "Recorded Segment",
    "connection.disconnected": "Disconnected",
    "connection.connected": "Connected",
    "connection.error": "Connection Error",
    "connection.waiting": "Waiting for Data",
    "connection.receiving": "Receiving Data",
    "connection.startBackendUnreachable": "Start Failed: Backend Unreachable",
    "connection.startHttp": "Start Failed: HTTP {status}",
    "connection.startSensorNotConnected": "Start Failed: Sensor Not Connected{detail}",
    "connection.sensorDisconnected": "Sensor Disconnected{detail}",
    "connection.startNoData": "Start Failed: No Breath Data",
    "connection.noData": "No Breath Data",
    "connection.noRecentData": "No Recent Breath Data",
    "connection.filterUpdateFailed": "Filter Update Failed",
    "quality.stable": "Stable",
    "quality.variable": "Variable",
    "quality.irregular": "Irregular",
    "quality.insufficient": "Insufficient",
    "hint.waitingEnoughBreaths": "waiting for enough breaths",
    "hint.intervalVariation": "variation between breath intervals",
    "hint.regular": "regular breathing rhythm",
    "hint.someVariation": "some rhythm variation",
    "hint.irregular": "irregular rhythm detected",
    "hint.needsTwoPeaks": "needs at least two detected peaks",
    "hint.stableCv": "stable: breath intervals vary less than 15%",
    "hint.variableCv": "variable: interval variation is 15%-35%",
    "hint.irregularCv": "irregular: interval variation is above 35%",
    "window.samples": "{start} - {end} samples",
    "window.review": "Review mode",
    "chart.value": "Value",
    "series.raw": "Raw",
    "series.filtered": "Filtered",
    "series.peak": "Peak",
    "series.valley": "Valley",
    "record.status.idle": "Idle",
    "record.status.recording": "Recording",
    "record.status.postCapture": "Post Capture",
    "record.status.filtering": "Filtering",
    "record.status.tooShort": "Too Short",
    "record.status.liveCapture": "Live Capture",
    "record.status.localRecord": "Local Record",
    "record.status.offlineFiltered": "Offline Filtered",
    "record.status.loadedFile": "Loaded File",
    "record.status.loadFailed": "Load Failed",
    "record.status.recorded": "Recorded",
    "record.file.none": "No file loaded",
    "record.index.empty": "Index -",
    "record.index.range": "Record {start} - {end}",
    "record.index.rangeWithFile": "Record {start} - {end} / File {fileStart} - {fileEnd}",
    "record.scans.empty": "Scans -",
    "record.scans.count": "{count} scans",
    "record.scans.detail": "{count} scans: {ranges}",
    "record.time.empty": "Time -",
    "record.time.range": "Time {start} - {end}",
    "record.points": "{count} points",
    "record.pointsWithPadding": "{count} points ({pre} pre / {post} post)",
    "record.error.noWaveform": "No waveform data in file",
    "record.range.recording": "Recording",
    "record.range.postCapture": "Post Capture",
    "record.range.recorded": "Recorded",
    "record.range.scan": "Scan #{index}",
    "record.range.scanActive": "Scan #{index}",
    "duration.seconds": "{seconds}s",
    "duration.minutesSeconds": "{minutes}m {seconds}s",
  },
};

const DEFAULT_FILTER_CONFIG = {
  low_bpm: 6,
  high_bpm: 40,
  order: 1,
  gaussian_sigma: 1.8,
  auto_peak_detection: true,
  peak_threshold_ratio: 0.3,
  prominence: 1,
  confirm_realtime_events: false,
  confirmation_delay_points: CONFIRMATION_DELAY_POINTS,
  data_gap_reset_points: DATA_GAP_RESET_POINTS,
  gap_warmup_points: FILTER_MARKER_WARMUP_POINTS,
};

const state = {
  socket: null,
  running: false,
  paused: false,
  followLive: true,
  smoothingMode: "auto",
  ignoreDataZoomEvent: false,
  renderScheduled: false,
  lastRenderMode: null,
  pendingReviewRange: null,
  sequenceOrigin: null,
  liveYAxis: null,
  filterConfig: null,
  lastRawAt: null,
  hasReceivedData: false,
  initialDataTimer: null,
  noDataTimer: null,
  postRecordTimer: null,
  raw: [],
  filtered: [],
  peaks: [],
  valleys: [],
  recording: false,
  resettingRecord: false,
  activeRecord: null,
  lastRecord: null,
  metrics: {
    bpm: null,
    quality: "-",
    breath_count: 0,
    interval_cv: null,
  },
};

const dom = {
  shell: document.querySelector(".monitor-shell"),
  languageSelect: document.querySelector("#languageSelect"),
  startBtn: document.querySelector("#startBtn"),
  recordStartBtn: document.querySelector("#recordStartBtn"),
  scanStartBtn: document.querySelector("#scanStartBtn"),
  scanEndBtn: document.querySelector("#scanEndBtn"),
  recordEndBtn: document.querySelector("#recordEndBtn"),
  pauseBtn: document.querySelector("#pauseBtn"),
  resetBtn: document.querySelector("#resetBtn"),
  followBtn: document.querySelector("#followBtn"),
  saveRecordBtn: document.querySelector("#saveRecordBtn"),
  loadRecordBtn: document.querySelector("#loadRecordBtn"),
  loadRecordInput: document.querySelector("#loadRecordInput"),
  smoothingSelect: document.querySelector("#smoothingSelect"),
  confirmRealtimeEvents: document.querySelector("#confirmRealtimeEvents"),
  connectionStatus: document.querySelector("#connectionStatus"),
  bpmValue: document.querySelector("#bpmValue"),
  qualityValue: document.querySelector("#qualityValue"),
  stabilityHintValue: document.querySelector("#stabilityHintValue"),
  intervalCvHintValue: document.querySelector("#intervalCvHintValue"),
  rawCountValue: document.querySelector("#rawCountValue"),
  filteredCountValue: document.querySelector("#filteredCountValue"),
  windowValue: document.querySelector("#windowValue"),
  intervalCvValue: document.querySelector("#intervalCvValue"),
  recordFileValue: document.querySelector("#recordFileValue"),
  lastUpdateValue: document.querySelector("#lastUpdateValue"),
  recordSection: document.querySelector("#recordSection"),
  recordStatus: document.querySelector("#recordStatus"),
  recordDuration: document.querySelector("#recordDuration"),
  recordIndexRange: document.querySelector("#recordIndexRange"),
  recordScanRange: document.querySelector("#recordScanRange"),
  recordTimeRange: document.querySelector("#recordTimeRange"),
  recordPointCount: document.querySelector("#recordPointCount"),
  waveChart: document.querySelector("#waveChart"),
  recordChart: document.querySelector("#recordChart"),
};

let language = preferredLanguage();

function preferredLanguage() {
  const saved = localStorage.getItem(LANGUAGE_KEY);
  if (saved === "zh" || saved === "en") {
    return saved;
  }
  return navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function t(key, params = {}) {
  const template = TRANSLATIONS[language]?.[key] ?? TRANSLATIONS.en[key] ?? key;
  return Object.entries(params).reduce((text, [name, value]) => text.replaceAll(`{${name}}`, value), template);
}

function setConnectionStatus(key, params = {}) {
  dom.connectionStatus.dataset.statusKey = key;
  dom.connectionStatus.dataset.statusParams = JSON.stringify(params);
  dom.connectionStatus.textContent = t(key, params);
}

function getCurrentLanguage() {
  return language;
}

function buildFilterConfig(overrides = {}) {
  const config = {
    ...DEFAULT_FILTER_CONFIG,
    confirm_realtime_events: Boolean(dom.confirmRealtimeEvents?.checked),
    confirmation_delay_points: CONFIRMATION_DELAY_POINTS,
    ...overrides,
  };
  return {
    ...config,
    lowpass_cutoff: config.low_bpm / 60,
    highpass_cutoff: config.high_bpm / 60,
  };
}

function trimSeries(series, maxPoints = MAX_POINTS) {
  if (series.length > maxPoints) {
    series.splice(0, series.length - maxPoints);
  }
}

function pointSequence(point) {
  return Array.isArray(point) ? Number(point[0]) : Number(point?.sequence);
}

function displaySequence(sequence) {
  const numeric = Number(sequence);
  if (!Number.isFinite(numeric)) {
    return numeric;
  }
  if (state.sequenceOrigin === null) {
    state.sequenceOrigin = numeric;
  }
  return Math.max(0, numeric - state.sequenceOrigin);
}

function normalizePoint(point, origin) {
  const sourceSequence = Array.isArray(point) ? point[0] : point?.sequence;
  const sequence = Number.isFinite(origin) ? Number(sourceSequence) - origin : displaySequence(sourceSequence);
  if (Array.isArray(point)) {
    return [sequence, Number(point[1])];
  }
  return [sequence, Number(point.value)];
}

function normalizeSeries(points, origin) {
  if (!Array.isArray(points)) {
    return [];
  }
  return points.map((point) => normalizePoint(point, origin)).filter((point) => Number.isFinite(point[0]) && Number.isFinite(point[1]));
}

function appendSeries(series, batch, recordKey) {
  const normalized = normalizeSeries(batch);
  if (normalized.length === 0) {
    return 0;
  }

  series.push(...normalized);
  trimSeries(series);

  if (state.recording && recordKey) {
    recordApi.appendRecordSeries(recordKey, normalized);
  }

  return normalized.length;
}

function copySeriesRange(series, minSeq, maxSeq) {
  if (!Array.isArray(series) || !Number.isFinite(minSeq) || !Number.isFinite(maxSeq)) {
    return [];
  }
  return series.filter((point) => {
    const sequence = pointSequence(point);
    return Number.isFinite(sequence) && sequence >= minSeq && sequence <= maxSeq;
  });
}

state.filterConfig = buildFilterConfig();

function togglePause() {
  state.paused = !state.paused;
  dom.pauseBtn.textContent = state.paused ? t("button.resumeView") : t("button.pauseView");
  if (!state.paused) {
    chartApi.scheduleRender(true);
  }
}

async function resetBackendRecord() {
  const response = await fetch(`${API_BASE}/record/reset`, { method: "POST" });
  if (!response.ok) {
    throw new Error(`record/reset ${response.status}`);
  }
}

async function resetData({ syncBackend = false } = {}) {
  state.resettingRecord = syncBackend;
  if (syncBackend) {
    recordApi.updateRecordButtons();
  }
  statusApi.clearDataWatch();
  state.raw = [];
  state.filtered = [];
  state.peaks = [];
  state.valleys = [];
  state.paused = false;
  state.followLive = true;
  state.ignoreDataZoomEvent = false;
  state.renderScheduled = false;
  state.pendingReviewRange = null;
  state.lastRenderMode = null;
  state.sequenceOrigin = null;
  state.liveYAxis = null;
  state.lastRawAt = null;
  state.hasReceivedData = false;
  state.metrics = {
    bpm: null,
    quality: "-",
    breath_count: 0,
    interval_cv: null,
  };
  dom.pauseBtn.textContent = t("button.pauseView");
  recordApi.resetRecordState();
  dom.recordFileValue.dataset.recordFileKey = "record.file.none";
  dom.recordFileValue.textContent = t("record.file.none");
  chartApi.clearCharts();
  chartApi.updateFollowButton();
  statusApi.updateStats();
  chartApi.scheduleRender(true);

  try {
    if (syncBackend) {
      await resetBackendRecord();
    }
  } catch (error) {
    recordApi.setRecordStatus("Local Record");
  } finally {
    state.resettingRecord = false;
    recordApi.updateRecordButtons();
    if (state.running) {
      statusApi.startDataWatch();
    }
  }
}

const recordApiRef = {};
const moduleContext = {
  API_BASE,
  DISPLAY_WINDOW,
  DATA_GAP_RESET_POINTS,
  FILTER_MARKER_WARMUP_POINTS,
  FILTER_STARTUP_POINTS,
  INITIAL_DATA_TIMEOUT_MS,
  LIVE_RIGHT_PADDING_RATIO,
  NO_DATA_CHECK_MS,
  NO_DATA_WARNING_MS,
  POST_RECORD_TIMEOUT_MS,
  RECORD_MAX_POINTS,
  RECORD_POST_POINTS,
  RECORD_PRE_POINTS,
  RECORD_RANGE_ACTIVE_COLOR,
  RECORD_RANGE_DONE_COLOR,
  SCAN_RANGE_ACTIVE_COLOR,
  SCAN_RANGE_DONE_COLOR,
  SOCKET_URL,
  Y_AXIS_MIN_SPAN,
  Y_AXIS_PADDING_RATIO,
  appendSeries,
  buildFilterConfig,
  copySeriesRange,
  dom,
  getCurrentLanguage,
  normalizeSeries,
  pointSequence,
  recordApi: recordApiRef,
  resetData,
  setConnectionStatus,
  state,
  t,
  trimSeries,
};

const chartApi = createChartModule(moduleContext);
moduleContext.chartApi = chartApi;
const recordApi = createRecordModule(moduleContext);
Object.assign(recordApiRef, recordApi);
const statusApi = createStatusModule(moduleContext);
moduleContext.statusApi = statusApi;
const socketApi = createSocketModule(moduleContext);

function translatePage(nextLanguage = language) {
  language = nextLanguage;
  localStorage.setItem(LANGUAGE_KEY, language);
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.title = t("monitor.title");
  if (dom.languageSelect) {
    dom.languageSelect.value = language;
  }
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });

  const statusKey = dom.connectionStatus.dataset.statusKey;
  if (statusKey) {
    const statusParams = dom.connectionStatus.dataset.statusParams
      ? JSON.parse(dom.connectionStatus.dataset.statusParams)
      : {};
    dom.connectionStatus.textContent = t(statusKey, statusParams);
  }

  const recordFileKey = dom.recordFileValue.dataset.recordFileKey;
  if (recordFileKey) {
    dom.recordFileValue.textContent = t(recordFileKey);
  }

  dom.pauseBtn.textContent = state.paused ? t("button.resumeView") : t("button.pauseView");
  recordApi.refreshLanguage?.();
  statusApi.updateStats();
  chartApi.updateFollowButton();
  chartApi.scheduleRender(true);
  chartApi.renderRecord();
}

chartApi.attachChartEvents();

dom.startBtn.addEventListener("click", () => {
  socketApi.startMonitoring().catch((error) => {
    statusApi.clearDataWatch();
    state.running = false;
    if (error.statusKey) {
      setConnectionStatus(error.statusKey, error.statusParams ?? {});
    } else {
      dom.connectionStatus.dataset.statusKey = "";
      dom.connectionStatus.textContent = error.message;
    }
    recordApi.updateRecordButtons();
  });
});
dom.recordStartBtn.addEventListener("click", recordApi.startRecord);
dom.scanStartBtn.addEventListener("click", () => {
  recordApi.startScan().catch(() => {
    recordApi.setRecordStatus("Local Record");
  });
});
dom.scanEndBtn.addEventListener("click", () => {
  recordApi.endScan().catch(() => {
    recordApi.setRecordStatus("Local Record");
  });
});
dom.recordEndBtn.addEventListener("click", () => {
  recordApi.endRecord().catch(() => {
    recordApi.setRecordStatus("Live Capture");
    chartApi.renderRecord();
  });
});
dom.saveRecordBtn.addEventListener("click", recordApi.downloadRecord);
dom.loadRecordBtn.addEventListener("click", () => {
  dom.loadRecordInput.click();
});
dom.loadRecordInput.addEventListener("change", (event) => {
  recordApi.loadRecordFile(event.target.files?.[0]);
});
dom.pauseBtn.addEventListener("click", togglePause);
dom.resetBtn.addEventListener("click", () => resetData({ syncBackend: true }));
dom.followBtn.addEventListener("click", () => {
  state.followLive = true;
  state.pendingReviewRange = null;
  chartApi.updateFollowButton();
  chartApi.scheduleRender(true);
});
dom.smoothingSelect.addEventListener("change", (event) => {
  state.smoothingMode = event.target.value;
  chartApi.scheduleRender(true);
  chartApi.renderRecord();
});
dom.confirmRealtimeEvents?.addEventListener("change", () => {
  state.filterConfig = buildFilterConfig();
  if (state.running) {
    fetch(`${API_BASE}/setRTFilterParams`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.filterConfig),
    }).catch(() => {
      setConnectionStatus("connection.filterUpdateFailed");
    });
  }
});
dom.languageSelect?.addEventListener("change", (event) => {
  translatePage(event.target.value);
});
window.addEventListener("resize", () => {
  chartApi.resizeCharts();
});

window.addEventListener("storage", (event) => {
  if (event.key === LANGUAGE_KEY && (event.newValue === "zh" || event.newValue === "en")) {
    translatePage(event.newValue);
  }
});

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin) {
    return;
  }
  if (event.data?.type === "RespiraScope-language" && (event.data.language === "zh" || event.data.language === "en")) {
    translatePage(event.data.language);
  }
});

translatePage(language);
resetData({ syncBackend: true });
