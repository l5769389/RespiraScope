export function createChartModule(ctx) {
  const {
    DATA_GAP_RESET_POINTS,
    DISPLAY_WINDOW,
    FILTER_MARKER_WARMUP_POINTS,
    LIVE_RIGHT_PADDING_RATIO,
    RECORD_RANGE_ACTIVE_COLOR,
    RECORD_RANGE_DONE_COLOR,
    SCAN_RANGE_ACTIVE_COLOR,
    SCAN_RANGE_DONE_COLOR,
    Y_AXIS_MIN_SPAN,
    Y_AXIS_PADDING_RATIO,
    dom,
    pointSequence,
    recordApi,
    state,
    t,
  } = ctx;

  const chart = echarts.init(dom.waveChart);
  const recordChart = echarts.init(dom.recordChart);
  const MOBILE_DISPLAY_WINDOW = Math.min(DISPLAY_WINDOW, 620);

  function isCompactViewport() {
    return window.matchMedia?.("(max-width: 640px)")?.matches ?? window.innerWidth <= 640;
  }

  function liveDisplayWindow() {
    return isCompactViewport() ? MOBILE_DISPLAY_WINDOW : DISPLAY_WINDOW;
  }

  function roundDownToHundred(value) {
    return Math.floor(value / 100) * 100;
  }

  function roundUpToHundred(value) {
    return Math.ceil(value / 100) * 100;
  }

  function formatSample(value) {
    return roundDownToHundred(Number(value)).toString();
  }

  function smoothingWindow() {
    if (state.smoothingMode === "off") {
      return 1;
    }
    if (state.smoothingMode === "light") {
      return 5;
    }
    if (state.smoothingMode === "medium") {
      return 9;
    }
    if (state.smoothingMode === "strong") {
      return 15;
    }

    if (state.metrics.quality === "irregular") {
      return 11;
    }
    if (state.metrics.quality === "variable") {
      return 7;
    }
    return 5;
  }

  function sequenceGapThreshold() {
    return Math.max(1, Number(DATA_GAP_RESET_POINTS) || 25);
  }

  function splitContinuousSegments(series, gapThreshold = sequenceGapThreshold()) {
    const segments = [];
    let current = [];
    let previousSequence = null;

    for (const point of series) {
      const sequence = pointSequence(point);
      if (!Number.isFinite(sequence)) {
        continue;
      }
      if (
        previousSequence !== null &&
        Number.isFinite(previousSequence) &&
        sequence - previousSequence > gapThreshold
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

  function withGapBreaks(series, gapThreshold = sequenceGapThreshold()) {
    if (!Array.isArray(series) || series.length < 2) {
      return series;
    }

    const broken = [];
    let previousSequence = null;
    for (const point of series) {
      const sequence = pointSequence(point);
      if (
        previousSequence !== null &&
        Number.isFinite(previousSequence) &&
        Number.isFinite(sequence) &&
        sequence - previousSequence > gapThreshold
      ) {
        broken.push([Math.max(previousSequence + 1, sequence - 1), null]);
      }
      broken.push(point);
      previousSequence = sequence;
    }
    return broken;
  }

  function smoothSegment(segment, windowSize) {
    if (windowSize <= 1 || segment.length < 3) {
      return segment;
    }

    const radius = Math.floor(windowSize / 2);
    const smoothed = [];
    for (let index = 0; index < segment.length; index += 1) {
      let sum = 0;
      let count = 0;
      const from = Math.max(0, index - radius);
      const to = Math.min(segment.length - 1, index + radius);
      for (let inner = from; inner <= to; inner += 1) {
        sum += Number(segment[inner][1]);
        count += 1;
      }
      smoothed.push([segment[index][0], Number((sum / count).toFixed(2))]);
    }
    return smoothed;
  }

  function smoothSeries(series) {
    const windowSize = smoothingWindow();
    if (windowSize <= 1 || series.length < 3) {
      return withGapBreaks(series);
    }

    const smoothed = splitContinuousSegments(series)
      .flatMap((segment) => smoothSegment(segment, windowSize));
    return withGapBreaks(smoothed);
  }

  function markerData(points) {
    return points.map((point) => ({
      value: point,
    }));
  }

  function latestSequenceFrom(source) {
    const candidates = [source.raw, source.filtered, source.peaks, source.valleys]
      .filter((series) => Array.isArray(series) && series.length > 0)
      .map((series) => pointSequence(series[series.length - 1]))
      .filter(Number.isFinite);
    return candidates.length > 0 ? Math.max(...candidates) : DISPLAY_WINDOW;
  }

  function firstSequenceFromSeries(series) {
    if (!Array.isArray(series) || series.length === 0) {
      return undefined;
    }
    return pointSequence(series[0]);
  }

  function firstSequenceFrom(source) {
    const candidates = [
      firstSequenceFromSeries(source.raw),
      firstSequenceFromSeries(source.filtered),
      firstSequenceFromSeries(source.peaks),
      firstSequenceFromSeries(source.valleys),
    ].filter(Number.isFinite);
    return candidates.length > 0 ? Math.min(...candidates) : 0;
  }

  function filterMarkersBySupport(markers, supportSeries) {
    if (!supportSeries.length) {
      return [];
    }

    const supportSegments = splitContinuousSegments(supportSeries).map((segment) => ({
      minX: pointSequence(segment[0]) + FILTER_MARKER_WARMUP_POINTS,
      maxX: pointSequence(segment[segment.length - 1]),
    }));
    return markers.filter((point) => {
      const sequence = pointSequence(point);
      return supportSegments.some((segment) => sequence >= segment.minX && sequence <= segment.maxX);
    });
  }

  function valueExtent(seriesList) {
    let min = Infinity;
    let max = -Infinity;

    seriesList.forEach((series) => {
      series.forEach((point) => {
        if (point[1] === null || point[1] === undefined) {
          return;
        }
        const value = Number(point[1]);
        if (!Number.isFinite(value)) {
          return;
        }
        min = Math.min(min, value);
        max = Math.max(max, value);
      });
    });

    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      return null;
    }

    return { min, max };
  }

  function paddedAxis(extent) {
    if (!extent) {
      return null;
    }

    const center = (extent.min + extent.max) / 2;
    const span = Math.max(extent.max - extent.min, Y_AXIS_MIN_SPAN);
    const paddedSpan = span * (1 + Y_AXIS_PADDING_RATIO);
    return {
      min: Math.floor(center - paddedSpan / 2),
      max: Math.ceil(center + paddedSpan / 2),
    };
  }

  function mergeLiveYAxis(nextAxis) {
    if (!nextAxis) {
      return state.liveYAxis;
    }
    if (!state.liveYAxis) {
      state.liveYAxis = nextAxis;
      return state.liveYAxis;
    }

    const current = state.liveYAxis;
    const currentSpan = Math.max(current.max - current.min, Y_AXIS_MIN_SPAN);
    const overflows = nextAxis.min < current.min || nextAxis.max > current.max;
    const muchSmaller = nextAxis.max - nextAxis.min < currentSpan * 0.62;

    if (overflows) {
      state.liveYAxis = {
        min: Math.min(current.min, nextAxis.min),
        max: Math.max(current.max, nextAxis.max),
      };
    } else if (muchSmaller) {
      state.liveYAxis = {
        min: Math.round(current.min * 0.92 + nextAxis.min * 0.08),
        max: Math.round(current.max * 0.92 + nextAxis.max * 0.08),
      };
    }

    return state.liveYAxis;
  }

  function recordMarkArea(recordRange) {
    if (!recordRange) {
      return undefined;
    }

    const active = recordRange.active;
    const recordStyle = {
      color: active ? RECORD_RANGE_ACTIVE_COLOR : RECORD_RANGE_DONE_COLOR,
      borderColor: active ? "rgba(245, 158, 11, 0.32)" : "rgba(20, 184, 166, 0.28)",
      borderWidth: 1,
    };
    const scanStyle = (isActive) => ({
      color: isActive ? SCAN_RANGE_ACTIVE_COLOR : SCAN_RANGE_DONE_COLOR,
      borderColor: isActive ? "rgba(37, 99, 235, 0.42)" : "rgba(37, 99, 235, 0.3)",
      borderWidth: 1,
    });
    const areaLabel = (label, color, borderColor) => ({
      show: true,
      formatter: label,
      position: "insideTop",
      color,
      fontSize: 12,
      fontWeight: 700,
      padding: [3, 8],
      backgroundColor: "rgba(255, 255, 255, 0.9)",
      borderColor,
      borderWidth: 1,
      borderRadius: 4,
    });
    const areaData = [
      [
        {
          xAxis: recordRange.minX,
          itemStyle: recordStyle,
          label: areaLabel(
            recordRange.label,
            active ? "#92400e" : "#0f766e",
            active ? "rgba(245, 158, 11, 0.32)" : "rgba(20, 184, 166, 0.28)",
          ),
        },
        { xAxis: recordRange.maxX },
      ],
    ];

    for (const scan of recordRange.scans ?? []) {
      areaData.push([
        {
          xAxis: scan.minX,
          itemStyle: scanStyle(scan.active),
          label: areaLabel(scan.label, "#1d4ed8", "rgba(37, 99, 235, 0.32)"),
        },
        { xAxis: scan.maxX },
      ]);
    }

    return {
      silent: true,
      itemStyle: {
        color: RECORD_RANGE_DONE_COLOR,
        borderColor: "rgba(20, 184, 166, 0.28)",
        borderWidth: 1,
      },
      emphasis: {
        disabled: true,
      },
      data: areaData,
    };
  }

  function liveBounds() {
    const latestX = latestSequenceFrom(state);
    const displayWindow = liveDisplayWindow();
    const followPoint = displayWindow * (1 - LIVE_RIGHT_PADDING_RATIO);
    const minX = latestX <= followPoint ? 0 : Math.max(0, latestX - followPoint);
    return {
      minX,
      maxX: minX + displayWindow,
    };
  }

  function sliceByRange(series, minX, maxX) {
    const points = [];
    for (let index = series.length - 1; index >= 0; index -= 1) {
      const point = series[index];
      const sequence = pointSequence(point);
      if (sequence < minX) {
        break;
      }
      if (sequence <= maxX) {
        points.push(point);
      }
    }
    return points.reverse();
  }

  function sourceInRange(source, minX, maxX) {
    const rangedSource = {
      raw: sliceByRange(source.raw, minX, maxX),
      filtered: sliceByRange(source.filtered, minX, maxX),
    };
    const markerSupport = source.filtered.length > 0 ? source.filtered : source.raw;
    return {
      ...rangedSource,
      peaks: filterMarkersBySupport(sliceByRange(source.peaks, minX, maxX), markerSupport),
      valleys: filterMarkersBySupport(sliceByRange(source.valleys, minX, maxX), markerSupport),
    };
  }

  function visibleRecordRange(recordRange, minX, maxX) {
    if (!recordRange) {
      return null;
    }

    const visibleMin = Math.max(recordRange.minX, minX);
    const visibleMax = Math.min(recordRange.maxX, maxX);
    if (visibleMax < minX || visibleMin > maxX) {
      return null;
    }

    return {
      ...recordRange,
      minX: visibleMin,
      maxX: Math.max(visibleMin + 1, visibleMax),
      scans: (recordRange.scans ?? [])
        .map((scan) => {
          const scanMin = Math.max(scan.minX, minX);
          const scanMax = Math.min(scan.maxX, maxX);
          if (scanMax < minX || scanMin > maxX) {
            return null;
          }
          return {
            ...scan,
            minX: scanMin,
            maxX: Math.max(scanMin + 1, scanMax),
          };
        })
        .filter(Boolean),
    };
  }

  function chartOption(source, options = {}) {
    const mode = options.mode ?? "review";
    const raw = withGapBreaks(source.raw);
    const filtered = smoothSeries(source.filtered);
    const isLive = mode === "live";
    const compact = isCompactViewport();
    const markArea = recordMarkArea(options.recordRange);
    const maxX = isLive ? options.maxX ?? liveDisplayWindow() : undefined;
    const yAxisBounds =
      options.yAxisBounds ?? (isLive ? { min: 0, max: Y_AXIS_MIN_SPAN } : paddedAxis(valueExtent([raw, filtered])));
    const insideZoom = {
      id: "inside",
      type: "inside",
      xAxisIndex: 0,
      filterMode: "none",
      zoomOnMouseWheel: true,
      moveOnMouseMove: true,
      moveOnMouseWheel: false,
      preventDefaultMouseMove: true,
    };
    const dataZoom = isLive
      ? [
          insideZoom,
        ]
      : [
          insideZoom,
          {
            id: "slider",
            type: "slider",
            xAxisIndex: 0,
            filterMode: "none",
            height: compact ? 34 : 24,
            bottom: compact ? 10 : 14,
            borderColor: "#d9e2ef",
            fillerColor: "rgba(37, 99, 235, 0.12)",
            handleSize: compact ? "96%" : "80%",
            moveHandleSize: compact ? 14 : 8,
            showDetail: !compact,
            handleStyle: {
              color: "#ffffff",
              borderColor: "#2563eb",
            },
            moveHandleStyle: {
              color: "#bfdbfe",
            },
          },
        ];

    if (!isLive && options.initialRange) {
      dataZoom.forEach((zoom) => {
        zoom.startValue = options.initialRange.minX;
        zoom.endValue = options.initialRange.maxX;
      });
    }

    return {
      animation: false,
      grid: {
        left: compact ? 42 : 52,
        right: compact ? 12 : 28,
        top: compact ? 26 : 34,
        bottom: isLive ? (compact ? 32 : 44) : (compact ? 64 : 72),
      },
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(255, 255, 255, 0.96)",
        borderColor: "#d9e2ef",
        borderWidth: 1,
        textStyle: {
          color: "#17202a",
        },
        axisPointer: {
          animation: false,
          lineStyle: {
            color: "#64748b",
            type: "dashed",
          },
        },
      },
      dataZoom,
      xAxis: {
        type: "value",
        min: isLive ? options.minX : undefined,
        max: isLive ? maxX : undefined,
        minInterval: compact ? 50 : 100,
        scale: true,
        axisLine: {
          lineStyle: {
            color: "#cbd5e1",
          },
        },
        axisTick: {
          lineStyle: {
            color: "#cbd5e1",
          },
        },
        axisLabel: {
          color: "#64748b",
          formatter: formatSample,
        },
        splitLine: {
          lineStyle: {
            color: "#edf2f7",
          },
        },
      },
      yAxis: {
        type: "value",
        name: t("chart.value"),
        min: yAxisBounds?.min ?? "dataMin",
        max: yAxisBounds?.max ?? "dataMax",
        nameTextStyle: {
          color: "#64748b",
        },
        axisLabel: {
          color: "#64748b",
        },
        splitLine: {
          lineStyle: {
            color: "#eef2f7",
          },
        },
      },
      series: [
        {
          name: t("series.raw"),
          type: "line",
          animation: false,
          showSymbol: false,
          connectNulls: false,
          data: raw,
          sampling: "lttb",
          lineStyle: {
            color: "#8a96a8",
            width: 1,
            opacity: 0.7,
          },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(148, 163, 184, 0.14)" },
                { offset: 1, color: "rgba(148, 163, 184, 0.02)" },
              ],
            },
          },
          ...(markArea ? { markArea } : {}),
        },
        {
          name: t("series.filtered"),
          type: "line",
          animation: false,
          showSymbol: false,
          smooth: smoothingWindow() > 1,
          connectNulls: false,
          data: filtered,
          sampling: "lttb",
          lineStyle: {
            color: "#2563eb",
            width: 2.5,
            shadowColor: "rgba(29, 78, 216, 0.16)",
            shadowBlur: 8,
          },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(37, 99, 235, 0.2)" },
                { offset: 1, color: "rgba(20, 184, 166, 0.02)" },
              ],
            },
          },
        },
        {
          name: t("series.peak"),
          type: "scatter",
          animation: false,
          data: markerData(source.peaks),
          symbol: "triangle",
          symbolSize: 13,
          z: 8,
          itemStyle: {
            color: "#f43f5e",
            borderColor: "#ffffff",
            borderWidth: 2,
            shadowBlur: 8,
            shadowColor: "rgba(244, 63, 94, 0.22)",
          },
        },
        {
          name: t("series.valley"),
          type: "scatter",
          animation: false,
          data: markerData(source.valleys),
          symbol: "triangle",
          symbolRotate: 180,
          symbolSize: 13,
          z: 8,
          itemStyle: {
            color: "#14b8a6",
            borderColor: "#ffffff",
            borderWidth: 2,
            shadowBlur: 8,
            shadowColor: "rgba(20, 184, 166, 0.22)",
          },
        },
      ],
    };
  }

  function scheduleRender(force = false) {
    if (force) {
      state.renderScheduled = false;
      render({ force: true });
      return;
    }
    if (state.renderScheduled) {
      return;
    }
    state.renderScheduled = true;
    window.requestAnimationFrame(() => {
      state.renderScheduled = false;
      render();
    });
  }

  function render({ force = false } = {}) {
    if (state.paused && !force) {
      return;
    }

    const mode = state.followLive ? "live" : "review";
    let option;
    if (state.followLive) {
      const bounds = liveBounds();
      const source = sourceInRange(state, bounds.minX, bounds.maxX);
      const yAxisBounds = mergeLiveYAxis(paddedAxis(valueExtent([source.raw, source.filtered])));
      const recordRange = visibleRecordRange(recordApi.currentRecordRange(), bounds.minX, bounds.maxX);
      dom.windowValue.textContent = t("window.samples", {
        start: formatSample(bounds.minX),
        end: formatSample(bounds.maxX),
      });
      option = chartOption(source, {
        mode,
        minX: bounds.minX,
        maxX: bounds.maxX,
        yAxisBounds,
        recordRange,
      });
    } else {
      dom.windowValue.textContent = t("window.review");
      option = chartOption(state, {
        mode,
        initialRange: state.pendingReviewRange,
        recordRange: recordApi.currentRecordRange(),
      });
      state.pendingReviewRange = null;
    }

    state.ignoreDataZoomEvent = true;
    chart.setOption(option, state.lastRenderMode !== mode);
    state.lastRenderMode = mode;
    window.requestAnimationFrame(() => {
      state.ignoreDataZoomEvent = false;
    });
  }

  function renderRecord() {
    if (!state.lastRecord) {
      return;
    }

    recordApi.setRecordSectionVisible(true);
    const minX = recordApi.captureStartSequence(state.lastRecord);
    const maxX = recordApi.captureEndSequence(state.lastRecord);
    const recordSource = sourceInRange(state.lastRecord, minX, maxX);
    const option = chartOption(recordSource, {
      mode: "review",
      recordRange: recordApi.buildRecordRange(state.lastRecord, state.lastRecord.endSeq, t("record.range.recorded")),
      initialRange: {
        minX,
        maxX,
      },
    });
    recordChart.setOption(option, true);
    recordChart.resize();
  }

  function updateFollowButton() {
    dom.followBtn.textContent = state.followLive ? t("follow.enterReview") : t("follow.returnLive");
    dom.followBtn.classList.toggle("active", !state.followLive);
  }

  function enterReviewMode() {
    if (!state.followLive) {
      return;
    }
    state.pendingReviewRange = liveBounds();
    state.followLive = false;
    updateFollowButton();
    scheduleRender(true);
  }

  function exitReviewMode() {
    state.pendingReviewRange = null;
    state.followLive = true;
    updateFollowButton();
    scheduleRender(true);
  }

  function clearCharts() {
    chart.clear();
    recordChart.clear();
  }

  function resizeCharts() {
    chart.resize();
    recordChart.resize();
  }

  function attachChartEvents() {
    chart.on("dataZoom", () => {
      if (state.ignoreDataZoomEvent) {
        return;
      }
      enterReviewMode();
      dom.windowValue.textContent = t("window.review");
    });
  }

  return {
    attachChartEvents,
    buildRecordRange: (...args) => recordApi.buildRecordRange(...args),
    chart,
    clearCharts,
    enterReviewMode,
    exitReviewMode,
    firstSequenceFrom,
    formatSample,
    latestSequenceFrom,
    recordChart,
    render,
    renderRecord,
    resizeCharts,
    scheduleRender,
    sourceInRange,
    updateFollowButton,
  };
}
