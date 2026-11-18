"""Tool-calling loop. The model chooses every tool; this file does not branch on faults."""

import json
import os
import sys
import urllib.error
import urllib.request

from agent.policy import Policy
from agent.tools import make_tools, run_tool

SYSTEM = """你是 NetBox Docker 栈的 SRE。用户只会给你一个目标，不会告诉你哪个服务坏了。
你必须自己调用工具完成闭环，顺序是：
1. 用 compose_ps 和 netbox_status 发现异常。
2. 用 service_logs 或 netbox_get 拿到证据，说明原因。
3. 调用 propose_remediation 写出要重启的服务和依据。这一步不会改系统。
4. 调用 restart_service 执行刚才的建议。服务名必须一致。
5. 再查一次 compose_ps 和 netbox_status，确认恢复。
不要猜测没有看到的日志。一次只重启一个服务。不要执行白名单以外的动作。"""


def chat(base_url, api_key, model, messages, tools):
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "tools": tools,
        "max_tokens": 2048,
    }).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=payload,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        raise RuntimeError("HTTP %s %s" % (exc.code, body[:500]))


def load_env(path):
    if not os.path.isfile(path):
        return
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_env(os.path.join(root, ".env"))
    task = " ".join(sys.argv[1:]).strip() or "检查 NetBox 栈，有异常就处理到恢复。"
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", "deepseek-chat")
    if not api_key:
        sys.stderr.write("缺少 OPENAI_API_KEY\n")
        sys.exit(2)
    policy = Policy()
    specs, functions = make_tools(policy)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": task},
    ]
    print("任务: %s" % task)
    print("模型: %s" % model)
    for step in range(1, 13):
        try:
            data = chat(base_url, api_key, model, messages, specs)
        except Exception as exc:
            sys.stderr.write("模型请求失败: %s\n" % exc)
            return
        if "choices" not in data:
            print(json.dumps(data, ensure_ascii=False)[:1000])
            return
        msg = data["choices"][0]["message"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            print("\n--- 结论 ---\n%s" % (msg.get("content") or ""))
            return
        for call in calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments") or "{}"
            print("\n[%s] 调用 %s %s" % (step, name, arguments))
            result = run_tool(functions, name, arguments)
            print(result[:2000])
            messages.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result[:6000],
            })
    print("\n已达到 12 轮，停止。")


if __name__ == "__main__":
    main()
