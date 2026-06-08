import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  FlaskConical,
  Play,
  Server,
  ShieldCheck,
  SlidersHorizontal,
  Wifi,
} from "lucide-react";

const shared = window.RespiraScopeShared || {};
const runtimeConfig = shared.runtimeConfig || window.CT_BREATH_RUNTIME_CONFIG || {};
const LANGUAGE_KEY = shared.languageKey || "RespiraScope-language";

const TEXT = {
  zh: {
    appTitle: "4D 呼吸采集辅助算法",
    appSubtitle: "面向 4D 检查中的患者呼吸采集，把呼吸信号处理成可用于观察节律、评估稳定性和标记扫描区间的实时结果。",
    language: "语言",
    backend: "后端",
    backendChecking: "检查中",
    backendOnline: "正常",
    backendOffline: "不可达",
    dataSource: "数据源",
    dataSourceMock: "模拟信号",
    dataSourceSensor: "真实设备",
    dataSourceDisabled: "未启用",
    session: "会话",
    sessionIsolated: "本标签页独立",
    offlineHint: "后端暂不可达，请确认启动窗口中的 Backend API 地址和服务状态。",
    heroKicker: "Algorithm Workflow",
    heroTitle: "从呼吸波形到 4D 采集可用的节律信息",
    heroText: "系统完成实时信号接收、滤波降噪、峰谷识别、BPM 估计、记录片段、扫描标记和离线复算，帮助快速判断呼吸采集过程是否稳定、是否可回看。",
    startDemo: "查看算法演示",
    openMonitor: "进入实时监测",
    openLab: "调整模拟参数",
    monitor: "4D 采集监测",
    monitorText: "波形、BPM、记录片段和扫描标记",
    lab: "模拟与滤波",
    labText: "配置呼吸场景并观察滤波效果",
    monitorFrameTitle: "RespiraScope 4D 呼吸采集监测",
    labFrameTitle: "RespiraScope 模拟与滤波",
    disabledTitle: "没有可用前端",
    disabledText: "请检查配置文件中的 [console]、[monitor] 和 [lab] 开关。",
  },
  en: {
    appTitle: "4D Respiratory Acquisition Algorithm",
    appSubtitle: "For patient respiratory acquisition in 4D imaging, RespiraScope turns breath signals into realtime rhythm, stability, and scan-marker information.",
    language: "Language",
    backend: "Backend",
    backendChecking: "Checking",
    backendOnline: "Online",
    backendOffline: "Offline",
    dataSource: "Data Source",
    dataSourceMock: "Mock Signal",
    dataSourceSensor: "Physical Sensor",
    dataSourceDisabled: "Disabled",
    session: "Session",
    sessionIsolated: "This tab only",
    offlineHint: "Backend is unreachable. Check the Backend API address and service status in the startup window.",
    heroKicker: "Algorithm Workflow",
    heroTitle: "From breath waveform to 4D acquisition-ready rhythm data",
    heroText: "The system handles realtime signal intake, denoising, peak and valley detection, BPM estimation, segment recording, scan markers, and offline recalculation so the acquisition process can be reviewed.",
    startDemo: "View Algorithm Demo",
    openMonitor: "Open Monitor",
    openLab: "Tune Simulation",
    monitor: "4D Acquisition Monitor",
    monitorText: "Waveform, BPM, recorded segments, and scan markers",
    lab: "Simulation & Filtering",
    labText: "Configure breath scenarios and inspect filtering",
    monitorFrameTitle: "RespiraScope 4D respiratory acquisition monitor",
    labFrameTitle: "RespiraScope simulation and filtering",
    disabledTitle: "No frontend is enabled",
    disabledText: "Check [console], [monitor], and [lab] in the config file.",
  },
};

const MODE_ALIASES = {
  monitor: "monitor",
  realtime: "monitor",
  guide: "monitor",
  api: "monitor",
  apiDocs: "monitor",
  "api-docs": "monitor",
  lab: "lab",
  setup: "lab",
  mock: "lab",
};

function preferredLanguage() {
  if (typeof shared.preferredLanguage === "function") {
    return shared.preferredLanguage();
  }
  const saved = localStorage.getItem(LANGUAGE_KEY);
  if (saved === "zh" || saved === "en") {
    return saved;
  }
  return navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
}

function normalizeMode(value) {
  const cleaned = String(value || "")
    .replace(/^#/, "")
    .replace(/^\//, "")
    .trim();
  return MODE_ALIASES[cleaned] || "";
}

function availableModes() {
  return {
    monitor: runtimeConfig.monitorEnabled !== false,
    lab: runtimeConfig.labEnabled === true,
  };
}

function publicUrl(path) {
  return typeof shared.publicUrl === "function" ? shared.publicUrl(path) : path;
}

function apiFetch(path, options) {
  if (typeof shared.apiFetch === "function") {
    return shared.apiFetch(path, options);
  }
  const host = runtimeConfig.backendHost || "127.0.0.1";
  const port = runtimeConfig.backendPort || 8000;
  return fetch(`http://${host}:${port}${path}`, options);
}

function StatusPill({ icon: Icon, label, value, tone }) {
  return (
    <div className={`status-pill ${tone}`}>
      <Icon aria-hidden="true" size={17} strokeWidth={2.4} />
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function App() {
  const [language, setLanguage] = useState(preferredLanguage);
  const [activeMode, setActiveMode] = useState(() => normalizeMode(window.location.hash) || "monitor");
  const [loadedModes, setLoadedModes] = useState(() => new Set([normalizeMode(window.location.hash) || "monitor"]));
  const [backendState, setBackendState] = useState("checking");
  const [mockEnabled, setMockEnabled] = useState(Boolean(runtimeConfig.mockSignalEnabled));
  const monitorFrameRef = useRef(null);
  const labFrameRef = useRef(null);
  const t = useCallback((key) => TEXT[language]?.[key] ?? TEXT.en[key] ?? key, [language]);
  const modes = useMemo(availableModes, []);

  const activateMode = useCallback((nextMode, options = {}) => {
    const normalized = normalizeMode(nextMode);
    let mode = normalized;
    if (!modes[mode]) {
      mode = modes.monitor ? "monitor" : modes.lab ? "lab" : "";
    }
    if (!mode) {
      return Promise.resolve("");
    }
    setActiveMode(mode);
    setLoadedModes((current) => new Set(current).add(mode));
    const nextHash = `#${mode}`;
    if (options.updateHash !== false && window.location.hash !== nextHash) {
      if (options.replaceHash) {
        window.history.replaceState(null, "", nextHash);
      } else {
        window.location.hash = mode;
      }
    }
    return Promise.resolve(mode);
  }, [modes]);

  const frameForMode = useCallback((mode) => {
    return mode === "lab" ? labFrameRef.current : monitorFrameRef.current;
  }, []);

  const sendLanguageToFrames = useCallback((nextLanguage = language) => {
    [monitorFrameRef.current, labFrameRef.current].forEach((frame) => {
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
  }, [language]);

  const postToFrame = useCallback((mode, message) => {
    const frame = frameForMode(mode);
    if (!frame?.contentWindow) {
      return;
    }
    frame.contentWindow.postMessage(message, window.location.origin);
  }, [frameForMode]);

  const refreshRuntimeStatus = useCallback(async () => {
    setBackendState("checking");
    try {
      const response = await apiFetch("/health");
      if (!response.ok) {
        throw new Error(`health ${response.status}`);
      }
      const payload = await response.json();
      const data = payload.data || payload;
      setBackendState("online");
      setMockEnabled(Boolean(data.mock_signal_enabled ?? runtimeConfig.mockSignalEnabled));
    } catch {
      setBackendState("offline");
      setMockEnabled(Boolean(runtimeConfig.mockSignalEnabled));
    }
  }, []);

  const startMockDemo = useCallback(async () => {
    await activateMode("monitor");
    if (runtimeConfig.mockSignalEnabled !== false) {
      try {
        await apiFetch("/mock/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ scenario: "normal" }),
        });
      } catch {
        // The monitor can still start with the current mock config.
      }
    }
    window.setTimeout(() => postToFrame("monitor", { type: "RespiraScope-start-demo" }), 80);
  }, [activateMode, postToFrame]);

  const updateLanguage = useCallback((nextLanguage) => {
    setLanguage(nextLanguage);
    if (typeof shared.setPreferredLanguage === "function") {
      shared.setPreferredLanguage(nextLanguage);
    } else {
      localStorage.setItem(LANGUAGE_KEY, nextLanguage);
    }
    sendLanguageToFrames(nextLanguage);
  }, [sendLanguageToFrames]);

  useEffect(() => {
    document.documentElement.lang = language === "zh" ? "zh-CN" : "en";
    document.title = t("appTitle");
    sendLanguageToFrames(language);
  }, [language, sendLanguageToFrames, t]);

  useEffect(() => {
    activateMode(window.location.hash || "monitor", { replaceHash: true });
    refreshRuntimeStatus();
    const timer = window.setInterval(refreshRuntimeStatus, 10000);
    return () => window.clearInterval(timer);
  }, [activateMode, refreshRuntimeStatus]);

  useEffect(() => {
    const onHashChange = () => activateMode(window.location.hash, { updateHash: false });
    const onStorage = (event) => {
      if (event.key === LANGUAGE_KEY && (event.newValue === "zh" || event.newValue === "en")) {
        setLanguage(event.newValue);
      }
    };
    const onMessage = (event) => {
      if (event.origin !== window.location.origin) {
        return;
      }
      if (event.data?.type === "RespiraScope-open-monitor") {
        activateMode("monitor").then(() => {
          if (event.data.startDemo) {
            window.setTimeout(() => postToFrame("monitor", { type: "RespiraScope-start-demo" }), 80);
          }
        });
      }
    };
    window.addEventListener("hashchange", onHashChange);
    window.addEventListener("storage", onStorage);
    window.addEventListener("message", onMessage);
    return () => {
      window.removeEventListener("hashchange", onHashChange);
      window.removeEventListener("storage", onStorage);
      window.removeEventListener("message", onMessage);
    };
  }, [activateMode, postToFrame]);

  const backendText = backendState === "online"
    ? t("backendOnline")
    : backendState === "offline"
      ? t("backendOffline")
      : t("backendChecking");
  const sourceText = mockEnabled
    ? t("dataSourceMock")
    : runtimeConfig.mockSignalEnabled === false
      ? `${t("dataSourceSensor")} ${runtimeConfig.sensorHost || ""}:${runtimeConfig.sensorPort || ""}`
      : t("dataSourceDisabled");
  const sessionText = shared.sessionId ? t("sessionIsolated") : "-";
  const noFrontend = !modes.monitor && !modes.lab;

  return (
    <main className="console-shell">
      <header className="console-topbar">
        <div className="console-brand">
          <span className="brand-mark" aria-hidden="true">R</span>
          <div className="brand-copy">
            <span className="eyebrow">RespiraScope</span>
            <h1>{t("appTitle")}</h1>
            <p>{t("appSubtitle")}</p>
          </div>
        </div>
        <div className="console-actions">
          <StatusPill
            icon={Server}
            label={t("backend")}
            value={backendText}
            tone={backendState === "online" ? "ok" : backendState === "offline" ? "danger" : "pending"}
          />
          <StatusPill
            icon={Wifi}
            label={t("dataSource")}
            value={sourceText}
            tone={mockEnabled ? "ok" : runtimeConfig.mockSignalEnabled === false ? "sensor" : "warn"}
          />
          <StatusPill
            icon={ShieldCheck}
            label={t("session")}
            value={sessionText}
            tone="info"
          />
          <label className="language-field">
            <span>{t("language")}</span>
            <select value={language} onChange={(event) => updateLanguage(event.target.value)}>
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </label>
        </div>
      </header>

      <section className="experience-panel" aria-label="RespiraScope overview">
        <div className="experience-copy">
          <span className="eyebrow">{t("heroKicker")}</span>
          <h2>{t("heroTitle")}</h2>
          <p>{t("heroText")}</p>
          {backendState === "offline" && (
            <div className="inline-alert" role="status">
              <AlertTriangle aria-hidden="true" size={17} strokeWidth={2.5} />
              <span>{t("offlineHint")}</span>
            </div>
          )}
        </div>
        <div className="quick-actions">
          <button type="button" onClick={startMockDemo}>
            <Play aria-hidden="true" size={17} strokeWidth={2.5} />
            {t("startDemo")}
          </button>
          <button className="secondary" type="button" onClick={() => activateMode("monitor")}>
            <Activity aria-hidden="true" size={17} strokeWidth={2.4} />
            {t("openMonitor")}
          </button>
          <button className="secondary" type="button" onClick={() => activateMode("lab")}>
            <SlidersHorizontal aria-hidden="true" size={17} strokeWidth={2.4} />
            {t("openLab")}
          </button>
        </div>
      </section>

      {noFrontend ? (
        <section className="disabled-panel">
          <h2>{t("disabledTitle")}</h2>
          <p>{t("disabledText")}</p>
        </section>
      ) : (
        <section className="console-workspace">
          <nav className="mode-rail" aria-label="RespiraScope modes">
            {modes.monitor && (
              <button
                className={`mode-button ${activeMode === "monitor" ? "active" : ""}`}
                type="button"
                onClick={() => activateMode("monitor")}
              >
                <Activity aria-hidden="true" size={19} strokeWidth={2.5} />
                <span>{t("monitor")}</span>
                <small>{t("monitorText")}</small>
              </button>
            )}
            {modes.lab && (
              <button
                className={`mode-button ${activeMode === "lab" ? "active" : ""}`}
                type="button"
                onClick={() => activateMode("lab")}
              >
                <FlaskConical aria-hidden="true" size={19} strokeWidth={2.5} />
                <span>{t("lab")}</span>
                <small>{t("labText")}</small>
              </button>
            )}
          </nav>

          <div className="frame-stage">
            {loadedModes.has("monitor") && (
              <iframe
                ref={monitorFrameRef}
                className={`mode-frame ${activeMode === "monitor" ? "active" : ""}`}
                title={t("monitorFrameTitle")}
                src={publicUrl("/monitor/index.html")}
                onLoad={() => sendLanguageToFrames()}
              />
            )}
            {loadedModes.has("lab") && (
              <iframe
                ref={labFrameRef}
                className={`mode-frame ${activeMode === "lab" ? "active" : ""}`}
                title={t("labFrameTitle")}
                src={publicUrl("/lab/index.html")}
                onLoad={() => sendLanguageToFrames()}
              />
            )}
          </div>
        </section>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
