const shared = window.RespiraScopeShared || {};
const runtimeConfig = shared.runtimeConfig || window.CT_BREATH_RUNTIME_CONFIG || {};
const LANGUAGE_KEY = shared.languageKey || "RespiraScope-language";

const TEXT = {
  zh: {
    appTitle: "4D 呼吸采集辅助算法",
    brandSubtitle: "呼吸采集与分析",
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
    guideKicker: "Workflow",
    guideTitle: "使用说明",
    guideStartTitle: "开始监测",
    guideStartText: "连接后端并接收实时呼吸波形，观察滤波、峰谷识别和 BPM 估计。",
    guideRecordStartTitle: "开始记录",
    guideRecordStartText: "从当前时刻截取一段采集片段，实时图中会高亮记录区间。",
    guideScanTitle: "扫描标记",
    guideScanText: "在记录过程中标记扫描或重点时间段，便于之后回看定位。",
    guideRecordEndTitle: "结束记录",
    guideRecordEndText: "停止片段采集并展示记录波形，包含前后缓冲和离线复算结果。",
    heroKicker: "Algorithm Workflow",
    heroTitle: "从呼吸波形到 4D 采集可用的节律信息",
    heroText: "系统完成实时信号接收、滤波降噪、峰谷识别、BPM 估计、记录片段、扫描标记和离线复算，帮助快速判断呼吸采集过程是否稳定、是否可回看。",
    startDemo: "查看算法演示",
    openMonitor: "进入实时监测",
    openLab: "调整模拟参数",
    monitor: "实时监测",
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
    brandSubtitle: "Respiratory acquisition & analysis",
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
    guideKicker: "Workflow",
    guideTitle: "Usage",
    guideStartTitle: "Start Monitoring",
    guideStartText: "Connect to the backend and receive realtime breath waveforms with filtering, peak/valley detection, and BPM.",
    guideRecordStartTitle: "Start Record",
    guideRecordStartText: "Capture a segment from the current moment; the realtime chart highlights the recorded range.",
    guideScanTitle: "Scan Marker",
    guideScanText: "Mark scan or review ranges while recording so they can be located later.",
    guideRecordEndTitle: "End Record",
    guideRecordEndText: "Stop segment capture and show the recorded waveform with pre/post buffer and offline recalculation.",
    heroKicker: "Algorithm Workflow",
    heroTitle: "From breath waveform to 4D acquisition-ready rhythm data",
    heroText: "The system handles realtime signal intake, denoising, peak and valley detection, BPM estimation, segment recording, scan markers, and offline recalculation so the acquisition process can be reviewed.",
    startDemo: "View Algorithm Demo",
    openMonitor: "Open Monitor",
    openLab: "Tune Simulation",
    monitor: "Live Monitor",
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

const modes = availableModes();
const frames = new Map();
let language = preferredLanguage();
let activeMode = '';
let backendState = 'checking';
let mockEnabled = Boolean(runtimeConfig.mockSignalEnabled);
let demoPending = false;
const t = key => TEXT[language]?.[key] ?? TEXT.en[key] ?? key;

function sendLanguage(frame) {
  frame.contentWindow?.postMessage({type:'RespiraScope-language',language},location.origin);
}

function renderStatus() {
  const source = mockEnabled ? t('dataSourceMock') : runtimeConfig.mockSignalEnabled === false
    ? `${t('dataSourceSensor')} ${runtimeConfig.sensorHost || ''}:${runtimeConfig.sensorPort || ''}` : t('dataSourceDisabled');
  const statuses = {
    backend:{label:t('backend'),value:t(backendState==='online'?'backendOnline':backendState==='offline'?'backendOffline':'backendChecking'),
      tone:backendState==='online'?'ok':backendState==='offline'?'danger':'pending'},
    source:{label:t('dataSource'),value:source,tone:mockEnabled?'ok':runtimeConfig.mockSignalEnabled===false?'sensor':'warn'},
    session:{label:t('session'),value:shared.sessionId?t('sessionIsolated'):'-',tone:'info'},
  };
  for (const [id,info] of Object.entries(statuses)) {
    const node=document.getElementById(`status-${id}`);
    node.className=`status-pill ${info.tone}`;
    node.querySelector('span').textContent=info.label;
    node.querySelector('strong').textContent=info.value;
    node.title=`${info.label}: ${info.value}`;
    node.setAttribute('aria-label',node.title);
  }
}

function translate() {
  document.documentElement.lang=language==='zh'?'zh-CN':'en';
  document.title=t('appTitle');
  document.querySelectorAll('[data-text]').forEach(node=>{node.textContent=t(node.dataset.text);});
  document.getElementById('languageSelect').value=language;
  document.querySelectorAll('[data-mode]').forEach(button=>{
    button.title=`${t(button.dataset.mode)}: ${t(`${button.dataset.mode}Text`)}`;
    button.setAttribute('aria-label',button.title);
  });
  document.querySelector('.rail-guide').setAttribute('aria-label',t('guideTitle'));
  frames.forEach((frame,mode)=>{frame.title=t(`${mode}FrameTitle`);sendLanguage(frame);});
  renderStatus();
}

function startPendingDemo() {
  const frame=frames.get('monitor');
  if (demoPending && frame?.dataset.loaded==='true') {
    frame.contentWindow.postMessage({type:'RespiraScope-start-demo'},location.origin);
    demoPending=false;
  }
}

function activateMode(value,{updateHash=true,replaceHash=false}={}) {
  let mode=normalizeMode(value);
  if (!modes[mode]) mode=modes.monitor?'monitor':modes.lab?'lab':'';
  if (!mode) return;
  activeMode=mode;
  if (!frames.has(mode)) {
    const frame=document.createElement('iframe');
    frame.className='mode-frame';
    frame.title=t(`${mode}FrameTitle`);
    frame.src=publicUrl(`/${mode}/index.html`);
    frame.addEventListener('load',()=>{frame.dataset.loaded='true';sendLanguage(frame);startPendingDemo();});
    frames.set(mode,frame);
    document.querySelector('.frame-stage').append(frame);
  }
  frames.forEach((frame,name)=>frame.classList.toggle('active',name===mode));
  document.querySelectorAll('[data-mode]').forEach(button=>{
    button.classList.toggle('active',button.dataset.mode===mode);
    button.setAttribute('aria-pressed',String(button.dataset.mode===mode));
  });
  if (updateHash && location.hash!==`#${mode}`) {
    if (replaceHash) history.replaceState(null,'',`#${mode}`);
    else location.hash=mode;
  }
  startPendingDemo();
}

async function refreshRuntimeStatus() {
  try {
    const response=await apiFetch('/health',{signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error(`health ${response.status}`);
    const payload=await response.json();
    backendState='online';
    mockEnabled=Boolean((payload.data || payload).mock_signal_enabled ?? runtimeConfig.mockSignalEnabled);
  } catch {
    backendState='offline';
    mockEnabled=Boolean(runtimeConfig.mockSignalEnabled);
  }
  renderStatus();
}

function updateLanguage(value) {
  if (!['zh','en'].includes(value)) return;
  language=value;
  if (typeof shared.setPreferredLanguage==='function') shared.setPreferredLanguage(value);
  else localStorage.setItem(LANGUAGE_KEY,value);
  translate();
}

document.querySelectorAll('[data-mode]').forEach(button=>{
  button.hidden=!modes[button.dataset.mode];
  button.addEventListener('click',()=>activateMode(button.dataset.mode));
});
document.querySelector('.disabled-panel').hidden=modes.monitor || modes.lab;
document.querySelector('.console-workspace').hidden=!modes.monitor && !modes.lab;
document.getElementById('languageSelect').addEventListener('change',event=>updateLanguage(event.target.value));
window.addEventListener('hashchange',()=>activateMode(location.hash,{updateHash:false}));
window.addEventListener('storage',event=>{
  if (event.key===LANGUAGE_KEY && ['zh','en'].includes(event.newValue)) {language=event.newValue;translate();}
});
window.addEventListener('message',event=>{
  if (event.origin!==location.origin || ![...frames.values()].some(frame=>frame.contentWindow===event.source)) return;
  if (event.data?.type==='RespiraScope-open-monitor' && modes.monitor) {
    demoPending=Boolean(event.data.startDemo);
    activateMode('monitor');
  }
});
translate();
activateMode(location.hash || 'monitor',{replaceHash:true});
refreshRuntimeStatus();
const healthTimer=setInterval(refreshRuntimeStatus,10000);
window.addEventListener('pagehide',()=>clearInterval(healthTimer));
