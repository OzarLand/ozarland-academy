#!/usr/bin/env bash
# Workstation step: export the infrastructure facts and copy the repository
# (scripts, manifests, settings) to the bastion, where all cluster-side steps
# run. Safe to re-run at any time; the bastion copy is overwritten.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
# shellcheck source=scripts/workstation/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

load_config
require_cmd "${TERRAFORM}" python3 ssh tar
require_var SSH_PRIVATE_KEY_FILE BASTION_USER

info "Rendering ${INFRA_ENV_FILE} from the Terraform outputs"
"${TERRAFORM}" -chdir="${TF_DIR}" output -json lab |
  python3 "${REPO_ROOT}/scripts/workstation/render_infra_env.py" >"${INFRA_ENV_FILE}.tmp"
mv "${INFRA_ENV_FILE}.tmp" "${INFRA_ENV_FILE}"

[[ -f "${DATAPLANE_KEY_FILE}" ]] || die "Missing ${DATAPLANE_KEY_FILE}. Run scripts/workstation/create-dataplane-key.sh before terraform apply."

info "Waiting for SSH on the bastion ($(bastion_host))"
wait_until "bastion SSH" 600 bastion_ssh true

info "Copying the repository to the bastion"
bastion_ssh "mkdir -p ${BASTION_REPO_DIR}"
# Only files tracked by Git are sent, so that credentials or notes kept next
# to the repository (cloud credentials, Terraform variables and state) never
# reach the bastion. Without Git (repository downloaded as an archive), fall
# back to an explicit exclusion list.
send_repository() {
  if git -C "${REPO_ROOT}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C "${REPO_ROOT}" ls-files -z | tar -C "${REPO_ROOT}" --null -T - -czf -
  else
    tar -C "${REPO_ROOT}" \
      --exclude=.git --exclude=.work --exclude=lab.env --exclude='.terraform*' \
      --exclude='*.tfstate*' --exclude='*.tfvars' --exclude='clouds.yaml' \
      --exclude='secure.yaml' --exclude='*-openrc.sh' --exclude='*.pem' --exclude='*.key' \
      -czf - .
  fi | bastion_ssh "tar -C ${BASTION_REPO_DIR} -xzf -"
}
send_repository
# Installer state on the bastion (.work/okd) must survive a re-sync, so only
# the files that originate on the workstation are sent from .work.
tar -C "${REPO_ROOT}" -czf - lab.env .work/infra.env .work/dataplane-ssh-key .work/dataplane-ssh-key.pub |
  bastion_ssh "tar -C ${BASTION_REPO_DIR} -xzf - && chmod 700 ${BASTION_REPO_DIR}/.work"

info "Bastion is up to date. Connect with: scripts/workstation/ssh-bastion.sh"
