#!/usr/bin/env bash
# Bastion step 7: turn the compute VMs into OpenStack compute nodes.
#
#   1. secrets: SSH key for Ansible, SSH key for nova live migration,
#      libvirt password
#   2. nova-compute settings (hypervisor type)
#   3. OpenStackDataPlaneNodeSet (what) + OpenStackDataPlaneDeployment (run it)
#   4. register the new hypervisors in nova (cell discovery)
#
# Usage: 07-openstack-dataplane.sh [deployment-name]
# A deployment is immutable; pass a new name to run the services again.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

load_config
require_infra_config
# shellcheck source=scripts/lib/addressing.sh
source "${REPO_ROOT}/scripts/lib/addressing.sh"
require_cmd oc jq ssh ssh-keygen openssl
require_var COMPUTE_COUNT DATAPLANE_USER NTP_SERVER COMPUTE_VIRT_TYPE

((COMPUTE_COUNT > 0)) || die "The infrastructure has no compute node (compute_count = 0)."

ns=openstack
rendered="${WORK_DIR}/rendered/openstack"
manifests="${REPO_ROOT}/deployment/openstack/dataplane"
dataplane_key="${WORK_DIR}/dataplane-ssh-key"
DATAPLANE_DEPLOYMENT_NAME="${1:-edpm-deployment}"
export DATAPLANE_DEPLOYMENT_NAME

[[ -f "${dataplane_key}" ]] || die "Missing ${dataplane_key}. Re-run scripts/workstation/sync-to-bastion.sh."

compute_ssh() {
  local ip="$1"
  shift
  ssh -i "${dataplane_key}" -o StrictHostKeyChecking=accept-new -o BatchMode=yes \
    -o "UserKnownHostsFile=${WORK_DIR}/known_hosts" -o ConnectTimeout=10 \
    "${DATAPLANE_USER}@${ip}" "$@"
}

create_secrets() {
  local tmp
  if ! oc -n "${ns}" get secret dataplane-ansible-ssh-private-key-secret >/dev/null 2>&1; then
    info "Creating the Ansible SSH key Secret"
    oc -n "${ns}" create secret generic dataplane-ansible-ssh-private-key-secret \
      --from-file=ssh-privatekey="${dataplane_key}" \
      --from-file=ssh-publickey="${dataplane_key}.pub" \
      --from-file=authorized_keys="${dataplane_key}.pub"
  fi
  if ! oc -n "${ns}" get secret nova-migration-ssh-key >/dev/null 2>&1; then
    info "Creating the nova live migration SSH key Secret"
    tmp="$(mktemp -d)"
    ssh-keygen -q -t ecdsa -b 521 -N '' -f "${tmp}/id"
    oc -n "${ns}" create secret generic nova-migration-ssh-key \
      --type kubernetes.io/ssh-auth \
      --from-file=ssh-privatekey="${tmp}/id" \
      --from-file=ssh-publickey="${tmp}/id.pub"
    rm -rf "${tmp}"
  fi
  # Required by the stock "libvirt" data plane service (libvirt SASL
  # authentication, used for live migration).
  if ! oc -n "${ns}" get secret libvirt-secret >/dev/null 2>&1; then
    info "Generating the libvirt password into Secret libvirt-secret"
    printf 'LibvirtPassword=%s\n' "$(openssl rand -hex 16)" |
      oc -n "${ns}" create secret generic libvirt-secret --from-env-file=/dev/stdin
  fi
}

# Proxy settings for the Ansible plays, as a JSON object: every stock
# playbook runs its tasks with the environment variables found in
# edpm_playbook_environment (package and container image downloads).
playbook_environment() {
  if proxy_enabled; then
    jq -cn --arg proxy "${HTTP_PROXY_URL}" --arg no_proxy "${NO_PROXY_LIST}" \
      '{http_proxy: $proxy, https_proxy: $proxy, no_proxy: $no_proxy,
        HTTP_PROXY: $proxy, HTTPS_PROXY: $proxy, NO_PROXY: $no_proxy}'
  else
    printf '{}'
  fi
}

# Decide between KVM and software emulation by looking at the first node.
configure_hypervisor() {
  local virt_type="${COMPUTE_VIRT_TYPE}" ip_var="COMPUTE_0_CTLPLANE_IP" rc=0
  if [[ "${virt_type}" == "auto" ]]; then
    compute_ssh "${!ip_var}" "grep -qE 'vmx|svm' /proc/cpuinfo" || rc=$?
    # grep answers 0 (found) or 1 (not found); anything else means the
    # question was not asked (ssh failure is 255): do not guess.
    case "${rc}" in
      0) virt_type=kvm ;;
      1) virt_type=qemu ;;
      *) die "Could not check hardware virtualization on ${!ip_var} (ssh exit code ${rc})" ;;
    esac
    info "Compute nodes expose $([[ ${virt_type} == kvm ]] && echo 'hardware virtualization: using KVM' || echo 'no hardware virtualization: using QEMU emulation')"
  fi
  case "${virt_type}" in
    # kvm and host-model are the operator defaults, written explicitly because
    # the same snippet also carries the live migration address.
    kvm) export NOVA_VIRT_TYPE=kvm NOVA_CPU_MODE=host-model ;;
    qemu) export NOVA_VIRT_TYPE=qemu NOVA_CPU_MODE=none ;;
    *) die "COMPUTE_VIRT_TYPE must be kvm, qemu or auto (got '${virt_type}')" ;;
  esac
  render_template "${manifests}/nova-extra-config.yaml.tmpl" "${rendered}/nova-extra-config.yaml"
  oc apply -f "${rendered}/nova-extra-config.yaml"
}

# Build the "nodes" section of the NodeSet from the Terraform facts.
render_nodes() {
  local index ip_var
  for ((index = 0; index < COMPUTE_COUNT; index++)); do
    ip_var="COMPUTE_${index}_CTLPLANE_IP"
    cat <<NODE
    edpm-compute-${index}:
      hostName: edpm-compute-${index}
      ansible:
        ansibleHost: ${!ip_var}
      networks:
        - name: ctlplane
          subnetName: subnet1
          defaultRoute: true
          fixedIP: ${!ip_var}
        - name: internalapi
          subnetName: subnet1
          fixedIP: $(node_ip "${index}" INTERNALAPI)
        - name: tenant
          subnetName: subnet1
          fixedIP: $(node_ip "${index}" TENANT)
NODE
  done
}

node_ip() {
  local var="COMPUTE_$1_$2_IP"
  printf '%s' "${!var}"
}

deployment_finished() {
  oc -n "${ns}" get openstackdataplanedeployment "${DATAPLANE_DEPLOYMENT_NAME}" -o json |
    jq -e '.status.conditions[] | select(.type == "Ready") | .status == "True" or .reason == "BackoffLimitExceeded"'
}

info "Checking SSH access to the compute nodes"
for ((i = 0; i < COMPUTE_COUNT; i++)); do
  ip_var="COMPUTE_${i}_CTLPLANE_IP"
  wait_until "SSH on ${!ip_var}" 300 compute_ssh "${!ip_var}" true
done

create_secrets
configure_hypervisor

info "Applying data plane services and NodeSet"
oc apply -f "${manifests}/services.yaml"
DATAPLANE_NODES="$(render_nodes)"
EDPM_PLAYBOOK_ENVIRONMENT="$(playbook_environment)"
export DATAPLANE_NODES EDPM_PLAYBOOK_ENVIRONMENT
render_template "${manifests}/nodeset.yaml.tmpl" "${rendered}/nodeset.yaml"
oc apply -f "${rendered}/nodeset.yaml"
wait_until "NodeSet inputs validated (SetupReady)" 300 \
  oc -n "${ns}" wait openstackdataplanenodeset openstack-edpm --for=condition=SetupReady --timeout=5s

if oc -n "${ns}" get openstackdataplanedeployment "${DATAPLANE_DEPLOYMENT_NAME}" >/dev/null 2>&1; then
  info "Deployment ${DATAPLANE_DEPLOYMENT_NAME} already exists; waiting for it"
else
  info "Starting deployment ${DATAPLANE_DEPLOYMENT_NAME}"
  render_template "${manifests}/deployment.yaml.tmpl" "${rendered}/deployment-${DATAPLANE_DEPLOYMENT_NAME}.yaml"
  oc apply -f "${rendered}/deployment-${DATAPLANE_DEPLOYMENT_NAME}.yaml"
fi

info "Follow the Ansible jobs from another terminal with:"
info "  oc -n ${ns} get pods -l app=openstackansibleee -w"
wait_until "data plane deployment to finish" 5400 deployment_finished

if ! oc -n "${ns}" wait openstackdataplanedeployment "${DATAPLANE_DEPLOYMENT_NAME}" --for=condition=Ready --timeout=5s >/dev/null 2>&1; then
  oc -n "${ns}" get openstackdataplanedeployment "${DATAPLANE_DEPLOYMENT_NAME}" -o json |
    jq -r '.status.conditions[] | select(.status != "True") | "  \(.type): \(.reason) - \(.message)"' >&2
  die "Data plane deployment failed. See docs/troubleshooting/dataplane.md"
fi

info "Registering the compute hosts in nova (cell discovery)"
oc -n "${ns}" exec nova-cell0-conductor-0 -- nova-manage cell_v2 discover_hosts --verbose
oc -n "${ns}" exec openstackclient -c openstackclient -- openstack compute service list
oc -n "${ns}" exec openstackclient -c openstackclient -- openstack network agent list
