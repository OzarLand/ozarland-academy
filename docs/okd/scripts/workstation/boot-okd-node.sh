#!/usr/bin/env bash
# Workstation step: fetch the agent installer ISO built on the bastion,
# upload it to the image service and create the OKD node booting from it.
#
# This is the only step that needs both cloud credentials (workstation) and
# an artifact produced on the bastion, which is why it is split this way.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
# shellcheck source=scripts/workstation/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

load_config
require_cmd "${TERRAFORM}" openstack ssh scp
require_var SSH_PRIVATE_KEY_FILE BASTION_USER

iso_local="${WORK_DIR}/agent.x86_64.iso"
tfvars_file="${TF_DIR}/agent-iso.auto.tfvars"
name_prefix="$("${TERRAFORM}" -chdir="${TF_DIR}" output -raw name_prefix)"
iso_prefix="${name_prefix}-agent-iso-"

if [[ "$("${TERRAFORM}" -chdir="${TF_DIR}" output -raw okd_node_created)" == "true" ]]; then
  info "The OKD node already exists; nothing to do."
  info "To reinstall the cluster, destroy the node first (see docs/installation/02-okd.md)."
  exit 0
fi

info "Fetching the agent ISO from the bastion"
bastion_scp_from "${BASTION_REPO_DIR}/.work/okd/agent.x86_64.iso" "${iso_local}"

if [[ "${ISO_BLANK_SYSTEM_AREA:-false}" == "true" ]]; then
  # A "hybrid" ISO starts with a disk partition table in the first 32 KiB
  # (the system area, unused by the ISO 9660 format itself) so that it can
  # also be written to a USB stick. Blanking it leaves a plain CD-ROM image,
  # which still boots: CD-ROM boot uses the El Torito catalog further on.
  info "Blanking the system area of the ISO"
  dd if=/dev/zero of="${iso_local}" bs=32k count=1 conv=notrunc status=none
fi

# The ISO embeds certificates valid for 24 hours: always upload the fresh one
# under a new name instead of reusing an older image.
image_name="${iso_prefix}$(date -u +%Y%m%d%H%M%S)"
info "Uploading ${image_name} to the image service"
image_id="$(openstack image create "${image_name}" \
  --disk-format iso --container-format bare --private \
  --file "${iso_local}" -f value -c id)"

printf 'agent_iso_image_id = "%s"\n' "${image_id}" >"${tfvars_file}"
info "Creating the OKD node"
# -target: create the node only. Any other difference between the Terraform
# files and the cloud is left for a deliberate "terraform apply".
"${TERRAFORM}" -chdir="${TF_DIR}" apply -auto-approve -input=false \
  -target=openstack_compute_instance_v2.okd

# Installer images of earlier attempts are useless (expired certificates).
# The volume of the node is a copy, so the image just uploaded stays only as
# the record Terraform refers to.
openstack image list --private -f value -c ID -c Name |
  awk -v prefix="${iso_prefix}" -v keep="${image_name}" 'index($2, prefix) == 1 && $2 != keep {print $1}' |
  while read -r old_image; do
    info "Deleting the previous installer image ${old_image}"
    openstack image delete "${old_image}" || warn "Could not delete image ${old_image}"
  done

info "Node created. Follow the installation from the bastion:"
info "  scripts/workstation/ssh-bastion.sh scripts/bastion/03-wait-for-okd.sh"
