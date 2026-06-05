export function createRecordModule(ctx) {
  const {
    API_BASE,
    DATA_GAP_RESET_POINTS,
    FILTER_STARTUP_POINTS,
    POST_RECORD_TIMEOUT_MS,
    RECORD_MAX_POINTS,
    RECORD_POST_POINTS,
    RECORD_PRE_POINTS,
    apiFetch,
    buildFilterConfig,
    chartApi,
    copySeriesRange,
    dom,
    normalizeSeries,
    pointSequence,
    state,
    t,
    trimSeries,
  } = ctx;

  const STATUS_KEYS = {
    Idle: "record.status.idle",
    Recording: "record.status.recording",
    "Post Capture": "record.status.postCapture",
    Filtering: "record.status.filtering",
    "Too Short": "record.status.tooShort",
    "Live Capture": "record.status.liveCapture",
    "Local Record": "record.status.localRecord",
    "Offline Filtered": "record.status.offlineFiltered",
    "Loaded File": "record.status.loadedFile",
    "Load Failed": "record.status.loadFailed",
    Recorded: "record.status.recorded",
  };

  function statusKey(status) {
    return STATUS_KEYS[status] ?? status;
  }

  function setRecordSectionVisible(visible) {
    dom.recordSection.hidden = !visible;
    dom.shell.classList.toggle("has-record", visible);
    window.requestAnimationFrame(() => {
      chartApi.resizeCharts();
    });
  }

  function setRecordStatus(status) {
    const key = statusKey(status);
    dom.recordStatus.dataset.statusKey = key;
    dom.recordStatus.textContent = t(key);
    dom.recordStatus.dataset.status = status.toLowerCase().replace(/\s+/g, "-");
  }

  function appendUniquePoints(target, batch) {
    if (!Array.isArray(batch) || batch.length === 0) {
      return;
    }
    const existing = new Set(target.map((point) => pointSequence(point)));
    for (const point of batch) {
      const sequence = pointSequence(point);
      if (!existing.has(sequence)) {
        target.push(point);
        existing.add(sequence);
      }
    }
  }

  function sortSeries(series) {
    return series.sort((left, right) => pointSequence(left) - pointSequence(right));
  }

  function mergeUniquePoints(...seriesList) {
    const bySequence = new Map();
    for (const series of seriesList) {
      if (!Array.isArray(series)) {
        continue;
      }
      for (const point of series) {
        const sequence = pointSequence(point);
        if (Number.isFinite(sequence)) {
          bySequence.set(sequence, point);
        }
      }
    }
    return Array.from(bySequence.values()).sort((left, right) => pointSequence(left) - pointSequence(right));
  }

  function mergeSeriesRange(existing, source, minSeq, maxSeq) {
    return mergeUniquePoints(existing, copySeriesRange(source, minSeq, maxSeq));
  }

  function latestSequenceFromSeries(series) {
    if (!Array.isArray(series) || series.length === 0) {
      return undefined;
    }
    const sorted = sortSeries([...series]);
    return pointSequence(sorted[sorted.length - 1]);
  }

  function finiteNumber(value) {
    if (value === null || value === undefined || value === "") {
      return undefined;
    }
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : undefined;
  }

  function normalizeScan(scan) {
    if (!scan) {
      return null;
    }
    const index = finiteNumber(scan.index ?? scan.scan_index);
    const startSeq = finiteNumber(scan.startSeq ?? scan.start_sequence);
    const endSeq = finiteNumber(scan.endSeq ?? scan.end_sequence);
    const backendStartSeq = finiteNumber(scan.backendStartSeq ?? scan.backend_start_sequence);
    const backendEndSeq = finiteNumber(scan.backendEndSeq ?? scan.backend_end_sequence);
    return {
      ...scan,
      index,
      startSeq,
      endSeq,
      start_sequence: startSeq,
      end_sequence: endSeq,
      backendStartSeq,
      backendEndSeq,
      backend_start_sequence: backendStartSeq,
      backend_end_sequence: backendEndSeq,
    };
  }

  function backendSequenceToLocal(record, sequence) {
    const value = finiteNumber(sequence);
    if (value === undefined) {
      return undefined;
    }

    const backendRecordStart = finiteNumber(record?.backendStartSeq ?? record?.backend_start_sequence);
    const localRecordStart = finiteNumber(record?.startSeq ?? record?.start_sequence);
    if (backendRecordStart !== undefined && localRecordStart !== undefined) {
      return value - backendRecordStart + localRecordStart;
    }

    const origin = finiteNumber(state.sequenceOrigin);
    return origin === undefined ? value : Math.max(0, value - origin);
  }

  function applyBackendRecordStatus(record, payload) {
    if (!record || !payload) {
      return;
    }
    const backendStartSeq = finiteNumber(
      payload.record_start_sequence ?? payload.recordStartSeq ?? payload.start_sequence ?? payload.startSeq,
    );
    const backendEndSeq = finiteNumber(
      payload.record_end_sequence ?? payload.recordEndSeq ?? payload.end_sequence ?? payload.endSeq,
    );
    if (backendStartSeq !== undefined) {
      record.backendStartSeq = backendStartSeq;
      record.backend_start_sequence = backendStartSeq;
    }
    if (backendEndSeq !== undefined) {
      record.backendEndSeq = backendEndSeq;
      record.backend_end_sequence = backendEndSeq;
    }
  }

  function mergeBackendScan(record, backendScan, localScan = null) {
    const backend = normalizeScan(backendScan);
    if (!backend) {
      return normalizeScan(localScan);
    }

    const local = normalizeScan(localScan);
    const backendStartSeq = backend.backendStartSeq ?? backend.startSeq;
    const backendEndSeq = backend.backendEndSeq ?? backend.endSeq;
    const startSeq = local?.startSeq ?? backendSequenceToLocal(record, backendStartSeq);
    const endSeq = local?.endSeq ?? backendSequenceToLocal(record, backendEndSeq);

    return {
      ...backend,
      ...local,
      index: backend.index ?? local?.index,
      startSeq,
      endSeq,
      start_sequence: startSeq,
      end_sequence: endSeq,
      backendStartSeq,
      backendEndSeq,
      backend_start_sequence: backendStartSeq,
      backend_end_sequence: backendEndSeq,
      auto_closed: backend.auto_closed ?? local?.auto_closed,
    };
  }

  function normalizeScans(scans) {
    if (!Array.isArray(scans)) {
      return [];
    }
    return scans.map(normalizeScan).filter(Boolean).sort((left, right) => {
      const leftIndex = Number(left.index ?? 0);
      const rightIndex = Number(right.index ?? 0);
      return leftIndex - rightIndex;
    });
  }

  function nextScanIndex(record) {
    const indexes = normalizeScans(record.scans)
      .map((scan) => Number(scan.index))
      .filter(Number.isFinite);
    const activeIndex = Number(record.activeScan?.index);
    if (Number.isFinite(activeIndex)) {
      indexes.push(activeIndex);
    }
    return indexes.length > 0 ? Math.max(...indexes) + 1 : 1;
  }

  function upsertScan(record, scan) {
    if (!record || !scan) {
      return null;
    }
    const normalized = normalizeScan(scan);
    const index = Number(normalized?.index);
    if (!Number.isFinite(index)) {
      return normalized;
    }
    const scans = normalizeScans(record.scans);
    const existingIndex = scans.findIndex((item) => Number(item.index) === index);
    if (existingIndex >= 0) {
      scans[existingIndex] = {
        ...scans[existingIndex],
        ...normalized,
      };
    } else {
      scans.push(normalized);
    }
    record.scans = normalizeScans(scans);
    return normalized;
  }

  function closeActiveScan(record, endSeq, autoClosed = false) {
    if (!record?.activeScan) {
      return null;
    }
    const startSeq = finiteNumber(record.activeScan.startSeq ?? record.activeScan.start_sequence);
    const candidateEndSeq = finiteNumber(endSeq);
    const normalizedEndSeq =
      startSeq !== undefined && (candidateEndSeq === undefined || candidateEndSeq < startSeq)
        ? startSeq
        : candidateEndSeq;
    const scan = {
      ...record.activeScan,
      endSeq: normalizedEndSeq,
      end_sequence: normalizedEndSeq,
      endAt: Date.now(),
      auto_closed: autoClosed,
    };
    record.activeScan = null;
    return upsertScan(record, scan);
  }

  function hydrateRecordFromState(record) {
    const minSeq = captureStartSequence(record);
    const maxSeq = captureEndSequence(record);
    if (!Number.isFinite(minSeq) || !Number.isFinite(maxSeq)) {
      return;
    }

    record.raw = mergeSeriesRange(record.raw, state.raw, minSeq, maxSeq);
    record.filtered = mergeSeriesRange(record.filtered, state.filtered, minSeq, maxSeq);
    record.peaks = mergeSeriesRange(record.peaks, state.peaks, minSeq, maxSeq);
    record.valleys = mergeSeriesRange(record.valleys, state.valleys, minSeq, maxSeq);
    trimSeries(record.raw, RECORD_MAX_POINTS);
    trimSeries(record.filtered, RECORD_MAX_POINTS);
    trimSeries(record.peaks, RECORD_MAX_POINTS);
    trimSeries(record.valleys, RECORD_MAX_POINTS);
  }

  function splitContinuousSeries(series) {
    const threshold = Math.max(1, Number(DATA_GAP_RESET_POINTS) || 25);
    const sorted = sortSeries([...normalizeSeries(series, 0)]);
    const segments = [];
    let current = [];
    let previousSequence = null;

    for (const point of sorted) {
      const sequence = pointSequence(point);
      if (
        previousSequence !== null &&
        Number.isFinite(previousSequence) &&
        sequence - previousSequence > threshold
      ) {
        if (current.length > 0) {
          segments.push(current);
        }
        current = [];
      }
      current.push(point);
      previousSequence = sequence;
    }

    if (current.length > 0) {
      segments.push(current);
    }
    return segments;
  }

  function pointsInRecordWindow(series, record) {
    return normalizeSeries(series, 0).filter((point) => {
      const sequence = pointSequence(point);
      return sequence >= Number(record.startSeq) && sequence <= Number(record.endSeq);
    });
  }

  function appendRecordSeries(recordKey, batch) {
    if (!state.activeRecord || !Array.isArray(batch)) {
      return;
    }

    const target = state.activeRecord[recordKey];
    const record = state.activeRecord;
    const startSeq = Number(record.captureStartSeq ?? record.startSeq);
    const endSeq = Number(record.captureEndSeq);
    const accepted = batch.filter((point) => {
      const sequence = pointSequence(point);
      return (
        Number.isFinite(sequence) &&
        sequence >= startSeq &&
        (!Number.isFinite(endSeq) || sequence <= endSeq)
      );
    });
    appendUniquePoints(target, accepted);
    trimSeries(target, RECORD_MAX_POINTS);

    if (
      recordKey === "raw" &&
      record.postCapturing &&
      !record.awaitingBackendEnd &&
      Number.isFinite(endSeq) &&
      accepted.some((point) => pointSequence(point) >= endSeq)
    ) {
      finishRecordCapture(record).catch(() => {
        setRecordStatus("Live Capture");
      });
    }
  }

  function appendMetricBatch(batch) {
    if (!Array.isArray(batch) || batch.length === 0) {
      return;
    }
    state.metrics = batch[batch.length - 1];
    if (state.recording && state.activeRecord) {
      state.activeRecord.metrics = state.metrics;
    }
  }

  function clearPostRecordTimer() {
    if (state.postRecordTimer) {
      window.clearTimeout(state.postRecordTimer);
      state.postRecordTimer = null;
    }
  }

  function latestSequence() {
    const latestRaw = state.raw.length > 0 ? pointSequence(state.raw[state.raw.length - 1]) : 0;
    const latestFiltered =
      state.filtered.length > 0 ? pointSequence(state.filtered[state.filtered.length - 1]) : 0;
    return Math.max(latestRaw, latestFiltered);
  }

  function latestRawSequence() {
    return state.raw.length > 0 ? pointSequence(state.raw[state.raw.length - 1]) : 0;
  }

  async function startRecord() {
    if (state.recording) {
      updateRecordButtons();
      updateRecordSummary(state.activeRecord);
      return state.activeRecord;
    }

    clearPostRecordTimer();
    const startSeq = latestRawSequence() + 1;
    const captureStartSeq = Math.max(0, startSeq - RECORD_PRE_POINTS);
    state.activeRecord = {
      startAt: Date.now(),
      endAt: null,
      startSeq,
      endSeq: null,
      captureStartSeq,
      captureEndSeq: null,
      prePoints: RECORD_PRE_POINTS,
      postPoints: RECORD_POST_POINTS,
      postCapturing: false,
      awaitingBackendEnd: false,
      recordStartPending: true,
      recordStartPromise: null,
      finalizing: false,
      scans: [],
      activeScan: null,
      raw: copySeriesRange(state.raw, captureStartSeq, startSeq - 1),
      filtered: copySeriesRange(state.filtered, captureStartSeq, startSeq - 1),
      peaks: copySeriesRange(state.peaks, captureStartSeq, startSeq - 1),
      valleys: copySeriesRange(state.valleys, captureStartSeq, startSeq - 1),
      metrics: state.metrics,
      filterConfig: state.filterConfig,
    };
    const record = state.activeRecord;
    state.recording = true;
    setRecordSectionVisible(true);
    updateRecordButtons();
    updateRecordSummary(state.activeRecord);
    chartApi.scheduleRender(true);
    record.recordStartPromise = (async () => {
      try {
        const response = await apiFetch("/record/start", { method: "POST" });
        if (!response.ok) {
          throw new Error(`record/start ${response.status}`);
        }
        const result = await response.json();
        applyBackendRecordStatus(record, result.data?.record ?? result.record);
      } catch (error) {
        setRecordStatus("Local Record");
      } finally {
        record.recordStartPending = false;
        if (state.activeRecord === record) {
          updateRecordButtons();
          updateRecordSummary(record);
        }
      }
    })();
    await record.recordStartPromise;
  }

  async function startScan() {
    const record = state.activeRecord;
    const hasRecordEnded =
      record?.endSeq !== null &&
      record?.endSeq !== undefined &&
      Number.isFinite(Number(record.endSeq));
    if (!state.recording || !record || record.activeScan || hasRecordEnded) {
      return;
    }

    const localScan = {
      index: nextScanIndex(record),
      startSeq: latestRawSequence() + 1,
      start_sequence: latestRawSequence() + 1,
      endSeq: null,
      end_sequence: null,
      startAt: Date.now(),
    };
    record.activeScan = localScan;
    updateRecordButtons();
    updateRecordSummary(record);
    chartApi.scheduleRender(true);

    try {
      await record.recordStartPromise?.catch(() => null);
      const response = await apiFetch("/scan/start", { method: "POST" });
      if (!response.ok) {
        throw new Error(`scan/start ${response.status}`);
      }
      const result = await response.json();
      const scan = result.data?.scan ?? result.scan;
      if (scan && state.activeRecord === record) {
        record.activeScan = mergeBackendScan(record, scan, record.activeScan);
        updateRecordSummary(record);
        updateRecordButtons();
        chartApi.scheduleRender(true);
      }
    } catch (error) {
      if (state.activeRecord === record && record.activeScan === localScan) {
        record.activeScan = null;
        updateRecordSummary(record);
        updateRecordButtons();
        chartApi.scheduleRender(true);
      }
      setRecordStatus("Local Record");
    }
  }

  async function endScan() {
    const record = state.activeRecord;
    if (!state.recording || !record?.activeScan) {
      return;
    }

    closeActiveScan(record, latestRawSequence());
    const localScans = normalizeScans(record.scans);
    const localClosedScan = localScans[localScans.length - 1];
    updateRecordButtons();
    updateRecordSummary(record);
    chartApi.scheduleRender(true);

    try {
      await record.recordStartPromise?.catch(() => null);
      const response = await apiFetch("/scan/end", { method: "POST" });
      if (!response.ok) {
        throw new Error(`scan/end ${response.status}`);
      }
      const result = await response.json();
      const scan = result.data?.scan ?? result.scan;
      if (scan && state.activeRecord === record) {
        upsertScan(record, mergeBackendScan(record, scan, localClosedScan));
        updateRecordSummary(record);
        updateRecordButtons();
        chartApi.scheduleRender(true);
      }
    } catch (error) {
      setRecordStatus("Local Record");
    }
  }

  async function endRecord() {
    if (!state.recording || !state.activeRecord) {
      return;
    }

    const record = state.activeRecord;
    record.endAt = Date.now();
    record.endSeq = latestRawSequence();
    record.captureEndSeq = record.endSeq + RECORD_POST_POINTS;
    record.postCapturing = RECORD_POST_POINTS > 0;
    record.awaitingBackendEnd = true;
    closeActiveScan(record, record.endSeq, true);

    updateRecordButtons();
    updateRecordSummary(record);
    setRecordStatus(record.postCapturing ? "Post Capture" : "Filtering");
    chartApi.scheduleRender(true);

    try {
      const response = await apiFetch("/record/end", { method: "POST" });
      if (!response.ok) {
        throw new Error(`record/end ${response.status}`);
      }
      const result = await response.json();
      const payload = normalizeRecordEndPayload(result);
      if (payload) {
        applyBackendRecordPayload(payload);
        return;
      }
    } catch (error) {
      record.awaitingBackendEnd = false;
    }

    if (record.postCapturing) {
      clearPostRecordTimer();
      state.postRecordTimer = window.setTimeout(() => {
        finishRecordCapture(record).catch(() => {
          setRecordStatus("Live Capture");
        });
      }, POST_RECORD_TIMEOUT_MS);
      return;
    }

    await finishRecordCapture(record);
  }

  async function finishRecordCapture(record) {
    if (!record || record.finalizing) {
      return;
    }
    record.finalizing = true;
    closeActiveScan(record, record.endSeq ?? latestRawSequence(), true);
    hydrateRecordFromState(record);
    const actualCaptureEndSeq = latestSequenceFromSeries(record.raw) ?? chartApi.latestSequenceFrom(record);
    if (
      Number.isFinite(actualCaptureEndSeq) &&
      (!Number.isFinite(Number(record.captureEndSeq)) || actualCaptureEndSeq < Number(record.captureEndSeq))
    ) {
      record.captureEndSeq = actualCaptureEndSeq;
    }
    record.postCapturing = false;
    clearPostRecordTimer();
    state.lastRecord = record;
    state.activeRecord = null;
    state.recording = false;
    updateRecordButtons();
    updateRecordSummary(record);
    setRecordStatus("Filtering");
    chartApi.scheduleRender(true);
    await finalizeRecord(record);
  }

  function applyBackendRecordPayload(payload) {
    const record = normalizeRecordPayload(payload);
    state.lastRecord = record;
    state.activeRecord = null;
    state.recording = false;
    clearPostRecordTimer();
    setRecordSectionVisible(true);
    setRecordStatus(record.filtered.length > 0 ? "Offline Filtered" : "Too Short");
    updateRecordButtons();
    updateRecordSummary(record);
    chartApi.scheduleRender(true);
    chartApi.renderRecord();
  }

  function resetRecordState({ hideSection = true } = {}) {
    clearPostRecordTimer();
    state.recording = false;
    state.activeRecord = null;
    state.lastRecord = null;
    if (hideSection) {
      setRecordSectionVisible(false);
    }
    dom.scanEndBtn.classList.remove("active");
    updateRecordSummary(null);
    setRecordStatus("Idle");
    updateRecordButtons();
  }

  function normalizeRecordEndPayload(result) {
    const nestedRecord = result.data?.record ?? result.record;
    if (nestedRecord) {
      return nestedRecord;
    }
    if (!Array.isArray(result.data)) {
      return null;
    }
    return {
      ...result,
      filtered_data: result.data,
      filter_params: result.filter_config,
      start_time: result.record_time?.start_time,
      end_time: result.record_time?.end_time,
    };
  }

  async function finalizeRecord(record) {
    hydrateRecordFromState(record);
    record.raw = sortSeries(normalizeSeries(record.raw, 0));
    record.filtered = sortSeries(normalizeSeries(record.filtered, 0));
    record.peaks = sortSeries(normalizeSeries(record.peaks, 0));
    record.valleys = sortSeries(normalizeSeries(record.valleys, 0));

    const recordedRawPoints = pointsInRecordWindow(record.raw, record);
    if (recordedRawPoints.length < FILTER_STARTUP_POINTS) {
      setRecordStatus("Too Short");
      updateRecordSummary(record);
      chartApi.renderRecord();
      return;
    }

    const recordFilterConfig = record.filterConfig ?? buildFilterConfig();
    const filterConfig = buildFilterConfig({
      ...recordFilterConfig,
      gaussian_sigma: Math.max(recordFilterConfig.gaussian_sigma ?? 1.8, 2.2),
      peak_threshold_ratio: Math.max(recordFilterConfig.peak_threshold_ratio ?? 0.3, 0.35),
    });
    const rawSegments = splitContinuousSeries(record.raw)
      .filter((segment) => segment.length >= FILTER_STARTUP_POINTS)
      .filter((segment) => pointsInRecordWindow(segment, record).length > 0);

    if (rawSegments.length === 0) {
      setRecordStatus("Too Short");
      updateRecordSummary(record);
      chartApi.renderRecord();
      return;
    }

    try {
      const filteredSegments = [];
      const peakSegments = [];
      const valleySegments = [];
      let latestMetrics = record.metrics;

      for (const rawSegment of rawSegments) {
        const response = await apiFetch("/applyFilter", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filter_config: filterConfig,
            raw_data: rawSegment,
          }),
        });
        const result = await response.json();
        const filtered = normalizeSeries(result.data, 0);
        if (filtered.length === 0) {
          continue;
        }
        filteredSegments.push(filtered);
        peakSegments.push(normalizeSeries(result.peaks ?? result.peak, 0));
        valleySegments.push(normalizeSeries(result.valleys ?? result.valley, 0));
        latestMetrics = result.metrics ?? latestMetrics;
      }

      if (filteredSegments.length > 0) {
        record.filtered = mergeUniquePoints(...filteredSegments);
        record.peaks = mergeUniquePoints(...peakSegments);
        record.valleys = mergeUniquePoints(...valleySegments);
        record.captureEndSeq = Number.isFinite(Number(record.captureEndSeq))
          ? Number(record.captureEndSeq)
          : chartApi.latestSequenceFrom(record);
        record.metrics = latestMetrics;
        setRecordStatus("Offline Filtered");
      } else {
        setRecordStatus("Live Capture");
      }
    } catch (error) {
      setRecordStatus("Live Capture");
    }

    updateRecordSummary(record);
    updateRecordButtons();
    chartApi.renderRecord();
  }

  function updateRecordButtons() {
    const activeRecordEnded =
      state.activeRecord?.endSeq !== null &&
      state.activeRecord?.endSeq !== undefined &&
      Number.isFinite(Number(state.activeRecord.endSeq));
    dom.recordStartBtn.disabled =
      state.resettingRecord ||
      state.recording ||
      !state.running ||
      !state.hasReceivedData;
    dom.scanStartBtn.disabled =
      state.resettingRecord ||
      !state.recording ||
      activeRecordEnded ||
      Boolean(state.activeRecord?.activeScan);
    dom.scanEndBtn.disabled =
      state.resettingRecord ||
      !state.recording ||
      activeRecordEnded ||
      !state.activeRecord?.activeScan;
    dom.scanEndBtn.classList.toggle("active", Boolean(state.activeRecord?.activeScan));
    dom.recordEndBtn.disabled =
      state.resettingRecord ||
      !state.recording ||
      activeRecordEnded ||
      Boolean(state.activeRecord?.recordStartPending);
    dom.saveRecordBtn.disabled = state.resettingRecord || state.recording || !state.lastRecord;
    if (!state.recording && !state.lastRecord) {
      setRecordStatus("Idle");
    } else if (state.activeRecord?.postCapturing) {
      setRecordStatus("Post Capture");
    } else if (state.recording) {
      setRecordStatus("Recording");
    }
  }

  function formatDuration(ms) {
    if (!Number.isFinite(ms) || ms <= 0) {
      return t("duration.seconds", { seconds: 0 });
    }
    const seconds = Math.round(ms / 1000);
    const minutes = Math.floor(seconds / 60);
    const rest = seconds % 60;
    return minutes > 0
      ? t("duration.minutesSeconds", { minutes, seconds: rest })
      : t("duration.seconds", { seconds: rest });
  }

  function normalizeTimestamp(value, fallback = Date.now()) {
    if (value === null || value === undefined || value === "") {
      return fallback;
    }
    if (value instanceof Date) {
      return value.getTime();
    }
    if (typeof value === "string") {
      const parsed = Date.parse(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }

    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return fallback;
    }
    return numeric > 0 && numeric < 1_000_000_000_000 ? numeric * 1000 : numeric;
  }

  function formatTimestamp(value) {
    const timestamp = normalizeTimestamp(value, NaN);
    if (!Number.isFinite(timestamp)) {
      return "-";
    }
    return new Date(timestamp).toLocaleString();
  }

  function sequenceRangeText(record) {
    const startSeq = Number(record.startSeq);
    const endSeq = Number(record.endSeq ?? chartApi.latestSequenceFrom(record));
    if (!Number.isFinite(startSeq) || !Number.isFinite(endSeq)) {
      return t("record.index.empty");
    }
    const captureStartSeq = Number(record.captureStartSeq);
    const captureEndSeq = Number(record.captureEndSeq ?? chartApi.latestSequenceFrom(record));
    const recordText = t("record.index.range", {
      start: Math.round(startSeq),
      end: Math.round(endSeq),
    });
    if (
      Number.isFinite(captureStartSeq) &&
      Number.isFinite(captureEndSeq) &&
      (captureStartSeq < startSeq || captureEndSeq > endSeq)
    ) {
      return t("record.index.rangeWithFile", {
        start: Math.round(startSeq),
        end: Math.round(endSeq),
        fileStart: Math.round(captureStartSeq),
        fileEnd: Math.round(captureEndSeq),
      });
    }
    return recordText;
  }

  function scanSummaryText(record) {
    const scans = normalizeScans([
      ...(record?.scans ?? []),
      ...(record?.activeScan ? [record.activeScan] : []),
    ]);
    if (scans.length === 0) {
      return t("record.scans.empty");
    }

    const ranges = scans
      .map((scan) => {
        const startSeq = Number(scan.startSeq ?? scan.start_sequence);
        const endSeq = Number(scan.endSeq ?? scan.end_sequence);
        const start = Number.isFinite(startSeq) ? Math.round(startSeq) : "?";
        const end = Number.isFinite(endSeq) ? Math.round(endSeq) : "...";
        return `#${scan.index ?? "?"} ${start}-${end}`;
      })
      .join(", ");
    return t("record.scans.detail", { count: scans.length, ranges });
  }

  function recordTimeRangeText(record) {
    const startAt = normalizeTimestamp(record.startAt, NaN);
    const endAt = normalizeTimestamp(record.endAt ?? Date.now(), NaN);
    if (!Number.isFinite(startAt) || !Number.isFinite(endAt)) {
      return t("record.time.empty");
    }
    return t("record.time.range", {
      start: formatTimestamp(startAt),
      end: formatTimestamp(endAt),
    });
  }

  function updateRecordSummary(record) {
    if (!record) {
      dom.recordDuration.textContent = t("duration.seconds", { seconds: 0 });
      dom.recordIndexRange.textContent = t("record.index.empty");
      dom.recordScanRange.textContent = t("record.scans.empty");
      dom.recordTimeRange.textContent = t("record.time.empty");
      dom.recordPointCount.textContent = t("record.points", { count: 0 });
      return;
    }

    const startAt = normalizeTimestamp(record.startAt);
    const endAt = normalizeTimestamp(record.endAt ?? Date.now());
    const pointCount = Math.max(record.raw.length, record.filtered.length);
    const preCount = record.raw.filter((point) => segmentForSequence(pointSequence(point), record) === "pre").length;
    const postCount = record.raw.filter((point) => segmentForSequence(pointSequence(point), record) === "post").length;
    dom.recordDuration.textContent = formatDuration(endAt - startAt);
    dom.recordIndexRange.textContent = sequenceRangeText(record);
    dom.recordScanRange.textContent = scanSummaryText(record);
    dom.recordTimeRange.textContent = recordTimeRangeText(record);
    dom.recordPointCount.textContent =
      preCount > 0 || postCount > 0
        ? t("record.pointsWithPadding", { count: pointCount, pre: preCount, post: postCount })
        : t("record.points", { count: pointCount });
    if (state.recording) {
      setRecordStatus(record.postCapturing ? "Post Capture" : "Recording");
    }
  }

  function recordFileName(record) {
    const timestamp = new Date(record.endAt ?? Date.now())
      .toISOString()
      .replace(/[:.]/g, "-");
    return `breath-record-${timestamp}.json`;
  }

  function captureStartSequence(record) {
    const value = Number(record.captureStartSeq);
    return Number.isFinite(value) ? value : record.startSeq;
  }

  function captureEndSequence(record) {
    const value = Number(record.captureEndSeq);
    return Number.isFinite(value) ? value : chartApi.latestSequenceFrom(record);
  }

  function segmentForSequence(sequence, record) {
    if (!Number.isFinite(sequence)) {
      return "record";
    }
    if (sequence < Number(record.startSeq)) {
      return "pre";
    }
    const hasEndSeq =
      record?.endSeq !== null &&
      record?.endSeq !== undefined &&
      Number.isFinite(Number(record.endSeq));
    if (hasEndSeq && sequence > Number(record.endSeq)) {
      return "post";
    }
    return "record";
  }

  function scanIndexesForSequence(sequence, record) {
    if (!Number.isFinite(sequence)) {
      return [];
    }
    return normalizeScans(record?.scans)
      .filter((scan) => {
        const startSeq = Number(scan.startSeq ?? scan.start_sequence);
        const endSeq = Number(scan.endSeq ?? scan.end_sequence);
        return Number.isFinite(startSeq) && Number.isFinite(endSeq) && sequence >= startSeq && sequence <= endSeq;
      })
      .map((scan) => scan.index);
  }

  function annotateSeriesForRecord(series, record) {
    return normalizeSeries(series, 0).map((point) => ({
      sequence: point[0],
      value: point[1],
      segment: segmentForSequence(point[0], record),
      scan_indexes: scanIndexesForSequence(point[0], record),
    }));
  }

  function recordSegments(record) {
    return {
      pre: {
        start_sequence: captureStartSequence(record),
        end_sequence: Number(record.startSeq) - 1,
        auxiliary: true,
      },
      record: {
        start_sequence: record.startSeq,
        end_sequence: record.endSeq,
        auxiliary: false,
      },
      post: {
        start_sequence: Number(record.endSeq) + 1,
        end_sequence: captureEndSequence(record),
        auxiliary: true,
      },
    };
  }

  function serializeRecord(record) {
    const startAt = normalizeTimestamp(record.startAt);
    const endAt = normalizeTimestamp(record.endAt ?? Date.now());
    const raw = annotateSeriesForRecord(record.raw, record);
    const filtered = annotateSeriesForRecord(record.filtered, record);
    const peaks = annotateSeriesForRecord(record.peaks, record);
    const valleys = annotateSeriesForRecord(record.valleys, record);
    return {
      version: 2,
      exportedAt: new Date().toISOString(),
      startAt,
      endAt,
      startTime: new Date(startAt).toISOString(),
      endTime: new Date(endAt).toISOString(),
      recordTime: {
        startAt,
        endAt,
        startTime: new Date(startAt).toISOString(),
        endTime: new Date(endAt).toISOString(),
        durationMs: Math.max(0, endAt - startAt),
        durationSeconds: Math.max(0, (endAt - startAt) / 1000),
      },
      startSeq: record.startSeq,
      endSeq: record.endSeq,
      captureStartSeq: captureStartSequence(record),
      captureEndSeq: captureEndSequence(record),
      recordStartSeq: record.startSeq,
      recordEndSeq: record.endSeq,
      start_sequence: record.startSeq,
      end_sequence: record.endSeq,
      capture_start_sequence: captureStartSequence(record),
      capture_end_sequence: captureEndSequence(record),
      record_start_sequence: record.startSeq,
      record_end_sequence: record.endSeq,
      segments: recordSegments(record),
      scans: normalizeScans(record.scans),
      recordPadding: {
        prePoints: record.prePoints ?? RECORD_PRE_POINTS,
        postPoints: record.postPoints ?? RECORD_POST_POINTS,
      },
      record_padding: {
        pre_points: record.prePoints ?? RECORD_PRE_POINTS,
        post_points: record.postPoints ?? RECORD_POST_POINTS,
      },
      raw,
      raw_data: raw,
      filtered,
      filtered_data: filtered,
      peaks,
      peak: peaks,
      valleys,
      valley: valleys,
      metrics: record.metrics,
      filterConfig: record.filterConfig,
      filter_status: record.filterStatus,
    };
  }

  function downloadRecord() {
    if (!state.lastRecord) {
      return;
    }

    const payload = JSON.stringify(serializeRecord(state.lastRecord), null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = recordFileName(state.lastRecord);
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    dom.recordFileValue.dataset.recordFileKey = "";
    dom.recordFileValue.textContent = link.download;
  }

  function normalizeRecordPayload(payload) {
    const sourceRaw = payload.raw ?? payload.raw_data;
    const raw = normalizeSeries(sourceRaw, 0);
    const filtered = normalizeSeries(payload.filtered ?? payload.filtered_data, 0);
    const peaks = normalizeSeries(payload.peaks ?? payload.peak, 0);
    const valleys = normalizeSeries(payload.valleys ?? payload.valley, 0);
    const recordSource = { raw, filtered, peaks, valleys };
    const sourceStartSeq = Number(
      payload.recordStartSeq ??
        payload.record_start_sequence ??
        payload.startSeq ??
        payload.start_sequence ??
        chartApi.firstSequenceFrom(recordSource),
    );
    const startSeq = Number.isFinite(sourceStartSeq) ? sourceStartSeq : chartApi.firstSequenceFrom(recordSource);
    const sourceEndSeq = Number(
      payload.recordEndSeq ??
        payload.record_end_sequence ??
        payload.endSeq ??
        payload.end_sequence,
    );
    const endSeq = Number.isFinite(sourceEndSeq)
      ? sourceEndSeq
      : chartApi.latestSequenceFrom(recordSource);
    const sourceCaptureStartSeq = Number(
      payload.captureStartSeq ??
        payload.capture_start_sequence ??
        payload.segments?.pre?.start_sequence ??
        chartApi.firstSequenceFrom(recordSource),
    );
    const captureStartSeq = Number.isFinite(sourceCaptureStartSeq)
      ? sourceCaptureStartSeq
      : chartApi.firstSequenceFrom(recordSource);
    const sourceCaptureEndSeq = Number(
      payload.captureEndSeq ??
        payload.capture_end_sequence ??
        payload.segments?.post?.end_sequence ??
        chartApi.latestSequenceFrom(recordSource),
    );
    const captureEndSeq = Number.isFinite(sourceCaptureEndSeq)
      ? sourceCaptureEndSeq
      : chartApi.latestSequenceFrom(recordSource);
    const startAt = normalizeTimestamp(
      payload.startAt ??
        payload.startTime ??
        payload.start_time ??
        payload.recordTime?.startAt ??
        payload.recordTime?.startTime ??
        payload.record_time?.start_time,
    );
    const endAt = normalizeTimestamp(
      payload.endAt ??
        payload.endTime ??
        payload.end_time ??
        payload.recordTime?.endAt ??
        payload.recordTime?.endTime ??
        payload.record_time?.end_time,
      startAt,
    );

    return {
      startAt,
      endAt,
      startSeq,
      endSeq,
      captureStartSeq,
      captureEndSeq,
      prePoints: Number(payload.recordPadding?.prePoints ?? payload.record_padding?.pre_points ?? RECORD_PRE_POINTS),
      postPoints: Number(payload.recordPadding?.postPoints ?? payload.record_padding?.post_points ?? RECORD_POST_POINTS),
      raw,
      filtered,
      peaks,
      valleys,
      metrics: payload.metrics ?? state.metrics,
      filterConfig: payload.filterConfig ?? payload.filter_params ?? buildFilterConfig(),
      filterStatus: payload.filterStatus ?? payload.filter_status,
      scans: normalizeScans(payload.scans),
      activeScan: null,
    };
  }

  function loadRecordFile(file) {
    if (!file) {
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      try {
        const payload = JSON.parse(String(reader.result));
        const record = normalizeRecordPayload(payload);
        if (record.raw.length === 0 && record.filtered.length === 0) {
          throw new Error(t("record.error.noWaveform"));
        }
        state.lastRecord = record;
        state.activeRecord = null;
        state.recording = false;
        dom.recordFileValue.dataset.recordFileKey = "";
        dom.recordFileValue.textContent = file.name;
        setRecordSectionVisible(true);
        setRecordStatus("Loaded File");
        updateRecordSummary(record);
        updateRecordButtons();
        chartApi.renderRecord();
      } catch (error) {
        setRecordStatus("Load Failed");
        dom.recordFileValue.dataset.recordFileKey = "";
        dom.recordFileValue.textContent = error.message;
      } finally {
        dom.loadRecordInput.value = "";
      }
    };
    reader.readAsText(file);
  }

  function buildRecordRange(record, fallbackEndSeq, label) {
    if (!record || !Number.isFinite(record.startSeq)) {
      return null;
    }

    const hasEnded =
      record.endSeq !== null &&
      record.endSeq !== undefined &&
      Number.isFinite(Number(record.endSeq));
    const endSeq = hasEnded ? record.endSeq : fallbackEndSeq;
    if (!Number.isFinite(endSeq) || (hasEnded && endSeq < record.startSeq)) {
      return null;
    }

    return {
      minX: record.startSeq,
      maxX: Math.max(record.startSeq + 1, endSeq),
      active: !hasEnded,
      label,
      scans: scanRangesForRecord(record, endSeq),
    };
  }

  function scanRangesForRecord(record, fallbackEndSeq) {
    const fallback = Number(fallbackEndSeq);
    return normalizeScans([
      ...(record?.scans ?? []),
      ...(record?.activeScan ? [record.activeScan] : []),
    ])
      .map((scan) => {
        const startSeq = Number(scan.startSeq ?? scan.start_sequence);
        const endSeq = Number(scan.endSeq ?? scan.end_sequence);
        const hasEnded = Number.isFinite(endSeq);
        const maxX = hasEnded ? endSeq : fallback;
        if (!Number.isFinite(startSeq) || !Number.isFinite(maxX)) {
          return null;
        }
        return {
          minX: startSeq,
          maxX: Math.max(startSeq + 1, maxX),
          active: !hasEnded,
          index: scan.index,
          label: t(hasEnded ? "record.range.scan" : "record.range.scanActive", {
            index: scan.index ?? "?",
          }),
        };
      })
      .filter(Boolean);
  }

  function currentRecordRange() {
    if (state.activeRecord) {
      return buildRecordRange(
        state.activeRecord,
        state.activeRecord.endSeq ?? latestSequence(),
        state.activeRecord.postCapturing ? t("record.range.postCapture") : t("record.range.recording"),
      );
    }
    if (state.lastRecord) {
      return buildRecordRange(state.lastRecord, state.lastRecord.endSeq, t("record.range.recorded"));
    }
    return null;
  }

  function refreshLanguage() {
    const key = dom.recordStatus.dataset.statusKey;
    if (key) {
      dom.recordStatus.textContent = t(key);
    }
    updateRecordSummary(state.activeRecord ?? state.lastRecord);
    updateRecordButtons();
  }

  return {
    appendMetricBatch,
    appendRecordSeries,
    buildRecordRange,
    captureEndSequence,
    captureStartSequence,
    clearPostRecordTimer,
    currentRecordRange,
    downloadRecord,
    endRecord,
    finishRecordCapture,
    loadRecordFile,
    refreshLanguage,
    resetRecordState,
    segmentForSequence,
    setRecordSectionVisible,
    setRecordStatus,
    startScan,
    startRecord,
    endScan,
    updateRecordButtons,
    updateRecordSummary,
  };
}
