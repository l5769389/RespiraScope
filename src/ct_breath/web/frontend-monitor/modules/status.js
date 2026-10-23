export function createStatusModule(ctx) {
  const {
    API_BASE,
    INITIAL_DATA_TIMEOUT_MS,
    NO_DATA_CHECK_MS,
    NO_DATA_WARNING_MS,
    apiFetch,
    dom,
    recordApi,
    setConnectionStatus,
    state,
    t,
  } = ctx;

  function clearDataWatch() {
    if (state.initialDataTimer) {
      window.clearTimeout(state.initialDataTimer);
      state.initialDataTimer = null;
    }
    if (state.noDataTimer) {
      window.clearInterval(state.noDataTimer);
      state.noDataTimer = null;
    }
  }

  function startDataWatch() {
    clearDataWatch();
    state.initialDataTimer = window.setTimeout(() => {
      reportNoData(true);
    }, INITIAL_DATA_TIMEOUT_MS);
    state.noDataTimer = window.setInterval(() => {
      if (!state.running || !state.hasReceivedData) {
        return;
      }
      if (Date.now() - state.lastRawAt >= NO_DATA_WARNING_MS) {
        reportNoData(false);
      }
    }, NO_DATA_CHECK_MS);
  }

  function markDataReceived() {
    state.lastRawAt = Date.now();
    state.hasReceivedData = true;
    state.running = true;
    if (state.initialDataTimer) {
      window.clearTimeout(state.initialDataTimer);
      state.initialDataTimer = null;
    }
    setConnectionStatus("connection.receiving");
    recordApi.updateRecordButtons();
  }

  async function fetchStreamStatus() {
    const response = await apiFetch("/stream/status", {
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error(`Status request failed: ${response.status}`);
    }
    return response.json();
  }

  function streamStatusDescriptor(payload, startup) {
    const stream = payload?.data ?? payload?.stream ?? payload;
    const receiver = stream?.receiver ?? {};
    const socket = receiver.socket ?? {};
    const connected = Boolean(socket.connected);
    const receivedCount = Number(receiver.received_count ?? socket.received_count ?? 0);

    if (!connected) {
      const detail = socket.last_error ? ` (${socket.last_error})` : "";
      return startup
        ? { key: "connection.startSensorNotConnected", params: { detail } }
        : { key: "connection.sensorDisconnected", params: { detail } };
    }
    if (receivedCount <= 0) {
      return { key: startup ? "connection.startNoData" : "connection.noData", params: {} };
    }
    return { key: "connection.noRecentData", params: {} };
  }

  function statusMessageFromStream(payload, startup) {
    const descriptor = streamStatusDescriptor(payload, startup);
    return t(descriptor.key, descriptor.params);
  }

  async function reportNoData(startup) {
    if (!state.running) {
      return;
    }
    if (startup && state.hasReceivedData) {
      return;
    }
    try {
      const status = await fetchStreamStatus();
      const descriptor = streamStatusDescriptor(status, startup);
      setConnectionStatus(descriptor.key, descriptor.params);
    } catch (error) {
      setConnectionStatus(startup ? "connection.startNoData" : "connection.noRecentData");
    }
    if (startup && !state.hasReceivedData) {
      state.running = false;
      clearDataWatch();
      recordApi.updateRecordButtons();
    }
  }

  function qualityText(quality) {
    return quality && quality !== "-" ? t(`quality.${quality}`) : "-";
  }

  function stabilityHint(metrics) {
    const cv = metrics.interval_cv;
    const numericCv = Number(cv);
    if (cv === null || cv === undefined || cv === "" || !Number.isFinite(numericCv)) {
      return t("hint.waitingEnoughBreaths");
    }

    if (numericCv < 0.15) {
      return t("hint.regular");
    }
    if (numericCv < 0.35) {
      return t("hint.someVariation");
    }
    return t("hint.irregular");
  }

  function formatIntervalCv(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return "-";
    }
    return `${numeric.toFixed(3)} (${Math.round(numeric * 100)}%)`;
  }

  function intervalCvHint(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return t("hint.needsTwoPeaks");
    }
    if (numeric < 0.15) {
      return t("hint.stableCv");
    }
    if (numeric < 0.35) {
      return t("hint.variableCv");
    }
    return t("hint.irregularCv");
  }

  function updateStats() {
    const quality = state.metrics.quality && state.metrics.quality !== "-" ? state.metrics.quality : "insufficient";
    dom.bpmValue.textContent = state.metrics.bpm ?? "-";
    dom.qualityValue.textContent = qualityText(quality);
    dom.qualityValue.dataset.quality = quality;
    dom.stabilityHintValue.textContent = stabilityHint(state.metrics);
    dom.intervalCvValue.textContent = formatIntervalCv(state.metrics.interval_cv);
    dom.intervalCvHintValue.textContent = intervalCvHint(state.metrics.interval_cv);
    dom.rawCountValue.textContent = state.raw.length.toString();
    dom.filteredCountValue.textContent = state.filtered.length.toString();
    dom.lastUpdateValue.textContent = new Date().toLocaleTimeString();
    if (state.recording) {
      recordApi.updateRecordSummary(state.activeRecord);
    }
  }

  return {
    clearDataWatch,
    fetchStreamStatus,
    intervalCvHint,
    markDataReceived,
    qualityText,
    reportNoData,
    stabilityHint,
    startDataWatch,
    statusMessageFromStream,
    updateStats,
  };
}
