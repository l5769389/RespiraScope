import {invalidIntervals,validSequence} from './record-quality.js';
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
    return points.map(point => ({value:point}));
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

  function filterMarkersBySupport(markers, supportSeries, warmup = FILTER_MARKER_WARMUP_POINTS) {
    if (!supportSeries.length) {
      return [];
    }

    const supportSegments = splitContinuousSegments(supportSeries).map((segment) => ({
      minX: pointSequence(segment[0]) + warmup,
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

  function sourceInRange(source, minX, maxX, {analysis = false} = {}) {
    const rangedSource = {
      raw: sliceByRange(source.raw, minX, maxX),
      filtered: sliceByRange(source.filtered, minX, maxX),
    };
    const markerSupport = source.filtered.length > 0 ? source.filtered : source.raw;
    // Offline records already contain detected extrema; retain those saved markers.
    const warmup = analysis ? 0 : FILTER_MARKER_WARMUP_POINTS;
    return {
      ...rangedSource,
      processingQuality:source.processingQuality,
      peaks: filterMarkersBySupport(sliceByRange(source.peaks, minX, maxX), markerSupport, warmup),
      valleys: filterMarkersBySupport(sliceByRange(source.valleys, minX, maxX), markerSupport, warmup),
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
    const unprocessed = invalidIntervals(source).filter(i=>i.reason === 'motion' || i.reason === 'too_short');
    const filtered = options.analysis ? withGapBreaks(source.filtered).map(p=>validSequence(p[0],unprocessed) ? p : [p[0],null]) : smoothSeries(source.filtered);
    const reference = options.analysis && source.processingQuality?.version === 2
      ? withGapBreaks(source.filtered).map(p=>validSequence(p[0],unprocessed) ? [p[0],null] : p) : [];
    const isLive = mode === "live";
    const compact = isCompactViewport();
    const markArea = recordMarkArea(options.recordRange);
    if (options.analysis && markArea) {
      for (const [area] of markArea.data) area.label = {show:false};
    }
    const maxX = isLive ? options.maxX ?? liveDisplayWindow() : undefined;
    const yAxisBounds =
      options.yAxisBounds ?? (isLive ? { min: 0, max: Y_AXIS_MIN_SPAN } : paddedAxis(valueExtent([raw, filtered, reference])));
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
      ...(reference.some(p=>p[1] != null) ? {legend:{top:0,right:20,
        data:[t('series.reference')],selectedMode:false,textStyle:{color:'#64748b',fontSize:11}}} : {}),
      xAxis: {
        type: "value",
        min: isLive ? options.minX : undefined,
        max: isLive ? maxX : undefined,
        minInterval: options.analysis ? 1 : (compact ? 50 : 100),
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
          formatter: options.analysis ? value => Math.round(value).toString() : formatSample,
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
          sampling: options.analysis ? undefined : "lttb",
          lineStyle: {
            color: "#8a96a8",
            width: 1,
            opacity: 0.7,
          },
          areaStyle: {
            opacity: 0,
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
          smooth: !options.analysis && smoothingWindow() > 1,
          connectNulls: false,
          data: filtered,
          sampling: options.analysis ? undefined : "lttb",
          lineStyle: {
            color: "#2563eb",
            width: 2.5,
            shadowColor: "rgba(29, 78, 216, 0.16)",
            shadowBlur: 0,
          },
          areaStyle: {
            opacity: 0,
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
          id:"peaks",
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
            shadowBlur: 0,
            shadowColor: "rgba(244, 63, 94, 0.22)",
          },
        },
        {
          id:"valleys",
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
            shadowBlur: 0,
            shadowColor: "rgba(20, 184, 166, 0.22)",
          },
        },
        {
          id:'artifact-reference', name:t('series.reference'), type:'line',
          animation:false, showSymbol:false, connectNulls:false, data:reference,
          lineStyle:{color:'#2563eb',width:2,type:'dashed'}, itemStyle:{color:'#2563eb'},
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

  function binSeries() {
    const bins = ctx.analysisApi?.bins() ?? [];
    const settings = ctx.analysisApi?.settings();
    const count = (settings?.totalBins ?? 10)/2;
    const fixed = settings?.basis === "amplitude" && settings.amplitudeMode === "fixed";
    const zh = ctx.getCurrentLanguage() === "zh";
    const color = direction => direction === "inhale" ? "#0f766e" : "#b45309";
    const boundaryMap = new Map();
    if (fixed) {
      for (let i = 1; i < count; i++) {
        boundaryMap.set(i, {yAxis:settings.lower+(settings.upper-settings.lower)*i/count,
          lineStyle:{color:'#399aa2'}});
      }
    } else {
      for (const bin of bins) {
        for (const x of [bin.start,bin.end]) boundaryMap.set(x, {xAxis:x,lineStyle:{color:color(bin.direction)}});
      }
    }
    const labelY = bin => {
      if (!fixed) return bin.direction === "inhale" ? top-(top-bottom)*0.06 : bottom+(top-bottom)*0.06;
      const rising = (bin.direction === 'inhale') === (settings.inhaleRising !== false);
      const band = rising ? bin.bin : count+1-bin.bin;
      return settings.lower+(settings.upper-settings.lower)*(band-0.5)/count;
    };
    const axis = recordChart.getOption()?.yAxis?.[0];
    const top = Number(axis?.max), bottom = Number(axis?.min);
    return {
      id:"record-bins", name:zh ? "呼吸分箱" : "Respiratory bins", type:"scatter", symbolSize:0,
      silent:true, z:9, animation:false,
      data:bins.map(bin=>({value:[(bin.start+bin.end)/2,labelY(bin)],
        label:{show:Math.abs(recordChart.convertToPixel({xAxisIndex:0},bin.end)-recordChart.convertToPixel({xAxisIndex:0},bin.start)) >= 24,
          formatter:`${bin.direction === "inhale" ? (zh?"吸":"I") : (zh?"呼":"E")} ${bin.bin}`,
          color:color(bin.direction),position:fixed ? "inside" : bin.direction === "inhale" ? "bottom" : "top"},
      })),
      label:{show:true,fontSize:10}, labelLayout:{hideOverlap:true},
      markLine:{silent:true,symbol:"none",label:{show:false},lineStyle:{type:"dashed",width:1,opacity:0.65},data:[...boundaryMap.values()]},
    };
  }

  function updateRecordBins() {
    if (!state.lastRecord) return;
    const record = state.lastRecord;
    const source = sourceInRange(record,recordApi.captureStartSequence(record),recordApi.captureEndSequence(record),{analysis:true});
    recordChart.setOption({series:[binSeries(),
      {id:'peaks',data:markerData(source.peaks)},
      {id:'valleys',data:markerData(source.valleys)},
    ]});
  }

  function installAmplitudeHandles() {
    const options = ctx.analysisApi?.settings();
    if (!options || options.basis !== "amplitude" || options.amplitudeMode !== "fixed") {
      return;
    }
    const compact = isCompactViewport();
    const left = compact ? 42 : 52, right = recordChart.getWidth()-(compact ? 12 : 28);
    const zh = ctx.getCurrentLanguage() === "zh";
    recordChart.setOption({graphic:["lower","upper"].map(key=>({
      id:`amp-${key}`, type:"group", x:0,
      y:recordChart.convertToPixel({yAxisIndex:0},options[key]),
      draggable:ctx.analysisApi.isBusy() ? false : "vertical", cursor:"ns-resize", z:100,
      children:[
        {type:"rect",z:100,shape:{x:left,y:-8,width:right-left,height:16},style:{fill:"rgba(8,127,140,0.06)"}},
        {type:"line",z:101,shape:{x1:left,y1:0,x2:right,y2:0},style:{stroke:"#087f8c",lineWidth:2}},
        {type:"text",z:102,x:right-6,y:-5,style:{text:`↕ ${key === "lower" ? (zh?"下界":"Lower") : (zh?"上界":"Upper")}`,
          textAlign:"right",textVerticalAlign:"bottom",fill:"#087f8c",backgroundColor:"#ffffff",padding:[2,4]}},
      ],
      ondrag:function() {
        const value = recordChart.convertFromPixel({yAxisIndex:0},this.y);
        ctx.analysisApi.updateBound(key,value,{preview:true});
        this.y = recordChart.convertToPixel({yAxisIndex:0},options[key]);
      },
      ondragend:function() { ctx.analysisApi.updateBound(key,options[key]); },
    }))});
  }

  function renderRecord({preserveZoom=false} = {}) {
    if (!state.lastRecord) return;
    recordApi.setRecordSectionVisible(true);
    ctx.analysisApi?.sync();
    const minX = recordApi.captureStartSequence(state.lastRecord);
    const maxX = recordApi.captureEndSequence(state.lastRecord);
    const recordSource = sourceInRange(state.lastRecord, minX, maxX, {analysis:true});
    const settings = ctx.analysisApi?.settings();
    let extent = valueExtent([recordSource.raw,recordSource.filtered]);
    if (extent && settings?.basis === "amplitude" && settings.amplitudeMode === "fixed") {
      extent = {min:Math.min(extent.min,settings.lower),max:Math.max(extent.max,settings.upper)};
    }
    const previousZoom = preserveZoom ? recordChart.getOption()?.dataZoom : null;
    const option = chartOption(recordSource, {
      mode:"review", analysis:true, yAxisBounds:paddedAxis(extent),
      recordRange:recordApi.buildRecordRange(state.lastRecord,state.lastRecord.endSeq,t("record.range.recorded")),
      initialRange:{minX:state.lastRecord.startSeq ?? minX,maxX:state.lastRecord.endSeq ?? maxX},
    });
    if (previousZoom?.length) option.dataZoom.forEach((zoom,i)=>{
      delete zoom.startValue; delete zoom.endValue;
      zoom.start = previousZoom[i]?.start ?? previousZoom[0].start;
      zoom.end = previousZoom[i]?.end ?? previousZoom[0].end;
    });
    recordChart.setOption(option,true);
    recordChart.resize();
    updateRecordBins();
    installAmplitudeHandles();
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
    if (state.lastRecord) updateRecordBins();
    installAmplitudeHandles();
  }

  function attachChartEvents() {
    recordChart.on("dataZoom", () => {updateRecordBins();installAmplitudeHandles();});
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
    updateRecordBins,
    resizeCharts,
    scheduleRender,
    sourceInRange,
    updateFollowButton,
  };
}
