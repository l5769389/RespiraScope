export function createSocketModule(ctx) {
  const {
    API_BASE,
    SOCKET_URL,
    appendSeries,
    buildFilterConfig,
    chartApi,
    dom,
    recordApi,
    setConnectionStatus,
    state,
    statusApi,
    t,
  } = ctx;

  function startError(statusKey, statusParams = {}) {
    return Object.assign(new Error(t(statusKey, statusParams)), {
      statusKey,
      statusParams,
    });
  }

  async function startMonitoring() {
    ctx.resetData();
    connectSocket();
    state.filterConfig = buildFilterConfig();
    setConnectionStatus("connection.waiting");

    let response;
    try {
      response = await fetch(`${API_BASE}/startReceive`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state.filterConfig),
      });
    } catch (error) {
      throw startError("connection.startBackendUnreachable");
    }
    if (!response.ok) {
      throw startError("connection.startHttp", { status: response.status });
    }

    state.running = true;
    state.paused = false;
    state.followLive = true;
    state.hasReceivedData = false;
    state.lastRawAt = null;
    state.lastRenderMode = null;
    dom.pauseBtn.textContent = t("button.pauseView");
    statusApi.startDataWatch();
    recordApi.updateRecordButtons();
    chartApi.updateFollowButton();
    chartApi.scheduleRender(true);
  }

  function connectSocket() {
    if (state.socket?.connected) {
      return;
    }

    if (!state.socket) {
      state.socket = io(SOCKET_URL, {
        autoConnect: false,
        withCredentials: true,
        transports: ["websocket"],
      });

      state.socket.on("connect", () => {
        setConnectionStatus("connection.connected");
      });

      state.socket.on("disconnect", () => {
        setConnectionStatus("connection.disconnected");
        state.running = false;
        recordApi.updateRecordButtons();
      });

      state.socket.on("connect_error", () => {
        setConnectionStatus("connection.error");
        state.running = false;
        recordApi.updateRecordButtons();
      });

      state.socket.on("breath", (message) => {
        if (message.type === "raw") {
          const added = appendSeries(state.raw, message.data, "raw");
          if (added > 0) {
            statusApi.markDataReceived();
          }
        } else if (message.type === "filtered") {
          appendSeries(state.filtered, message.data, "filtered");
        } else if (message.type === "peak") {
          appendSeries(state.peaks, message.data, "peaks");
        } else if (message.type === "valley") {
          appendSeries(state.valleys, message.data, "valleys");
        } else if (message.type === "metrics") {
          recordApi.appendMetricBatch(message.data);
        }
        statusApi.updateStats();
        if (state.followLive) {
          chartApi.scheduleRender();
        }
      });
    }

    state.socket.connect();
  }

  return {
    connectSocket,
    startMonitoring,
  };
}
