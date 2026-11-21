#!/usr/bin/env bash
# Bastion step 3: follow the OKD installation until the cluster is usable,
# then install the kubeconfig for the bastion user.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

load_config
require_infra_config
require_cmd openshift-install oc

install_dir="${WORK_DIR}/okd/install"
[[ -f "${install_dir}/auth/kubeconfig" ]] || die "No installation found in ${install_dir}. Run 02-create-agent-iso.sh first."

info "Waiting for the bootstrap phase (the node installs itself to disk and reboots)"
openshift-install agent wait-for bootstrap-complete --dir "${install_dir}" --log-level info

info "Waiting for all cluster operators (typically 30-60 minutes in total)"
openshift-install agent wait-for install-complete --dir "${install_dir}" --log-level info

mkdir -p "${HOME}/.kube"
install -m 0600 "${install_dir}/auth/kubeconfig" "${HOME}/.kube/config"

info "Cluster is installed"
oc get clusterversion
oc get nodes -o wide
info "Console: https://console-openshift-console.apps.${CLUSTER_DOMAIN}"
info "kubeadmin password file: ${install_dir}/auth/kubeadmin-password"
