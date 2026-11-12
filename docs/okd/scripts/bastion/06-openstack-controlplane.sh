#!/usr/bin/env bash
# Bastion step 6: deploy the OpenStack control plane.
#
#   1. namespace + passwords (osp-secret)
#   2. networks (NetworkAttachmentDefinitions, NetConfig)
#   3. the OpenStackControlPlane custom resource
# Then wait for the operators to converge.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

load_config
require_infra_config
# shellcheck source=scripts/lib/addressing.sh
source "${REPO_ROOT}/scripts/lib/addressing.sh"
require_cmd oc jq openssl

[[ -f "${WORK_DIR}/okd-interfaces.env" ]] || die "Missing ${WORK_DIR}/okd-interfaces.env. Run 04-platform-services.sh first."
set -a
# shellcheck source=/dev/null
source "${WORK_DIR}/okd-interfaces.env"
set +a

ns=openstack
rendered="${WORK_DIR}/rendered/openstack"
manifests="${REPO_ROOT}/deployment/openstack/controlplane"

random_password() { openssl rand -hex 16; }

# Passwords are generated once, directly into the cluster. They are never
# written to disk on the bastion nor stored in Git, and they are passed to oc
# through a pipe rather than on its command line, where other users of the
# bastion could read them. To read one back:
#   oc -n openstack get secret osp-secret -o jsonpath='{.data.AdminPassword}' | base64 -d
create_osp_secret() {
  local key
  if oc -n "${ns}" get secret osp-secret >/dev/null 2>&1; then
    info "Secret osp-secret already exists; keeping the existing passwords"
    return
  fi
  info "Generating service passwords into Secret osp-secret"
  {
    for key in AdminPassword DbRootPassword DatabasePassword MetadataSecret \
      KeystonePassword PlacementPassword GlancePassword NeutronPassword NovaPassword \
      CinderPassword SwiftPassword BarbicanPassword CeilometerPassword AodhPassword \
      HeatPassword HeatStackDomainAdminPassword ManilaPassword OctaviaPassword \
      DesignatePassword IronicPassword IronicInspectorPassword; do
      printf '%s=%s\n' "${key}" "$(random_password)"
    done
    # Keys with format constraints (32-byte values).
    printf 'HeatAuthEncryptionKey=%s\n' "$(openssl rand -hex 16)"
    printf 'BarbicanSimpleCryptoKEK=%s\n' "$(openssl rand -base64 32)"
  } | oc -n "${ns}" create secret generic osp-secret --from-env-file=/dev/stdin
}

controlplane_ready() {
  oc -n "${ns}" get openstackcontrolplane openstack -o json |
    jq -e '.status.conditions[] | select(.type == "Ready") | .status == "True"'
}

print_not_ready_conditions() {
  oc -n "${ns}" get openstackcontrolplane openstack -o json |
    jq -r '.status.conditions[] | select(.status != "True") | "  \(.type): \(.reason) - \(.message)"' >&2 || true
}

oc apply -f "${manifests}/namespace.yaml"
create_osp_secret

info "Applying networks"
render_template "${manifests}/networks.yaml.tmpl" "${rendered}/networks.yaml"
oc apply -f "${rendered}/networks.yaml"

info "Applying the OpenStackControlPlane"
render_template "${manifests}/openstackcontrolplane.yaml.tmpl" "${rendered}/openstackcontrolplane.yaml"
oc apply -f "${rendered}/openstackcontrolplane.yaml"

# Run the wait in a subshell so that a timeout can be reported with details.
if ! (wait_until "OpenStackControlPlane Ready" 2400 controlplane_ready); then
  warn "Control plane conditions that are not True:"
  print_not_ready_conditions
  die "The control plane did not become Ready. See docs/troubleshooting/"
fi

info "Control plane is ready"
oc -n "${ns}" get openstackcontrolplane
oc -n "${ns}" exec openstackclient -c openstackclient -- openstack endpoint list
