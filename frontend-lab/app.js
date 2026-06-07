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
    "app.title": "模拟信号设置",
    "app.subtitle": "先选择一个可理解的呼吸场景，再进入实时监测观察算法表现。",
    "language.label": "语言",
    "button.applyMock": "应用并开始体验",
    "button.preview": "生成预览",
    "button.useScenario": "载入预设",
    "field.scenario": "模拟预设",
    "field.bpm": "BPM",
    "field.amplitude": "幅度",
    "field.noise": "噪声",
    "field.irregularity": "不规则度",
    "field.seconds": "预览秒数",
    "field.lowBpm": "低 BPM",
    "field.highBpm": "高 BPM",
    "field.order": "阶数",
    "field.sigma": "高斯 Sigma",
    "field.peakRatio": "峰谷阈值比例",
    "field.autoPeak": "自动识别峰谷",
    "demo.kicker": "预设波形",
    "demo.title": "选择一个呼吸场景",
    "demo.subtitle": "优先从正常、浅呼吸、噪声、屏气和体动伪影开始，最容易看出滤波和峰谷识别的边界。",
    "demo.selected": "已选",
    "demo.expand": "展开全部",
    "demo.collapse": "收起",
    "panel.mockKicker": "模拟信号",
    "panel.mockTitle": "当前场景",
    "panel.filterKicker": "处理",
    "panel.filterTitle": "滤波与峰谷识别",
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
    "chart.peaks": "波峰",
    "chart.valleys": "波谷",
    "status.loading": "正在加载预设...",
    "status.loaded": "场景已加载，选择后可直接开始体验。",
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
    "app.title": "Mock Signal Setup",
    "app.subtitle": "Choose a clear breathing scenario, then open realtime monitoring to inspect the algorithm.",
    "language.label": "Language",
    "button.applyMock": "Apply and Start Demo",
    "button.preview": "Generate Preview",
    "button.useScenario": "Load Preset",
    "field.scenario": "Preset",
    "field.bpm": "BPM",
    "field.amplitude": "Amplitude",
    "field.noise": "Noise",
    "field.irregularity": "Irregularity",
    "field.seconds": "Seconds",
    "field.lowBpm": "Low BPM",
    "field.highBpm": "High BPM",
    "field.order": "Order",
    "field.sigma": "Gaussian Sigma",
    "field.peakRatio": "Peak Ratio",
    "field.autoPeak": "Auto peak detection",
    "demo.kicker": "Preset Waveforms",
    "demo.title": "Choose a Breathing Scenario",
    "demo.subtitle": "Start with normal, shallow, noisy, apnea, and motion artifact scenes to see the filtering and peak-detection boundaries.",
    "demo.selected": "Selected",
    "demo.expand": "Show All",
    "demo.collapse": "Collapse",
    "panel.mockKicker": "Mock Signal",
    "panel.mockTitle": "Current Scenario",
    "panel.filterKicker": "Processing",
    "panel.filterTitle": "Filter and Peak Detection",
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
  scenarioDemoGrid: document.querySelector("#scenarioDemoGrid"),
  bpmInput: document.querySelector("#bpmInput"),
  amplitudeInput: document.querySelector("#amplitudeInput"),
  noiseInput: document.querySelector("#noiseInput"),
  irregularityInput: document.querySelector("#irregularityInput"),
  secondsInput: document.querySelector("#secondsInput"),
  lowBpmInput: document.querySelector("#lowBpmInput"),
  highBpmInput: document.querySelector("#highBpmInput"),
  orderInput: document.querySelector("#orderInput"),
  sigmaInput: document.querySelector("#sigmaInput"),
  peakRatioInput: document.querySelector("#peakRatioInput"),
  autoPeakInput: document.querySelector("#autoPeakInput"),
  statusText: document.querySelector("#statusText"),
  bpmMetric: document.querySelector("#bpmMetric"),
  qualityMetric: document.querySelector("#qualityMetric"),
  countMetric: document.querySelector("#countMetric"),
  chartCanvas: document.querySelector("#chartCanvas"),
  chartEmpty: document.querySelector("#chartEmpty"),
};

let language = preferredLanguage();
let scenarios = [];
let demoWaveforms = new Map();
let lastPreviewData = null;
let lastPreviewMetrics = null;
let currentStatus = null;
let demoExpanded = false;

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

function setStatus(messageOrKey, params = {}) {
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
    throw new Error(`${response.status} ${response.statusText}`);
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
    low_bpm: Number(elements.lowBpmInput.value),
    high_bpm: Number(elements.highBpmInput.value),
    order: Number(elements.orderInput.value),
    gaussian_sigma: Number(elements.sigmaInput.value),
    peak_threshold_ratio: Number(elements.peakRatioInput.value),
    auto_peak_detection: elements.autoPeakInput.checked,
  };
}

function fillScenario(config) {
  elements.bpmInput.value = config.bpm;
  elements.amplitudeInput.value = config.amplitude;
  elements.noiseInput.value = config.noise;
  elements.irregularityInput.value = config.irregularity;
}

function selectScenario(name) {
  const selected = scenarios.find((item) => item.name === name);
  if (!selected) {
    return;
  }
  elements.scenarioSelect.value = name;
  fillScenario(selected.config);
  renderDemoCards();
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
  await loadScenarioDemos();
}

async function loadScenarioDemos() {
  if (scenarios.length === 0) {
    return;
  }
  setStatus("status.loadingDemos");
  const previews = await Promise.all(
    scenarios.map(async (item) => {
      const response = await request("/mock/preview", {
        method: "POST",
        body: JSON.stringify({
          ...item.config,
          seconds: DEMO_SECONDS,
          sampling_rate: DEMO_SAMPLING_RATE,
        }),
      });
      return [item.name, response.data];
    }),
  );
  demoWaveforms = new Map(previews);
  renderDemoCards();
  setStatus("status.demosReady");
}

function renderDemoCards() {
  elements.scenarioDemoGrid.innerHTML = "";
  scenarios.forEach((item, index) => {
    const theme = scenarioTheme(item.name);
    const active = item.name === elements.scenarioSelect.value;
    const visible = demoExpanded || index < COLLAPSED_DEMO_COUNT || active;
    if (!visible) {
      return;
    }
    const card = document.createElement("button");
    card.type = "button";
    card.className = "demo-card";
    card.classList.toggle("active", active);
    card.style.setProperty("--scenario-color", theme.color);
    card.style.setProperty("--scenario-soft", theme.soft);
    card.innerHTML = `
      <div class="demo-card-header">
        <div class="demo-title">
          <strong>${scenarioName(item.name)}</strong>
          <span>${t("field.scenario")}</span>
        </div>
        <span class="bpm-badge">${Math.round(item.config.bpm)} BPM</span>
      </div>
      <div class="sparkline-frame">
        <canvas width="300" height="108" aria-hidden="true"></canvas>
      </div>
      <p>${scenarioDescription(item.name)}</p>
      <div class="demo-stats">
        <span>${t("stat.amplitude")} ${formatNumber(item.config.amplitude)}</span>
        <span>${t("stat.noise")} ${formatNumber(item.config.noise, 1)}</span>
        <span>${t("stat.irregularity")} ${formatNumber(item.config.irregularity, 2)}</span>
      </div>
      ${active ? `<span class="selected-indicator">${t("demo.selected")}</span>` : ""}
      <small>${t("button.useScenario")}</small>
    `;
    card.addEventListener("click", () => selectScenario(item.name));
    elements.scenarioDemoGrid.appendChild(card);
    const canvas = card.querySelector("canvas");
    drawMiniWaveform(canvas, demoWaveforms.get(item.name) || [], theme);
  });
  updateDemoToggle();
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
      filter_config: readFilterConfig(),
      raw_data: preview.data,
    }),
  });

  lastPreviewData = {
    raw: preview.data,
    filtered: filtered.data || [],
    peaks: filtered.peak || [],
    valleys: filtered.valley || [],
  };
  lastPreviewMetrics = filtered.metrics || {};
  drawChart(lastPreviewData);
  drawMetrics(filtered.metrics || {});
  setStatus("status.complete");
}

function drawMetrics(metrics) {
  elements.bpmMetric.textContent = metrics.bpm ?? "-";
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

function drawChart({ raw, filtered, peaks, valleys }) {
  const canvas = elements.chartCanvas;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const padding = { left: 58, right: 26, top: 28, bottom: 44 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const allPoints = [...raw, ...filtered];

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#fbfdff";
  ctx.fillRect(0, 0, width, height);

  if (allPoints.length === 0) {
    elements.chartEmpty.hidden = false;
    return;
  }
  elements.chartEmpty.hidden = true;

  const minX = sequenceOf(allPoints[0]);
  const maxX = sequenceOf(allPoints[allPoints.length - 1]);
  const ys = allPoints.map((item) => valueOf(item));
  const yPadding = Math.max(20, (Math.max(...ys) - Math.min(...ys)) * 0.12);
  const minY = Math.min(...ys) - yPadding;
  const maxY = Math.max(...ys) + yPadding;
  const xScale = (x) => padding.left + ((x - minX) / Math.max(1, maxX - minX)) * plotWidth;
  const yScale = (y) => padding.top + (1 - (y - minY) / Math.max(1, maxY - minY)) * plotHeight;

  drawGrid(ctx, width, height, padding, minY, maxY, yScale);
  drawLine(ctx, raw, xScale, yScale, "#8a96a8", 1.35, 0.82);

  drawLine(ctx, filtered, xScale, yScale, "#2563eb", 2.7, 1);
  drawMarkers(ctx, peaks, xScale, yScale, "#d13f64", true);
  drawMarkers(ctx, valleys, xScale, yScale, "#0f8f86", false);
}

function drawGrid(ctx, width, height, padding, minY, maxY, yScale) {
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;

  ctx.save();
  ctx.fillStyle = "#ffffff";
  roundedRect(ctx, padding.left, padding.top, plotWidth, plotHeight, 8);
  ctx.fill();
  ctx.restore();

  ctx.strokeStyle = "#e6edf5";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i += 1) {
    const value = minY + ((maxY - minY) * i) / 5;
    const y = yScale(value);
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
    ctx.fillStyle = "#64748b";
    ctx.font = "12px Arial";
    ctx.fillText(Math.round(value), 12, y + 4);
  }

  ctx.strokeStyle = "#eef2f7";
  for (let i = 1; i <= 6; i += 1) {
    const x = padding.left + (plotWidth * i) / 6;
    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, height - padding.bottom);
    ctx.stroke();
  }

  ctx.strokeStyle = "#cbd6e2";
  roundedRect(ctx, padding.left, padding.top, plotWidth, plotHeight, 8);
  ctx.stroke();
}

function drawLine(ctx, points, xScale, yScale, color, width, opacity = 1) {
  if (!points || points.length === 0) {
    return;
  }
  ctx.save();
  ctx.globalAlpha = opacity;
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineJoin = "round";
  ctx.lineCap = "round";
  ctx.beginPath();
  points.forEach((point, index) => {
    const x = xScale(sequenceOf(point));
    const y = yScale(valueOf(point));
    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });
  ctx.stroke();
  ctx.restore();
}

function drawMarkers(ctx, points, xScale, yScale, color, upward) {
  ctx.save();
  ctx.fillStyle = color;
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 2.2;
  ctx.shadowColor = hexToRgba(color, 0.2);
  ctx.shadowBlur = 8;
  points.forEach((point) => {
    const x = xScale(sequenceOf(point));
    const y = yScale(valueOf(point));
    ctx.beginPath();
    if (upward) {
      ctx.moveTo(x, y - 10);
      ctx.lineTo(x - 7, y + 7);
      ctx.lineTo(x + 7, y + 7);
    } else {
      ctx.moveTo(x, y + 10);
      ctx.lineTo(x - 7, y - 7);
      ctx.lineTo(x + 7, y - 7);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  });
  ctx.restore();
}

function roundedRect(ctx, x, y, width, height, radius) {
  if (typeof ctx.roundRect === "function") {
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, radius);
    return;
  }
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + width - radius, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
  ctx.lineTo(x + width, y + height - radius);
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
  ctx.lineTo(x + radius, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
}

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
  applyMockConfig().catch((error) => setStatus(error.message));
});
document.querySelector("#previewBtn").addEventListener("click", () => {
  previewAndFilter().catch((error) => setStatus(error.message));
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

applyLanguage(language);
loadScenarios().catch((error) => setStatus(error.message));
