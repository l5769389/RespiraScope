# RespiraScope 对外接口使用说明

本文面向需要接入 RespiraScope 的外部系统，说明当前项目真实可用的 HTTP 接口、Socket.IO 实时推送、请求体、返回体和常见错误条件。

## 1. 基础约定

### 1.1 服务地址

默认后端地址：

```text
http://127.0.0.1:8000
```

实际地址以运行配置为准，可通过：

```http
GET /runtime/config
```

读取 `backend_host`、`backend_port`、`sensor.host`、`sensor.port` 等运行时信息。

### 1.2 响应结构

核心 HTTP 接口通常返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "ok",
  "data": {}
}
```

说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | number | `1` 表示业务成功，`0` 表示业务失败 |
| `status` | string | `success` 或 `error` |
| `message` | string | 本次操作说明 |
| `data` | any | 推荐外部系统优先读取的业务数据 |

兼容说明：

- 部分接口仍会把 `stream`、`record`、`scan`、`peak`、`valley`、`metrics` 等字段放在顶层，便于旧前端继续使用。
- 新系统建议优先读取 `data`，只有在文档明确说明时再读取顶层补充字段。
- `GET /stream/status` 使用 Pydantic 响应模型，返回 `{ code, status, data }`，不包含 `message`。
- `/mock/*` 模拟信号接口返回较轻量，通常为 `{ code, data }`。

错误响应通常使用 HTTP 400，错误信息在 `detail` 内：

```json
{
  "detail": {
    "code": 0,
    "status": "error",
    "message": "No recording has been started",
    "data": {
      "record": {
        "recording": false,
        "scan_active": false,
        "scans": []
      }
    }
  }
}
```

### 1.3 时间和序号

| 概念 | 说明 |
| --- | --- |
| `sequence` | 后端生成的递增采样序号，是实时波形、滤波结果、峰谷、记录区间和扫描区间对齐的主键 |
| ISO 时间 | 所有接口返回的时间字段使用 ISO-8601 字符串，例如 `2026-05-25T10:30:10.000000+00:00` |
| 秒数 | 耗时、间隔类字段使用数值秒，例如 `duration_seconds`、`seconds_since_last_data` |
| 断流判断 | 如果 `sequence` 出现明显跳跃，外部系统应认为中间发生过断流或丢包，不建议把缺口两端直接连线 |

### 1.4 多用户会话隔离

云端多人访问时，推荐每个浏览器标签页或每个外部业务会话生成一个不重复的匿名会话 ID，并在所有请求中携带：

```http
X-RespiraScope-Session: <session-id>
```

Socket.IO 连接需要同时在 query 或 auth 中携带：

```text
session_id=<session-id>
```

带 session 的请求会使用独立的实时采集、滤波参数、记录区间、扫描区间、模拟信号配置和 Socket.IO 推送房间。未携带 session 的请求继续使用旧版全局运行实例，主要用于本地调试和兼容旧客户端。

## 2. 推荐调用流程

### 2.1 实时监测流程

1. 调用 `GET /health` 或 `GET /stream/status`，确认后端和传感器状态。
2. 调用 `POST /startReceive`，可传入滤波配置；如果已经开始接收，接口会直接返回当前状态，不会用本次请求体更新滤波参数。
3. 连接 Socket.IO `/breath` 命名空间，监听 `breath` 事件。
4. 按 `type` 消费实时消息：`raw`、`filtered`、`peak`、`valley`、`metrics`、`signal_quality`。
5. 如需更新实时滤波参数，调用 `POST /setRTFilterParams`。
6. 如需停止接收，调用 `POST /stopReceive`。

### 2.2 记录和扫描流程

一次典型记录流程：

```text
POST /startReceive
等待至少收到 1 个 raw 点
POST /record/start
POST /scan/start
POST /scan/end
POST /scan/start
POST /scan/end
POST /record/end
POST /record/save
```

调用规则：

| 接口 | 规则 |
| --- | --- |
| `record/start` | 只能在已开始接收且已经收到 raw 数据后调用 |
| `scan/start` | 只能在 `record/start` 和 `record/end` 之间调用 |
| `scan/end` | 只能在存在活动扫描时调用 |
| 多段扫描 | 一次记录中可以有多组 `scan/start` 到 `scan/end` |
| `record/end` | 结束用户选择的记录区间，等待 end 后辅助点采集完成，然后返回离线滤波结果 |
| `record/reset` | 清空后端当前 record/scan 状态，不会停止传感器接收 |

### 2.3 离线复算流程

如果外部系统已有历史原始数据，可调用：

```http
POST /applyFilter
```

该接口对任意 `raw_data` 做离线滤波和峰谷识别。当前记录流程不再需要前端把 record 阶段数据发给 `/applyFilter`，因为 `/record/end` 已经会返回本次记录的离线滤波结果。

## 3. Socket.IO 实时推送

### 3.1 连接方式

| 项 | 值 |
| --- | --- |
| 协议 | Socket.IO |
| 命名空间 | `/breath` |
| 事件名 | `breath` |
| 示例地址 | `http://127.0.0.1:8000/breath` |
| 推送节奏 | 默认约 40ms 一批 |

多用户隔离模式下，连接示例：

```js
const sessionId = crypto.randomUUID();
const socket = io("http://127.0.0.1:8000/breath", {
  transports: ["websocket"],
  auth: { session_id: sessionId },
  query: { session_id: sessionId },
});
```

新客户端连接后，如果后端已有最近的实时数据，会立即向该客户端补发一组最近快照。快照仍然使用同一个 `breath` 事件，外部系统不需要监听额外事件。

统一消息结构：

```json
{
  "type": "raw",
  "data": [[1024, 188.42], [1025, 189.1]]
}
```

### 3.2 `raw`

原始呼吸数据，来自传感器输入。

```json
{
  "type": "raw",
  "data": [[1024, 188.42]]
}
```

| 位置 | 字段 | 说明 |
| --- | --- | --- |
| `data[n][0]` | `sequence` | 后端生成的递增采样序号 |
| `data[n][1]` | `value` | 原始呼吸信号值 |

### 3.3 `filtered`

实时滤波后的呼吸数据，和 `raw` 使用同一条 `sequence` 轴。

```json
{
  "type": "filtered",
  "data": [[1024, 187.63]]
}
```

| 位置 | 字段 | 说明 |
| --- | --- | --- |
| `data[n][0]` | `sequence` | 对应原始数据序号 |
| `data[n][1]` | `value` | 滤波后的呼吸信号值 |

### 3.4 `peak` / `valley`

实时识别出的波峰和波谷。

```json
{
  "type": "peak",
  "data": [[1088, 246.19]]
}
```

| 位置 | 字段 | 说明 |
| --- | --- | --- |
| `data[n][0]` | `sequence` | 波峰或波谷所在采样序号 |
| `data[n][1]` | `value` | 波峰或波谷对应的滤波值 |

### 3.5 `metrics`

BPM 和呼吸稳定性指标。

```json
{
  "type": "metrics",
  "data": [
    {
      "bpm": 18.25,
      "quality": "stable",
      "breath_count": 6,
      "interval_cv": 0.08
    }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `bpm` | number \| null | 呼吸频率，单位：次/分钟 |
| `quality` | string | `insufficient`、`stable`、`variable`、`irregular` |
| `breath_count` | number | 当前窗口内参与计算的波峰数量 |
| `interval_cv` | number \| null | 波峰间隔变异系数，越低表示节律越稳定 |

### 3.6 `signal_quality`

实时信号质量和异常片段事件，可用于提示传感器断流、低幅度、强干扰或噪声异常。

```json
{
  "type": "signal_quality",
  "data": [
    {
      "sequence": 2048,
      "value": 845.68,
      "quality": "artifact",
      "details": {
        "delta": 421.93,
        "baseline_delta": 335.23,
        "kind": "sudden_change"
      }
    }
  ]
}
```

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `sequence` | number | 异常或质量状态对应的采样序号 |
| `value` | number | 触发事件时的原始信号值 |
| `quality` | string | `good`、`low_amplitude`、`artifact`、`noisy`、`gap` |
| `details` | object | 触发原因的附加信息，例如 `delta`、`baseline_delta`、`gap_points` |

## 4. HTTP 接口明细

### 4.1 `GET /health`

用途：启动前检查后端是否运行，以及当前配置的传感器和前端入口。

请求体：无。

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "healthy",
  "data": {
    "status": "healthy",
    "mock_signal_enabled": true,
    "sensor": {
      "host": "127.0.0.1",
      "port": 9000
    },
    "frontends": {
      "console_enabled": true,
      "console_host": "127.0.0.1",
      "console_port": 8000,
      "lab_enabled": true,
      "monitor_enabled": true,
      "guide_enabled": true,
      "api_docs_enabled": true
    }
  }
}
```

关键字段：

| 字段 | 说明 |
| --- | --- |
| `data.status` | `healthy` 表示后端服务已启动 |
| `data.mock_signal_enabled` | 是否使用内置模拟信号 |
| `data.sensor.host` / `data.sensor.port` | 后端尝试连接的传感器 TCP 地址 |
| `data.frontends` | 当前启用的前端页面信息 |

### 4.2 `GET /runtime/config`

用途：读取运行时配置，前端和外部系统可用它发现后端、传感器、前端页面和记录辅助点配置。

请求体：无。

成功返回关键字段：

| 字段 | 说明 |
| --- | --- |
| `data.mock_signal_enabled` | 是否启用模拟信号 |
| `data.config_path` | 当前配置文件路径 |
| `data.sensor.host` / `data.sensor.port` | 传感器 TCP 地址 |
| `data.backend_host` / `data.backend_port` | 后端服务地址 |
| `data.console_*` / `data.monitor_*` / `data.api_docs_*` | 前端页面配置 |
| `data.record.pre_points` | `record/start` 前保留的辅助点数量 |
| `data.record.post_points` | `record/end` 后保留的辅助点数量 |

### 4.3 `GET /stream/status`

用途：检查实时接收、任务、队列、信号质量和记录状态。

请求体：无。

成功返回结构：

```json
{
  "code": 1,
  "status": "success",
  "data": {
    "started": true,
    "state": "running",
    "last_error": null,
    "tasks": {
      "receiver": { "done": false, "cancelled": false },
      "processor": { "done": false, "cancelled": false },
      "sender": { "done": false, "cancelled": false }
    },
    "receiver": {
      "sensor_host": "127.0.0.1",
      "sensor_port": 9000,
      "sequence_number": 2048,
      "received_count": 2048,
      "last_data_at": "2026-05-25T10:30:10.000000+00:00",
      "seconds_since_last_data": 0.04,
      "socket": {
        "host": "127.0.0.1",
        "port": 9000,
        "running": true,
        "connected": true,
        "received_count": 2048,
        "last_error": null,
        "last_connected_at": "2026-05-25T10:29:00.000000+00:00",
        "last_disconnected_at": null,
        "last_received_at": "2026-05-25T10:30:10.000000+00:00",
        "seconds_since_last_data": 0.04
      }
    },
    "queues": {
      "raw": 0,
      "filtered": 0,
      "peaks": 0,
      "valleys": 0,
      "metrics": 0,
      "signal_quality": 0
    },
    "queue_stats": {
      "dropped": {
        "raw": 0,
        "filtered": 0,
        "peaks": 0,
        "valleys": 0,
        "metrics": 0,
        "signal_quality": 0
      },
      "high_watermark": {
        "raw": 12,
        "filtered": 12,
        "peaks": 1,
        "valleys": 1,
        "metrics": 1,
        "signal_quality": 0
      }
    },
    "record": {
      "pre_points": 200,
      "post_points": 200,
      "recording": false,
      "post_recording": false,
      "record_complete": false,
      "record_start_sequence": null,
      "record_end_sequence": null,
      "capture_start_sequence": null,
      "capture_end_sequence": null,
      "scan_active": false,
      "active_scan": null,
      "scans": []
    },
    "signal_quality": {
      "current_quality": "good",
      "last_event": null,
      "event_counts": {}
    },
    "filter_config": {
      "low_bpm": 6,
      "high_bpm": 40,
      "sampling_rate": 50
    }
  }
}
```

关键字段：

| 字段 | 说明 |
| --- | --- |
| `data.started` | 是否已调用 `POST /startReceive` 且系统处于接收流程 |
| `data.state` | `idle`、`running`、`stopped`、`error` |
| `data.receiver.sequence_number` | 当前采样序号 |
| `data.receiver.received_count` | 已接收采样点数量 |
| `data.receiver.seconds_since_last_data` | 距离上一次收到数据的秒数；未收到过数据时为 `null` |
| `data.receiver.socket.connected` | 是否连接到传感器 TCP 服务 |
| `data.queues` | 各实时队列当前长度 |
| `data.queue_stats.dropped` | 各实时队列因满载而丢弃的数据数量 |
| `data.queue_stats.high_watermark` | 各实时队列历史最高水位 |
| `data.record.recording` | 是否处于用户记录区间 |
| `data.record.scan_active` | 是否存在活动扫描区间 |
| `data.signal_quality` | 当前信号质量、最近事件和事件累计次数 |
| `data.filter_config` | 当前实时滤波配置 |

### 4.4 `POST /startReceive`

用途：启动传感器接收、实时滤波、峰谷识别和实时推送。

前置条件：无。若已经处于运行状态，接口不会重复启动任务，也不会用本次请求体更新滤波参数；它会直接返回当前状态，`message` 为 `Receive already started`。运行中需要调整参数时请调用 `POST /setRTFilterParams`。

请求体：可省略。省略或传 `{}` 时使用默认 `FilterConfig`。

```json
{
  "low_bpm": 6,
  "high_bpm": 40,
  "order": 1,
  "sampling_rate": 50,
  "gaussian_sigma": 1,
  "min_peak_distance": 15,
  "peak_threshold_ratio": 0.3,
  "prominence": 1,
  "auto_peak_detection": true,
  "confirm_realtime_events": false,
  "confirmation_delay_points": 12,
  "data_gap_reset_points": 25,
  "gap_warmup_points": 75,
  "restore_baseline": true
}
```

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "Filter configuration updated",
  "data": {
    "config": {
      "low_bpm": 6,
      "high_bpm": 40,
      "lowpass_cutoff": 0.1,
      "highpass_cutoff": 0.6666666666666666,
      "order": 1,
      "sampling_rate": 50,
      "gaussian_sigma": 1,
      "min_peak_distance": 15,
      "peak_threshold_ratio": 0.3,
      "prominence": 1,
      "auto_peak_detection": true,
      "confirm_realtime_events": false,
      "confirmation_delay_points": 12,
      "data_gap_reset_points": 25,
      "gap_warmup_points": 75,
      "restore_baseline": true
    },
    "stream": {
      "started": true,
      "state": "running"
    }
  },
  "config": {},
  "stream": {}
}
```

说明：

- `bandpass_mode` 默认为 `preset`：时间模式由 `low_bpm`、`high_bpm` 换算截止频率，幅值模式使用 0.03–2 Hz；设为 `custom` 时保留传入的 Hz 上下限。
- 外部系统通常只需要配置 BPM、采样率、平滑窗口、峰谷参数。
- `data.stream` 完整结构同 `GET /stream/status` 的 `data`。

### 4.5 `POST /stopReceive`

用途：停止传感器接收并清理实时处理上下文。

前置条件：无。即使当前未运行，也会返回当前 stopped 状态。

请求体：无。

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "Receive stopped",
  "data": {
    "stream": {
      "started": false,
      "state": "stopped"
    }
  },
  "stream": {
    "started": false,
    "state": "stopped"
  }
}
```

### 4.6 `POST /setRTFilterParams`

用途：更新实时滤波和实时峰谷识别参数。

前置条件：无。未开始接收时也可以调用，但如果随后 `POST /startReceive` 又传入请求体，则以 `startReceive` 的请求体为准。推荐在已经接收数据后用本接口调整实时参数。

请求体：同 `POST /startReceive`，可省略。

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "Filter configuration updated",
  "data": {
    "config": {
      "low_bpm": 6,
      "high_bpm": 40,
      "sampling_rate": 50
    }
  },
  "config": {
    "low_bpm": 6,
    "high_bpm": 40,
    "sampling_rate": 50
  }
}
```

### 4.7 `POST /applyFilter`

用途：对任意历史原始数据做离线滤波、峰谷识别和指标计算。

前置条件：无。

请求体：可省略。省略或传 `{}` 时使用默认滤波参数和空 `raw_data`，返回空结果。

```json
{
  "filter_config": {
    "low_bpm": 6,
    "high_bpm": 40,
    "sampling_rate": 50,
    "gaussian_sigma": 1,
    "min_peak_distance": 15,
    "peak_threshold_ratio": 0.3,
    "prominence": 1,
    "auto_peak_detection": true,
    "restore_baseline": true
  },
  "raw_data": [[1024, 188.42], [1025, 189.1]]
}
```

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "ok",
  "data": [[1024, 187.63], [1025, 188.02]],
  "peak": [
    { "sequence": 1088, "value": 246.19 }
  ],
  "valley": [
    { "sequence": 1154, "value": 95.31 }
  ],
  "filter_config": {
    "low_bpm": 6,
    "high_bpm": 40,
    "sampling_rate": 50
  },
  "metrics": {
    "bpm": 18.25,
    "quality": "stable",
    "breath_count": 6,
    "interval_cv": 0.08
  }
}
```

返回字段：

| 字段 | 说明 |
| --- | --- |
| `data` | 离线滤波结果，格式为 `[[sequence, value], ...]` |
| `peak` | 离线识别出的波峰，格式为 `[{ sequence, value }, ...]` |
| `valley` | 离线识别出的波谷，格式为 `[{ sequence, value }, ...]` |
| `filter_config` | 实际使用的滤波参数 |
| `metrics` | 离线 BPM 和稳定性指标 |

### 4.8 `POST /record/start`

用途：开始记录用户选择的记录区间。

前置条件：

- 已调用 `POST /startReceive`。
- 后端已经收到至少 1 个 `raw` 数据点。

重复调用：如果已经处于记录中，会直接返回当前 `record` 状态，`message` 为 `Record already started`。

请求体：无。

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "Record started",
  "data": {
    "record": {
      "pre_points": 200,
      "post_points": 200,
      "recording": true,
      "post_recording": false,
      "record_complete": false,
      "record_start_sequence": 6608,
      "record_end_sequence": null,
      "capture_start_sequence": 6508,
      "capture_end_sequence": null,
      "scan_active": false,
      "active_scan": null,
      "scans": []
    }
  },
  "record": {}
}
```

常见错误：

| HTTP | message | 说明 |
| --- | --- | --- |
| 400 | `Receive has not been started` | 还没有调用 `/startReceive` |
| 400 | `No raw data has been received` | 已开始接收，但还没有收到任何 raw 点 |

### 4.9 `POST /scan/start`

用途：在记录过程中开始一个扫描区间标记。

前置条件：

- 已经调用 `POST /record/start`。
- 当前仍处于 `recording = true`。
- 当前没有未结束的活动 scan。

请求体：无。

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "Scan started",
  "data": {
    "scan": {
      "index": 1,
      "start_time": "2026-05-25T10:30:10.000000+00:00",
      "end_time": null,
      "start_sequence": 6700,
      "end_sequence": null,
      "auto_closed": false
    },
    "record": {
      "recording": true,
      "scan_active": true,
      "active_scan": {
        "index": 1,
        "start_sequence": 6700
      },
      "scans": []
    }
  },
  "scan": {},
  "record": {}
}
```

返回字段：

| 字段 | 说明 |
| --- | --- |
| `scan.index` | 本次扫描编号，从 1 开始递增 |
| `scan.start_time` | 扫描开始时间，ISO 字符串 |
| `scan.start_sequence` | 扫描开始序号，通常为当前最新 raw 序号的下一个点 |
| `scan.end_time` / `scan.end_sequence` | 扫描未结束时为 `null` |

常见错误：

| HTTP | message | 说明 |
| --- | --- | --- |
| 400 | `Scan can only start while recording` | 未开始记录，或记录已经结束 |
| 400 | `A scan is already active` | 上一个 scan 还没有调用 `/scan/end` |

### 4.10 `POST /scan/end`

用途：结束当前活动扫描区间。

前置条件：存在活动 scan。

请求体：无。

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "Scan ended",
  "data": {
    "scan": {
      "index": 1,
      "start_time": "2026-05-25T10:30:10.000000+00:00",
      "end_time": "2026-05-25T10:30:35.000000+00:00",
      "start_sequence": 6700,
      "end_sequence": 7320,
      "auto_closed": false
    },
    "record": {
      "recording": true,
      "scan_active": false,
      "active_scan": null,
      "scans": [
        {
          "index": 1,
          "start_sequence": 6700,
          "end_sequence": 7320
        }
      ]
    }
  },
  "scan": {},
  "record": {}
}
```

常见错误：

| HTTP | message | 说明 |
| --- | --- | --- |
| 400 | `No active scan to stop` | 当前没有活动 scan |

### 4.11 `POST /record/end`

用途：结束用户选择的记录区间，并返回本次记录的离线滤波结果。

前置条件：已经调用过 `POST /record/start`。

处理行为：

- 如果当前仍在记录中，接口会先结束记录。
- 如果有活动 scan，会自动关闭该 scan，`auto_closed` 为 `true`。
- 后端会等待 end 后辅助点采集完成，最长等待约 10 秒。
- 离线滤波会使用包含 `pre`、`record`、`post` 的原始数据上下文。
- 返回体保持精简，不返回 `scan_indexes`、`capture_start_sequence`、`capture_end_sequence`；`filter_config` 返回实际滤波参数，防止前端回填为默认值。

请求体：无。

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "Record ended and offline filter completed",
  "data": [
    { "sequence": 6608, "value": 205.9, "segment": "record" },
    { "sequence": 6609, "value": 206.4, "segment": "record" }
  ],
  "raw_data": [
    {
      "sequence": 6508,
      "value": 210.4,
      "timestamp": "2026-05-25T10:30:00.000000+00:00",
      "segment": "pre"
    },
    {
      "sequence": 6608,
      "value": 212.1,
      "timestamp": "2026-05-25T10:30:02.000000+00:00",
      "segment": "record"
    }
  ],
  "peak": [
    { "sequence": 6720, "value": 246.1, "segment": "record" }
  ],
  "valley": [
    { "sequence": 6802, "value": 96.4, "segment": "record" }
  ],
  "metrics": {
    "bpm": 18.25,
    "quality": "stable",
    "breath_count": 6,
    "interval_cv": 0.08
  },
  "filter_status": "offline",
  "segments": {
    "pre": {
      "start_sequence": 6508,
      "end_sequence": 6607,
      "auxiliary": true
    },
    "record": {
      "start_sequence": 6608,
      "end_sequence": 8091,
      "auxiliary": false
    },
    "post": {
      "start_sequence": 8092,
      "end_sequence": 8191,
      "auxiliary": true
    }
  },
  "scans": [
    {
      "index": 1,
      "start_time": "2026-05-25T10:30:10.000000+00:00",
      "end_time": "2026-05-25T10:30:35.000000+00:00",
      "start_sequence": 6700,
      "end_sequence": 7320,
      "auto_closed": false
    }
  ],
  "record_start_sequence": 6608,
  "record_end_sequence": 8091,
  "record_time": {
    "start_time": "2026-05-25T10:30:02.000000+00:00",
    "end_time": "2026-05-25T10:30:50.000000+00:00",
    "duration_seconds": 48.0
  },
  "record_padding": {
    "pre_points": 200,
    "post_points": 200
  }
}
```

返回字段：

| 字段 | 说明 |
| --- | --- |
| `data` | 离线滤波后的点数组，结构接近 `/applyFilter`，但点为对象并带 `segment` |
| `raw_data` | 本次记录捕获的原始点，包含 `pre`、`record`、`post` |
| `peak` / `valley` | 离线重新识别出的波峰和波谷 |
| `metrics` | 离线计算出的 BPM 和稳定性指标 |
| `filter_status` | 离线滤波状态：`offline`、`too_short`、`no_data` |
| `segments.pre` | `record/start` 前辅助区间，`auxiliary = true` |
| `segments.record` | 用户真实选择的记录区间，`auxiliary = false` |
| `segments.post` | `record/end` 后辅助区间，`auxiliary = true` |
| `scans` | 本次记录中的扫描区间数组 |
| `record_start_sequence` / `record_end_sequence` | 用户真实记录范围 |
| `record_time` | 记录开始、结束时间和持续秒数 |
| `record_padding` | 当前配置的辅助点数量 |

`filter_status` 说明：

| 值 | 说明 |
| --- | --- |
| `offline` | 已完成离线滤波 |
| `too_short` | 数据短于滤波启动点数，无法产出有效离线滤波结果 |
| `no_data` | 没有可滤波的原始数据 |

常见错误：

| HTTP | message | 说明 |
| --- | --- | --- |
| 400 | `No recording has been started` | 尚未调用过 `/record/start` |
| 400 | `No record data is available` | 没有捕获到可用于本次记录的数据 |

### 4.12 `POST /record/reset`

用途：清空后端当前 record/scan 状态。

前置条件：无。

请求体：无。

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "Record reset",
  "data": {
    "record": {
      "recording": false,
      "post_recording": false,
      "record_complete": false,
      "record_start_sequence": null,
      "record_end_sequence": null,
      "capture_start_sequence": null,
      "capture_end_sequence": null,
      "scan_active": false,
      "active_scan": null,
      "scans": []
    }
  },
  "record": {}
}
```

说明：该接口不会停止传感器接收，只清理记录相关状态。Monitor 页面点击“重置”时应调用该接口，避免界面清空但后端仍保留旧扫描状态。

### 4.13 `POST /record/save`

用途：把当前记录写入 JSON 文件。

前置条件：

- 已调用 `POST /record/start`。
- 已调用 `POST /record/end`。
- end 后辅助点采集已经完成。
- 当前记录中存在 raw 或 filtered 数据。

请求体：可省略。

带 `X-RespiraScope-Session` 的云端会话请求会忽略 `folder_path`，由后端强制保存到：

```text
<record.storage_root>/<session-id>/
```

未携带 session 的旧客户端仍兼容 `folder_path`。省略或传 `{}` 时保存到旧默认目录 `D:/ct/breath-file`。

```json
{
  "folder_path": "D:/ct/breath-file"
}
```

成功返回：

```json
{
  "code": 1,
  "status": "success",
  "message": "ok",
  "data": {
    "file_path": "D:/ct/breath-file/session-a/breath_record_1779690000.json"
  }
}
```

常见错误：

| HTTP | message | 说明 |
| --- | --- | --- |
| 400 | `No recording has been started` | 尚未开始过记录 |
| 400 | `Recording has not ended` | 记录仍在进行 |
| 400 | `Recording is still collecting post-record padding` | 仍在采集 end 后辅助点 |
| 400 | `No record data is available to save` | 没有可保存的数据 |
| 400 | `Invalid record folder: ...` | 保存目录不可用或无法创建 |

### 4.14 `/mock/*` 模拟信号接口

只有配置启用模拟信号时才注册这些接口。

#### `GET /mock/scenarios`

返回可用场景：

```json
{
  "code": 1,
  "data": ["normal", "irregular", "apnea"]
}
```

#### `GET /mock/config`

返回当前模拟信号配置。

#### `POST /mock/config`

更新模拟信号配置。

请求体可只传需要修改的字段：

```json
{
  "scenario": "normal",
  "bpm": 18,
  "amplitude": 120,
  "baseline": 180,
  "noise": 5,
  "drift": 0,
  "irregularity": 0.1,
  "apnea_interval_sec": 0,
  "apnea_duration_sec": 0,
  "artifact_chance": 0.02,
  "artifact_amplitude": 250,
  "sample_interval_ms": 20
}
```

#### `POST /mock/preview`

生成一段模拟信号预览数据。

请求体：

```json
{
  "seconds": 30,
  "sampling_rate": 50,
  "scenario": "normal",
  "bpm": 18
}
```

成功返回：

```json
{
  "code": 1,
  "data": [[0, 180.0], [1, 183.2]],
  "config": {},
  "sampling_rate": 50
}
```

## 5. 数据结构说明

### 5.1 `FilterConfig`

`POST /startReceive`、`POST /setRTFilterParams`、`POST /applyFilter`、`POST /detectPeaks` 都会使用该配置。有效截止频率须满足 0 < 下限 < 上限 < 采样率 / 2；自定义上下限各为 0.01–20 Hz。非法配置返回 HTTP 422。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `low_bpm` | number | `6` | 低呼吸频率边界，后端会换算成滤波截止频率 |
| `high_bpm` | number | `40` | 高呼吸频率边界，后端会换算成滤波截止频率 |
| `processing_mode` | string | `time` | `time` 或 `amplitude` |
| `offline_filter` | string | `bandpass` | 原带通；`baseline_lowpass` 为保留基线低通，仅用于离线接口，实时接口返回 422 |
| `lowpass_order` | integer | `4` | 保留基线低通阶数，范围 1–5；不改变原带通 `order` |
| `bandpass_mode` | string | `preset` | `preset` 使用方式预设；`custom` 保留传入的截止频率 |
| `lowpass_cutoff` | number | `0.1` | 带通下限（Hz）；自定义时直接生效 |
| `highpass_cutoff` | number | `0.6667` | 带通上限或低通截止频率（Hz）；低通 preset 为 2 Hz，自定义时直接生效 |
| `order` | number | `1` | 滤波阶数 |
| `sampling_rate` | number | `50` | 采样率，影响 BPM 和峰谷间隔计算 |
| `gaussian_sigma` | number | `1` | 高斯平滑强度 |
| `min_peak_distance` | number | `15` | 峰谷之间的最小采样点距离 |
| `peak_threshold_ratio` | number | `0.3` | 自适应峰谷显著性比例 |
| `prominence` | number | `1` | 手动峰谷显著性参数 |
| `auto_peak_detection` | boolean | `true` | 是否启用自适应峰谷识别 |
| `confirm_realtime_events` | boolean | `false` | 是否启用短延迟确认峰谷；更稳，但实时峰谷会稍晚输出 |
| `confirmation_delay_points` | number | `12` | 短延迟确认等待的未来采样点数 |
| `data_gap_reset_points` | number | `25` | `sequence` 断开超过该点数时重置实时识别上下文 |
| `gap_warmup_points` | number | `75` | 断流恢复后等待多少点再输出峰谷 |
| `restore_baseline` | boolean | `true` | 滤波后是否恢复到原始基线附近 |

`baseline_lowpass` 不使用带通下限，也不执行带通基线偏置恢复；`restore_baseline` 返回 true，`processingQuality.baselines[].status` 返回 `preserved`（offset=0，cycles=0）。它保留输入的慢变化，包括可能的设备漂移。自定义低通只要求 0.01 Hz ≤ 上限 ≤ 20 Hz 且小于采样率的一半；下限字段保留用于切换回带通，但不约束低通上限。低通自适应峰谷阈值基于局部突出度，返回的峰谷值仍取自实际低通曲线。缺失 `offline_filter` 的旧文件和旧请求保持带通语义。分箱质量排除不因低通而取消。

### 5.2 `record` 状态

`GET /stream/status`、`POST /record/start`、`POST /scan/start`、`POST /scan/end`、`POST /record/reset` 会返回 record 状态。

| 字段 | 说明 |
| --- | --- |
| `pre_points` | start 前辅助点数量 |
| `post_points` | end 后辅助点数量 |
| `recording` | 是否正在记录用户选择区间 |
| `post_recording` | 是否正在采集 end 后辅助点 |
| `record_complete` | 当前记录是否已经完整结束 |
| `record_start_sequence` | 用户记录区间起点 |
| `record_end_sequence` | 用户记录区间终点 |
| `capture_start_sequence` | 内部捕获起点，包含 pre 辅助区间 |
| `capture_end_sequence` | 内部捕获终点，包含 post 辅助区间 |
| `scan_active` | 是否存在活动 scan |
| `active_scan` | 当前未结束 scan |
| `scans` | 已结束 scan 列表 |

### 5.3 `/record/end` 与保存文件的差异

`POST /record/end` 默认保持既有接口结构。新版页面发送 `Accept: application/vnd.respirascope.record.v6+json`，响应为 `{code,status,message,data}`，其中 `data` 直接使用下表右列的 JSON v6 结构，且 `Content-Type` 为该媒体类型；响应带 `Vary: Accept`。显式指定新媒体类型且其质量权重不低于 JSON 时才返回新格式；`q=0` 不会选择新格式。旧后端忽略此请求头时，页面继续兼容旧返回格式。`POST /record/save` 保存到磁盘的文件与界面下载均使用 JSON v6 精简格式；导入兼容旧版文件。

| 内容 | `/record/end` 返回 | v6 保存文件 |
| --- | --- | --- |
| 原始、滤波点 | `raw_data` / `data` | `raw` / `filtered`，`[序号, 幅值, 可选原有时间戳]` |
| 峰谷 | `peak` / `valley` | `peaks` / `valleys`，`{sequence,value}`，仅超界附加 `amplitudeRange` |
| 记录范围 | `record_start_sequence` / `record_end_sequence` | `startSeq` / `endSeq` |
| 记录时间 | `record_time` | `startTime` / `endTime`，ISO 8601 |
| 扫描范围 | `scans`，snake_case 字段 | `scans`，`index/startSeq/endSeq/startTime/endTime`；仅自动结束时添加 `autoClosed: true` |
| 滤波参数和状态 | `filter_config` / `filter_status` | `filterConfig` / `filterStatus`；两种分箱共用一份参数 |
| 分箱 | 接口提供的分析结果 | `analysis` 保存方式、上下限与 `totalBins`，`binningData` v4 包含 `inhaleRising`、`bins.inhale/exhale`、按分类保存的 `excluded/unassigned` 区间数组；各区间索引对应完整 filtered 数组，每方向 N = totalBins / 2 箱 |
| 离线质量 | `processingQuality` | 原样保留无效区间、基线估计状态与偏移量；旧文件可缺省 |
| 摘要和逐点标签 | `metrics`、`segments` 等 | 不保存，通过序号和记录/扫描范围推算 |

`raw` 和 `filtered` 包含前后缓冲点，`startSeq` 至 `endSeq`（含端点）才是用户真实记录范围。分箱区间使用 `[start,end)`，只覆盖真实记录范围。固定幅值分箱的边界为 `lower + i * (upper - lower) / N`（`i=0..N`，`N=totalBins/2`），未到达的箱不写区间。波形和时间只保存一份。分箱不再依赖前后半组的隐含方向；仅区分有效、排除、无法分箱；有效数据在 `bins` 中，后两类分别使用区间数组，不携带原因。同类相邻或重叠区间已合并，不同分类互不重叠。子协议字段示例见 [分箱数据明细](../development/architecture-zh.md#分箱数据明细与精简存储)。

原有时间戳保留；缺失的点时间戳不补造。固定幅值峰谷高于上限时附加 `amplitudeRange: "above"`，低于下限时为 `"below"`；界内或非固定幅值不添加此字段。

旧文件中的模式差异配置不再用于切换；新文件仅保留当前公共 `filterConfig`。更完整的字段说明见 [README 数据记录](../../README.md#数据记录)。

`/applyFilter`、`/record/end` 和新保存的离线记录提供以下可选扩展，仍兼容 v6：

```json
{
  "processingQuality": {
    "version": 2,
    "invalidIntervals": [{"start": 4500, "end": 4503, "reason": "spike"}],
    "baselines": [{"start": 0, "end": 9000, "status": "estimated", "cycles": 36, "offset": 180.1}]
  }
}
```

区间以原始采样序号表示，使用 `[start,end)`，覆盖完整输入（包括缓冲）；重叠区间取并集。`reason` 可为 `spike`（插值尖峰）、`motion`（持续伪影/跳变）、`filter_edge`（滤波影响边缘）、`gap`（缺失数据）、`too_short`（片段不足）。这些区间及跨过它们的半周期不能参与分箱；质量元数据 v2 的 `motion`、`too_short` 结果是同一连续采集段计算的滤波参考值，界面以虚线显示，不参与峰谷、边界估计或分箱。参考处理使用相同带通与平滑参数、同一段基线偏移，不跨数据缺口。已局部界定且不超过 1 秒的短暂伪影在工作副本中桥接后连续滤波，避免把正常呼吸切成过短片段；参考值仍按未桥接输入计算，伪影及局部滤波影响区间均不参与分箱。持续偏移、长体动及缺口仍分段处理。v1 在这些区间保存的是原始占位值，导入后仍隐藏，重新计算才生成 v2 参考值。原始数据不被插值覆盖。

`baselines` 每项对应一个无数据缺口的采集段。`status` 为 `estimated` / `insufficient_cycles` / `disabled`；`cycles` 是用于评估基线的周期数，`offset` 是实际加回的常量（禁用时省略）。`insufficient_cycles` 使用中位数回退，不表示基线已经可靠校正。

只重判峰谷时，调用 `/detectPeaks` 需将上述 `invalidIntervals` 原样放入请求的 `invalid_intervals` 字段。省略该字段兼容旧调用；新页面会自动传递，以免把伪影重新识别为峰谷。反向、负值或非有限区间会被拒绝。导入时保留质量信息，缺省代表旧文件；存在但格式非法时拒绝导入，不静默丢弃掩码。

### 5.4 区间字段

| 区间 | 说明 | `auxiliary` |
| --- | --- | --- |
| `pre` | `record/start` 前的辅助数据，用于给离线滤波提供上下文 | `true` |
| `record` | 用户真实选择的记录区间 | `false` |
| `post` | `record/end` 后的辅助数据，用于给离线滤波提供上下文 | `true` |

`auxiliary = true` 只表示该区间是辅助上下文，不表示无效数据。

## 6. 传感器输入数据

这是后端连接真实呼吸传感器或模拟传感器时使用的底层输入格式。外部系统通常只消费 HTTP 和 Socket.IO 输出，不需要直接处理该格式。

### 6.1 连接方式

| 项 | 说明 |
| --- | --- |
| 协议 | TCP |
| 地址 | 配置文件中的 `[sensor].host` |
| 端口 | 配置文件中的 `[sensor].port` |
| 后端角色 | TCP client，主动连接传感器 TCP server |

### 6.2 单个采样包

后端每次读取 4 字节，并只使用第 3、4 字节计算呼吸原始值。

```text
byte[0]  byte[1]  byte[2]  byte[3]
unused   unused   high     low
```

计算方式：

```text
sensor_value = byte[2] * 256 + byte[3]
```

映射到实时输出：

```json
{
  "type": "raw",
  "data": [[1024, 188.42]]
}
```

## 7. 常见错误速查

| 接口 | message | 原因 | 建议处理 |
| --- | --- | --- | --- |
| `/record/start` | `Receive has not been started` | 未启动接收 | 先调用 `/startReceive` |
| `/record/start` | `No raw data has been received` | 已启动接收但还没收到 raw 点 | 等待 Socket.IO `raw` 或检查 `/stream/status` |
| `/scan/start` | `Scan can only start while recording` | 未处于记录中 | 先调用 `/record/start` |
| `/scan/start` | `A scan is already active` | 已有未结束 scan | 先调用 `/scan/end` |
| `/scan/end` | `No active scan to stop` | 当前没有活动 scan | 忽略或检查按钮状态 |
| `/record/end` | `No recording has been started` | 未开始记录 | 先调用 `/record/start` |
| `/record/end` | `No record data is available` | 没有记录到数据 | 检查接收状态和传感器数据 |
| `/record/save` | `Recording has not ended` | 记录仍在进行 | 先调用 `/record/end` |
| `/record/save` | `Recording is still collecting post-record padding` | post 辅助点还没采完 | 稍后重试 |
| `/record/save` | `No record data is available to save` | 没有可保存数据 | 重新记录 |
| `/record/save` | `Invalid record folder: ...` | 保存目录不可用 | 更换或创建可写目录 |

## 8. 最小调用示例

### 8.1 启动实时接收

```bash
curl -X POST http://127.0.0.1:8000/startReceive \
  -H "Content-Type: application/json" \
  -d '{"low_bpm":6,"high_bpm":40,"sampling_rate":50}'
```

### 8.2 开始记录

```bash
curl -X POST http://127.0.0.1:8000/record/start
```

### 8.3 标记一次扫描

```bash
curl -X POST http://127.0.0.1:8000/scan/start
curl -X POST http://127.0.0.1:8000/scan/end
```

### 8.4 结束记录并获取离线滤波结果

```bash
curl -X POST http://127.0.0.1:8000/record/end
```

### 8.5 保存记录

```bash
curl -X POST http://127.0.0.1:8000/record/save \
  -H "Content-Type: application/json" \
  -H "X-RespiraScope-Session: session-a" \
  -d '{"folder_path":"D:/ct/breath-file"}'
```

带 session 时，示例中的 `folder_path` 会被忽略，记录保存到服务端配置的 session 临时目录。

### 离线峰谷重识别 `POST /detectPeaks`

请求体为 `{ "filter_config": { "peak_threshold_ratio": 0.15, "auto_peak_detection": true }, "filtered_data": [[sequence, value], ...] }`。使用已有滤波数据重新识别峰谷，返回标准成功结构及顶层 `peak`、`valley`、`metrics`。不再滤波、不返回替换曲线，也不修改实时处理器。数据格式为严格的二元数值点对；缺口按 `data_gap_reset_points` 分段识别。

离线界面的保守、标准、灵敏分别对应比例 0.45、0.30、0.15。保存文件的 `filterConfig` 记录已应用设置；切换时间／幅值只重新计算分箱，沿用当前滤波参数和结果，不恢复另一套参数。

### 接口数据校验与传输

`/applyFilter.raw_data` 和 `/detectPeaks.filtered_data` 均为二元数值点对 `[sequence,value]`：序号是非负整数，必须严格递增，允许缺口，不允许重复或倒序；幅值必须是有限数值。空输入合法；数据过短时 `/applyFilter.data` 返回空数组，避免数组和对象混用。

校验失败返回 HTTP 422，`detail` 数组只保留 `loc`、`msg`、`type`，不回传整段输入波形或无法用 JSON 表示的数值。页面显示字段路径及原因，保留已提交结果和待应用设置。

支持 gzip 的客户端可通过 `Accept-Encoding: gzip` 协商压缩，大于 1024 字节的 HTTP 响应启用压缩；Socket.IO 数据协议不变。新版紧凑记录只保存一次波形与分箱，保留已有时间戳和实际滤波参数；统计摘要及逐点区间标签可由范围信息推导。

`analysis.totalBins` 可选 4、6、8、10、12、16、20，默认 10；吸气和呼气各占一半。保存接口对其他数量返回 422，旧文件缺少该字段时按 10 箱导入。


记录缓冲：`/runtime/config` 的 `record.pre_points` / `post_points` 返回两种分箱共用的前后缓冲，默认各 200 点（50 Hz 下各 4 秒）。前端运行配置对应 `record.prePoints` / `postPoints`，不再提供按分箱模式拆分的重复缓冲字段。配置修改后重启生效，不按滤波参数自动扩大；数据不足时使用已有部分。

`POST /applyFilter` 可额外提供 `record_start_sequence`、`record_end_sequence`（闭区间，非负整数，必须同时提供，起点不大于终点）。提供时按公共前后缓冲配置从 `raw_data` 中取对应范围；省略时仍处理完整输入，保持预览和旧调用兼容。记录页面切换/重新滤波发送这两个字段；原始数据保留完整采集上下文，返回滤波数据仅包含本次实际使用范围。`POST /record/end` 与 `/record/save` 使用相同的公共缓冲规则。

`/record/end` 收满后缓冲后返回，等待上限为剩余采样时长加 8 秒，请调用方相应设置 HTTP 超时；数据不足时使用已收到的部分。记录范围不包含前后缓冲。
