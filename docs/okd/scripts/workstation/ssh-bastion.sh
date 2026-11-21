#!/usr/bin/env bash
# Workstation helper: open a shell on the bastion, or run a command there.
# Usage: ssh-bastion.sh [command...]

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"
# shellcheck source=scripts/workstation/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

load_config
require_cmd "${TERRAFORM}" ssh
require_var SSH_PRIVATE_KEY_FILE BASTION_USER

if (($# == 0)); then
  bastion_ssh -t "cd ${BASTION_REPO_DIR} && exec bash -l"
else
  # Quote each argument again: ssh joins them into one remote command line.
  bastion_ssh "cd ${BASTION_REPO_DIR} && $(printf '%q ' "$@")"
fi
