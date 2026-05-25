# 呼吸信号滤波与波峰波谷识别说明

本文说明当前项目里呼吸原始数据从传感器进入后，如何被实时滤波、标记波峰波谷，并计算 BPM 和呼吸稳定性。相关代码主要在：

- `src/ct_breath/breath_process/data_receive.py`
- `src/ct_breath/breath_process/signal_processor.py`
- `src/ct_breath/breath_process/peak_valley_detector.py`
- `src/ct_breath/http/http_service.py`

## 数据流程

1. `AsyncSocketClient` 连接呼吸传感器 TCP 地址，按 4 字节读取一帧数据。
2. `DataReceiver` 给每个数据点分配递增的 `sequence_number`。
3. 原始数据进入 `DataQueueManager.raw_data_queue`，再通过 Socket.IO 推送给 Monitor 前端。
4. 同一份原始数据进入 `SignalProcessor`，做滑动窗口实时滤波。
5. 滤波后的数据进入 `PeakValleyDetector`，识别波峰、波谷，并计算 BPM、稳定性。
6. raw、filtered、peak、valley、metrics 会分批推送到 Monitor 页面。

## 实时滤波

实时滤波在 `SignalProcessor.process_sliding_window()` 中完成。默认参数：

- `window_size = 2000`：保留最近 2000 个点作为上下文。
- `step_size = 5`：每次处理 5 个新点，降低前端等待感。
- `FILTER_STARTUP_DELAY = 300`：至少积累 300 个点后才开始滤波，避免数据太短导致滤波不稳定。

滤波步骤在 `apply_filters()`：

1. Butterworth 带通滤波。
2. 可选恢复基线 `restore_baseline`。
3. Gaussian 平滑。
4. 输出四舍五入到 1 位小数的滤波结果。

实时模式调用：

```python
butterworth_filter(..., rt=True)
```

这会使用 `scipy.signal.sosfilt`。它适合实时流式处理，但会有一定相位延迟，也就是说波峰波谷的位置可能略微滞后于真实信号。

## 离线滤波

Monitor 点击 `Record End` 后，会调用后端 `/record/end`。后端结束记录、等待 end 后辅助点采集完成，然后对本次记录的原始数据重新做一次离线滤波并返回结果。`/applyFilter` 仍保留给外部系统复算任意历史 raw_data 使用。

离线模式调用：

```python
butterworth_filter(..., rt=False)
```

这会使用 `scipy.signal.sosfiltfilt`。它是零相位双向滤波，不适合实时流式数据，但更适合记录结束后的复盘分析，波形会更平滑，波峰波谷位置也更可靠。

所以当前设计是：

- 实时页面：优先低延迟，允许轻微滞后。
- 记录复盘：优先波形质量和识别准确性。

## 关键滤波参数

前端传给后端的核心参数在 `FilterConfig` 中：

- `sampling_rate`：采样率，默认 50 Hz。
- `low_bpm`：最低有效呼吸频率，默认 6 次/分钟。
- `high_bpm`：最高有效呼吸频率，默认 40 次/分钟。
- `order`：Butterworth 滤波器阶数，阶数越高越陡，但也越容易引入振铃。
- `gaussian_sigma`：高斯平滑强度，越大越平滑，但细节越容易被抹掉。
- `restore_baseline`：是否把滤波后的信号加回原始中位数基线。

项目会把 BPM 转换成 Hz 作为带通滤波截止频率：

```text
lowpass_cutoff = low_bpm / 60
highpass_cutoff = high_bpm / 60
```

这里字段名沿用了旧接口，实际传入 Butterworth 时表示 `[低频截止, 高频截止]` 的带通范围。

## 波峰波谷识别

波峰波谷识别使用 `scipy.signal.find_peaks`：

- 找波峰：对滤波数据直接调用 `find_peaks(data)`。
- 找波谷：对负信号调用 `find_peaks(-data)`。

识别时主要受三个条件影响：

- `distance`：两次峰值之间的最小距离。
- `prominence`：峰值相对周围信号的突出程度。
- `peak_threshold_ratio`：自动阈值比例，用于根据当前信号幅度自适应计算 prominence。

当 `auto_peak_detection = true` 时，系统会根据 `high_bpm` 推导最小间隔：

```text
最短呼吸周期秒数 = 60 / high_bpm
最小峰间距点数 = sampling_rate * 最短呼吸周期秒数 * 0.65
```

然后根据当前窗口的信号跨度和噪声估计 prominence：

```text
adaptive_prominence = max(0.5, 信号跨度 * peak_threshold_ratio, 相邻差分噪声 * 3)
```

## 为什么可能出现连续波峰或连续波谷

理论上，一个干净的呼吸周期应当是“波峰、波谷、波峰、波谷”交替出现。连续两个波峰或连续两个波谷通常不理想，常见原因有：

- 信号噪声较大，局部抖动被识别为多个峰。
- 平滑不够，滤波后曲线还有毛刺。
- `prominence` 太低，导致小起伏也被当作峰。
- `high_bpm` 设置过高，使最小峰间距太短。
- 患者真实呼吸不稳定，例如屏气、浅呼吸、咳嗽、体动。

当前 `PeakValleyDetector` 已经做了两个保护：

- 同类型事件连续出现时，实时模式会忽略后一个。
- 离线模式会通过 `_collapse_alternating_events()` 折叠连续同类型事件，只保留更强的那个。

后续如果要继续提高稳定性，可以增加“候选峰延迟确认”机制：实时检测到峰后先不立即发出，等待一小段数据确认它仍是局部最强点，再推送给前端。

## BPM 和稳定性

BPM 由最近若干个波峰之间的间隔计算：

```text
间隔秒数 = 相邻波峰 sequence 差值 / sampling_rate
BPM = 60 / 平均间隔秒数
```

稳定性使用波峰间隔的变异系数 `interval_cv`：

```text
interval_cv = 标准差 / 平均值
```

当前分级：

- `< 0.15`：stable
- `< 0.35`：variable
- `>= 0.35`：irregular
- 波峰不足：insufficient

## 无数据状态

如果没有启动模拟器，也没有真实传感器连接，后端不会产生 raw 数据。现在后端提供：

```text
GET /stream/status
```

该接口会返回：

- 后端是否已经调用 `startReceive`。
- 传感器 socket 是否连接。
- 最近一次收到数据的时间。
- 累计收到的数据量。
- 最近连接错误。

Monitor 页面点击 Start 后，会先进入 `Waiting for Data`。如果几秒内没有收到 raw 数据，会根据 `/stream/status` 提示：

- `Start Failed: Sensor Not Connected`
- `Start Failed: No Breath Data`
- `No Recent Breath Data`

## 推荐调参思路

如果波形太抖：

- 增大 `gaussian_sigma`，例如从 1.8 调到 2.2 或 2.8。
- 增大 `peak_threshold_ratio`，例如从 0.30 调到 0.35。
- 适当降低 `high_bpm`，避免把很近的小抖动识别成多个呼吸周期。

如果波峰漏检：

- 降低 `peak_threshold_ratio`。
- 降低 `prominence`。
- 检查 `low_bpm` 和 `high_bpm` 是否覆盖真实呼吸范围。

如果实时波峰位置看起来滞后：

- 这是实时因果滤波的正常现象。
- Record End 后的离线结果会更接近真实位置。
- 若必须实时更准，可以考虑引入短延迟窗口确认，牺牲 200 到 500 ms 的实时性换取更稳定标记。

当前 Monitor 页面提供 `Confirm Peaks` 开关。选中后会启用
`confirm_realtime_events`，后端在实时推送波峰/波谷前等待
`confirmation_delay_points` 个采样点确认候选峰仍然成立。默认延迟是 12 个点，
在 50 Hz 采样率下约 240 ms；离线 `/applyFilter` 不受这个开关影响。

## 后续代码优化建议

1. 把 `frontend-monitor/app.js` 拆分为 socket、chart、record、status 四个模块，后续维护会轻很多。
2. 给 `SignalProcessor`、`PeakValleyDetector` 增加单元测试，覆盖稳定呼吸、浅呼吸、屏气、体动噪声、突然断流。
3. 把实时滤波和离线滤波抽成明确的两个策略类，避免以后参数越来越多时互相影响。
4. 把后端运行状态整理为 Pydantic schema，`/stream/status` 的返回结构会更稳定。
5. 把旧文件里的乱码注释统一清理为中文或英文，减少后续阅读成本。
