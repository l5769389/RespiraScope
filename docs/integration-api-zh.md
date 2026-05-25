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
      "pre_points": 100,
      "post_points": 100,
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
  "moving_avg_window": 3,
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
      "moving_avg_window": 3,
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

- `lowpass_cutoff` 和 `highpass_cutoff` 会由 `low_bpm`、`high_bpm` 换算并规范化。
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
    "moving_avg_window": 3,
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
      "pre_points": 100,
      "post_points": 100,
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
- 返回体保持精简，不返回 `scan_indexes`、`filter_config`、`capture_start_sequence`、`capture_end_sequence`。

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
    "pre_points": 100,
    "post_points": 100
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

请求体：可省略。省略或传 `{}` 时保存到默认目录 `D:/ct/breath-file`。

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
    "file_path": "D:/ct/breath-file/breath_record_1779690000.json"
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

`POST /startReceive`、`POST /setRTFilterParams`、`POST /applyFilter` 都会使用该配置。

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `low_bpm` | number | `6` | 低呼吸频率边界，后端会换算成滤波截止频率 |
| `high_bpm` | number | `40` | 高呼吸频率边界，后端会换算成滤波截止频率 |
| `lowpass_cutoff` | number | `0.1` | 由 `low_bpm / 60` 规范化；外部系统通常无需直接传 |
| `highpass_cutoff` | number | `0.6667` | 由 `high_bpm / 60` 规范化；外部系统通常无需直接传 |
| `order` | number | `1` | 滤波阶数 |
| `sampling_rate` | number | `50` | 采样率，影响 BPM 和峰谷间隔计算 |
| `moving_avg_window` | number | `3` | 移动平均窗口 |
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

`POST /record/end` 返回给外部系统的是精简结果，便于前端直接展示和业务系统直接消费。

| 字段 | `/record/end` 返回 | 保存文件返回 |
| --- | --- | --- |
| `data` / `filtered_data` | `data`，离线滤波点 | `filtered_data` |
| `raw_data` | 有 | 有 |
| `peak` / `valley` | 有 | 有 |
| `metrics` | 有 | 有 |
| `segments` | 有，包含 `auxiliary` | 有，包含 `auxiliary` |
| `scans` | 有 | 有 |
| `scan_indexes` | 不返回 | 每个点会保存 |
| `filter_config` / `filter_params` | 不返回 | 保存为 `filter_params` |
| `capture_start_sequence` / `capture_end_sequence` | 不返回 | 保存 |

保存文件示例：

```json
{
  "version": 2,
  "record_time": {
    "start_time": "2026-05-25T10:30:02.000000+00:00",
    "end_time": "2026-05-25T10:30:50.000000+00:00",
    "duration_seconds": 48.0
  },
  "record_start_sequence": 6608,
  "record_end_sequence": 8091,
  "capture_start_sequence": 6508,
  "capture_end_sequence": 8191,
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
  "raw_data": [
    {
      "sequence": 6608,
      "value": 212.1,
      "timestamp": "2026-05-25T10:30:02.000000+00:00",
      "segment": "record",
      "scan_indexes": []
    }
  ],
  "filtered_data": [
    {
      "sequence": 6608,
      "value": 205.9,
      "timestamp": "2026-05-25T10:30:02.000000+00:00",
      "segment": "record",
      "scan_indexes": []
    }
  ],
  "filter_params": {},
  "filter_status": "live",
  "peak": [
    {
      "sequence": 6720,
      "value": 246.1,
      "segment": "record",
      "scan_indexes": [1]
    }
  ],
  "valley": [
    {
      "sequence": 6802,
      "value": 96.4,
      "segment": "record",
      "scan_indexes": [1]
    }
  ],
  "metrics": {}
}
```

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
  -d '{"folder_path":"D:/ct/breath-file"}'
```
