"""Real tools. Each one talks to Docker Compose or the NetBox API."""

import json
import os
import subprocess
import urllib.error
import urllib.request

from agent.policy import ALLOWLIST, Policy

def _compose(*args, timeout=90):
    netbox_dir = os.environ.get("NETBOX_DIR", "/opt/netbox-docker")
    proc = subprocess.run(
        ["docker", "compose"] + list(args),
        cwd=netbox_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=timeout,
    )
    text = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        return f"命令失败（exit {proc.returncode}）:\n{text[-4000:]}"
    return text[-4000:] or "(无输出)"


def _http_get(path):
    if not path.startswith("/api/") or ".." in path:
        return "拒绝：只允许读取 /api/ 下的路径。"
    base = os.environ.get("NETBOX_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.environ.get("NETBOX_TOKEN", "")
    req = urllib.request.Request(base + path)
    if token:
        if token.startswith("Bearer ") or token.startswith("Token "):
            req.add_header("Authorization", token)
        else:
            req.add_header("Authorization", "Token " + token)
    req.add_header("Accept", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(8000).decode("utf-8", "replace")
            return f"HTTP {resp.status}\n{body}"
    except urllib.error.HTTPError as exc:
        body = exc.read(2000).decode("utf-8", "replace")
        return f"HTTP {exc.code}\n{body}"
    except Exception as exc:
        return f"请求失败: {exc}"


def make_tools(policy: Policy):
    def compose_ps() -> str:
        return _compose("ps", "-a")

    def service_logs(service: str, tail: int = 80) -> str:
        service = (service or "").strip()
        if service not in ALLOWLIST:
            return f"拒绝：只能查看白名单服务日志 {sorted(ALLOWLIST)}。"
        tail = max(10, min(int(tail or 80), 200))
        return _compose("logs", "--tail", str(tail), service)

    def netbox_status() -> str:
        return _http_get("/api/status/")

    def netbox_get(path: str) -> str:
        return _http_get(path or "/api/status/")

    def propose_remediation(service: str, reason: str) -> str:
        return policy.propose(service, reason)

    def restart_service(service: str) -> str:
        denied = policy.authorize_restart(service)
        if denied:
            return denied
        result = _compose("up", "-d", service.strip(), timeout=180)
        policy.proposal = None
        return "已执行 docker compose up -d。\n" + result

    specs = [
        {
            "type": "function",
            "function": {
                "name": "compose_ps",
                "description": "查看 NetBox Docker Compose 栈里每个容器的状态。",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "service_logs",
                "description": "读取指定服务最近的日志，用于判断失败原因。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {"type": "string"},
                        "tail": {"type": "integer"},
                    },
                    "required": ["service"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "netbox_status",
                "description": "调用 NetBox /api/status/，查看 PostgreSQL 和 Redis 是否健康。",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "netbox_get",
                "description": "只读调用 NetBox API。path 必须以 /api/ 开头，例如 /api/dcim/devices/。",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "propose_remediation",
                "description": "记录处置建议，不修改系统。重启前必须先调用本工具。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["service", "reason"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "restart_service",
                "description": "按已记录的建议，用 docker compose up -d 拉起一个白名单内的服务。",
                "parameters": {
                    "type": "object",
                    "properties": {"service": {"type": "string"}},
                    "required": ["service"],
                },
            },
        },
    ]
    functions = {
        "compose_ps": lambda **_: compose_ps(),
        "service_logs": lambda **kw: service_logs(kw.get("service", ""), kw.get("tail", 80)),
        "netbox_status": lambda **_: netbox_status(),
        "netbox_get": lambda **kw: netbox_get(kw.get("path", "")),
        "propose_remediation": lambda **kw: propose_remediation(kw.get("service", ""), kw.get("reason", "")),
        "restart_service": lambda **kw: restart_service(kw.get("service", "")),
    }
    return specs, functions


def run_tool(functions, name: str, arguments: str) -> str:
    try:
        payload = json.loads(arguments or "{}")
    except json.JSONDecodeError as exc:
        return f"参数不是合法 JSON: {exc}"
    func = functions.get(name)
    if func is None:
        return f"未知工具: {name}"
    try:
        return func(**payload)
    except Exception as exc:
        return f"工具执行异常: {exc}"
