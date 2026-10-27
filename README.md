<div align="center">
  <img src="src/ct_breath/web/assets/logo.svg" width="80" height="80" alt="RespiraScope" />
  <h1>RespiraScope</h1>
  <p>呼吸信号采集 · 波形分析 · 呼吸分箱</p>
  <p>
    <a href="#快速启动">快速启动</a> ·
    <a href="docs/README.md">文档</a> ·
    <a href="docs/demos/README.md">操作演示</a> ·
    <a href="docs/reports/时间分箱与固定幅值分箱波形对比.pdf">对比报告</a>
  </p>
</div>

RespiraScope 用于呼吸设备联调、信号处理验证和记录分析。支持 TCP 传感器与内置模拟信号，将实时监测、离线滤波、峰谷编辑和呼吸分箱整合在同一界面中。

源码通过 **uv 一条命令启动后端与界面**，无需 Node.js 或前端构建。Windows 打包版以独立桌面窗口运行。

## 功能

| 功能 | 内容 |
| --- | --- |
| 实时监测 | 原始与滤波波形、峰谷标记、呼吸频率、历史回看 |
| 模拟与滤波 | 正常、急促、浅呼吸、基线漂移、咳嗽与体动伪影等预设及组合波形 |
| 记录分析 | 截取记录区间，保留前后辅助数据，使用双向低通重新滤波 |
| 呼吸分箱 | 时间分箱、固定幅值分箱、周期内相对幅值分箱；可设置箱数与吸气方向 |
| 人工编辑 | 添加或删除峰谷、撤销修改、恢复自动标记，重新计算分箱 |
| 数据保存 | 保存与导入波形、处理参数、峰谷、扫描区间及分箱结果 |
| 外部集成 | HTTP 接口、Socket.IO 实时数据推送、会话隔离 |

<details>
<summary>查看界面示例</summary>

**实时监测**

![实时监测](docs/assets/screenshots/breath-monitor.png)

**记录分析**

![记录分析](docs/assets/screenshots/breath-record.png)

界面示例与录屏可能早于当前版本，操作演示及版本差异见[演示说明](docs/demos/README.md)。

</details>

## 快速启动

在已安装 uv 的环境中，进入项目根目录执行：

```bash
uv run --frozen respirascope
```

uv 会根据 `uv.lock` 准备 Python 3.13 和依赖。服务就绪后自动打开默认浏览器，终端打印实际访问地址。

| 入口 | 默认地址 |
| --- | --- |
| Web Console | `http://localhost:5175` |
| 实时监测 | `http://localhost:5175/#monitor` |
| 模拟与滤波 | `http://localhost:5175/#lab` |
| 后端接口 | `http://localhost:8000` |

端口占用时自动选择可用端口，**以启动输出为准**。首次启动会在没有现有配置时生成默认配置，并启用模拟信号。

常用启动选项：

```bash
# 不自动打开浏览器
uv run respirascope --no-browser

# 指定配置文件
uv run respirascope --config ./config/local.toml

# 指定偏好端口，冲突时仍自动避让
uv run respirascope --port 8000 --ui-port 5175

# 开发模式：Python 改动自动重载，界面改动刷新浏览器即可
uv run respirascope --reload
```

Windows 源码环境也可双击根目录的 `start.bat`。Linux 默认配置路径位于 `/ct/`；无写入权限时，可用 `--config` 指定用户可写路径，并设置 `[record].storage_root`。

## 操作流程

1. **选择数据源**：使用模拟信号，或在配置文件中填写真实设备的 TCP 地址。
2. **开始监测与记录**：观察实时波形，选择“开始记录”和“结束记录”；需要时添加扫描标记。
3. **离线分析**：调整低通上限频率，重新计算记录区间的滤波结果。
4. **选择分箱**：设置时间或幅值方式、每周期箱数、吸气方向；固定幅值方式可拖动上下界。
5. **检查并编辑峰谷**：进入编辑模式修正漏标或错标，应用修改后重新分箱。
6. **查看与保存**：在分箱数据中核对有效、排除、无法分箱区间，保存记录以便后续导入。

### 滤波与分箱

离线的时间和幅值分箱**共用同一条双向低通滤波结果**，切换分箱方式不会改变滤波曲线。默认每周期 10 箱，吸气、呼气各 5 箱；可切换其他支持的偶数箱数。

| 方式 | 划分依据 | 图中边界 |
| --- | --- | --- |
| 时间分箱 | 在可确定的吸气、呼气半周期内等分时间 | 纵向虚线 |
| 固定幅值分箱 | 在统一的上下界之间等分幅值，吸气和呼气分别编号 | 上下界实线及内部横向虚线 |
| 自由幅值分箱 | 按各半周期自身的幅值范围等分 | 随各半周期范围变化 |

异常区间保留滤波参考，但不作为有效分箱。人工补充峰谷不自动取消质量排除，也不会补造未实际经过的分箱。

### 峰谷编辑

进入编辑模式后，点击波形附近的横向位置可寻找并添加峰谷；点击已有标记的横向邻域可删除，支持在标记正上方或下方点击。

- `Ctrl / ⌘ + Z`：撤销一步。
- `Delete / Backspace`：删除当前标记。
- “应用并退出”保留修改，“取消并退出”放弃本轮编辑。

### 记录与分箱数据

记录采用 JSON v6 格式，包含原始及滤波波形、峰谷、分析参数和分箱数据；旧版记录可导入后重新保存。

`binningData` 使用 v4 结构，分别保存吸气箱、呼气箱、排除区间和无法分箱区间，**不细分排除或无法分箱的原因**。区间使用完整 `filtered` 数组的 `[start, end)` 下标，不是采样序号。具体结构见[分箱数据说明](docs/development/architecture-zh.md#分箱数据明细与精简存储)。

## 配置

配置使用外部 TOML 文件。可通过 `--config` 或 `RESPIRASCOPE_CONFIG` 指定；未指定时查找现有配置，再使用平台默认路径。

| 系统 | 默认配置路径 |
| --- | --- |
| Windows | `%LOCALAPPDATA%/RespiraScope/config/breath.toml` |
| macOS | `~/Library/Application Support/RespiraScope/config/breath.toml` |
| Linux | `/ct/breath-config/breath.toml` |

完整字段见[示例配置](config/breath.example.toml)。连接真实设备时修改：

```toml
[mock]
enabled = false

[sensor]
host = "设备 IP"
port = 8088 # 替换为设备实际端口
```

离线滤波辅助数据由公共配置控制，两种分箱共用，**重启后生效**：

```toml
[record]
pre_points = 200
post_points = 200
```

前后各默认 200 点，在 50 Hz 采样率下各对应 4 秒。数据不足时使用已有部分，不补造采样点。记录保存目录通过同节的 `storage_root` 设置。

## 项目结构

```text
src/ct_breath/
├── main.py / app.py / asgi.py   # CLI、应用工厂、ASGI 入口
├── core/                       # 配置、日志、公共设施
├── models/                     # 共享数据模型
├── acquisition/                # 设备接收与模拟信号
├── processing/                 # 滤波、峰谷与质量分析
├── binning/                    # 分箱与区间数据
├── recording/                  # 记录管理与文件序列化
├── streaming/                  # 实时队列与推送
├── application/                # 服务编排与会话管理
├── api/                        # HTTP 与 Socket.IO
├── runtime/                    # 桌面窗口、端口与资源服务
└── web/                        # 页面、共享组件、图标与第三方库

tests/                         # unit、integration、ui、fixtures、support
scripts/                       # 开发入口、packaging、reports
docs/                          # 开发、接口、部署、技术说明与报告
config/                        # 示例配置
```

源码、wheel 与桌面包使用同一套界面资源。模块职责及依赖约定见[项目结构说明](docs/development/project-layout.md)。

## 开发与验证

```bash
uv sync --frozen
uv run --frozen pytest tests/unit tests/integration

# 浏览器测试
uv sync --frozen --group ui-test
uv run --group ui-test playwright install chromium
uv run --group ui-test pytest tests/ui

# 构建 Python wheel
uv build --wheel
```

浏览器测试也可设置 `BROWSER_CHANNEL=chrome` 使用本机 Chrome。贡献约定见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 桌面打包

### Windows

在 Windows 上安装 uv 后，从仓库根目录执行：

```powershell
.\scripts\packaging\build-exe.bat
```

输出为 `dist/RespiraScope.exe`。双击后打开独立桌面窗口，不弹出命令行，也不打开浏览器；关闭窗口时停止后台服务。

运行端无需 Python、uv 或 Node.js，需要 Edge WebView2 Runtime。日志位于 `%LOCALAPPDATA%/RespiraScope/logs/`。可加 `--onedir` 构建展开目录包用于调试。

### macOS

```bash
./scripts/packaging/build-macos-app.sh
open dist/RespiraScope.app
```

当前 macOS 启动器通过 Terminal 运行服务并打开浏览器，与 Windows 的独立桌面窗口方式不同。PyInstaller 需要在目标系统上构建，不能在 macOS 上直接生成 Windows exe。详细选项见[打包脚本说明](scripts/README.md)。

## 文档与演示

| 内容 | 链接 |
| --- | --- |
| 文档总览 | [文档索引](docs/README.md) |
| 操作演示 | [录屏与操作时间表](docs/demos/README.md) |
| 分箱效果 | [PDF 报告](docs/reports/时间分箱与固定幅值分箱波形对比.pdf) · [Word 报告](docs/reports/时间分箱与固定幅值分箱波形对比.docx) |
| 算法说明 | [滤波、峰谷与质量处理](docs/technical/filtering-algorithm-zh.md) |
| 系统集成 | [HTTP 与 Socket.IO](docs/api/integration-api-zh.md) |
| 服务部署 | [云部署](docs/deployment/deploy-jdcloud-zh.md) · [多用户会话](docs/deployment/cloud-multi-user-zh.md) |
| 报告复现 | [测算及绘图脚本](scripts/README.md#offline-binning-comparison) |

## 使用范围与许可

本项目用于工程验证、算法学习和设备调试，不作为医疗诊断、治疗决策或临床监护依据。示例与公开报告使用模拟数据；请勿向仓库提交真实患者记录、生产配置或凭据。

采用 [MIT License](LICENSE)。
