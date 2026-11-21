#!/usr/bin/env bash
# Bastion step 4: prepare OKD to host OpenStack.
#
# The OpenStack operators expect four things from the platform that a fresh
# OKD cluster does not provide:
#   1. persistent storage      -> local PersistentVolumes on the node
#   2. certificate management  -> cert-manager
#   3. service IPs on the OpenStack networks -> MetalLB
#   4. IP forwarding between the node interfaces and the pod network
#
# Every action is idempotent: the script can be re-run after a failure.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

load_config
require_infra_config
# shellcheck source=scripts/lib/addressing.sh
source "${REPO_ROOT}/scripts/lib/addressing.sh"
require_cmd oc jq
require_var CERT_MANAGER_VERSION METALLB_VERSION FRR_K8S_VERSION STORAGE_PV_COUNT STORAGE_PV_SIZE
[[ "${STORAGE_PV_COUNT}" =~ ^[1-9][0-9]?$ ]] || die "STORAGE_PV_COUNT must be a number between 1 and 99 (got '${STORAGE_PV_COUNT}')"
# oc downloads the cert-manager and MetalLB manifests itself.
use_proxy

rendered="${WORK_DIR}/rendered/okd"
node="$(oc get nodes -o jsonpath='{.items[0].metadata.name}')"
OKD_NODE_HOSTNAME="$(oc get node "${node}" -o jsonpath='{.metadata.labels.kubernetes\.io/hostname}')"
STORAGE_PV_BASE_DIR=/var/lib/openstack-lab-pv
export OKD_NODE_HOSTNAME STORAGE_PV_BASE_DIR

# Run a command on the node's host OS through a temporary privileged pod.
on_node() {
  oc debug "node/${node}" --quiet -- chroot /host bash -c "$1"
}

discover_interfaces() {
  local addresses name ip_var iface
  info "Discovering the node interface of each OpenStack network"
  addresses="$(on_node 'ip -json -4 address show')" || die "Could not run a command on ${node} (oc debug)"
  # Written to a temporary file first: a failed run must not leave a partial
  # file behind for the next steps to read.
  : >"${WORK_DIR}/okd-interfaces.env.tmp"
  for name in CTLPLANE INTERNALAPI TENANT; do
    ip_var="${name}_OKD_IP"
    iface="$(jq -r --arg ip "${!ip_var}" '.[] | select(any(.addr_info[]; .local == $ip)) | .ifname' <<<"${addresses}")"
    [[ -n "${iface}" ]] || die "No interface on ${node} carries ${!ip_var} (${name})"
    printf '%s_IFACE=%s\n' "${name}" "${iface}" >>"${WORK_DIR}/okd-interfaces.env.tmp"
    info "  ${name}: ${iface} (${!ip_var})"
  done
  mv "${WORK_DIR}/okd-interfaces.env.tmp" "${WORK_DIR}/okd-interfaces.env"
  set -a
  # shellcheck source=/dev/null
  source "${WORK_DIR}/okd-interfaces.env"
  set +a
}

enable_ip_forwarding() {
  info "Enabling IP forwarding and host routing in OVN-Kubernetes"
  # ipForwarding=Global lets traffic arriving on the OpenStack network
  # interfaces reach MetalLB service IPs. routingViaHost=true makes pod
  # egress follow the node routing table, so pods reach the OpenStack
  # networks through the node interfaces.
  oc patch network.operator cluster --type=merge --patch \
    '{"spec":{"defaultNetwork":{"ovnKubernetesConfig":{"gatewayConfig":{"routingViaHost":true,"ipForwarding":"Global"}}}}}'
}

create_storage() {
  local index
  info "Creating ${STORAGE_PV_COUNT} local persistent volumes of ${STORAGE_PV_SIZE}"
  # container_file_t is the SELinux type pods are allowed to write to.
  # Only new or still empty directories are prepared: on a re-run, the data
  # that services already wrote keeps its owner, mode and label, while a
  # directory left half-prepared by an interrupted run is repaired.
  on_node "set -e
    for i in \$(seq 1 ${STORAGE_PV_COUNT}); do
      dir=${STORAGE_PV_BASE_DIR}/pv\$(printf '%02d' \$i)
      [ -d \$dir ] && [ -n \"\$(ls -A \$dir)\" ] && continue
      mkdir -p \$dir
      chmod 0777 \$dir
      chcon -t container_file_t \$dir
    done" || die "Could not create the volume directories on ${node}"
  oc apply -f "${REPO_ROOT}/deployment/okd/storage/storageclass.yaml"
  # Start from an empty directory so that a lower STORAGE_PV_COUNT does not
  # re-apply volumes rendered by an earlier run.
  rm -rf "${rendered}/storage"
  for ((index = 1; index <= STORAGE_PV_COUNT; index++)); do
    PV_INDEX="$(printf '%02d' "${index}")"
    export PV_INDEX
    render_template "${REPO_ROOT}/deployment/okd/storage/persistentvolume.yaml.tmpl" "${rendered}/storage/pv${PV_INDEX}.yaml"
  done
  oc apply -f "${rendered}/storage/"
}

install_cert_manager() {
  info "Installing cert-manager ${CERT_MANAGER_VERSION}"
  oc apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
  oc -n cert-manager wait deployment --all --for=condition=Available --timeout=300s
}

install_metallb() {
  info "Installing MetalLB ${METALLB_VERSION}"
  oc apply -f "https://raw.githubusercontent.com/metallb/metallb/${METALLB_VERSION}/config/manifests/metallb-native.yaml"
  # The upstream manifests assume plain Kubernetes. On OKD, pods run under
  # Security Context Constraints: the speaker needs host networking and raw
  # sockets (privileged), the controller a fixed non-root UID.
  oc adm policy add-scc-to-user privileged -n metallb-system -z speaker
  oc adm policy add-scc-to-user nonroot-v2 -n metallb-system -z controller
  oc -n metallb-system rollout status deployment/controller --timeout=300s
  oc -n metallb-system rollout status daemonset/speaker --timeout=300s
  # The OpenStack infra-operator watches FRRConfiguration resources (BGP
  # announcements) and restarts in a loop when the kind does not exist. The
  # lab announces addresses with ARP (layer 2) only, so the definition alone
  # is installed, without the frr-k8s daemon.
  oc apply -f "https://raw.githubusercontent.com/metallb/frr-k8s/${FRR_K8S_VERSION}/config/crd/bases/frrk8s.metallb.io_frrconfigurations.yaml"
  render_template "${REPO_ROOT}/deployment/okd/metallb/address-pools.yaml.tmpl" "${rendered}/metallb/address-pools.yaml"
  # The validating webhook needs a moment after the controller starts.
  wait_until "MetalLB address pools accepted" 180 oc apply -f "${rendered}/metallb/address-pools.yaml"
}

discover_interfaces
enable_ip_forwarding
create_storage
install_cert_manager
install_metallb

info "Platform services are ready"
oc get storageclass,pv
oc -n metallb-system get ipaddresspools,l2advertisements
