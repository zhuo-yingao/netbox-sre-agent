"""Guardrails for the one write action the agent is allowed to take."""

ALLOWLIST = {
    "redis",
    "redis-cache",
    "netbox",
    "netbox-worker",
    "postgres",
}


class Policy(object):
    def __init__(self):
        self.proposal = None

    def propose(self, service, reason):
        service = (service or "").strip()
        reason = (reason or "").strip()
        if service not in ALLOWLIST:
            return "拒绝：%s 不在可修复服务白名单 %s 中。" % (service, sorted(ALLOWLIST))
        if not reason:
            return "拒绝：必须写明原因和依据。"
        self.proposal = {"service": service, "reason": reason}
        return (
            "已记录处置建议：重启 %s。原因：%s。"
            "下一步才能调用 restart_service，且服务名必须与建议一致。"
        ) % (service, reason)

    def authorize_restart(self, service):
        service = (service or "").strip()
        if service not in ALLOWLIST:
            return "拒绝：%s 不在白名单中。" % service
        if not self.proposal:
            return "拒绝：还没有处置建议。请先调用 propose_remediation。"
        if self.proposal["service"] != service:
            return (
                "拒绝：建议重启的是 %s，不能直接重启 %s。请重新给出建议。"
                % (self.proposal["service"], service)
            )
        return None
