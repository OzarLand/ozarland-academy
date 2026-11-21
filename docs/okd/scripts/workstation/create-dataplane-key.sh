#!/usr/bin/env bash
# Workstation step: create the SSH key pair the data plane Ansible jobs use
# to reach compute nodes. Terraform injects the public key into the compute
# nodes; the private key later becomes a Secret in the cluster.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
# shellcheck source=scripts/workstation/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

require_cmd ssh-keygen
mkdir -p "${WORK_DIR}"
chmod 700 "${WORK_DIR}"

if [[ -f "${DATAPLANE_KEY_FILE}" ]]; then
  info "Data plane key already exists: ${DATAPLANE_KEY_FILE}"
else
  ssh-keygen -q -t ed25519 -N '' -C 'openstack-dataplane' -f "${DATAPLANE_KEY_FILE}"
  info "Created ${DATAPLANE_KEY_FILE}"
fi
