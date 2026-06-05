const runtimeConfig = window.CT_BREATH_RUNTIME_CONFIG || {};
const LANGUAGE_KEY = "RespiraScope-language";
const PUBLIC_BASE_PATH = normalizePathPrefix(runtimeConfig.publicBasePath);

const TEXT = {
  zh: {
    kicker: "Breath Console",
    title: "呼吸控制台",
    language: "语言",
    monitor: "呼吸监测",
    lab: "模拟信号设置",
    guide: "使用说明",
    apiDocs: "接口说明",
    disabledTitle: "没有可用前端",
    disabledText: "请检查配置文件中的 [console]、[monitor] 和 [lab] 开关。",
  },
  en: {
    kicker: "Breath Console",
    title: "Breath Console",
    language: "Language",
    monitor: "Breath Monitor",
    lab: "Mock Signal Setup",
    guide: "Guide",
    apiDocs: "API",
    disabledTitle: "No frontend is enabled",
    disabledText: "Check [console], [monitor], and [lab] in the config file.",
  },
};

const dom = {
  kicker: document.querySelector("#consoleKicker"),
  title: document.querySelector("#consoleTitle"),
  disabledPanel: document.querySelector("#disabledPanel"),
  disabledTitle: document.querySelector("#disabledTitle"),
  disabledText: document.querySelector("#disabledText"),
  languageLabel: document.querySelector("#languageLabel"),
  languageSelect: document.querySelector("#languageSelect"),
  tabs: Array.from(document.querySelectorAll(".tab-button")),
  frames: {
    monitor: document.querySelector("#monitorFrame"),
    lab: document.querySelector("#labFrame"),
    guide: document.querySelector("#guideFrame"),
    apiDocs: document.querySelector("#apiDocsFrame"),
  },
};

const TAB_ALIASES = {
  monitor: "monitor",
  lab: "lab",
  guide: "guide",
  api: "apiDocs",
  apiDocs: "apiDocs",
  "api-docs": "apiDocs",
};

function normalizePathPrefix(value) {
  const text = String(value || "").trim();
  if (!text || text === "/") {
    return "";
  }
  const withSlash = text.startsWith("/") ? text : `/${text}`;
  return withSlash.replace(/\/+$/, "");
}

function withPublicBasePath(path) {
  if (!path || !PUBLIC_BASE_PATH || /^[a-z]+:\/\//i.test(path)) {
    return path;
  }
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${PUBLIC_BASE_PATH}${normalized}`;
}

function preferredLanguage() {
  const saved = localStorage.getItem(LANGUAGE_KEY);
  if (saved === "zh" || saved === "en") {
    return saved;
  }
  return navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function labels() {
  return TEXT[preferredLanguage()] ?? TEXT.en;
}

function sendLanguageToFrames(nextLanguage = preferredLanguage()) {
  Object.values(dom.frames).forEach((frame) => {
    if (!frame?.contentWindow) {
      return;
    }
    frame.contentWindow.postMessage(
      {
        type: "RespiraScope-language",
        language: nextLanguage,
      },
      window.location.origin,
    );
  });
}

function applyLanguage() {
  const text = labels();
  document.documentElement.lang = preferredLanguage() === "zh" ? "zh-CN" : "en";
  document.title = text.title;
  dom.kicker.textContent = text.kicker;
  dom.title.textContent = text.title;
  dom.disabledTitle.textContent = text.disabledTitle;
  dom.disabledText.textContent = text.disabledText;
  dom.languageLabel.textContent = text.language;
  dom.languageSelect.value = preferredLanguage();
  document.querySelector("#monitorTab").textContent = text.monitor;
  document.querySelector("#labTab").textContent = text.lab;
  document.querySelector("#guideTab").textContent = text.guide;
  document.querySelector("#apiDocsTab").textContent = text.apiDocs;
}

function normalizeTabName(value) {
  const cleaned = String(value || "")
    .replace(/^#/, "")
    .replace(/^\//, "")
    .trim();
  return TAB_ALIASES[cleaned] ?? "";
}

function availableTabs() {
  return {
    monitor: runtimeConfig.monitorEnabled !== false,
    lab: runtimeConfig.labEnabled === true,
    guide: true,
    apiDocs: true,
  };
}

function ensureFrameLoaded(tabName) {
  const frame = dom.frames[tabName];
  if (!frame || frame.src) {
    sendLanguageToFrames();
    return;
  }
  frame.src = withPublicBasePath(frame.dataset.src);
}

function activateTab(tabName, options = {}) {
  tabName = normalizeTabName(tabName);
  const availability = availableTabs();
  if (!availability[tabName]) {
    tabName = availability.monitor ? "monitor" : availability.lab ? "lab" : "guide";
  }
  if (!availability[tabName]) {
    dom.disabledPanel.hidden = false;
    document.querySelector(".tab-stage").hidden = true;
    return;
  }

  ensureFrameLoaded(tabName);
  dom.disabledPanel.hidden = true;
  document.querySelector(".tab-stage").hidden = false;
  dom.tabs.forEach((button) => {
    const active = button.dataset.tab === tabName;
    button.classList.toggle("active", active);
    button.setAttribute("aria-selected", String(active));
  });
  Object.entries(dom.frames).forEach(([name, frame]) => {
    frame.classList.toggle("active", name === tabName);
  });
  const nextHash = `#${tabName}`;
  if (options.updateHash !== false && window.location.hash !== nextHash) {
    if (options.replaceHash) {
      window.history.replaceState(null, "", nextHash);
    } else {
      window.location.hash = tabName;
    }
  }
}

function setupTabs() {
  const availability = availableTabs();
  dom.tabs.forEach((button) => {
    button.hidden = !availability[button.dataset.tab];
    button.addEventListener("click", () => activateTab(button.dataset.tab));
  });
  Object.values(dom.frames).forEach((frame) => {
    frame.addEventListener("load", () => sendLanguageToFrames());
  });
  const requested = normalizeTabName(window.location.hash);
  activateTab(requested || (availability.monitor ? "monitor" : availability.lab ? "lab" : "guide"), {
    replaceHash: true,
  });
}

dom.languageSelect.addEventListener("change", (event) => {
  localStorage.setItem(LANGUAGE_KEY, event.target.value);
  applyLanguage();
  sendLanguageToFrames(event.target.value);
});

window.addEventListener("storage", (event) => {
  if (event.key === LANGUAGE_KEY) {
    applyLanguage();
    sendLanguageToFrames();
  }
});

window.addEventListener("hashchange", () => {
  activateTab(window.location.hash, { updateHash: false });
});

applyLanguage();
setupTabs();
