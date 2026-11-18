# NetBox Docker SRE Agent

用 [netbox-docker](https://github.com/netbox-community/netbox-docker) 作为被运维的系统和数据来源，实现一个真正会 Tool Calling 的 SRE Agent。模型自己决定调用哪个工具，程序只负责执行，并把结果交回模型。

## 闭环

发现异常 → 用日志或健康检查确认原因 → 提出处置建议 → 执行重启 → 再次验证。

同一套代码不写死故障类型。下面两种故障会走出不同的工具参数：

- 停掉 `redis`：`/api/status/` 失败，日志里能看到缓存连接错误，建议并重启 `redis`。
- 停掉 `netbox-worker`：HTTP 健康检查可能仍正常，但 `compose_ps` 显示 worker 已退出，建议并重启 `netbox-worker`。

## 结构

```text
用户指令
  → OpenAI 兼容接口（模型返回 tool_calls）
  → compose_ps / service_logs / netbox_status / netbox_get
  → propose_remediation（只记录，不改系统）
  → restart_service（必须和上一步的服务名一致）
  → 再次 compose_ps 和 netbox_status
```

`restart_service` 只允许 `redis`、`redis-cache`、`netbox`、`netbox-worker`、`postgres`。没有通用 shell。

NetBox 在这里有两层用途：容器栈是被操作的对象；`/api/status/` 和只读 API 是判断依据。

## 运行

在已经装好 Docker 和 Docker Compose v2 的 Linux 上：

```bash
git clone -b release https://github.com/netbox-community/netbox-docker.git /opt/netbox-docker
cp /opt/netbox-sre-agent/docker-compose.override.yml /opt/netbox-docker/docker-compose.override.yml
cd /opt/netbox-docker
docker compose up -d
```

这份 override 把页面映射到宿主机 8000 端口，管理员是 `admin` / `admin12345`。CentOS 7 的 libseccomp 会拦住 Postgres 18 的新系统调用，所以 postgres 服务加了 `seccomp:unconfined`。

等 `docker compose ps` 里 netbox 变成 healthy。NetBox 4.7 不带令牌访问 `/api/status/` 会返回 403。用下面的命令创建一个只读 v2 令牌，把打印出的整行 `Bearer ...` 写入 `.env` 的 `NETBOX_TOKEN`：

```bash
bash /opt/netbox-sre-agent/scripts/create_token.sh
```

Agent 使用 Python 3 标准库，不需要安装第三方包。

```bash
cd /opt/netbox-sre-agent
cp .env.example .env
# 编辑 .env，填上模型密钥和上面打印的 Bearer 令牌
export OPENAI_BASE_URL=https://api.deepseek.com
export OPENAI_API_KEY=你的密钥
export OPENAI_MODEL=deepseek-chat
export NETBOX_DIR=/opt/netbox-docker
export NETBOX_URL=http://127.0.0.1:8000
export NETBOX_TOKEN='Bearer 上面命令打印的整行'

# 另开一个终端注入故障，不要把服务名告诉 Agent
python3 scripts/inject_fault.py redis

python3 -m agent "检查 NetBox 栈，有异常就处理到恢复。"
```

通义千问使用业务空间的兼容地址，模型可用 `qwen4-max`。密钥放在 `.env`，不要提交。

镜像拉完后可以一次跑完两轮故障，轨迹写到 `demo/redis.log` 和 `demo/worker.log`：

```bash
bash scripts/run-demo.sh
```

## 效果演示

真实运行记录在 `demo/redis.log` 和 `demo/worker.log`。里面是模型选出的工具名和参数，不是只保留最后一段总结。
