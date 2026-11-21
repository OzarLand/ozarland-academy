#!/usr/bin/env bash
# Helpers shared by the workstation scripts. Source after common.sh.
# shellcheck shell=bash

TF_DIR="${REPO_ROOT}/deployment/infrastructure"
DATAPLANE_KEY_FILE="${WORK_DIR}/dataplane-ssh-key"
# Path of the repository copy on the bastion, relative to the login directory.
BASTION_REPO_DIR="okd-openstack-lab"
# Terraform-compatible command (set TERRAFORM=tofu in lab.env for OpenTofu).
TERRAFORM="${TERRAFORM:-terraform}"
export TF_DIR DATAPLANE_KEY_FILE BASTION_REPO_DIR TERRAFORM

bastion_host() {
  "${TERRAFORM}" -chdir="${TF_DIR}" output -raw bastion_ssh_host
}

# The bastion is re-created with the lab, so its host key is recorded in a
# lab-specific known_hosts file instead of polluting the user's own.
bastion_ssh_options() {
  printf '%s\n' \
    -i "${SSH_PRIVATE_KEY_FILE/#\~/${HOME}}" \
    -o "UserKnownHostsFile=${WORK_DIR}/known_hosts" \
    -o StrictHostKeyChecking=accept-new \
    -o BatchMode=yes \
    -o ConnectTimeout=10 \
    -o ServerAliveInterval=30
}

bastion_ssh() {
  local -a options
  mapfile -t options < <(bastion_ssh_options)
  # shellcheck disable=SC2029 # arguments are meant to be expanded locally
  ssh "${options[@]}" "${BASTION_USER}@$(bastion_host)" "$@"
}

bastion_scp_from() {
  local -a options
  mapfile -t options < <(bastion_ssh_options)
  scp "${options[@]}" "${BASTION_USER}@$(bastion_host):$1" "$2"
}
