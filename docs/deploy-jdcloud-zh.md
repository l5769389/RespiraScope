# 京东云 GitHub Actions 部署说明

本文说明如何把 RespiraScope 通过 GitHub Actions 部署到京东云 Linux 服务器。

## 1. 部署方式

工作流文件：

```text
.github/workflows/deploy-jdcloud.yml
```

触发方式：

- 推送到 `main` 分支后自动部署。
- 在 GitHub Actions 页面手动运行 `Deploy to JD Cloud`。

部署流程：

1. GitHub Actions 拉取代码。
2. 安装 `uv`。
3. 执行 `uv sync --frozen` 和 `uv run pytest`。
4. 测试通过后，把当前代码打成 tar 包上传到京东云服务器。
5. 服务器解压到 `${DEPLOY_PATH}/releases/<commit_sha>`。
6. 更新 `${DEPLOY_PATH}/current` 软链接。
7. 执行 `uv sync --frozen --no-dev` 安装生产依赖。
8. 创建或更新 systemd 服务。
9. 重启服务。

默认部署目录：

```text
/opt/RespiraScope
```

默认 systemd 服务名：

```text
respiscope
```

## 2. 服务器准备

推荐系统：Ubuntu 22.04/24.04 或 Debian 12。

服务器需要安装基础工具：

```bash
sudo apt-get update
sudo apt-get install -y curl tar ca-certificates
```

如果服务器没有 Python 3.13，可以先安装。Ubuntu/Debian 可使用 deadsnakes、源码安装或系统镜像自带包，确保下面命令可用：

```bash
python3.13 --version
```

部署用户需要满足：

- 可以通过 SSH 登录。
- 可以执行 `sudo`。
- 建议配置免密码 sudo，避免 GitHub Actions 部署时卡住。

示例：

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
```

## 3. SSH Key 配置

在本地生成一对部署用 SSH key：

```bash
ssh-keygen -t ed25519 -C "github-actions-respiscope" -f jdcloud_respiscope
```

把公钥加入服务器：

```bash
ssh-copy-id -i jdcloud_respiscope.pub deploy@你的服务器公网IP
```

确认可以登录：

```bash
ssh -i jdcloud_respiscope deploy@你的服务器公网IP
```

## 4. GitHub Secrets

进入 GitHub 仓库：

```text
Settings -> Secrets and variables -> Actions -> New repository secret
```

至少添加：

| Secret | 必填 | 示例 | 说明 |
| --- | --- | --- | --- |
| `JDCLOUD_HOST` | 是 | `1.2.3.4` | 京东云服务器公网 IP 或域名 |
| `JDCLOUD_USER` | 是 | `deploy` | SSH 登录用户 |
| `JDCLOUD_SSH_KEY` | 是 | 私钥全文 | `jdcloud_respiscope` 私钥内容 |

可选添加：

| Secret | 默认值 | 说明 |
| --- | --- | --- |
| `JDCLOUD_PORT` | `22` | SSH 端口 |
| `JDCLOUD_DEPLOY_PATH` | `/opt/RespiraScope` | 部署目录 |
| `JDCLOUD_SERVICE_NAME` | `respiscope` | systemd 服务名 |
| `JDCLOUD_SERVICE_USER` | `JDCLOUD_USER` | systemd 运行用户 |

`JDCLOUD_SSH_KEY` 要填私钥完整内容，例如：

```text
-----BEGIN OPENSSH PRIVATE KEY-----
...
-----END OPENSSH PRIVATE KEY-----
```

## 5. 云服务器配置文件

首次部署时，如果服务器不存在：

```text
/ct/breath-config/breath.toml
```

工作流会复制：

```text
config/breath.jdcloud.example.toml
```

到服务器配置目录。

云端模板的关键点：

```toml
[backend]
host = "0.0.0.0"
port = 8000

[console]
enabled = true
host = "0.0.0.0"
port = 5175
```

这样后端和 Web Console 才能通过公网 IP 访问。

如果接入真实呼吸设备，请登录服务器编辑：

```bash
sudo nano /ct/breath-config/breath.toml
```

把模拟信号关闭，并配置设备地址：

```toml
[mock]
enabled = false

[sensor]
host = "真实设备IP"
port = 8088
```

修改配置后重启服务：

```bash
sudo systemctl restart respiscope
```

## 6. 京东云安全组

如果直接公网访问，需要在京东云控制台安全组放行：

| 端口 | 用途 |
| --- | --- |
| `22` | SSH 部署 |
| `8000` | RespiraScope Backend |
| `5175` | Web Console |

访问地址：

```text
http://你的服务器公网IP:5175
http://你的服务器公网IP:8000/health
```

生产环境更推荐只放行 80/443，并用 Nginx 反向代理到本机 `8000` 和 `5175`。

## 7. 常用运维命令

查看服务状态：

```bash
sudo systemctl status respiscope
```

查看日志：

```bash
sudo journalctl -u respiscope -f
```

重启服务：

```bash
sudo systemctl restart respiscope
```

查看当前部署版本：

```bash
readlink -f /opt/RespiraScope/current
```

查看配置文件：

```bash
cat /ct/breath-config/breath.toml
```

## 8. 回滚

部署目录会保留每个 commit 的 release：

```text
/opt/RespiraScope/releases/<commit_sha>
```

如果需要手动回滚：

```bash
cd /opt/RespiraScope
ln -sfn releases/上一个commit current
sudo systemctl restart respiscope
```

## 9. 常见问题

### GitHub Actions 提示缺少 Secret

检查仓库 Actions Secrets 是否添加了：

- `JDCLOUD_HOST`
- `JDCLOUD_USER`
- `JDCLOUD_SSH_KEY`

### SSH 连接失败

检查：

- 京东云安全组是否放行 SSH 端口。
- `JDCLOUD_PORT` 是否正确。
- 私钥是否是完整私钥，不是 `.pub` 公钥。
- 公钥是否已经添加到服务器用户的 `~/.ssh/authorized_keys`。

### 服务启动失败

登录服务器查看日志：

```bash
sudo journalctl -u respiscope -n 100 --no-pager
```

常见原因：

- 服务器没有 Python 3.13。
- `/ct/breath-config/breath.toml` 配置了不可用的端口。
- `5175` 或 `8000` 已被其他进程占用。

### 页面无法访问

检查：

- systemd 服务是否运行。
- 京东云安全组是否放行 `5175`。
- `/ct/breath-config/breath.toml` 中 `[console].host` 是否为 `0.0.0.0`。
