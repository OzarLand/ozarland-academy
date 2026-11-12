#!/usr/bin/env bash
# Bastion step 2: build the agent-based installer ISO.
#
# The ISO contains everything the VM needs to turn itself into a single-node
# cluster: the node's static network configuration, the cluster settings and
# short-lived bootstrap certificates (valid 24 hours - boot it the same day).

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

load_config
require_infra_config
require_cmd openshift-install nmstatectl
require_var NTP_SERVER
# The installer downloads the release content (and the base ISO) itself.
use_proxy

install_dir="${WORK_DIR}/okd/install"
templates="${REPO_ROOT}/deployment/okd/agent-installer"

if [[ -f "${install_dir}/auth/kubeconfig" && "${1:-}" != "--force" ]]; then
  die "An installation already exists in ${install_dir}. Re-run with --force to discard it and build a new ISO."
fi

# The node is reachable as core@<node> with a key that lives on the bastion.
ssh_key="${HOME}/.ssh/id_ed25519"
if [[ ! -f "${ssh_key}" ]]; then
  ssh-keygen -q -t ed25519 -N '' -C "bastion@${CLUSTER_DOMAIN}" -f "${ssh_key}"
fi
OKD_SSH_PUBLIC_KEY="$(<"${ssh_key}.pub")"
MACHINE_PREFIX="$(cidr_prefix "${MACHINE_CIDR}")"
CTLPLANE_PREFIX="$(cidr_prefix "${CTLPLANE_CIDR}")"
INTERNALAPI_PREFIX="$(cidr_prefix "${INTERNALAPI_CIDR}")"
TENANT_PREFIX="$(cidr_prefix "${TENANT_CIDR}")"
export OKD_SSH_PUBLIC_KEY MACHINE_PREFIX CTLPLANE_PREFIX INTERNALAPI_PREFIX TENANT_PREFIX

rm -rf "${install_dir}"
mkdir -p "${install_dir}"
render_template "${templates}/install-config.yaml.tmpl" "${install_dir}/install-config.yaml"
if proxy_enabled; then
  # Cluster-wide proxy: the node pulls its images through it, during the
  # installation and afterwards.
  render_template "${templates}/install-config-proxy.yaml.tmpl" "${install_dir}/install-config-proxy.yaml"
  cat "${install_dir}/install-config-proxy.yaml" >>"${install_dir}/install-config.yaml"
  rm "${install_dir}/install-config-proxy.yaml"
fi
render_template "${templates}/agent-config.yaml.tmpl" "${install_dir}/agent-config.yaml"
# openshift-install consumes (deletes) its input files: keep a copy for review.
mkdir -p "${WORK_DIR}/okd/rendered"
cp "${install_dir}/install-config.yaml" "${install_dir}/agent-config.yaml" "${WORK_DIR}/okd/rendered/"

info "Building the agent ISO (downloads the base image on first run)"
openshift-install agent create image --dir "${install_dir}" --log-level info

mv "${install_dir}/agent.x86_64.iso" "${WORK_DIR}/okd/agent.x86_64.iso"
info "ISO ready: ${WORK_DIR}/okd/agent.x86_64.iso"
info "Next, on the workstation: scripts/workstation/boot-okd-node.sh"
