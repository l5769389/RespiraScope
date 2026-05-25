const runtimeConfig = window.CT_BREATH_RUNTIME_CONFIG || {};
const LANGUAGE_KEY = "RespiraScope-language";

const TEXT = {
  zh: {
    "app.kicker": "接口说明",
    "app.title": "RespiraScope 接口使用说明",
    "app.subtitle": "说明调用顺序、请求体、返回字段、前置条件和错误状态。",
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
    "record.title": "record/end 与保存文件",
    "table.method": "方法",
    "table.path": "路径",
    "table.description": "说明",
  },
  en: {
    "app.kicker": "Integration",
    "app.title": "RespiraScope API Guide",
    "app.subtitle": "Call order, request bodies, response fields, preconditions, and error states.",
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
    "record.title": "record/end and Saved Files",
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
      "调用 GET /health 或 GET /runtime/config，确认后端、传感器和前端入口。",
      "调用 POST /startReceive，传入可选 FilterConfig；如果已经开始接收，会直接返回当前 stream，不会用本次 body 更新参数。",
      "连接 Socket.IO /breath，监听 breath 事件；新客户端连接后会收到最近实时数据快照。",
      "按 type 分别消费 raw、filtered、peak、valley、metrics、signal_quality。",
      "录制前先确保已经收到 raw 数据；然后调用 /record/start，录制中可多次调用 /scan/start、/scan/end。",
      "/record/end 会结束记录，等待 post 辅助点，并返回精简的离线滤波结果、segments 和 scans。",
      "/record/save 保存完整文件；历史数据重新滤波仍可单独调用 /applyFilter。",
      "停止传感器接收时调用 /stopReceive。",
    ],
    socketSummary: [
      ["namespace", "/breath"],
      ["event", "breath"],
      ["message", "{ type, data }"],
      ["snapshot", "新客户端连接后会通过同一个 breath 事件收到最近 raw/filtered/peak/valley/metrics/signal_quality 快照。"],
      ["response", "核心 HTTP 接口通常返回 { code, status, message, data }；时间字段统一为 ISO-8601 字符串。"],
      ["sequence", "判断连续性的主键；断流时不要把缺口直接连线。"],
    ],
    endpoints: [
      ["GET", "/health", "启动前检查。无请求体；返回后端健康状态、mock 开关、sensor.host/port 和前端入口。"],
      ["GET", "/runtime/config", "读取运行时配置。无请求体；返回后端、传感器、前端页面和 record pre/post 辅助点。"],
      ["GET", "/stream/status", "读取实时状态。无请求体；返回 started/state、receiver、tasks、queues、queue_stats、record、signal_quality、filter_config。"],
      ["POST", "/startReceive", "开始接收和实时处理。请求体为可选 FilterConfig；已运行时直接返回当前 stream，不会更新本次 body 参数。"],
      ["POST", "/stopReceive", "停止传感器接收并清理实时上下文。无请求体；返回最新 stream，未运行时也返回 stopped 状态。"],
      ["POST", "/setRTFilterParams", "更新实时滤波和峰谷识别参数。请求体为可选 FilterConfig；运行中调参应使用该接口。"],
      ["POST", "/applyFilter", "对任意历史 raw_data 做离线滤波。请求体为 { filter_config, raw_data }；返回 data、peak、valley、filter_config、metrics。"],
      ["POST", "/record/start", "开始记录。无请求体；要求已 startReceive 且已收到 raw 数据；已记录中会直接返回当前 record。"],
      ["POST", "/scan/start", "开始一次扫描标记。无请求体；只能在 recording=true 且没有活动 scan 时调用；返回 scan 和 record。"],
      ["POST", "/scan/end", "结束当前扫描标记。无请求体；要求存在活动 scan；返回本次 scan 的 index、start_sequence、end_sequence。"],
      ["POST", "/record/end", "结束记录并离线滤波。无请求体；返回精简 data、raw_data、peak、valley、metrics、filter_status、segments、scans。"],
      ["POST", "/record/reset", "清空当前后端 record/scan 状态。无请求体；不会停止传感器接收，返回重置后的 record。"],
      ["POST", "/record/save", "保存完整记录文件。请求体为可选 { folder_path }；返回 data.file_path；前置条件不满足时返回 HTTP 400。"],
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
      {
        title: "signal_quality",
        desc: "实时信号质量和异常片段事件，可用于提示断流、低幅度、强干扰或噪声异常。",
        rows: [
          ["sequence", "触发异常或质量状态的采样序号"],
          ["value", "触发事件时的原始信号值"],
          ["quality", "good / low_amplitude / artifact / noisy / gap"],
          ["details", "附加原因，例如 delta、baseline_delta、gap_points"],
        ],
        sample: {
          type: "signal_quality",
          data: [{
            sequence: 2048,
            value: 845.68,
            quality: "artifact",
            details: { delta: 421.93, baseline_delta: 335.23, kind: "sudden_change" },
          }],
        },
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
      ["HTTP success", "object", "核心接口通常返回 { code, status, message, data }；兼容字段可能同步放在顶层。"],
      ["HTTP error", "object", "业务错误通常是 HTTP 400，错误详情在 detail.message，detail.data.record 会带当前记录状态。"],
      ["FilterConfig.low_bpm", "number", "低呼吸频率边界，用于换算滤波截止频率。"],
      ["FilterConfig.high_bpm", "number", "高呼吸频率边界，用于换算滤波截止频率。"],
      ["FilterConfig.lowpass_cutoff", "number", "由 low_bpm / 60 规范化，外部系统通常不用直接传。"],
      ["FilterConfig.highpass_cutoff", "number", "由 high_bpm / 60 规范化，外部系统通常不用直接传。"],
      ["FilterConfig.order", "number", "滤波阶数。"],
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
      ["applyFilter.raw_data", "array", "[[sequence, value], ...]，历史原始数据；返回 data、peak、valley、filter_config、metrics。"],
      ["record/save.folder_path", "string", "录制文件保存目录；省略时默认 D:/ct/breath-file。"],
      ["scan/start 与 scan/end", "endpoint", "只能在 record/start 与 record/end 之间调用，可形成多段扫描区间。"],
      ["record/reset", "endpoint", "清空后端当前 record/scan 状态；不会停止传感器接收。"],
      ["record/end compact", "response", "不返回 scan_indexes、filter_config、capture_start_sequence、capture_end_sequence。"],
      ["time fields", "string", "所有接口时间字段统一返回 ISO-8601 字符串；耗时字段仍使用数值秒数。"],
      ["stream.status.queue_stats", "object", "各实时队列 dropped 计数和 high_watermark。"],
      ["stream.status.signal_quality", "object", "当前信号质量、最近事件和事件累计次数。"],
    ],
    record: [
      ["record_start_sequence / record_end_sequence", "用户点击 start 到 end 的真实记录范围。"],
      ["segments.pre", "start 前辅助数据，auxiliary = true。"],
      ["segments.record", "用户真正选择的数据，auxiliary = false。"],
      ["segments.post", "end 后辅助数据，auxiliary = true。"],
      ["scans", "{ index, start_time, end_time, start_sequence, end_sequence }[]，时间字段为 ISO 字符串。"],
      ["record/end.data", "离线滤波结果数组，点结构为 { sequence, value, timestamp?, segment }。"],
      ["raw_data / data", "{ sequence, value, timestamp, segment }[]，timestamp 为 ISO 字符串。record/end 不返回 scan_indexes。"],
      ["peak / valley", "{ sequence, value, segment }[]。record/end 不返回 scan_indexes。"],
      ["filter_status", "record/end 返回 offline、too_short 或 no_data，用于说明离线滤波结果状态。"],
      ["saved file", "保存文件会额外包含 capture_start_sequence、capture_end_sequence、filter_params 和点级 scan_indexes。"],
    ],
    recordExample: `{
  "record_start_sequence": 1224,
  "record_end_sequence": 2547,
  "segments": {
    "pre": { "start_sequence": 1124, "end_sequence": 1223, "auxiliary": true },
    "record": { "start_sequence": 1224, "end_sequence": 2547, "auxiliary": false },
    "post": { "start_sequence": 2548, "end_sequence": 2647, "auxiliary": true }
  },
  "scans": [
    {
      "index": 1,
      "start_time": "2026-05-25T10:30:10.000000+00:00",
      "end_time": "2026-05-25T10:30:35.000000+00:00",
      "start_sequence": 1300,
      "end_sequence": 1600
    }
  ],
  "raw_data": [
    { "sequence": 1224, "value": 210.4, "timestamp": "2026-05-25T10:30:00.000000+00:00", "segment": "record" }
  ],
  "data": [
    { "sequence": 1302, "value": 205.9, "segment": "record" }
  ],
  "peak": [
    { "sequence": 1302, "value": 246.1, "segment": "record" }
  ],
  "filter_status": "offline"
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
      "Call GET /health or GET /runtime/config to check backend, sensor, and frontend entry points.",
      "Call POST /startReceive with an optional FilterConfig; if receiving is already running, the current stream is returned and this body does not update params.",
      "Connect to Socket.IO /breath and listen for breath events; new clients receive a recent realtime snapshot after connecting.",
      "Consume raw, filtered, peak, valley, metrics, and signal_quality by message type.",
      "Before recording, make sure at least one raw sample has arrived; then call /record/start and optionally call /scan/start and /scan/end multiple times.",
      "/record/end ends recording, waits for post padding, and returns compact offline-filtered data, segments, and scans.",
      "/record/save saves the full file; for arbitrary historical offline filtering, call /applyFilter with raw_data.",
      "Call /stopReceive when the integrating system needs to stop sensor receiving.",
    ],
    socketSummary: [
      ["namespace", "/breath"],
      ["event", "breath"],
      ["message", "{ type, data }"],
      ["snapshot", "After a new client connects, recent raw/filtered/peak/valley/metrics/signal_quality snapshots are emitted through the same breath event."],
      ["response", "Core HTTP APIs usually return { code, status, message, data }; time fields are ISO-8601 strings."],
      ["sequence", "Primary key for continuity. Do not connect chart gaps across lost data."],
    ],
    endpoints: [
      ["GET", "/health", "Startup check. No body; returns backend health, mock flag, sensor.host/port, and frontend entries."],
      ["GET", "/runtime/config", "Read runtime config. No body; returns backend, sensor, frontend entries, and record pre/post padding."],
      ["GET", "/stream/status", "Read realtime status. No body; returns started/state, receiver, tasks, queues, queue_stats, record, signal_quality, and filter_config."],
      ["POST", "/startReceive", "Start receiving and realtime processing. Body is optional FilterConfig; if already running, returns current stream and does not apply this body."],
      ["POST", "/stopReceive", "Stop sensor receiving and clear realtime context. No body; returns the latest stream and also returns stopped when it was not running."],
      ["POST", "/setRTFilterParams", "Update realtime filter and marker detection params. Body is optional FilterConfig; use this endpoint for runtime parameter changes."],
      ["POST", "/applyFilter", "Offline filter arbitrary raw_data. Body is { filter_config, raw_data }; returns data, peak, valley, filter_config, and metrics."],
      ["POST", "/record/start", "Start recording. No body; requires startReceive and at least one raw sample; if already recording, returns current record."],
      ["POST", "/scan/start", "Start one scan marker. No body; only valid when recording=true and no scan is active; returns scan and record."],
      ["POST", "/scan/end", "End the active scan marker. No body; requires an active scan; returns index, start_sequence, and end_sequence."],
      ["POST", "/record/end", "End recording and run offline filtering. No body; returns compact data, raw_data, peak, valley, metrics, filter_status, segments, and scans."],
      ["POST", "/record/reset", "Clear current backend record/scan state. No body; does not stop sensor receiving and returns the reset record state."],
      ["POST", "/record/save", "Save the full record file. Body is optional { folder_path }; returns data.file_path; unmet preconditions return HTTP 400."],
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
      {
        title: "signal_quality",
        desc: "Realtime signal-quality and abnormal-segment events for gap, low amplitude, strong artifact, or noise prompts.",
        rows: [
          ["sequence", "sample sequence that triggered the event"],
          ["value", "raw signal value at the event"],
          ["quality", "good / low_amplitude / artifact / noisy / gap"],
          ["details", "extra reason fields such as delta, baseline_delta, or gap_points"],
        ],
        sample: {
          type: "signal_quality",
          data: [{
            sequence: 2048,
            value: 845.68,
            quality: "artifact",
            details: { delta: 421.93, baseline_delta: 335.23, kind: "sudden_change" },
          }],
        },
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
      ["HTTP success", "object", "Core APIs usually return { code, status, message, data }; compatibility fields may also appear at the top level."],
      ["HTTP error", "object", "Business errors are usually HTTP 400. Read detail.message; detail.data.record carries current record state."],
      ["FilterConfig.low_bpm", "number", "Low breath-rate boundary for cutoff conversion."],
      ["FilterConfig.high_bpm", "number", "High breath-rate boundary for cutoff conversion."],
      ["FilterConfig.lowpass_cutoff", "number", "Normalized from low_bpm / 60; integrating systems usually do not need to pass it."],
      ["FilterConfig.highpass_cutoff", "number", "Normalized from high_bpm / 60; integrating systems usually do not need to pass it."],
      ["FilterConfig.order", "number", "Filter order."],
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
      ["applyFilter.raw_data", "array", "[[sequence, value], ...] historical raw data; returns data, peak, valley, filter_config, and metrics."],
      ["record/save.folder_path", "string", "Record output folder; defaults to D:/ct/breath-file when omitted."],
      ["scan/start and scan/end", "endpoint", "Only valid between record/start and record/end; creates scan ranges inside the record."],
      ["record/reset", "endpoint", "Clears backend record/scan state without stopping sensor receiving."],
      ["record/end compact", "response", "Does not return scan_indexes, filter_config, capture_start_sequence, or capture_end_sequence."],
      ["time fields", "string", "All API time fields are ISO-8601 strings; elapsed durations remain numeric seconds."],
      ["stream.status.queue_stats", "object", "Dropped counts and high_watermark for realtime queues."],
      ["stream.status.signal_quality", "object", "Current signal quality, latest event, and event counts."],
    ],
    record: [
      ["record_start_sequence / record_end_sequence", "The true user-selected record range."],
      ["segments.pre", "Pre-start padding, auxiliary = true."],
      ["segments.record", "User-selected data, auxiliary = false."],
      ["segments.post", "Post-end padding, auxiliary = true."],
      ["scans", "{ index, start_time, end_time, start_sequence, end_sequence }[] for each scan range. Times are ISO strings."],
      ["record/end.data", "Offline filtered points as { sequence, value, timestamp?, segment }."],
      ["raw_data / data", "{ sequence, value, timestamp, segment }[]. timestamp is an ISO string. record/end does not return scan_indexes."],
      ["peak / valley", "{ sequence, value, segment }[]. record/end does not return scan_indexes."],
      ["filter_status", "record/end returns offline, too_short, or no_data."],
      ["saved file", "Saved files also include capture_start_sequence, capture_end_sequence, filter_params, and per-point scan_indexes."],
    ],
    recordExample: `{
  "record_start_sequence": 1224,
  "record_end_sequence": 2547,
  "segments": {
    "pre": { "start_sequence": 1124, "end_sequence": 1223, "auxiliary": true },
    "record": { "start_sequence": 1224, "end_sequence": 2547, "auxiliary": false },
    "post": { "start_sequence": 2548, "end_sequence": 2647, "auxiliary": true }
  },
  "scans": [
    {
      "index": 1,
      "start_time": "2026-05-25T10:30:10.000000+00:00",
      "end_time": "2026-05-25T10:30:35.000000+00:00",
      "start_sequence": 1300,
      "end_sequence": 1600
    }
  ],
  "raw_data": [
    { "sequence": 1224, "value": 210.4, "timestamp": "2026-05-25T10:30:00.000000+00:00", "segment": "record" }
  ],
  "data": [
    { "sequence": 1302, "value": 205.9, "segment": "record" }
  ],
  "peak": [
    { "sequence": 1302, "value": 246.1, "segment": "record" }
  ],
  "filter_status": "offline"
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
