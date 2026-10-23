import {createLowpassRange} from '../shared/band-range.js';
const shared = window.RespiraScopeShared || {};
const runtimeConfig = shared.runtimeConfig || window.CT_BREATH_RUNTIME_CONFIG || {};
function normalizePathPrefix(value) {
  const text = String(value || "").trim();
  if (!text || text === "/") {
    return "";
  }
  const withSlash = text.startsWith("/") ? text : `/${text}`;
  return withSlash.replace(/\/+$/, "");
}

function trimUrl(value) {
  return String(value || "").trim().replace(/\/+$/, "");
}

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
const publicApiBasePath = normalizePathPrefix(runtimeConfig.apiBasePath);
const API_BASE = shared.apiBase || (runtimeConfig.apiBaseUrl
  ? trimUrl(runtimeConfig.apiBaseUrl)
  : publicApiBasePath
    ? `${window.location.origin}${publicApiBasePath}`
    : `http://${backendHost}:${backendPort}`);
const sessionConfig = runtimeConfig.session || {};
const SESSION_HEADER = shared.sessionHeader || sessionConfig.header || "X-RespiraScope-Session";
const SESSION_KEY = shared.sessionKey || "RespiraScope-session";
const SESSION_ID = shared.sessionId || getSessionId();
const SESSION_HEADERS = shared.sessionHeaders || { [SESSION_HEADER]: SESSION_ID };
const SAMPLING_RATE = 50;
const DEMO_SAMPLING_RATE = 25;
const DEMO_SECONDS = 18;
const COLLAPSED_DEMO_COUNT = 5;
const LANGUAGE_KEY = shared.languageKey || "RespiraScope-language";
const FEATURED_SCENARIOS = ["normal", "shallow", "noisy", "apnea", "motion_artifact"];
const SCENARIO_THEME = {
  normal: { color: "#2563eb", soft: "#e8f0ff" },
  tachypnea: { color: "#b42318", soft: "#fff1f2" },
  bradypnea: { color: "#0f766e", soft: "#ecfdf5" },
  shallow: { color: "#6941c6", soft: "#f4f3ff" },
  irregular: { color: "#b54708", soft: "#fffaeb" },
  apnea: { color: "#475467", soft: "#f1f5f9" },
  noisy: { color: "#c2410c", soft: "#fff7ed" },
  motion_artifact: { color: "#0f766e", soft: "#ecfdf5" },
  deep: { color: "#175cd3", soft: "#eff8ff" },
  rapid_shallow: { color: "#be123c", soft: "#fff1f2" },
  baseline_drift: { color: "#854d0e", soft: "#fefce8" },
  periodic_weakening: { color: "#344054", soft: "#f2f4f7" },
  weak_noisy: { color: "#93370d", soft: "#fff7ed" },
  cough_artifact: { color: "#0f766e", soft: "#ecfdf5" },
};
const FALLBACK_THEME = { color: "#2563eb", soft: "#e8f0ff" };
const ICONS = {
  check: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"></path></svg>',
  chevronUp: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m18 15-6-6-6 6"></path></svg>',
  waveform: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12h3l2.2-7 4.4 14 3.2-7H21"></path></svg>',
};

function getSessionId() {
  const existing = sessionStorage.getItem(SESSION_KEY);
  if (existing) {
    return existing;
  }
  const generated = crypto.randomUUID
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
  sessionStorage.setItem(SESSION_KEY, generated);
  return generated;
}

const TRANSLATIONS = {
  zh: {
    "app.kicker": "模拟控制台",
    "app.title": "模拟与滤波",
    "app.subtitle": "选择场景，调整参数，对照原始与滤波波形。",
    "language.label": "语言",
    "button.applyMock": "应用到实时监测",
    "button.preview": "生成预览",
    "field.scenario": "模拟预设",
    "field.bpm": "呼吸频率",
    "field.amplitude": "信号幅值",
    "field.noise": "噪声强度",
    "field.irregularity": "不规则度",
    "field.seconds": "预览时长",
    "field.filterMethod": "滤波方案", "field.bandpass": "带通滤波", "field.lowpass": "保留基线低通",
    "field.bandLow": "带通下限", "field.bandHigh": "低通上限频率", "field.bandHint": "双向低通，保留基线与慢变化。BPM = Hz × 60；方向键微调上限。",
    "sensitivity.conservative": "保守", "sensitivity.standard": "标准", "sensitivity.sensitive": "灵敏",
    "field.lowBpm": "带通下限（BPM）",
    "field.highBpm": "带通上限（BPM）",
    "field.order": "滤波阶数",
    "field.sigma": "高斯平滑 σ",
    "field.peakRatio": "峰谷灵敏度",
    "field.autoPeak": "自动识别峰谷",
    "demo.kicker": "预设波形",
    "demo.title": "选择一个呼吸场景",
    "demo.subtitle": "优先从正常、浅呼吸、噪声、屏气和体动伪影开始，最容易看出滤波和峰谷识别的边界。",
    "demo.selected": "已选",
    "demo.expand": "展开全部",
    "demo.collapse": "收起",
    "demo.viewWaveform": "查看波形",
    "demo.hideWaveform": "收起波形",
    "demo.chooseScenario": "选择预设",
    "panel.mockParameters": "模拟参数", "panel.scope": "模拟参数用于实时信号；以下滤波参数仅用于预览。",
    "chart.hint": "拖动底部滑块缩放，悬停查看数值；点击图例显示或隐藏曲线。",
    "chart.summary": "{scenario} · {seconds} 秒 · {points} 点", "chart.time": "时间（秒）", "chart.value": "幅值",
    "status.pending": "参数已修改，点击“生成预览”更新结果。", "status.ready": "选择场景后生成预览。",
    "status.short": "预览数据不足，请增加时长后重试。", "status.invalidBand": "带通下限必须小于上限。",
    "demo.failed": "示例加载失败，再次展开可重试。", "demo.loading": "加载示例…",
    "panel.mockKicker": "模拟信号",
    "panel.mockTitle": "当前场景",
    "panel.filterKicker": "处理",
    "panel.filterTitle": "离线低通与峰谷识别",
    "metric.bpm": "BPM",
    "metric.quality": "稳定性",
    "metric.breaths": "呼吸次数",
    "stat.amplitude": "幅度",
    "stat.noise": "噪声",
    "stat.irregularity": "波动",
    "chart.kicker": "输出",
    "chart.title": "波形预览",
    "chart.empty": "暂无预览数据。",
    "quality.stable": "稳定",
    "quality.variable": "波动",
    "quality.irregular": "不规则",
    "quality.insufficient": "数据不足",
    "chart.raw": "原始",
    "chart.filtered": "滤波",
    "chart.reference": "滤波参考（不参与分箱）",
    "chart.peaks": "波峰",
    "chart.valleys": "波谷",
    "status.loading": "正在加载预设...",
    "status.loaded": "场景已加载，可生成预览。",
    "status.loadingDemos": "正在生成波形示例...",
    "status.demosReady": "波形示例已更新。",
    "status.apply": "正在应用模拟参数...",
    "status.applied": "已应用：{scenario}，正在打开实时体验。",
    "status.preview": "正在生成预览...",
    "status.filtering": "正在滤波预览...",
    "status.complete": "预览完成。",
    "scenario.normal.name": "正常呼吸",
    "scenario.normal.desc": "节律稳定、幅度适中，适合作为滤波基线。",
    "scenario.tachypnea.name": "呼吸急促",
    "scenario.tachypnea.desc": "BPM 较高、周期更短，用于观察高频呼吸的峰谷识别。",
    "scenario.bradypnea.name": "呼吸过缓",
    "scenario.bradypnea.desc": "BPM 较低、周期更长，用于观察低频呼吸保留情况。",
    "scenario.shallow.name": "浅呼吸",
    "scenario.shallow.desc": "幅度较低，考验滤波后弱峰谷是否仍可识别。",
    "scenario.irregular.name": "不规则呼吸",
    "scenario.irregular.desc": "节律有明显波动，用于观察 BPM 和稳定性变化。",
    "scenario.apnea.name": "屏气/呼吸暂停",
    "scenario.apnea.desc": "中间出现低幅平台段，用于观察断续呼吸与漏检风险。",
    "scenario.noisy.name": "噪声干扰",
    "scenario.noisy.desc": "随机噪声更强，用于对比平滑和峰谷阈值效果。",
    "scenario.motion_artifact.name": "体动伪影",
    "scenario.motion_artifact.desc": "夹杂突发大幅尖峰，用于观察伪峰抑制能力。",
    "scenario.deep.name": "深呼吸",
    "scenario.deep.desc": "低频、大幅度的呼吸波形，用于检查大幅摆动下的滤波保真。",
    "scenario.rapid_shallow.name": "快速浅呼吸",
    "scenario.rapid_shallow.desc": "高频、低幅度的组合，用于观察弱信号和高频节律。",
    "scenario.baseline_drift.name": "基线漂移",
    "scenario.baseline_drift.desc": "基线缓慢上下移动，用于检查趋势漂移对滤波的影响。",
    "scenario.periodic_weakening.name": "周期性减弱",
    "scenario.periodic_weakening.desc": "周期内出现短暂低幅段，用于观察呼吸减弱和恢复。",
    "scenario.weak_noisy.name": "低幅噪声",
    "scenario.weak_noisy.desc": "有效呼吸幅度接近噪声，用于评估弱峰谷识别边界。",
    "scenario.cough_artifact.name": "咳嗽/冲击伪影",
    "scenario.cough_artifact.desc": "较密集的瞬时冲击，用于观察异常尖峰对结果的干扰。",
  },
  en: {
    "app.kicker": "Simulation Console",
    "app.title": "Simulation and Filtering",
    "app.subtitle": "Choose a scenario, adjust parameters, and compare raw and filtered signals.",
    "language.label": "Language",
    "button.applyMock": "Apply to Live Monitor",
    "button.preview": "Generate Preview",
    "field.scenario": "Preset",
    "field.bpm": "Breathing rate",
    "field.amplitude": "Amplitude",
    "field.noise": "Noise",
    "field.irregularity": "Irregularity",
    "field.seconds": "Preview duration",
    "field.filterMethod": "Filter method", "field.bandpass": "Band-pass filter", "field.lowpass": "Preserve baseline low-pass",
    "field.bandLow": "Lower cutoff", "field.bandHigh": "Low-pass cutoff", "field.bandHint": "BPM = Hz × 60. Low-pass retains baseline and slow changes; upper cutoff only.",
    "sensitivity.conservative": "Conservative", "sensitivity.standard": "Standard", "sensitivity.sensitive": "Sensitive",
    "field.lowBpm": "Lower cutoff (BPM)",
    "field.highBpm": "Upper cutoff (BPM)",
    "field.order": "Order",
    "field.sigma": "Gaussian Sigma",
    "field.peakRatio": "Peak sensitivity",
    "field.autoPeak": "Auto peak detection",
    "demo.kicker": "Preset Waveforms",
    "demo.title": "Choose a Breathing Scenario",
    "demo.subtitle": "Start with normal, shallow, noisy, apnea, and motion artifact scenes to see the filtering and peak-detection boundaries.",
    "demo.selected": "Selected",
    "demo.expand": "Show All",
    "demo.collapse": "Collapse",
    "demo.viewWaveform": "View Waveform",
    "demo.hideWaveform": "Hide Waveform",
    "demo.chooseScenario": "Choose Preset",
    "panel.mockParameters": "Signal parameters", "panel.scope": "Signal parameters apply to live monitoring; filter settings below affect this preview only.",
    "chart.hint": "Drag the lower slider to zoom, hover for values, and click the legend to toggle curves.",
    "chart.summary": "{scenario} · {seconds} s · {points} points", "chart.time": "Time (s)", "chart.value": "Amplitude",
    "status.pending": "Parameters changed. Generate a preview to update the result.", "status.ready": "Choose a scenario and generate a preview.",
    "status.short": "Not enough preview data. Increase duration and retry.", "status.invalidBand": "The lower cutoff must be below the upper cutoff.",
    "demo.failed": "Example unavailable. Reopen to retry.", "demo.loading": "Loading example…",
    "panel.mockKicker": "Mock Signal",
    "panel.mockTitle": "Current Scenario",
    "panel.filterKicker": "Processing",
    "panel.filterTitle": "Offline Low-pass and Peak Detection",
    "metric.bpm": "BPM",
    "metric.quality": "Quality",
    "metric.breaths": "Breaths",
    "stat.amplitude": "Amp",
    "stat.noise": "Noise",
    "stat.irregularity": "Var",
    "chart.kicker": "Output",
    "chart.title": "Waveform Preview",
    "chart.empty": "No preview data.",
    "quality.stable": "Stable",
    "quality.variable": "Variable",
    "quality.irregular": "Irregular",
    "quality.insufficient": "Insufficient",
    "chart.raw": "raw",
    "chart.filtered": "filtered",
    "chart.reference": "Filter reference (excluded from bins)",
    "chart.peaks": "peaks",
    "chart.valleys": "valleys",
    "status.loading": "Loading presets...",
    "status.loaded": "Scenarios loaded. Choose one to start the experience.",
    "status.loadingDemos": "Generating waveform examples...",
    "status.demosReady": "Waveform examples updated.",
    "status.apply": "Applying mock parameters...",
    "status.applied": "Applied: {scenario}. Opening realtime experience.",
    "status.preview": "Generating preview...",
    "status.filtering": "Filtering preview...",
    "status.complete": "Preview complete.",
    "scenario.normal.name": "Normal",
    "scenario.normal.desc": "Stable rhythm and moderate amplitude, useful as a baseline.",
    "scenario.tachypnea.name": "Tachypnea",
    "scenario.tachypnea.desc": "Higher BPM and shorter cycles for high-rate peak detection.",
    "scenario.bradypnea.name": "Bradypnea",
    "scenario.bradypnea.desc": "Lower BPM and longer cycles for low-rate breath preservation.",
    "scenario.shallow.name": "Shallow",
    "scenario.shallow.desc": "Low amplitude waveform for weak peak and valley detection.",
    "scenario.irregular.name": "Irregular",
    "scenario.irregular.desc": "Variable rhythm for BPM and stability changes.",
    "scenario.apnea.name": "Apnea",
    "scenario.apnea.desc": "Low-amplitude pause sections for intermittent breathing.",
    "scenario.noisy.name": "Noisy",
    "scenario.noisy.desc": "Stronger random noise for smoothing and threshold checks.",
    "scenario.motion_artifact.name": "Motion Artifact",
    "scenario.motion_artifact.desc": "Sudden large spikes for artifact rejection checks.",
    "scenario.deep.name": "Deep Breathing",
    "scenario.deep.desc": "Lower rate and larger amplitude for preservation checks under wide motion.",
    "scenario.rapid_shallow.name": "Rapid Shallow",
    "scenario.rapid_shallow.desc": "High rate with low amplitude for weak high-frequency breathing.",
    "scenario.baseline_drift.name": "Baseline Drift",
    "scenario.baseline_drift.desc": "Slow baseline movement for trend-drift filter checks.",
    "scenario.periodic_weakening.name": "Periodic Weakening",
    "scenario.periodic_weakening.desc": "Short low-amplitude windows inside a repeating breathing pattern.",
    "scenario.weak_noisy.name": "Low Signal Noise",
    "scenario.weak_noisy.desc": "Breath amplitude close to noise for weak peak and valley limits.",
    "scenario.cough_artifact.name": "Cough Artifact",
    "scenario.cough_artifact.desc": "Dense impulse artifacts for abnormal spike disturbance checks.",
  },
};

const elements = {
  languageSelect: document.querySelector("#languageSelect"),
  toggleDemoGridBtn: document.querySelector("#toggleDemoGridBtn"),
  scenarioSelect: document.querySelector("#scenarioSelect"),
  selectedScenarioName: document.querySelector("#selectedScenarioName"),
  scenarioDemoGrid: document.querySelector("#scenarioDemoGrid"),
  bpmInput: document.querySelector("#bpmInput"),
  amplitudeInput: document.querySelector("#amplitudeInput"),
  noiseInput: document.querySelector("#noiseInput"),
  irregularityInput: document.querySelector("#irregularityInput"),
  secondsInput: document.querySelector("#secondsInput"),
  bandHighInput: document.querySelector("#bandHighInput"),
  orderInput: document.querySelector("#orderInput"),
  sigmaInput: document.querySelector("#sigmaInput"),
  peakRatioInput: document.querySelector("#peakRatioInput"),
  autoPeakInput: document.querySelector("#autoPeakInput"),
  statusText: document.querySelector("#statusText"),
  bpmMetric: document.querySelector("#bpmMetric"),
  qualityMetric: document.querySelector("#qualityMetric"),
  countMetric: document.querySelector("#countMetric"),
  previewChart: document.querySelector("#previewChart"),
  previewSummary: document.querySelector("#previewSummary"),
  chartEmpty: document.querySelector("#chartEmpty"),
};

let language = preferredLanguage();
let scenarios = [];
let demoWaveforms = new Map();
let lastPreviewData = null;
let lastPreviewMetrics = null;
let currentStatus = null;
let demoExpanded = false;
let busy = false;
let activeTask = null;
let previewInfo = null;
let previewChart = null;
const demoRequests = new Map();
const demoErrors = new Set();
let expandedScenarioDemos = new Set();
const bandRange = createLowpassRange({high:elements.bandHighInput,track:document.querySelector('#bandTrack'),
  onChange:()=>{if (!busy) setStatus('status.pending');}});

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

function scenarioName(name) {
  return t(`scenario.${name}.name`);
}

function scenarioDescription(name) {
  return t(`scenario.${name}.desc`);
}

function scenarioTheme(name) {
  return SCENARIO_THEME[name] ?? FALLBACK_THEME;
}

function formatNumber(value, digits = 0) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return numeric.toFixed(digits).replace(/\.0+$/, "");
}

function applyLanguage(nextLanguage = language) {
  language = nextLanguage;
  localStorage.setItem(LANGUAGE_KEY, language);
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.title = t("app.title");
  if (elements.languageSelect) {
    elements.languageSelect.value = language;
  }
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  renderScenarioOptions();
  renderDemoCards();
  updateSelectedScenarioName();
  if (lastPreviewData) {
    drawChart(lastPreviewData);
  }
  if (lastPreviewMetrics) {
    drawMetrics(lastPreviewMetrics);
  }
  if (currentStatus?.key) {
    elements.statusText.textContent = t(currentStatus.key, localizedStatusParams(currentStatus));
  }
  updateDemoToggle();
  bandRange.sync();
  updatePreviewSummary();
}

function localizedStatusParams(status) {
  if (status?.key === "status.applied" && status.params?.scenarioId) {
    return {
      ...status.params,
      scenario: scenarioName(status.params.scenarioId),
    };
  }
  return status?.params ?? {};
}

function setStatus(messageOrKey, params = {}, state = null) {
  const phase = state ?? (['status.loading','status.preview','status.filtering','status.apply'].includes(messageOrKey) ? 'busy' : messageOrKey === 'status.pending' ? 'pending' : 'ready');
  document.querySelector('#labStatus').dataset.state = phase;
  if (TRANSLATIONS.en[messageOrKey]) {
    currentStatus = { key: messageOrKey, params };
    elements.statusText.textContent = t(messageOrKey, localizedStatusParams(currentStatus));
    return;
  }
  currentStatus = { text: messageOrKey };
  elements.statusText.textContent = messageOrKey;
}

async function request(path, options = {}) {
  const requestOptions = {
    ...options,
    headers: {
      ...SESSION_HEADERS,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  };
  const response = await (shared.apiFetch
    ? shared.apiFetch(path, requestOptions)
    : fetch(`${API_BASE}${path}`, requestOptions));
  if (!response.ok) {
    throw new Error(shared.responseError ? await shared.responseError(response) : `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function readMockPayload() {
  return {
    scenario: elements.scenarioSelect.value,
    bpm: Number(elements.bpmInput.value),
    amplitude: Number(elements.amplitudeInput.value),
    noise: Number(elements.noiseInput.value),
    irregularity: Number(elements.irregularityInput.value),
  };
}

function readFilterConfig() {
  return {
    offline_filter:'baseline_lowpass',
    lowpass_order:Number(elements.orderInput.value),
    bandpass_mode:'custom', highpass_cutoff:bandRange.value(),
    low_bpm:6, high_bpm:40,
    order: Number(elements.orderInput.value),
    gaussian_sigma: Number(elements.sigmaInput.value),
    peak_threshold_ratio: Number(elements.peakRatioInput.value),
    auto_peak_detection: elements.autoPeakInput.checked,
  };
}

function fillScenario(config) {
  elements.bpmInput.value = Number(config.bpm).toFixed(2);
  elements.amplitudeInput.value = Number(config.amplitude).toFixed(2);
  elements.noiseInput.value = Number(config.noise).toFixed(2);
  elements.irregularityInput.value = Number(config.irregularity).toFixed(2);
}

function selectScenario(name) {
  if (busy && activeTask !== "load") return;
  const selected = scenarios.find((item) => item.name === name);
  if (!selected) {
    return;
  }
  elements.scenarioSelect.value = name;
  fillScenario(selected.config);
  updateSelectedScenarioName();
  renderDemoCards();
  if (activeTask !== "load") setStatus("status.pending");
}

function updateSelectedScenarioName() {
  if (!elements.selectedScenarioName) {
    return;
  }
  const current = elements.scenarioSelect.value;
  elements.selectedScenarioName.textContent = current ? scenarioName(current) : "-";
}

function demoDetailId(name) {
  return `demo-detail-${String(name).replace(/[^a-z0-9_-]/gi, "-")}`;
}

function renderScenarioOptions() {
  const current = elements.scenarioSelect.value;
  elements.scenarioSelect.innerHTML = "";
  scenarios.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.name;
    option.textContent = scenarioName(item.name);
    elements.scenarioSelect.appendChild(option);
  });
  if (current && scenarios.some((item) => item.name === current)) {
    elements.scenarioSelect.value = current;
  }
}

function sortScenariosForDemo(items) {
  const rank = new Map(FEATURED_SCENARIOS.map((name, index) => [name, index]));
  return [...items].sort((left, right) => {
    const leftRank = rank.has(left.name) ? rank.get(left.name) : FEATURED_SCENARIOS.length;
    const rightRank = rank.has(right.name) ? rank.get(right.name) : FEATURED_SCENARIOS.length;
    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }
    return left.name.localeCompare(right.name);
  });
}

async function loadScenarios() {
  setStatus("status.loading");
  const result = await request("/mock/scenarios");
  scenarios = sortScenariosForDemo(result.data || []);
  renderScenarioOptions();
  if (scenarios.length > 0) {
    selectScenario(scenarios[0].name);
  }
  setStatus("status.loaded");
  await previewAndFilter();
}

async function loadScenarioDemo(item) {
  if (demoWaveforms.has(item.name) || demoRequests.has(item.name)) return;
  demoErrors.delete(item.name);
  const pending = request('/mock/preview', {method:'POST', body:JSON.stringify({
    ...item.config, seconds:DEMO_SECONDS, sampling_rate:DEMO_SAMPLING_RATE,
  })});
  demoRequests.set(item.name, pending);
  renderDemoCards();
  try {
    const response = await pending;
    demoWaveforms.set(item.name, response.data);
  } catch {
    demoErrors.add(item.name);
  } finally {
    demoRequests.delete(item.name);
    renderDemoCards();
  }
}

function renderDemoCards() {
  elements.scenarioDemoGrid.innerHTML = "";
  scenarios.forEach((item, index) => {
    const theme = scenarioTheme(item.name);
    const active = item.name === elements.scenarioSelect.value;
    const detailExpanded = expandedScenarioDemos.has(item.name);
    const visible = demoExpanded || index < COLLAPSED_DEMO_COUNT || active;
    if (!visible) {
      return;
    }
    const detailId = demoDetailId(item.name);
    const card = document.createElement("article");
    const toggleLabel = t(detailExpanded ? "demo.hideWaveform" : "demo.viewWaveform");
    card.className = "demo-card";
    card.dataset.scenario = item.name;
    card.classList.toggle("active", active);
    card.classList.toggle("detail-open", detailExpanded);
    card.style.setProperty("--scenario-color", theme.color);
    card.style.setProperty("--scenario-soft", theme.soft);
    card.innerHTML = `
      <div class="demo-card-main">
        <button class="demo-select-action" type="button" aria-pressed="${active}" aria-label="${t("demo.chooseScenario")}: ${scenarioName(item.name)}">
          <div class="demo-card-header">
            <div class="demo-title">
              <strong>${scenarioName(item.name)}</strong>
              <span>${scenarioDescription(item.name)}</span>
            </div>
            ${active ? `<span class="selected-indicator" aria-label="${t("demo.selected")}" title="${t("demo.selected")}">${ICONS.check}</span>` : ""}
          </div>
        </button>
        <button class="demo-detail-toggle secondary" type="button" aria-label="${toggleLabel}" title="${toggleLabel}" aria-expanded="${detailExpanded}" aria-controls="${detailId}">
          ${detailExpanded ? ICONS.chevronUp : ICONS.waveform}
        </button>
      </div>
      <div class="demo-card-detail" id="${detailId}">
        ${!demoWaveforms.has(item.name) ? `<p class="demo-load-state" role="status">${t(demoErrors.has(item.name) ? 'demo.failed' : 'demo.loading')}</p>` : ''}
        <div class="sparkline-frame">
          <div class="waveform-meta" aria-hidden="true">
            <span class="waveform-chip primary"><strong>${Math.round(item.config.bpm)}</strong><small>BPM</small></span>
            <span class="waveform-chip"><strong>${formatNumber(item.config.amplitude)}</strong><small>${t("stat.amplitude")}</small></span>
            <span class="waveform-chip"><strong>${formatNumber(item.config.noise, 1)}</strong><small>${t("stat.noise")}</small></span>
            <span class="waveform-chip"><strong>${formatNumber(item.config.irregularity, 2)}</strong><small>${t("stat.irregularity")}</small></span>
          </div>
          <canvas width="300" height="108" aria-hidden="true"></canvas>
        </div>
      </div>
    `;
    card.querySelector(".demo-select-action").addEventListener("click", () => selectScenario(item.name));
    card.querySelector(".demo-detail-toggle").addEventListener("click", () => {
      if (expandedScenarioDemos.has(item.name)) {
        expandedScenarioDemos.delete(item.name);
      } else {
        expandedScenarioDemos.add(item.name);
        loadScenarioDemo(item);
      }
      renderDemoCards();
    });
    elements.scenarioDemoGrid.appendChild(card);
    const canvas = card.querySelector("canvas");
    drawMiniWaveform(canvas, demoWaveforms.get(item.name) || [], theme);
  });
  updateDemoToggle();
  syncBusy();
}

function updateDemoToggle() {
  if (!elements.toggleDemoGridBtn) {
    return;
  }
  const shouldShow = scenarios.length > COLLAPSED_DEMO_COUNT;
  elements.toggleDemoGridBtn.hidden = !shouldShow;
  elements.toggleDemoGridBtn.textContent = t(demoExpanded ? "demo.collapse" : "demo.expand");
  elements.toggleDemoGridBtn.setAttribute("aria-expanded", String(demoExpanded));
}

async function applyMockConfig() {
  setStatus("status.apply");
  const result = await request("/mock/config", {
    method: "POST",
    body: JSON.stringify(readMockPayload()),
  });
  fillScenario(result.data);
  setStatus("status.applied", { scenarioId: result.data.scenario });
  window.parent?.postMessage({ type: "RespiraScope-open-monitor", startDemo: true }, window.location.origin);
}

async function previewAndFilter() {
  const filterConfig = readFilterConfig();
  setStatus("status.preview");
  const mockPayload = {
    ...readMockPayload(),
    seconds: Number(elements.secondsInput.value),
    sampling_rate: SAMPLING_RATE,
  };
  const preview = await request("/mock/preview", {
    method: "POST",
    body: JSON.stringify(mockPayload),
  });

  setStatus("status.filtering");
  const filtered = await request("/applyFilter", {
    method: "POST",
    body: JSON.stringify({
      filter_config: filterConfig,
      raw_data: preview.data,
    }),
  });

  if (!Array.isArray(preview.data) || !Array.isArray(filtered.data) || !filtered.data.length) throw new Error(t('status.short'));
  previewInfo = {scenario:mockPayload.scenario, seconds:mockPayload.seconds, points:preview.data.length};
  updatePreviewSummary();
  lastPreviewData = {
    raw: preview.data,
    filtered: filtered.data || [],
    peaks: filtered.peak || [],
    valleys: filtered.valley || [],
    processingQuality: filtered.processingQuality,
  };
  lastPreviewMetrics = filtered.metrics || {};
  drawChart(lastPreviewData);
  drawMetrics(filtered.metrics || {});
  setStatus("status.complete");
}

function drawMetrics(metrics) {
  elements.bpmMetric.textContent = metrics.bpm == null ? "-" : formatNumber(metrics.bpm, 1);
  elements.qualityMetric.textContent = metrics.quality ? t(`quality.${metrics.quality}`) : "-";
  elements.countMetric.textContent = metrics.breath_count ?? "-";
}

function hexToRgba(hex, alpha) {
  const normalized = hex.replace("#", "");
  const value = Number.parseInt(normalized, 16);
  const r = (value >> 16) & 255;
  const g = (value >> 8) & 255;
  const b = value & 255;
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function drawMiniWaveform(canvas, points, theme = FALLBACK_THEME) {
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, width, height);
  if (!points.length) {
    return;
  }
  const xs = points.map((point) => point[0]);
  const ys = points.map((point) => point[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const xScale = (x) => ((x - minX) / Math.max(1, maxX - minX)) * width;
  const yScale = (y) => 10 + (1 - (y - minY) / Math.max(1, maxY - minY)) * (height - 20);

  ctx.strokeStyle = "#edf2f7";
  ctx.lineWidth = 1;
  for (let i = 1; i < 5; i += 1) {
    const y = (height * i) / 4;
    ctx.beginPath();
    ctx.moveTo(8, y);
    ctx.lineTo(width - 8, y);
    ctx.stroke();
  }

  const path = new Path2D();
  points.forEach((point, index) => {
    const x = xScale(point[0]);
    const y = yScale(point[1]);
    if (index === 0) {
      path.moveTo(x, y);
    } else {
      path.lineTo(x, y);
    }
  });

  const area = new Path2D(path);
  area.lineTo(width, height - 8);
  area.lineTo(0, height - 8);
  area.closePath();

  const fill = ctx.createLinearGradient(0, 0, 0, height);
  fill.addColorStop(0, hexToRgba(theme.color, 0.22));
  fill.addColorStop(1, hexToRgba(theme.color, 0.02));
  ctx.fillStyle = fill;
  ctx.fill(area);

  ctx.strokeStyle = theme.color;
  ctx.lineWidth = 2.4;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.stroke(path);
}

function drawChart({raw,filtered,peaks,valleys,processingQuality}) {
  previewChart ??= echarts.init(elements.previewChart);
  const points = series => series.map(p=>[sequenceOf(p)/SAMPLING_RATE,valueOf(p)]);
  const unprocessed = (processingQuality?.invalidIntervals ?? []).filter(i=>i.reason === 'motion' || i.reason === 'too_short');
  const filteredPoints = filtered.map(p=>[sequenceOf(p)/SAMPLING_RATE,
    unprocessed.some(i=>sequenceOf(p)>=i.start && sequenceOf(p)<i.end) ? null : valueOf(p)]);
  const referencePoints = processingQuality?.version === 2 ? filtered.map(p=>[sequenceOf(p)/SAMPLING_RATE,
    unprocessed.some(i=>sequenceOf(p)>=i.start && sequenceOf(p)<i.end) ? valueOf(p) : null]) : [];
  elements.chartEmpty.hidden = raw.length > 0 || filtered.length > 0;
  const compact = elements.previewChart.clientWidth < 500;
  previewChart.setOption({
    animation:false,
    grid:{left:compact?44:56,right:18,top:64,bottom:78},
    tooltip:{trigger:'axis',confine:true,valueFormatter:value=>Number(value).toFixed(2)},
    legend:{top:4,itemWidth:16,itemHeight:9,textStyle:{color:'#607487',fontSize:11}},
    xAxis:{type:'value',name:t('chart.time'),nameLocation:'middle',nameGap:28,
      min:0,max:raw.length?sequenceOf(raw.at(-1))/SAMPLING_RATE:undefined,
      axisLabel:{color:'#607487'},splitLine:{show:false}},
    yAxis:{type:'value',name:t('chart.value'),scale:true,axisLabel:{color:'#607487'},
      splitLine:{lineStyle:{color:'#edf1f5'}}},
    dataZoom:[{type:'inside',filterMode:'none',zoomOnMouseWheel:'ctrl'},
      {type:'slider',filterMode:'none',left:compact?44:56,right:18,bottom:8,height:22,borderColor:'#dce4ec',
       fillerColor:'rgba(8,127,140,.12)',handleStyle:{color:'#087f8c'},showDetail:false}],
    series:[
      {name:t('chart.raw'),type:'line',data:points(raw),showSymbol:false,lineStyle:{color:'#95a1b2',width:1},itemStyle:{color:'#95a1b2'}},
      {name:t('chart.filtered'),type:'line',data:filteredPoints,connectNulls:false,showSymbol:false,lineStyle:{color:'#2563eb',width:2},itemStyle:{color:'#2563eb'}},
      {name:t('chart.peaks'),type:'scatter',data:points(peaks),symbol:'triangle',symbolSize:9,itemStyle:{color:'#d13f64'}},
      {name:t('chart.valleys'),type:'scatter',data:points(valleys),symbol:'triangle',symbolRotate:180,symbolSize:9,itemStyle:{color:'#0f8f86'}},
      ...(referencePoints.some(p=>p[1] != null) ? [{id:'artifact-reference',name:t('chart.reference'),type:'line',
        data:referencePoints,connectNulls:false,showSymbol:false,lineStyle:{color:'#2563eb',width:2,type:'dashed'},itemStyle:{color:'#2563eb'}}] : []),
    ],
  },true);
  previewChart.resize();
}

function updatePreviewSummary() {
  elements.previewSummary.textContent = previewInfo ? t('chart.summary',{
    ...previewInfo,scenario:scenarioName(previewInfo.scenario),
  }) : '';
  elements.previewChart.setAttribute('aria-label',t('chart.title'));
}

function syncBusy() {
  document.querySelectorAll('.control-panel input,.control-panel select,.demo-select-action,#previewBtn,#applyMockBtn').forEach(node=>{
    node.disabled = busy || !scenarios.length;
  });
  document.querySelector('#previewBtn').setAttribute('aria-busy',String(busy && activeTask !== 'apply'));
  document.querySelector('#applyMockBtn').setAttribute('aria-busy',String(busy && activeTask === 'apply'));
}

function validateInputs(kind) {
  const selector = kind === 'apply' ? '.mock-controls input:not(#secondsInput)' : '.control-panel input,.filter-controls select';
  for (const input of document.querySelectorAll(selector)) {
    input.removeAttribute('aria-invalid');
    if (!input.checkValidity()) {
      input.setAttribute('aria-invalid','true');
      input.focus();
      throw new Error(`${input.closest('label').querySelector('span').textContent}: ${input.validationMessage}`);
    }
  }

}

async function runTask(kind, work) {
  if (busy) return;
  try {
    if (kind !== 'load') validateInputs(kind);
    busy = true;
    activeTask = kind;
    syncBusy();
    await work();
  } catch (error) {
    setStatus(error.message,{},'error');
  } finally {
    busy = false;
    activeTask = null;
    syncBusy();
  }
}

new ResizeObserver(()=>previewChart?.resize()).observe(elements.previewChart);

function sequenceOf(point) {
  return Array.isArray(point) ? Number(point[0]) : Number(point?.sequence);
}

function valueOf(point) {
  return Array.isArray(point) ? Number(point[1]) : Number(point?.value);
}

elements.languageSelect?.addEventListener("change", (event) => {
  applyLanguage(event.target.value);
});
elements.toggleDemoGridBtn?.addEventListener("click", () => {
  demoExpanded = !demoExpanded;
  renderDemoCards();
});
elements.scenarioSelect.addEventListener("change", () => {
  selectScenario(elements.scenarioSelect.value);
});
document.querySelector("#applyMockBtn").addEventListener("click", () => {
  runTask("apply", applyMockConfig);
});
document.querySelector("#previewBtn").addEventListener("click", () => {
  runTask("preview", previewAndFilter);
});

window.addEventListener("storage", (event) => {
  if (event.key === LANGUAGE_KEY && (event.newValue === "zh" || event.newValue === "en")) {
    applyLanguage(event.newValue);
  }
});

window.addEventListener("message", (event) => {
  if (event.origin !== window.location.origin) {
    return;
  }
  if (event.data?.type === "RespiraScope-language" && (event.data.language === "zh" || event.data.language === "en")) {
    applyLanguage(event.data.language);
  }
});

document.querySelectorAll('.control-panel input,.filter-controls select').forEach(input=>input.addEventListener('input',()=>{
  input.removeAttribute('aria-invalid');
  bandRange.sync();
  if (!busy) setStatus('status.pending');
}));

document.querySelectorAll('.control-panel input[type=number]').forEach(input=>input.addEventListener('blur',()=>{
  if (input.value !== '' && input.checkValidity() && input.id !== 'secondsInput') input.value=Number(input.value).toFixed(2);
}));

applyLanguage(language);
runTask('load',loadScenarios);
