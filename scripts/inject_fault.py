"""Inject one fault from outside the agent. The agent is not told which fault this is."""

import argparse
import subprocess
import sys

FAULTS = {
    "redis": "redis",
    "worker": "netbox-worker",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fault", choices=sorted(FAULTS))
    parser.add_argument("--dir", default="/opt/netbox-docker")
    args = parser.parse_args()
    service = FAULTS[args.fault]
    proc = subprocess.run(
        ["docker", "compose", "stop", service],
        cwd=args.dir,
    )
    if proc.returncode != 0:
        sys.exit(proc.returncode)
    print(f"已停止 {service}。不要把服务名告诉 Agent。")


if __name__ == "__main__":
    main()
