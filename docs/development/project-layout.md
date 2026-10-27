# 项目结构与依赖约定

RespiraScope 使用 Python `src` 布局，通过 uv 管理依赖、启动和测试。浏览器界面作为包资源随应用分发，无需单独安装或构建前端。

## Python 模块

以下路径均相对于 `src/ct_breath/`。

| 目录 | 职责 |
| --- | --- |
| `core/` | 配置、日志、时间和会话标识等公共设施 |
| `models/` | 滤波、记录、模拟和运行状态的数据校验模型 |
| `acquisition/` | TCP 连接、设备数据接收、模拟传感器 |
| `processing/` | 滤波策略、缓冲、峰谷和质量判断 |
| `binning/` | 时间／幅值分箱、连续区间与紧凑数据结构 |
| `recording/` | 记录生命周期、保存与读取 |
| `streaming/` | 实时数据队列和推送 |
| `application/` | 采集、处理、记录等服务的编排和会话管理 |
| `api/` | HTTP 和 Socket.IO 请求适配 |
| `runtime/` | 端口、浏览器／桌面窗口、静态资源定位和服务 |

`main.py` 为命令行入口，`app.py` 创建应用，`asgi.py` 用于 ASGI 部署，`__main__.py` 支持 `python -m ct_breath`。保持这些入口稳定，内部实现按职责归入对应目录。

共享模型不导入接口或启动模块；`processing/` 和 `binning/` 不依赖 `api/`、`application/` 或 `runtime/`。接口调用应用服务，算法可在测试和报告脚本中独立复用。跨模块导入统一使用 `ct_breath.*`，不使用 `src.ct_breath`。

## 界面与资源

`web/console/` 为统一入口；`monitor/`、`lab/` 分别提供监测与模拟界面，`guide/`、`api-docs/` 提供说明页面。公共代码和样式放在 `shared/`，图标放在 `assets/`，第三方库放在 `vendor/`。

源码、wheel 和 PyInstaller 使用同一棵 `web/` 资源树，由 `runtime/resources.py` 定位。运行目录不影响资源解析；打包时无需额外复制另一份前端。外部配置和呼吸记录仍使用运行配置指定的目录，不写入安装包。

## 测试、工具与文档

- `tests/unit/`：算法和独立组件；`integration/`：服务、接口、记录和启动；`ui/`：浏览器交互。
- `tests/fixtures/`：固定样本；`support/`：可复用测试辅助函数。测试之间不互相导入。
- `scripts/dev.py`、`dev.ps1`：开发启动；`packaging/`：桌面构建；`reports/`：测算、绘图及报告生成。
- `docs/` 按开发、接口、部署、技术说明和报告归档，入口为[文档索引](../README.md)。

从仓库根目录运行：

```bash
uv run respirascope
uv run pytest tests/unit tests/integration
uv run --group ui-test pytest tests/ui
uv build --wheel
uv run --frozen python -m scripts.reports.compare_shared_binning
uv run --frozen python -m scripts.reports.plot_shared_binning
```

Windows 和 macOS 构建入口分别为 `scripts/packaging/build-exe.bat` 和 `scripts/packaging/build-macos-app.sh`，详见[脚本说明](../../scripts/README.md)。
