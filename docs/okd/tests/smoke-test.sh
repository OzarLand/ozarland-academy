#!/usr/bin/env bash
# Verify that the lab is operational. Run on the bastion.
#
#   tests/smoke-test.sh               read-only checks of every layer
#   tests/smoke-test.sh --functional  additionally boots a test instance
#                                     (creates and deletes OpenStack resources)
#
# Each check prints PASS, FAIL or SKIP; the exit code is the number of
# failures. The checks follow the layers bottom-up, which is also the order
# to investigate in when something is broken.

# Check functions are invoked indirectly through check(). ShellCheck reports
# this as SC2329 from 0.11 and as SC2317 in earlier releases.
# shellcheck disable=SC2317,SC2329

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../scripts/lib/common.sh"

load_config
require_infra_config
require_cmd oc jq

functional=false
[[ "${1:-}" == "--functional" ]] && functional=true

failures=0
ns=openstack

check() {
  local description="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    printf 'PASS  %s\n' "${description}"
  else
    printf 'FAIL  %s\n' "${description}"
    failures=$((failures + 1))
  fi
}

skip() { printf 'SKIP  %s\n' "$1"; }

osc() { oc -n "${ns}" exec openstackclient -c openstackclient -- openstack "$@"; }

condition_true() { # <namespace> <resource> <name> <condition>
  oc -n "$1" get "$2" "$3" -o json | jq -e --arg type "$4" \
    '.status.conditions[] | select(.type == $type) | .status == "True"'
}

# --- OKD ---------------------------------------------------------------------
nodes_ready() {
  oc get nodes -o json | jq -e '.items | length > 0 and all(.[]; any(.status.conditions[]; .type == "Ready" and .status == "True"))'
}
cluster_operators_healthy() {
  oc get clusteroperators -o json | jq -e '.items | all(
    (.status.conditions[] | select(.type == "Available") | .status) == "True" and
    (.status.conditions[] | select(.type == "Degraded") | .status) == "False")'
}
check "OKD: all nodes Ready" nodes_ready
check "OKD: all cluster operators Available and not Degraded" cluster_operators_healthy

# --- Platform services -------------------------------------------------------
pvs_usable() {
  oc get pv -o json | jq -e '[.items[] | select(.spec.storageClassName == "local-storage")] | length > 0 and all(.status.phase == "Available" or .status.phase == "Bound")'
}
check "Storage: local-storage volumes are Available or Bound" pvs_usable
check "cert-manager: deployments Available" oc -n cert-manager wait deployment --all --for=condition=Available --timeout=5s
check "MetalLB: controller Available" oc -n metallb-system wait deployment/controller --for=condition=Available --timeout=5s

# --- Operators ---------------------------------------------------------------
csv_succeeded() {
  oc -n openstack-operators get csv -o json | jq -e '.items | length > 0 and all(.status.phase == "Succeeded")'
}
check "Operators: ClusterServiceVersion Succeeded" csv_succeeded
check "Operators: OpenStack initialization resource Ready" condition_true openstack-operators openstack openstack Ready

# --- Control plane -----------------------------------------------------------
pods_healthy() {
  oc -n "${ns}" get pods -o json | jq -e '.items | all(
    .status.phase == "Succeeded" or
    (.status.phase == "Running" and all(.status.containerStatuses[]; .ready)))'
}
load_balancers_assigned() {
  oc -n "${ns}" get services -o json | jq -e '[.items[] | select(.spec.type == "LoadBalancer")] | length > 0 and all(.status.loadBalancer.ingress | length > 0)'
}
check "Control plane: OpenStackControlPlane Ready" condition_true "${ns}" openstackcontrolplane openstack Ready
check "Control plane: all pods Running and ready" pods_healthy
check "Control plane: LoadBalancer services have an address" load_balancers_assigned
check "Control plane: Keystone issues a token" osc token issue
check "Control plane: service catalog lists compute" osc endpoint list --service compute

# --- Data plane --------------------------------------------------------------
compute_services_up() {
  osc compute service list --service nova-compute -f json | jq -e 'length > 0 and all(.State == "up")'
}
network_agents_alive() {
  osc network agent list -f json | jq -e 'length > 0 and all(.Alive == true)'
}
if oc -n "${ns}" get openstackdataplanenodeset openstack-edpm >/dev/null 2>&1; then
  check "Data plane: NodeSet Ready" condition_true "${ns}" openstackdataplanenodeset openstack-edpm Ready
  check "Data plane: nova-compute services up" compute_services_up
  check "Data plane: OVN agents alive" network_agents_alive
else
  skip "Data plane: no NodeSet deployed"
  functional=false
fi

# --- Functional test (modifies OpenStack) ------------------------------------
functional_test() {
  local image_url="https://download.cirros-cloud.net/0.6.3/cirros-0.6.3-x86_64-disk.img"
  local prefix="smoke-$$" status=1
  # Resource creation happens inside the openstackclient pod.
  oc -n "${ns}" exec openstackclient -c openstackclient -- bash -euc "
    cleanup() {
      openstack server delete --wait ${prefix}-vm 2>/dev/null || true
      openstack subnet delete ${prefix}-subnet 2>/dev/null || true
      openstack network delete ${prefix}-net 2>/dev/null || true
      openstack flavor delete ${prefix}-flavor 2>/dev/null || true
      openstack image delete ${prefix}-image 2>/dev/null || true
    }
    trap cleanup EXIT
    curl -fsSL ${HTTP_PROXY_URL:+--proxy ${HTTP_PROXY_URL}} -o /tmp/${prefix}.img ${image_url}
    openstack image create ${prefix}-image --disk-format qcow2 --container-format bare --file /tmp/${prefix}.img
    rm -f /tmp/${prefix}.img
    openstack flavor create ${prefix}-flavor --vcpus 1 --ram 256 --disk 1
    openstack network create ${prefix}-net
    openstack subnet create ${prefix}-subnet --network ${prefix}-net --subnet-range 10.99.0.0/24
    openstack server create ${prefix}-vm --image ${prefix}-image --flavor ${prefix}-flavor --network ${prefix}-net --wait
    test \"\$(openstack server show ${prefix}-vm -f value -c status)\" = ACTIVE
  " && status=0
  return "${status}"
}
if "${functional}"; then
  check "Functional: boot an instance on a tenant network" functional_test
else
  skip "Functional: instance boot test (run with --functional on a lab with a data plane)"
fi

printf '\n%d check(s) failed\n' "${failures}"
exit "${failures}"
