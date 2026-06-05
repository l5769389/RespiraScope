# 云端多用户隔离部署说明

本文说明 RespiraScope 改造成云服务器多人访问后的运行模型和部署要点。

## 1. 隔离模型

RespiraScope 现在支持匿名会话隔离：

- 前端每个浏览器标签页会生成一个 `RespiraScope-session`，保存在 `sessionStorage`。
- HTTP 请求通过 `X-RespiraScope-Session` 请求头携带会话 ID。
- Socket.IO 通过 `session_id` query/auth 携带同一个会话 ID。
- 后端按会话 ID 创建独立的 `BreathProcessSystem`，包含独立的滤波参数、实时队列、记录状态、扫描状态、最近快照和模拟信号配置。
- Socket.IO 推送进入 `session:<session-id>` 房间，只发给同会话客户端。
- 记录文件保存到独立的 session 临时目录，session 回收时会一起清理。

未携带 session 的旧客户端仍使用全局实例，便于本地调试和向后兼容。

## 2. 模拟信号和真实设备

当 `[mock].enabled = true` 时，带 session 的云端访问会使用会话内模拟源。不同用户在“模拟信号设置”里调整 BPM、幅度、噪声等参数，不会影响其他用户。

当 `[mock].enabled = false` 时，每个会话会按 `[sensor]` 配置连接真实 TCP 设备。需要确认真实设备是否允许多个 TCP client 同时连接：

- 如果设备允许多连接：多个用户可以各自启动独立处理链路。
- 如果设备只允许单连接：建议增加一个设备采集代理，由代理独占连接真实设备，再把同一原始流分发给多个后端会话。

## 3. 配置

云端配置示例：

```toml
[backend]
host = "0.0.0.0"
port = 8000

[console]
enabled = true
host = "0.0.0.0"
port = 5175

[record]
storage_root = "/ct/breath-records"

[session]
idle_timeout_seconds = 14400
```

`idle_timeout_seconds` 控制匿名会话空闲多久后被后端回收，默认 4 小时。前端仍在轮询状态或 Socket 有消息时，会话会被触碰刷新。

带 session 的 `/record/save` 会忽略客户端传入的 `folder_path`，只写入：

```text
<storage_root>/<session-id>/
```

未携带 session 的旧客户端仍保留原来的 `folder_path` 行为，用于本地调试和向后兼容。

## 4. 反向代理

生产环境推荐只暴露 80/443，用 Nginx 转发：

```nginx
server {
    listen 80;
    server_name your-domain.example;

    location / {
        proxy_pass http://127.0.0.1:5175;
        proxy_set_header Host $host;
    }

    location /socket.io/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location ~ ^/(health|runtime|stream|startReceive|stopReceive|setRTFilterParams|record|scan|applyFilter|mock) {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

如果后端和前端分端口直接暴露，需要在安全组放行 `5175` 和 `8000`。公网生产环境更建议配 HTTPS，并在外围增加登录或访问控制。

## 5. 当前边界

本次隔离是匿名会话隔离，不是账号体系。任何知道某个 session id 的客户端都可以访问该会话的数据。面向公网正式使用时，建议后续增加：

- 登录认证和用户表。
- session id 与用户绑定。
- 需要长期保留记录时，把 session 临时目录同步到用户目录或对象存储 key。
- 对真实设备连接增加资源配额和并发限制。
