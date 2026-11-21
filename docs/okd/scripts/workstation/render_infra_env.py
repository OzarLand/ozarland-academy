#!/usr/bin/env python3
"""Turn the `lab` Terraform output (JSON on stdin) into a shell env file.

The cluster-side scripts are plain Bash; a flat KEY=value file is the
simplest contract between Terraform and them.
"""

import json
import shlex
import sys


def flatten(lab: dict) -> dict[str, str]:
    env = {
        "MACHINE_CIDR": lab["machine_cidr"],
        "MACHINE_GATEWAY": lab["machine_gateway"],
        "MACHINE_MTU": lab["machine_mtu"],
        "BASTION_IP": lab["bastion_ip"],
        "UPSTREAM_DNS": lab["upstream_dns"],
        "OKD_IP": lab["okd_ip"],
        "OKD_MAC": lab["okd_mac"],
    }
    for name, net in lab["networks"].items():
        prefix = name.upper()
        env[f"{prefix}_CIDR"] = net["cidr"]
        env[f"{prefix}_MTU"] = net["mtu"]
        env[f"{prefix}_GATEWAY"] = net["gateway"]
        env[f"{prefix}_OKD_IP"] = net["okd_ip"]
        env[f"{prefix}_OKD_MAC"] = net["okd_mac"]
    env["DATAPLANE_USER"] = lab["dataplane_user"]
    computes = lab["computes"]
    env["COMPUTE_COUNT"] = len(computes)
    for index, compute in enumerate(computes):
        env[f"COMPUTE_{index}_NAME"] = compute["name"]
        for name, address in compute["ips"].items():
            env[f"COMPUTE_{index}_{name.upper()}_IP"] = address
    return {key: str(value) for key, value in env.items()}


def main() -> int:
    try:
        lab = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        print(f"Invalid JSON on stdin: {error}", file=sys.stderr)
        return 1
    try:
        env = flatten(lab)
    except KeyError as error:
        print(f"Unexpected Terraform output, missing key: {error}", file=sys.stderr)
        return 1
    print("# Generated from the Terraform outputs. Do not edit.")
    for key, value in env.items():
        print(f"{key}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
