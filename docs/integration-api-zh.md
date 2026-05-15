# 呼吸系统对外接口说明

本文只描述新系统集成时需要关心的对外字段、调用流程和传感器输入数据格式。

## 1. 接入流程

1. 新系统调用 `GET /health` 或 `GET /stream/status`，确认后端是否运行、是否连接到传感器、是否已有数据。
2. 新系统调用 `POST /startReceive`，传入滤波配置，后端开始从传感器接收数据并实时处理。
3. 新系统通过 Socket.IO 连接 `/breath` 命名空间，监听 `breath` 事件。
4. 新系统根据 `type` 处理实时数据：`raw`、`filtered`、`peak`、`valley`、`metrics`。
5. 如果需要录制一段数据，依次调用 `POST /record/start`、`POST /record/end`、`POST /record/save`。
6. 如果需要对一段历史原始数据重新滤波，调用 `POST /applyFilter`。

## 2. 后端对外实时数据

- 协议：Socket.IO
- 命名空间：`/breath`
- 事件名：`breath`
- 连接示例：`http://127.0.0.1:8000/breath`

统一消息结构：

```json
{
  "type": "raw",
  "data": [[1024, 188.42], [1025, 189.1]]
}
```

字段说明：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 消息类型：`raw`、`filtered`、`peak`、`valley`、`metrics` |
| `data` | array | 当前批次的数据。后端默认约 40ms 推送一次，单次可能包含多个点 |

### `raw`

原始呼吸数据，来自传感器输入。

```json
{
  "type": "raw",
  "data": [[1024, 188.42]]
}
```

| 位置 | 字段 | 说明 |
| --- | --- | --- |
| `[0]` | `sequence` | 后端生成的递增采样序号 |
| `[1]` | `value` | 原始呼吸信号值 |

### `filtered`

实时滤波后的呼吸数据，和 `raw` 使用同一条 `sequence` 轴。

```json
{
  "type": "filtered",
  "data": [[1024, 187.63]]
}
```

| 位置 | 字段 | 说明 |
| --- | --- | --- |
| `[0]` | `sequence` | 对应原始数据序号 |
| `[1]` | `value` | 滤波后的呼吸信号值 |

### `peak` / `valley`

实时识别出的波峰和波谷。

```json
{
  "type": "peak",
  "data": [[1088, 246.19]]
}
```

| 位置 | 字段 | 说明 |
| --- | --- | --- |
| `[0]` | `sequence` | 波峰或波谷所在采样序号 |
| `[1]` | `value` | 波峰或波谷的滤波值 |

### `metrics`

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
| `bpm` | number \| null | 当前计算出的呼吸频率，单位：次/分钟 |
| `quality` | string | `insufficient`、`stable`、`variable`、`irregular` |
| `breath_count` | number | 当前窗口内参与计算的波峰数量 |
| `interval_cv` | number \| null | 波峰间隔变异系数，越低表示节律越稳定 |

`sequence` 是判断波形连续性的主键。如果 `sequence` 出现明显跳跃，外部系统应认为中间发生过断流或丢包，不建议把缺口两端直接连线。

## 3. HTTP 流程接口

### `GET /health`

用于启动前检查。

返回关键字段：

| 字段 | 说明 |
| --- | --- |
| `status` | `healthy` 表示后端已启动 |
| `sensor.host` | 后端尝试连接的传感器 IP |
| `sensor.port` | 后端尝试连接的传感器端口 |
| `mock_signal_enabled` | 是否使用内置模拟信号 |

### `GET /stream/status`

用于检查实时采集状态。

返回关键字段：

| 字段 | 说明 |
| --- | --- |
| `data.started` | 是否已经调用过 `startReceive` |
| `data.receiver.sequence_number` | 后端当前采样序号 |
| `data.receiver.received_count` | 后端已接收的采样点数量 |
| `data.receiver.seconds_since_last_data` | 距离上一次收到数据的秒数。为 `null` 表示还没有收到过数据 |
| `data.receiver.socket.connected` | 是否已连接到传感器 TCP 服务 |
| `data.receiver.socket.last_error` | 最近一次传感器连接或接收错误 |
| `data.record.recording` | 是否处于用户选中的记录区间 |
| `data.record.post_recording` | 是否正在记录 end 后冗余数据 |
| `data.record.record_complete` | 记录是否已经完成 |

### `POST /startReceive`

启动接收和实时滤波。

请求体可以省略；省略或传 `{}` 时使用系统默认参数。

请求体：

```json
{
  "low_bpm": 6,
  "high_bpm": 40,
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

请求字段说明：

| 字段 | 说明 |
| --- | --- |
| `low_bpm` | 低呼吸频率边界，后端会换算成滤波截止频率 |
| `high_bpm` | 高呼吸频率边界，后端会换算成滤波截止频率 |
| `sampling_rate` | 采样率，影响 BPM 和峰谷间隔计算 |
| `moving_avg_window` | 移动平均窗口 |
| `gaussian_sigma` | 平滑强度 |
| `min_peak_distance` | 峰谷最小采样点距离 |
| `peak_threshold_ratio` | 自适应峰谷显著性比例 |
| `prominence` | 手动峰谷显著性参数 |
| `auto_peak_detection` | 是否启用自适应峰谷识别 |
| `confirm_realtime_events` | 是否启用短延迟窗口确认峰谷。更准，但峰谷输出会稍晚 |
| `confirmation_delay_points` | 短延迟确认等待的未来采样点数 |
| `data_gap_reset_points` | `sequence` 断开超过该点数时重置实时识别上下文 |
| `gap_warmup_points` | 断流恢复后等待多少点再输出峰谷 |
| `restore_baseline` | 滤波后是否恢复到原始基线附近 |

### `POST /setRTFilterParams`

更新实时滤波参数。请求体同 `POST /startReceive`。

请求体可以省略；省略或传 `{}` 时使用系统默认参数。

### `POST /applyFilter`

对历史原始数据做离线滤波。

请求体可以省略；省略或传 `{}` 时使用默认滤波参数和空 `raw_data`，返回空结果。

请求体：

```json
{
  "filter_config": {
  "low_bpm": 6,
  "high_bpm": 40,
    "sampling_rate": 50
  },
  "raw_data": [[1024, 188.42], [1025, 189.1]]
}
```

返回关键字段：

| 字段 | 说明 |
| --- | --- |
| `data` | 离线滤波结果，格式为 `[[sequence, value], ...]` |
| `peak` | 离线识别波峰，格式为 `[{ sequence, value }, ...]` |
| `valley` | 离线识别波谷，格式为 `[{ sequence, value }, ...]` |
| `metrics` | 离线计算出的 BPM 和稳定性指标 |

## 4. 录制数据

### 录制流程

1. `POST /record/start`：开始记录。
2. `POST /record/end`：结束用户选中的记录区间。
3. `POST /record/save`：保存文件。

`POST /record/save` 请求体：

请求体可以省略；省略或传 `{}` 时默认保存到 `D:/ct/breath-file`。

```json
{
  "folder_path": "D:/ct/breath-file"
}
```

返回关键字段：

| 字段 | 说明 |
| --- | --- |
| `data.file_path` | 保存后的 JSON 文件路径 |

### 录制文件字段

```json
{
  "version": 2,
  "record_start_sequence": 1224,
  "record_end_sequence": 2547,
  "capture_start_sequence": 1124,
  "capture_end_sequence": 2647,
  "segments": {
    "pre": { "start_sequence": 1124, "end_sequence": 1223, "redundant": true },
    "record": { "start_sequence": 1224, "end_sequence": 2547, "redundant": false },
    "post": { "start_sequence": 2548, "end_sequence": 2647, "redundant": true }
  },
  "raw_data": [
    { "sequence": 1224, "value": 210.4, "timestamp": 1778482500.1, "segment": "record" }
  ],
  "filtered_data": [
    { "sequence": 1224, "value": 205.9, "timestamp": 1778482500.1, "segment": "record" }
  ],
  "peak": [
    { "sequence": 1302, "value": 246.1, "segment": "record" }
  ],
  "valley": [
    { "sequence": 1376, "value": 91.2, "segment": "record" }
  ]
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `record_start_sequence` / `record_end_sequence` | 用户点击 start 到 end 的真实记录范围 |
| `capture_start_sequence` / `capture_end_sequence` | 实际保存范围，包含 start 前和 end 后冗余点 |
| `segments.pre` | start 前冗余数据 |
| `segments.record` | 用户真正选择的数据 |
| `segments.post` | end 后冗余数据 |
| `raw_data` | 原始数据点数组 |
| `filtered_data` | 滤波后数据点数组 |
| `peak` | 波峰点数组 |
| `valley` | 波谷点数组 |
| `segment` | 单个点所属区间：`pre`、`record`、`post` |

## 5. 传感器输入数据

这是后端连接真实呼吸传感器或模拟传感器时使用的输入格式，和新系统订阅的 Socket.IO 输出是两层数据。

### 连接方式

- 协议：TCP
- 地址：配置文件中的 `[sensor].host`
- 端口：配置文件中的 `[sensor].port`
- 后端角色：TCP client，主动连接传感器 TCP server

### 单个采样包

后端每次读取 4 字节，并只使用第 3、4 字节计算呼吸原始值。

```text
byte[0]  byte[1]  byte[2]  byte[3]
unused   unused   high     low
```

计算方式：

```text
sensor_value = byte[2] * 256 + byte[3]
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `byte[2]` | 原始值高字节 |
| `byte[3]` | 原始值低字节 |
| `sensor_value` | 0-65535 的无符号整数，作为后端 `raw.value` |

后端收到每个 `sensor_value` 后，会自动生成递增 `sequence`，再输出到 Socket.IO 的 `raw` 消息中：

```json
{
  "type": "raw",
  "data": [[1024, 188]]
}
```
