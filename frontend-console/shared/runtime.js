(function () {
  const runtimeConfig = window.CT_BREATH_RUNTIME_CONFIG || {};
  const SESSION_KEY = "RespiraScope-session";
  const LANGUAGE_KEY = "RespiraScope-language";

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

  function publicUrl(path) {
    const base = normalizePathPrefix(runtimeConfig.publicBasePath);
    if (!path || !base || /^[a-z]+:\/\//i.test(path)) {
      return path;
    }
    const normalized = path.startsWith("/") ? path : `/${path}`;
    return `${base}${normalized}`;
  }

  function apiBaseUrl() {
    if (runtimeConfig.apiBaseUrl) {
      return trimUrl(runtimeConfig.apiBaseUrl);
    }
    const publicApiBasePath = normalizePathPrefix(runtimeConfig.apiBasePath);
    if (publicApiBasePath) {
      return `${window.location.origin}${publicApiBasePath}`;
    }
    const backendHost = resolveBackendHost(runtimeConfig.backendHost);
    const backendPort = runtimeConfig.backendPort || 8000;
    return `http://${backendHost}:${backendPort}`;
  }

  function socketConfig() {
    const apiBase = apiBaseUrl();
    const publicSocketPath = normalizePathPrefix(runtimeConfig.socketPath) || "/socket.io";
    const socketBase = runtimeConfig.socketBaseUrl
      ? trimUrl(runtimeConfig.socketBaseUrl)
      : runtimeConfig.socketPath
        ? window.location.origin
        : apiBase;
    return {
      url: `${socketBase}/breath`,
      path: publicSocketPath,
      queryParam: runtimeConfig.session?.queryParam || "session_id",
    };
  }

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

  function preferredLanguage() {
    const saved = localStorage.getItem(LANGUAGE_KEY);
    if (saved === "zh" || saved === "en") {
      return saved;
    }
    return navigator.language?.toLowerCase().startsWith("zh") ? "zh" : "en";
  }

  function setPreferredLanguage(language) {
    if (language === "zh" || language === "en") {
      localStorage.setItem(LANGUAGE_KEY, language);
    }
  }

  const sessionId = getSessionId();
  const sessionHeader = runtimeConfig.session?.header || "X-RespiraScope-Session";
  const sessionHeaders = { [sessionHeader]: sessionId };
  const apiBase = apiBaseUrl();
  const socket = socketConfig();

  function apiFetch(path, options = {}) {
    return fetch(`${apiBase}${path}`, {
      ...options,
      headers: {
        ...sessionHeaders,
        ...(options.headers || {}),
      },
    });
  }

  window.RespiraScopeShared = {
    runtimeConfig,
    sessionId,
    sessionHeader,
    sessionHeaders,
    sessionKey: SESSION_KEY,
    languageKey: LANGUAGE_KEY,
    apiBase,
    socketUrl: socket.url,
    socketPath: socket.path,
    sessionQueryParam: socket.queryParam,
    normalizePathPrefix,
    publicUrl,
    apiFetch,
    preferredLanguage,
    setPreferredLanguage,
  };
})();
