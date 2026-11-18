#!/bin/bash
exec >> /var/log/exam-run.log 2>&1
echo START $(date)
cd /opt/netbox-docker || exit 1
while pgrep -f "compose pull" >/dev/null; do
  echo WAIT_PULL $(date)
  sleep 20
done
echo PULL_DONE $(date)
docker images
docker compose up -d
echo UP_ISSUED $(date)
ok=0
i=0
while [ "$i" -lt 40 ]; do
  code=$(curl -sS -m 5 -o /tmp/nb-status.json -w "%{http_code}" http://127.0.0.1:8000/api/status/ || true)
  echo STATUS $code
  if [ "$code" = "200" ]; then
    ok=1
    break
  fi
  i=$((i + 1))
  sleep 15
done
if [ "$ok" != "1" ]; then
  echo STACK_NOT_READY
  docker compose ps -a
  exit 1
fi
mkdir -p /opt/netbox-sre-agent/demo
cd /opt/netbox-sre-agent
echo "===== REDIS $(date) =====" | tee demo/redis.log
python3 scripts/inject_fault.py redis
python3 -m agent "检查 NetBox 栈，有异常就处理到恢复。" | tee -a demo/redis.log
echo REDIS_DONE $(date)
cd /opt/netbox-docker
docker compose up -d redis
sleep 20
cd /opt/netbox-sre-agent
echo "===== WORKER $(date) =====" | tee demo/worker.log
python3 scripts/inject_fault.py worker
python3 -m agent "检查 NetBox 栈，有异常就处理到恢复。" | tee -a demo/worker.log
echo DONE $(date)
