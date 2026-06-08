# LabMon

[English](README.md)

LabMon 是一个面向课题组共享 GPU 服务器的轻量只读监控面板。它用来回答跑实验前最常见的问题：哪张卡空着、忙的卡是谁在用、跑的是什么命令、训练日志有没有继续推进。

![LabMon dashboard](img/dashboard.png)

## 功能亮点

- 按物理 GPU 顺序显示：GPU `0`、`1`、`2`、`3`，和 `nvidia-smi` 的编号一致。
- GPU 状态：利用率、显存、温度、功耗、用户、命令行、进程数量和启动时间。
- 主机状态：CPU、内存、磁盘、load average、空闲 GPU 数量和采集警告。
- 服务端趋势记录：即使没有打开浏览器页面，也会持续记录最近的 GPU、CPU 和内存曲线。
- 训练进度：扫描配置的日志目录，提取 `step`、`epoch`、`loss`、`reward`、`lr`、`eta` 等常见字段。
- 内置认证：本地用户、PBKDF2 密码哈希、签名 HttpOnly session、受保护的页面和 API。
- 只读设计：不提供 kill 进程、不做实验排队、不写入用户实验目录。

## 登录

LabMon 可以不启用认证，用于本机 demo。部署到课题组内网时，建议设置 `LABMON_AUTH=1`，只有本地 LabMon 账号能访问面板。

![LabMon login](img/login.png)

## 快速开始

使用 `uv` 安装依赖：

```bash
uv sync --dev
```

启动四卡 RTX 3090 模拟数据 demo：

```bash
LABMON_DEMO=1 uv run uvicorn labmon.app:app --reload --host 127.0.0.1 --port 8765
```

打开 <http://127.0.0.1:8765>。

如果想本机预览登录流程：

```bash
uv run python scripts/manage_users.py add demo
LABMON_DEMO=1 \
LABMON_AUTH=1 \
LABMON_AUTH_SECRET="$(openssl rand -hex 32)" \
uv run uvicorn labmon.app:app --reload --host 127.0.0.1 --port 8765
```

## 服务器一键安装

前提：服务器是 Linux，已安装 NVIDIA 驱动、`git`、`uv`，并且当前用户有 `sudo` 权限。

第一次安装推荐直接 clone 到 `/opt/labmon`：

```bash
sudo git clone https://github.com/Orange-Long320/LabMon.git /opt/labmon && cd /opt/labmon && sudo env LABMON_ADMIN_USER=alice bash deploy/install.sh
```

分步写法：

```bash
sudo git clone https://github.com/Orange-Long320/LabMon.git /opt/labmon
cd /opt/labmon
sudo env LABMON_ADMIN_USER=alice bash deploy/install.sh
```

把 `alice` 换成第一个课题组账号。脚本会提示你输入这个账号的密码。

安装脚本会自动完成：

- 执行 `uv sync --no-dev`
- 生成 `/etc/labmon/labmon.env`，包括随机 `LABMON_AUTH_SECRET`
- 安装并启动 `/etc/systemd/system/labmon.service`
- 设置 `systemd` 开机自启和异常重启

如果已经创建过账号，也可以不带 `LABMON_ADMIN_USER`：

```bash
cd /opt/labmon
sudo bash deploy/install.sh
```

状态和日志：

```bash
sudo systemctl status labmon
sudo journalctl -u labmon -f
```

`systemd` 会让 LabMon 脱离 SSH 会话运行，服务器重启后自动启动，进程异常退出后自动重启。它不能阻止管理员手动停止服务、服务器断电或 root 用户强制 kill，但能解决 SSH 断开导致服务退出的问题。

## 校园网内访问

默认安装会让 LabMon 监听 `0.0.0.0:8765`。这表示服务器所有网卡都接受连接，但它不等于“整个校园网一定能访问”。校园网能不能访问，取决于学校网络是否允许从校园网路由到机房服务器网段。

先在服务器上确认监听地址：

```bash
sudo ss -lntp | grep 8765
```

如果看到 `0.0.0.0:8765`，说明 LabMon 已经对服务器网卡开放。然后找一台校园网内的电脑测试：

```bash
curl http://<服务器IP>:8765/api/me
```

如果能返回 JSON，就可以通过 `http://<服务器IP>:8765` 访问。此时建议只对校园网网段放行端口，不要开放到公网。常见防火墙示例：

```bash
sudo ufw allow from <校园网CIDR> to any port 8765 proto tcp
```

或 firewalld：

```bash
sudo firewall-cmd --permanent --add-rich-rule='rule family="ipv4" source address="<校园网CIDR>" port port="8765" protocol="tcp" accept'
sudo firewall-cmd --reload
```

如果校园网电脑访问不了，但机房局域网能访问，说明机房网段和校园网之间有路由或防火墙隔离。这种情况需要找网管放行：

```text
源地址：校园网内网网段
目标地址：GPU 服务器 IP
目标端口：TCP 8765
用途：课题组 LabMon 只读 GPU 监控面板
```

如果学校不允许直接放行机房服务器端口，可以把 LabMon 绑定到 `127.0.0.1`，再在一个校园网可访问的跳板机或机房网关上用 Nginx 做反向代理。这个方案的入口地址会是跳板机地址，后端再转发到 GPU 服务器。

需要改端口、日志目录、历史记录窗口或 HTTPS cookie 时，编辑：

```bash
sudo nano /etc/labmon/labmon.env
sudo systemctl restart labmon
```

如果端口可能被校园网之外访问，建议绑定到 `127.0.0.1`，再通过 SSH tunnel、VPN 或带 HTTPS 的反向代理访问。通过 HTTPS 访问时，设置 `LABMON_AUTH_COOKIE_SECURE=1`。

## 临时调试

如果只想临时跑一下，不要用于长期服务：

```bash
uv sync --no-dev
uv run python scripts/manage_users.py add alice
LABMON_LOG_ROOTS="/home/*/runs,/home/*/logs,/data/runs,/data/logs" \
LABMON_AUTH=1 \
LABMON_AUTH_SECRET="$(openssl rand -hex 32)" \
uv run uvicorn labmon.app:app --host 0.0.0.0 --port 8765
```

这个命令在 SSH 前台运行，断开 SSH 后可能退出。

## 用户管理

服务器部署后建议使用安装目录里的 Python 和用户文件路径：

```bash
sudo env LABMON_USERS_FILE=/opt/labmon/labmon-users.json /opt/labmon/.venv/bin/python /opt/labmon/scripts/manage_users.py add bob
sudo env LABMON_USERS_FILE=/opt/labmon/labmon-users.json /opt/labmon/.venv/bin/python /opt/labmon/scripts/manage_users.py list
sudo env LABMON_USERS_FILE=/opt/labmon/labmon-users.json /opt/labmon/.venv/bin/python /opt/labmon/scripts/manage_users.py remove bob
```

本机开发时也可以用：

```bash
uv run python scripts/manage_users.py add alice
uv run python scripts/manage_users.py list
uv run python scripts/manage_users.py remove alice
```

建议每位组员使用独立账号。密码会以 PBKDF2 hash 的形式保存到 `LABMON_USERS_FILE`；默认文件是 `./labmon-users.json`，已经被 git 忽略。

## 配置项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LABMON_DEMO` | 未设置 | 设置为 `1` 后使用模拟四卡 RTX 3090 数据。 |
| `LABMON_LOG_ROOTS` | demo 示例日志 | 逗号分隔的日志目录或 glob pattern。 |
| `LABMON_HOST_LABEL` | 系统 hostname | 覆盖页面顶部显示的主机名。 |
| `LABMON_REFRESH_SECONDS` | `1` | dashboard 轮询间隔，单位为秒。 |
| `LABMON_HISTORY_SECONDS` | `3600` | 服务端指标历史保留时长，单位为秒。 |
| `LABMON_HISTORY_INTERVAL_SECONDS` | `1` | 服务端指标采样间隔，单位为秒。 |
| `LABMON_AUTH` | 未设置 | 设置为 `1` 后启用登录认证。 |
| `LABMON_AUTH_SECRET` | 未设置 | 认证模式必填，建议用 `openssl rand -hex 32` 生成。 |
| `LABMON_USERS_FILE` | `./labmon-users.json` | 本地用户数据库路径。 |
| `LABMON_AUTH_SESSION_HOURS` | `168` | 登录 session 有效期，单位为小时。 |
| `LABMON_AUTH_COOKIE_SECURE` | 未设置 | 通过 HTTPS 访问时设置为 `1`。 |

## API

- `GET /api/snapshot`：返回完整 dashboard 快照，包括主机、GPU、进程、日志和警告数据。
- `GET /api/history?seconds=600`：返回服务端记录的 GPU 利用率、GPU 显存、CPU 和内存历史曲线数据。
- `GET /api/logs/{log_id}?lines=200`：读取已发现日志文件的尾部内容。
- `GET /api/me`：认证开启时返回当前登录用户。
- `POST /api/login`：创建登录 session。
- `POST /api/logout`：清除登录 session。

`/api/logs/{log_id}` 只允许读取日志扫描器发现的文件，调用方不能传任意文件路径。

## 数据来源

demo 模式下，LabMon 会读取本机真实 CPU、内存和磁盘数据，同时生成四张动态 mock RTX 3090 和示例训练日志。

server 模式下，LabMon 使用 `psutil` 读取主机资源，使用 `nvidia-smi` 读取 GPU 和 compute process，再通过 PID 关联 Linux 用户、命令行、显存占用和启动时间。

## 测试

```bash
uv run pytest
```

测试覆盖 GPU CSV 解析、PID 信息补全、缺失或权限不足的采集器、日志字段解析、API 行为和认证路由保护。
