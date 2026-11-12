#!/usr/bin/env bash
# Offline check: render every manifest template with sample values and make
# sure the result is valid YAML. Catches undefined variables and indentation
# mistakes without needing a cluster. Used by CI and `make lint`.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/lib/common.sh"

require_cmd envsubst yamllint

out="$(mktemp -d)"
trap 'rm -rf "${out}"' EXIT

WORK_DIR="${out}/work"
LAB_ENV_FILE="${REPO_ROOT}/config/lab.env.example"
INFRA_ENV_FILE="${WORK_DIR}/infra.env"
mkdir -p "${WORK_DIR}"
cp "${REPO_ROOT}/tests/fixtures/infra.env" "${INFRA_ENV_FILE}"
load_config
# shellcheck source=scripts/lib/addressing.sh
source "${REPO_ROOT}/scripts/lib/addressing.sh"

# Optional settings that are empty by default but have their own template.
HTTP_PROXY_URL=http://proxy.example.com:3128

# Values normally computed at run time by the deployment scripts.
export OKD_SSH_PUBLIC_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleKeyOnly test"
export MACHINE_PREFIX=24 CTLPLANE_PREFIX=24 INTERNALAPI_PREFIX=24 TENANT_PREFIX=24
export CTLPLANE_IFACE=enp2s0 INTERNALAPI_IFACE=enp3s0 TENANT_IFACE=enp4s0
export OKD_NODE_HOSTNAME=okd-0 STORAGE_PV_BASE_DIR=/var/lib/openstack-lab-pv PV_INDEX=01
export EDPM_PLAYBOOK_ENVIRONMENT='{"https_proxy":"http://proxy.example.com:3128"}'
export NOVA_VIRT_TYPE=qemu NOVA_CPU_MODE=none DATAPLANE_DEPLOYMENT_NAME=edpm-deployment
export DATAPLANE_NODES="    edpm-compute-0:
      hostName: edpm-compute-0
      ansible:
        ansibleHost: 192.168.122.100"

status=0
while IFS= read -r template; do
  target="${out}/rendered/${template#"${REPO_ROOT}/"}"
  target="${target%.tmpl}"
  if render_template "${template}" "${target}" && yamllint -c "${REPO_ROOT}/.yamllint" "${target}"; then
    info "ok   ${template#"${REPO_ROOT}/"}"
  else
    warn "FAIL ${template#"${REPO_ROOT}/"}"
    status=1
  fi
done < <(find "${REPO_ROOT}/deployment" -name '*.yaml.tmpl' | sort)

exit "${status}"
