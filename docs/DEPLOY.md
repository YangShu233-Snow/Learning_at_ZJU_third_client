# LAZY SERVER 部署指南

## 前置条件

- Python >= 3.10
- 已 clone 本仓库并安装: `pip install -e '.[server]'`
- 至少一个有效学号/密码（部署后通过 `/api/auth/register` 注册）

## 方式一：systemd 服务（推荐）

### 1. 创建服务用户（可选）

```bash
sudo useradd -r -s /bin/false lazy
```

### 2. 准备运行目录

```bash
sudo mkdir -p /opt/lazy-server
sudo chown lazy:lazy /opt/lazy-server
cd /opt/lazy-server
git clone https://github.com/YangShu233-Snow/Learning_at_ZJU_third_client .
python3 -m venv venv
venv/bin/pip install -e '.[server]'
```

### 3. 创建 systemd 单元

`/etc/systemd/system/lazy-server.service`:

```ini
[Unit]
Description=LAZY SERVER - 学在浙大第三方服务端
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=lazy
WorkingDirectory=/opt/lazy-server
ExecStart=/opt/lazy-server/venv/bin/lazy-server --host 0.0.0.0 --port 8765
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
```

### 4. 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable lazy-server
sudo systemctl start lazy-server
sudo systemctl status lazy-server
```

### 5. 验证

```bash
curl http://127.0.0.1:8765/api/health
```

### 6. 注册用户

```bash
curl -X POST http://127.0.0.1:8765/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"studentid":"你的学号","password":"你的密码"}'
```

### 管理命令

```bash
sudo systemctl restart lazy-server    # 重启
sudo systemctl stop lazy-server       # 停止
sudo journalctl -u lazy-server -f     # 查看实时日志
```

---

## 方式二：Docker

### 1. Dockerfile

在项目根目录创建 `Dockerfile`：

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -e '.[server]'
VOLUME ["/root/.lazy_server"]
EXPOSE 8765
CMD ["lazy-server", "--host", "0.0.0.0", "--port", "8765"]
```

### 2. 构建与运行

```bash
docker build -t lazy-server .
docker run -d \
  --name lazy-server \
  -p 8765:8765 \
  -v ~/.lazy_server:/root/.lazy_server \
  --restart always \
  lazy-server
```

### 3. 注册用户

```bash
docker exec -it lazy-server curl -X POST http://127.0.0.1:8765/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"studentid":"你的学号","password":"你的密码"}'
```

### 常用命令

```bash
docker logs -f lazy-server       # 查看日志
docker restart lazy-server       # 重启
docker exec -it lazy-server bash # 进入容器
```

---

## 部署后验证

```bash
# 健康检查
curl http://127.0.0.1:8765/api/health

# 登录获取 token
TOKEN=$(curl -s -X POST http://127.0.0.1:8765/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"studentid":"你的学号","password":"你的密码"}' | \
  python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 查看监控任务
curl -s "http://127.0.0.1:8765/api/tasks?token=$TOKEN" | python -m json.tool

# 等待第一个轮询周期后查询数据
sleep 35
curl -s "http://127.0.0.1:8765/api/data/rollcall_watch?token=$TOKEN" | python -m json.tool
curl -s "http://127.0.0.1:8765/api/data/todo_watch?token=$TOKEN" | python -m json.tool
```

## 日志

LAZY SERVER 日志沿用 CLI 日志系统，位于 `~/.lazy_cli_logs/lazy_cli.log`（旋转策略：5MB × 3）：

```bash
tail -f ~/.lazy_cli_logs/lazy_cli.log
```

systemd 用户也可同步看 journalctl：

```bash
sudo journalctl -u lazy-server -f
```

## 安全注意事项

- `~/.lazy_server/master.key` — Fernet 主加密密钥，**chmod 600**，不可提交到版本控制
- `~/.lazy_server/credentials.enc` — 加密的用户凭据（学号、密码、cookies）
- 确保上述文件仅服务进程用户可读写
- 服务器被入侵后攻击者可解密所有凭据，请做好主机安全防护
- 如需更高安全等级，可通过环境变量 `LAZY_SERVER_KEY` 传入主密钥（每次重启需重新提供）

## 网络配置

如需通过代理访问学在浙大：

```bash
# systemd: 在单元文件中添加
Environment="HTTP_PROXY=http://代理地址:端口"
Environment="HTTPS_PROXY=http://代理地址:端口"

# Docker:
docker run -e HTTP_PROXY=http://代理地址:端口 ...

# 通用: lazy-server 自带 --proxy 参数
lazy-server --proxy --host 0.0.0.0 --port 8765
```
