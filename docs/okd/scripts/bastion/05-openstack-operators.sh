#!/usr/bin/env bash
# Bastion step 5: install the OpenStack operators.
#
# Two stages:
#   a. OLM installs the single "openstack-operator" bundle from the catalog.
#   b. The OpenStack initialization resource makes that operator deploy the
#      per-service operators.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

load_config
require_cmd oc jq
require_var OPENSTACK_OPERATOR_INDEX OPENSTACK_OPERATOR_CHANNEL BAREMETAL_OPERATOR_VERSION
# oc downloads the BareMetalHost CRD itself.
use_proxy

ns=openstack-operators
rendered="${WORK_DIR}/rendered/openstack"
manifests="${REPO_ROOT}/deployment/openstack/operators"

# Approve the install plan of the first installation only. Once an operator
# version is installed, a pending plan is an upgrade: that stays a deliberate
# operation (docs/lifecycle/02-operator-upgrade.md), even when this script
# is run again.
approve_initial_install_plan() {
  local subscription plan
  subscription="$(oc -n "${ns}" get subscription openstack-operator -o json)"
  [[ -z "$(jq -r '.status.installedCSV // empty' <<<"${subscription}")" ]] || return 0
  plan="$(jq -r '.status.installPlanRef.name // empty' <<<"${subscription}")"
  [[ -n "${plan}" ]] || return 0
  if [[ "$(oc -n "${ns}" get installplan "${plan}" -o jsonpath='{.spec.approved}')" == "false" ]]; then
    info "Approving install plan ${plan}"
    oc -n "${ns}" patch installplan "${plan}" --type=merge --patch '{"spec":{"approved":true}}'
  fi
}

csv_succeeded() {
  approve_initial_install_plan
  oc -n "${ns}" get csv -o json |
    jq -e '[.items[] | select(.metadata.name | startswith("openstack-operator"))] | length > 0 and all(.status.phase == "Succeeded")'
}

openstack_ready() {
  oc -n "${ns}" get openstack openstack -o json |
    jq -e '.status.conditions[]? | select(.type == "Ready") | .status == "True"'
}

info "Subscribing to the OpenStack operator (${OPENSTACK_OPERATOR_INDEX})"
render_template "${manifests}/operators.yaml.tmpl" "${rendered}/operators.yaml"
oc apply -f "${rendered}/operators.yaml"
wait_until "openstack-operator ClusterServiceVersion Succeeded" 900 csv_succeeded

# The bare metal provisioning operator is always deployed and fails to start
# when the Metal3 BareMetalHost CRD is absent. OKD 4.22 ships the CRD even
# on a platform "none" cluster; it is installed here only when missing.
# The lab never uses it.
if ! oc get crd baremetalhosts.metal3.io >/dev/null 2>&1; then
  info "Installing the BareMetalHost CRD"
  oc apply -f "https://raw.githubusercontent.com/metal3-io/baremetal-operator/${BAREMETAL_OPERATOR_VERSION}/config/base/crds/bases/metal3.io_baremetalhosts.yaml"
fi

info "Deploying the service operators"
oc apply -f "${manifests}/openstack.yaml"
wait_until "all OpenStack service operators Ready" 1200 openstack_ready

info "OpenStack operators are running"
oc -n "${ns}" get csv
oc -n "${ns}" get pods
