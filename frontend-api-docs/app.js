const runtimeConfig = window.CT_BREATH_RUNTIME_CONFIG || {};
const LANGUAGE_KEY = "RespiraScope-language";

const TEXT = {
  zh: {
    "app.kicker": "接口说明",
    "app.title": "呼吸系统对外接口说明",
    "app.subtitle": "只保留新系统集成需要的流程、字段和传感器输入格式。",
    "runtime.kicker": "入口",
    "runtime.title": "对接入口",
    "flow.kicker": "流程",
    "flow.title": "接入流程",
    "socket.kicker": "Socket.IO",
    "socket.title": "实时订阅",
    "payload.kicker": "Payload",
    "payload.title": "后端对外实时字段",
    "rest.kicker": "REST",
    "rest.title": "流程接口",
    "sensor.kicker": "Sensor",
    "sensor.title": "传感器输入数据",
    "filter.kicker": "Request",
    "filter.title": "请求字段",
    "record.kicker": "Record",
    "record.title": "录制文件字段",
    "table.method": "方法",
    "table.path": "路径",
    "table.description": "说明",
  },
  en: {
    "app.kicker": "Integration",
    "app.title": "Breath External API",
    "app.subtitle": "Only the flow, exposed fields, and sensor input format needed by an integrating system.",
    "runtime.kicker": "Entry",
    "runtime.title": "Integration Entry Points",
    "flow.kicker": "Flow",
    "flow.title": "Integration Flow",
    "socket.kicker": "Socket.IO",
    "socket.title": "Realtime Subscription",
    "payload.kicker": "Payload",
    "payload.title": "Realtime Output Fields",
    "rest.kicker": "REST",
    "rest.title": "Flow APIs",
    "sensor.kicker": "Sensor",
    "sensor.title": "Sensor Input Data",
    "filter.kicker": "Request",
    "filter.title": "Request Fields",
    "record.kicker": "Record",
    "record.title": "Record File Fields",
    "table.method": "Method",
    "table.path": "Path",
    "table.description": "Description",
  },
};

const CONTENT = {
  zh: {
    runtime: [
      ["后端 API", () => endpoint(runtimeConfig.backendHost, runtimeConfig.backendPort)],
      ["实时订阅", () => `${endpoint(runtimeConfig.backendHost, runtimeConfig.backendPort)}/breath`],
      ["传感器输入", () => `${runtimeConfig.sensorHost || "-"}:${runtimeConfig.sensorPort || "-"}`],
      ["推送节奏", () => "约 40ms 一批"],
    ],
    flow: [
      "调用 GET /health 或 GET /stream/status，确认后端和传感器状态。",
      "调用 POST /startReceive，传入滤波配置，开始接收并处理呼吸数据。",
      "连接 Socket.IO /breath，监听 breath 事件。",
      "按 type 分别消费 raw、filtered、peak、valley、metrics。",
      "录制时调用 /record/start、/record/end、/record/save。",
      "历史数据重新滤波时调用 /applyFilter。",
    ],
    socketSummary: [
      ["namespace", "/breath"],
      ["event", "breath"],
      ["message", "{ type, data }"],
      ["sequence", "判断连续性的主键；断流时不要把缺口直接连线。"],
    ],
    endpoints: [
      ["GET", "/health", "检查后端是否运行，以及后端连接的传感器 host、port。"],
      ["GET", "/stream/status", "检查是否已开始接收、是否连接传感器、是否收到数据、录制状态。"],
      ["POST", "/startReceive", "开始接收和实时处理。请求体可省略，默认使用系统 FilterConfig。"],
      ["POST", "/setRTFilterParams", "更新实时滤波和峰谷识别参数。请求体可省略，默认使用系统 FilterConfig。"],
      ["POST", "/applyFilter", "对历史 raw_data 做离线滤波。请求体可省略，省略时返回空结果。"],
      ["POST", "/record/start", "开始记录。"],
      ["POST", "/record/end", "结束用户选中的记录区间。"],
      ["POST", "/record/save", "保存记录文件，返回 data.file_path。请求体可省略，使用默认目录。"],
    ],
    payloads: [
      {
        title: "raw",
        desc: "原始呼吸采样点。",
        rows: [["data[n][0]", "sequence，后端递增采样序号"], ["data[n][1]", "value，传感器原始值"]],
        sample: { type: "raw", data: [[1024, 188.42]] },
      },
      {
        title: "filtered",
        desc: "实时滤波后的呼吸采样点。",
        rows: [["data[n][0]", "sequence，对应 raw 序号"], ["data[n][1]", "value，滤波值"]],
        sample: { type: "filtered", data: [[1024, 187.63]] },
      },
      {
        title: "peak / valley",
        desc: "实时识别出的波峰或波谷。",
        rows: [["data[n][0]", "sequence，峰谷所在序号"], ["data[n][1]", "value，峰谷滤波值"]],
        sample: { type: "peak", data: [[1088, 246.19]] },
      },
      {
        title: "metrics",
        desc: "BPM 和稳定性指标。",
        rows: [
          ["bpm", "呼吸频率，单位 次/分钟"],
          ["quality", "insufficient / stable / variable / irregular"],
          ["breath_count", "当前窗口参与计算的波峰数"],
          ["interval_cv", "波峰间隔变异系数，越低越稳定"],
        ],
        sample: { type: "metrics", data: [{ bpm: 18.25, quality: "stable", breath_count: 6, interval_cv: 0.08 }] },
      },
    ],
    sensor: [
      ["连接方式", "后端作为 TCP client，主动连接 [sensor].host:[sensor].port。"],
      ["单包长度", "4 字节。后端每次读取 4 字节作为一个采样包。"],
      ["有效字节", "只使用 byte[2] 和 byte[3]；byte[0]、byte[1] 当前不参与计算。"],
      ["原始值", "sensor_value = byte[2] * 256 + byte[3]，范围 0-65535。"],
      ["输出映射", "每个 sensor_value 会变成 Socket.IO raw 的 [sequence, value]。"],
    ],
    sensorExample: `byte[0]  byte[1]  byte[2]  byte[3]
unused   unused   high     low

sensor_value = high * 256 + low
raw message = { "type": "raw", "data": [[sequence, sensor_value]] }`,
    filters: [
      ["FilterConfig.low_bpm", "number", "低呼吸频率边界，用于换算滤波截止频率。"],
      ["FilterConfig.high_bpm", "number", "高呼吸频率边界，用于换算滤波截止频率。"],
      ["FilterConfig.sampling_rate", "number", "采样率，影响 BPM 和峰谷间隔计算。"],
      ["FilterConfig.moving_avg_window", "number", "移动平均窗口。"],
      ["FilterConfig.gaussian_sigma", "number", "平滑强度。"],
      ["FilterConfig.min_peak_distance", "number", "峰谷最小采样点距离。"],
      ["FilterConfig.peak_threshold_ratio", "number", "自适应峰谷显著性比例。"],
      ["FilterConfig.prominence", "number", "手动峰谷显著性参数。"],
      ["FilterConfig.auto_peak_detection", "boolean", "是否启用自适应峰谷识别。"],
      ["FilterConfig.confirm_realtime_events", "boolean", "是否启用短延迟确认峰谷。"],
      ["FilterConfig.confirmation_delay_points", "number", "确认峰谷等待的未来采样点数。"],
      ["FilterConfig.data_gap_reset_points", "number", "sequence 断开超过该值时重置实时识别。"],
      ["FilterConfig.gap_warmup_points", "number", "断流恢复后等待多少点再输出峰谷。"],
      ["FilterConfig.restore_baseline", "boolean", "滤波后是否恢复到原始基线附近。"],
      ["applyFilter.raw_data", "array", "[[sequence, value], ...]，历史原始数据。"],
      ["record/save.folder_path", "string", "录制文件保存目录。"],
    ],
    record: [
      ["record_start_sequence / record_end_sequence", "用户点击 start 到 end 的真实记录范围。"],
      ["capture_start_sequence / capture_end_sequence", "实际保存范围，包含 start 前和 end 后冗余点。"],
      ["segments.pre", "start 前冗余数据，redundant = true。"],
      ["segments.record", "用户真正选择的数据，redundant = false。"],
      ["segments.post", "end 后冗余数据，redundant = true。"],
      ["raw_data / filtered_data", "{ sequence, value, timestamp, segment }[]。"],
      ["peak / valley", "{ sequence, value, segment }[]。"],
    ],
    recordExample: `{
  "record_start_sequence": 1224,
  "record_end_sequence": 2547,
  "capture_start_sequence": 1124,
  "capture_end_sequence": 2647,
  "raw_data": [
    { "sequence": 1224, "value": 210.4, "timestamp": 1778482500.1, "segment": "record" }
  ],
  "peak": [
    { "sequence": 1302, "value": 246.1, "segment": "record" }
  ]
}`,
  },
  en: {
    runtime: [
      ["Backend API", () => endpoint(runtimeConfig.backendHost, runtimeConfig.backendPort)],
      ["Realtime subscription", () => `${endpoint(runtimeConfig.backendHost, runtimeConfig.backendPort)}/breath`],
      ["Sensor input", () => `${runtimeConfig.sensorHost || "-"}:${runtimeConfig.sensorPort || "-"}`],
      ["Push interval", () => "About every 40 ms"],
    ],
    flow: [
      "Call GET /health or GET /stream/status to check backend and sensor state.",
      "Call POST /startReceive with FilterConfig to start receiving and processing data.",
      "Connect to Socket.IO /breath and listen for breath events.",
      "Consume raw, filtered, peak, valley, and metrics by message type.",
      "For recording, call /record/start, /record/end, and /record/save.",
      "For offline filtering, call /applyFilter with historical raw_data.",
    ],
    socketSummary: [
      ["namespace", "/breath"],
      ["event", "breath"],
      ["message", "{ type, data }"],
      ["sequence", "Primary key for continuity. Do not connect chart gaps across lost data."],
    ],
    endpoints: [
      ["GET", "/health", "Check backend state and configured sensor host/port."],
      ["GET", "/stream/status", "Check receive state, sensor connection, last data, and record state."],
      ["POST", "/startReceive", "Start receiving and realtime processing. Body can be omitted to use default FilterConfig."],
      ["POST", "/setRTFilterParams", "Update realtime filter and detection params. Body can be omitted to use default FilterConfig."],
      ["POST", "/applyFilter", "Offline filter raw_data. Body can be omitted and returns an empty result."],
      ["POST", "/record/start", "Start recording."],
      ["POST", "/record/end", "End the user-selected record range."],
      ["POST", "/record/save", "Save record file and return data.file_path. Body can be omitted to use the default folder."],
    ],
    payloads: [
      {
        title: "raw",
        desc: "Raw breath sample points.",
        rows: [["data[n][0]", "sequence generated by backend"], ["data[n][1]", "raw sensor value"]],
        sample: { type: "raw", data: [[1024, 188.42]] },
      },
      {
        title: "filtered",
        desc: "Realtime filtered breath sample points.",
        rows: [["data[n][0]", "sequence matching raw"], ["data[n][1]", "filtered value"]],
        sample: { type: "filtered", data: [[1024, 187.63]] },
      },
      {
        title: "peak / valley",
        desc: "Detected peak or valley points.",
        rows: [["data[n][0]", "marker sequence"], ["data[n][1]", "marker filtered value"]],
        sample: { type: "peak", data: [[1088, 246.19]] },
      },
      {
        title: "metrics",
        desc: "BPM and stability metrics.",
        rows: [
          ["bpm", "breaths per minute"],
          ["quality", "insufficient / stable / variable / irregular"],
          ["breath_count", "peaks used by current window"],
          ["interval_cv", "peak interval coefficient of variation"],
        ],
        sample: { type: "metrics", data: [{ bpm: 18.25, quality: "stable", breath_count: 6, interval_cv: 0.08 }] },
      },
    ],
    sensor: [
      ["Connection", "Backend acts as TCP client and connects to [sensor].host:[sensor].port."],
      ["Packet length", "4 bytes. Each read packet is one sensor sample."],
      ["Used bytes", "Only byte[2] and byte[3] are used; byte[0] and byte[1] are ignored now."],
      ["Raw value", "sensor_value = byte[2] * 256 + byte[3], range 0-65535."],
      ["Output mapping", "Each sensor_value becomes Socket.IO raw [sequence, value]."],
    ],
    sensorExample: `byte[0]  byte[1]  byte[2]  byte[3]
unused   unused   high     low

sensor_value = high * 256 + low
raw message = { "type": "raw", "data": [[sequence, sensor_value]] }`,
    filters: [
      ["FilterConfig.low_bpm", "number", "Low breath-rate boundary for cutoff conversion."],
      ["FilterConfig.high_bpm", "number", "High breath-rate boundary for cutoff conversion."],
      ["FilterConfig.sampling_rate", "number", "Sampling rate used by BPM and marker intervals."],
      ["FilterConfig.moving_avg_window", "number", "Moving average window."],
      ["FilterConfig.gaussian_sigma", "number", "Smoothing strength."],
      ["FilterConfig.min_peak_distance", "number", "Minimum sample distance between markers."],
      ["FilterConfig.peak_threshold_ratio", "number", "Adaptive marker prominence ratio."],
      ["FilterConfig.prominence", "number", "Manual marker prominence."],
      ["FilterConfig.auto_peak_detection", "boolean", "Enable adaptive marker detection."],
      ["FilterConfig.confirm_realtime_events", "boolean", "Enable short-delay marker confirmation."],
      ["FilterConfig.confirmation_delay_points", "number", "Future samples to wait before confirming markers."],
      ["FilterConfig.data_gap_reset_points", "number", "Reset realtime detection when sequence gap exceeds this."],
      ["FilterConfig.gap_warmup_points", "number", "Samples to wait after a data gap before emitting markers."],
      ["FilterConfig.restore_baseline", "boolean", "Restore filtered signal near original baseline."],
      ["applyFilter.raw_data", "array", "[[sequence, value], ...] historical raw data."],
      ["record/save.folder_path", "string", "Record output folder."],
    ],
    record: [
      ["record_start_sequence / record_end_sequence", "The true user-selected record range."],
      ["capture_start_sequence / capture_end_sequence", "The full saved range including pre/post padding."],
      ["segments.pre", "Pre-start padding, redundant = true."],
      ["segments.record", "User-selected data, redundant = false."],
      ["segments.post", "Post-end padding, redundant = true."],
      ["raw_data / filtered_data", "{ sequence, value, timestamp, segment }[]."],
      ["peak / valley", "{ sequence, value, segment }[]."],
    ],
    recordExample: `{
  "record_start_sequence": 1224,
  "record_end_sequence": 2547,
  "capture_start_sequence": 1124,
  "capture_end_sequence": 2647,
  "raw_data": [
    { "sequence": 1224, "value": 210.4, "timestamp": 1778482500.1, "segment": "record" }
  ],
  "peak": [
    { "sequence": 1302, "value": 246.1, "segment": "record" }
  ]
}`,
  },
};

function preferredLanguage() {
  const saved = localStorage.getItem(LANGUAGE_KEY);
  if (saved === "zh" || saved === "en") {
    return saved;
  }
  return navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
}

let language = preferredLanguage();

function endpoint(host, port) {
  if (!host || !port) {
    return "-";
  }
  return `http://${host}:${port}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function t(key) {
  return TEXT[language]?.[key] ?? TEXT.en[key] ?? key;
}

function renderRuntime() {
  document.querySelector("#runtimeGrid").innerHTML = CONTENT[language].runtime
    .map(([label, value]) => `<div class="runtime-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value())}</strong></div>`)
    .join("");
}

function renderFlow() {
  document.querySelector("#flowList").innerHTML = CONTENT[language].flow
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
}

function renderSocket() {
  document.querySelector("#socketSummary").innerHTML = CONTENT[language].socketSummary
    .map(([label, value]) => `<div class="summary-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
}

function renderEndpoints() {
  document.querySelector("#endpointTable").innerHTML = CONTENT[language].endpoints
    .map(([method, route, desc]) => `
      <article class="endpoint-row">
        <div><span>${escapeHtml(t("table.method"))}</span><strong class="method ${method === "POST" ? "post" : ""}">${escapeHtml(method)}</strong></div>
        <div><span>${escapeHtml(t("table.path"))}</span><strong class="route">${escapeHtml(route)}</strong></div>
        <div><span>${escapeHtml(t("table.description"))}</span><strong>${escapeHtml(desc)}</strong></div>
      </article>
    `)
    .join("");
}

function renderPayloads() {
  document.querySelector("#payloadList").innerHTML = CONTENT[language].payloads
    .map((item) => `
      <article class="payload-card">
        <span>${escapeHtml(item.title)}</span>
        <strong>${escapeHtml(item.desc)}</strong>
        ${item.rows.map(([field, desc]) => `<p><code>${escapeHtml(field)}</code> ${escapeHtml(desc)}</p>`).join("")}
        <pre><code>${escapeHtml(JSON.stringify(item.sample, null, 2))}</code></pre>
      </article>
    `)
    .join("");
}

function renderSensor() {
  document.querySelector("#sensorList").innerHTML = CONTENT[language].sensor
    .map(([label, value]) => `<div class="summary-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
  document.querySelector("#sensorExample").textContent = CONTENT[language].sensorExample;
}

function renderFilters() {
  document.querySelector("#filterTable").innerHTML = CONTENT[language].filters
    .map(([name, type, desc]) => `
      <div class="field-row">
        <code>${escapeHtml(name)}</code>
        <em>${escapeHtml(type)}</em>
        <p>${escapeHtml(desc)}</p>
      </div>
    `)
    .join("");
}

function renderRecord() {
  document.querySelector("#recordList").innerHTML = CONTENT[language].record
    .map(([label, value]) => `<div class="summary-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`)
    .join("");
  document.querySelector("#recordExample").textContent = CONTENT[language].recordExample;
}

function applyLanguage(nextLanguage = language) {
  language = nextLanguage;
  localStorage.setItem(LANGUAGE_KEY, language);
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.title = t("app.title");
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  renderRuntime();
  renderFlow();
  renderSocket();
  renderPayloads();
  renderEndpoints();
  renderSensor();
  renderFilters();
  renderRecord();
}

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
