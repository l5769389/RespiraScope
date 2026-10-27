const runtimeConfig = window.CT_BREATH_RUNTIME_CONFIG || {};
const LANGUAGE_KEY = "RespiraScope-language";

const TEXT = {
  zh: {
    "app.kicker": "使用说明",
    "app.title": "配置与使用说明",
    "app.subtitle": "面向部署和日常使用的基础说明。",
    "runtime.kicker": "当前状态",
    "runtime.title": "当前运行摘要",
    "config.kicker": "配置",
    "config.title": "配置项作用",
    "quick.kicker": "入门",
    "quick.title": "基础使用流程",
    "notes.kicker": "判断",
    "notes.title": "常见判断",
  },
  en: {
    "app.kicker": "Guide",
    "app.title": "Configuration And Usage Guide",
    "app.subtitle": "Basic notes for deployment and daily operation.",
    "runtime.kicker": "Runtime",
    "runtime.title": "Current Runtime Summary",
    "config.kicker": "Config",
    "config.title": "What Each Config Item Does",
    "quick.kicker": "Quick Start",
    "quick.title": "Basic User Flow",
    "notes.kicker": "Checks",
    "notes.title": "Common Checks",
  },
};

const CONTENT = {
  zh: {
    runtime: [
      ["配置文件", () => runtimeConfig.configPath || "D:/ct/breath-config/breath.toml"],
      ["后端接口", () => endpoint(runtimeConfig.backendHost, runtimeConfig.backendPort)],
      ["控制台", () => endpoint(runtimeConfig.consoleHost, runtimeConfig.consolePort)],
      ["模拟信号", () => (runtimeConfig.mockSignalEnabled ? "已启用" : "未启用")],
      ["传感器", () => endpoint(runtimeConfig.sensorHost, runtimeConfig.sensorPort)],
      ["Monitor", () => (runtimeConfig.monitorEnabled ? "显示" : "隐藏")],
      ["模拟设置", () => (runtimeConfig.labEnabled ? "显示" : "隐藏")],
      ["接口说明", () => endpoint(runtimeConfig.apiDocsHost, runtimeConfig.apiDocsPort)],
      ["记录冗余点", () => `${runtimeConfig.record?.prePoints ?? 0} / ${runtimeConfig.record?.postPoints ?? 0}`],
    ],
    config: [
      {
        title: "[mock]",
        fields: [
          ["enabled", "是否启用内置模拟信号。启用后会开放 /mock/* 接口，并显示“模拟信号设置”页。"],
          ["bind_host", "模拟 TCP 信号服务监听地址。通常开发环境用 0.0.0.0。"],
        ],
      },
      {
        title: "[sensor]",
        fields: [
          ["host", "真实呼吸设备的 IP；启用模拟信号时也可以指向本机 localhost。"],
          ["port", "真实呼吸设备或模拟 TCP 信号服务的端口。"],
        ],
      },
      {
        title: "[backend]",
        fields: [
          ["host", "后端 API 和 Socket.IO 服务监听地址。部署到局域网时常用 0.0.0.0。"],
          ["port", "后端 API 端口，Monitor 会通过它接收实时呼吸数据。"],
        ],
      },
      {
        title: "[console]",
        fields: [
          ["enabled", "是否启动网页控制台。关闭后 Monitor、模拟设置和说明页都不会启动。"],
          ["host", "网页控制台监听地址。"],
          ["port", "网页控制台端口。默认访问入口通常是 http://127.0.0.1:5175。"],
        ],
      },
      {
        title: "[lab] / [monitor]",
        fields: [
          ["lab.enabled", "是否显示“模拟信号设置”Tab。真实设备模式下会自动隐藏。"],
          ["monitor.enabled", "是否显示“呼吸监测”Tab。"],
        ],
      },
      {
        title: "[record]",
        fields: [
          ["pre_points", "点击“开始记录”之前额外保留的采样点数。"],
          ["post_points", "点击“结束记录”之后额外保留的采样点数。"],
        ],
      },
    ],
    steps: [
      "确认配置文件位于 D:/ct/breath-config/breath.toml，并检查设备 IP、端口和后端端口。",
      "开发环境运行 scripts/dev.ps1，生产环境运行打包后的 RespiraScope.exe。",
      "打开控制台地址，进入“呼吸监测”Tab，点击“开始监测”。",
      "如果使用模拟信号，进入“模拟信号设置”Tab，选择预设并点击“应用到模拟源”。",
      "需要保存一段呼吸数据时，在 Monitor 中点击“开始记录”和“结束记录”，再保存记录文件。",
      "记录文件中的 record 区间是真正用户选择的片段，pre/post 是为离线滤波保留的冗余数据。",
    ],
    notes: [
      ["启动后无数据", "先确认传感器或模拟信号服务已连接，再检查 [sensor].host 和 [sensor].port。"],
      ["看不到模拟设置", "需要 [mock].enabled = true 且 [lab].enabled = true。真实设备模式会隐藏该页。"],
      ["需要给其他电脑访问", "把 [console].host 或 [backend].host 配成可被局域网访问的地址，并开放对应端口。"],
    ],
  },
  en: {
    runtime: [
      ["Config file", () => runtimeConfig.configPath || "D:/ct/breath-config/breath.toml"],
      ["Backend API", () => endpoint(runtimeConfig.backendHost, runtimeConfig.backendPort)],
      ["Console", () => endpoint(runtimeConfig.consoleHost, runtimeConfig.consolePort)],
      ["Mock signal", () => (runtimeConfig.mockSignalEnabled ? "Enabled" : "Disabled")],
      ["Sensor", () => endpoint(runtimeConfig.sensorHost, runtimeConfig.sensorPort)],
      ["Monitor", () => (runtimeConfig.monitorEnabled ? "Visible" : "Hidden")],
      ["Mock setup", () => (runtimeConfig.labEnabled ? "Visible" : "Hidden")],
      ["API docs", () => endpoint(runtimeConfig.apiDocsHost, runtimeConfig.apiDocsPort)],
      ["Record padding", () => `${runtimeConfig.record?.prePoints ?? 0} / ${runtimeConfig.record?.postPoints ?? 0}`],
    ],
    config: [
      {
        title: "[mock]",
        fields: [
          ["enabled", "Enables the built-in mock signal source, /mock/* APIs, and the Mock Signal Setup page."],
          ["bind_host", "Listening host for the mock TCP signal server."],
        ],
      },
      {
        title: "[sensor]",
        fields: [
          ["host", "IP address of the real breath device, or localhost when mock signal is enabled."],
          ["port", "Port of the real device or mock TCP signal server."],
        ],
      },
      {
        title: "[backend]",
        fields: [
          ["host", "Host for backend API and Socket.IO service."],
          ["port", "Backend API port used by Monitor for realtime breath data."],
        ],
      },
      {
        title: "[console]",
        fields: [
          ["enabled", "Starts or disables the web console, including Monitor, Mock Setup, and this guide."],
          ["host", "Listening host for the web console."],
          ["port", "Web console port. The default URL is usually http://127.0.0.1:5175."],
        ],
      },
      {
        title: "[lab] / [monitor]",
        fields: [
          ["lab.enabled", "Shows or hides the Mock Signal Setup tab. Real-device mode hides it automatically."],
          ["monitor.enabled", "Shows or hides the Breath Monitor tab."],
        ],
      },
      {
        title: "[record]",
        fields: [
          ["pre_points", "Extra samples kept before Record Start."],
          ["post_points", "Extra samples kept after Record End."],
        ],
      },
    ],
    steps: [
      "Check D:/ct/breath-config/breath.toml and confirm device IP, device port, and backend port.",
      "In dev, run scripts/dev.ps1. In production, run the packaged RespiraScope.exe.",
      "Open the console URL, go to Breath Monitor, and click Start Monitoring.",
      "When using mock signal, go to Mock Signal Setup, choose a preset, and apply it to the mock source.",
      "To save a segment, use Record Start and Record End in Monitor, then save the record file.",
      "In saved files, the record range is the true user-selected segment; pre/post data is padding for offline filtering.",
    ],
    notes: [
      ["No data after start", "Confirm the real sensor or mock signal source is connected, then check [sensor].host and [sensor].port."],
      ["Mock setup is hidden", "It requires [mock].enabled = true and [lab].enabled = true. Real-device mode hides it."],
      ["LAN access", "Use reachable [console].host and [backend].host values, and allow the configured ports."],
    ],
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

function normalizePathPrefix(value) {
  const text = String(value || "").trim();
  if (!text || text === "/") {
    return "";
  }
  const withSlash = text.startsWith("/") ? text : `/${text}`;
  return withSlash.replace(/\/+$/, "");
}

function publicEndpoint(kind) {
  const path =
    kind === "api"
      ? normalizePathPrefix(runtimeConfig.apiBasePath)
      : normalizePathPrefix(runtimeConfig.publicBasePath);
  return path ? `${window.location.origin}${path}` : "";
}

function endpoint(host, port) {
  if (!host || !port) {
    return "-";
  }
  if (host === runtimeConfig.backendHost && port === runtimeConfig.backendPort) {
    return publicEndpoint("api") || `http://${host}:${port}`;
  }
  if (
    (host === runtimeConfig.consoleHost && port === runtimeConfig.consolePort)
    || (host === runtimeConfig.apiDocsHost && port === runtimeConfig.apiDocsPort)
  ) {
    return publicEndpoint("frontend") || `http://${host}:${port}`;
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

function applyLanguage(nextLanguage = language) {
  language = nextLanguage;
  localStorage.setItem(LANGUAGE_KEY, language);
  document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
  document.title = t("app.title");
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  renderRuntime();
  renderConfig();
  renderSteps();
  renderNotes();
}

function renderRuntime() {
  const data = CONTENT[language].runtime;
  document.querySelector("#runtimeGrid").innerHTML = data
    .map(([label, value]) => `<div class="runtime-item"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value())}</strong></div>`)
    .join("");
}

function renderConfig() {
  document.querySelector("#configTable").innerHTML = CONTENT[language].config
    .map((section) => `
      <article class="config-section">
        <h3>${escapeHtml(section.title)}</h3>
        ${section.fields.map(([name, description]) => `
          <div class="field-row">
            <code>${escapeHtml(name)}</code>
            <p>${escapeHtml(description)}</p>
          </div>
        `).join("")}
      </article>
    `)
    .join("");
}

function renderSteps() {
  document.querySelector("#usageSteps").innerHTML = CONTENT[language].steps
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
}

function renderNotes() {
  document.querySelector("#notesList").innerHTML = CONTENT[language].notes
    .map(([title, description]) => `
      <article class="note-card">
        <span>${escapeHtml(t("notes.kicker"))}</span>
        <strong>${escapeHtml(title)}</strong>
        <p>${escapeHtml(description)}</p>
      </article>
    `)
    .join("");
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
