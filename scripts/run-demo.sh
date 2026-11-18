#!/bin/bash
exec >> /var/log/exam-demo.log 2>&1
echo START $(date)
cd /opt/netbox-docker || exit 1
docker compose up -d
sleep 20
mkdir -p /opt/netbox-sre-agent/demo
cd /opt/netbox-sre-agent
echo "===== REDIS $(date) =====" | tee demo/redis.log
python3 scripts/inject_fault.py redis
python3 -m agent "检查 NetBox 栈，有异常就处理到恢复。" | tee -a demo/redis.log
echo REDIS_DONE $(date)
cd /opt/netbox-docker
docker compose up -d redis
sleep 25
cd /opt/netbox-sre-agent
echo "===== WORKER $(date) =====" | tee demo/worker.log
python3 scripts/inject_fault.py worker
python3 -m agent "检查 NetBox 栈，有异常就处理到恢复。" | tee -a demo/worker.log
echo DONE $(date)
