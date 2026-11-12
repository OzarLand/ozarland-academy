#!/usr/bin/env bash
# Shared helpers. Source this file; do not execute it.
# shellcheck shell=bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
WORK_DIR="${WORK_DIR:-${REPO_ROOT}/.work}"
LAB_ENV_FILE="${LAB_ENV_FILE:-${REPO_ROOT}/lab.env}"
INFRA_ENV_FILE="${WORK_DIR}/infra.env"
export REPO_ROOT WORK_DIR

log() { printf '%s [%s] %s\n' "$(date -u +%H:%M:%S)" "$1" "${*:2}" >&2; }
info() { log INFO "$@"; }
warn() { log WARN "$@"; }
die() {
  log ERROR "$@"
  exit 1
}

require_cmd() {
  local cmd
  for cmd in "$@"; do
    command -v "${cmd}" >/dev/null 2>&1 || die "Required command not found: ${cmd}"
  done
}

# require_bool <name>...: the setting must be exactly "true" or "false".
# Anything else (yes, True, 1) would otherwise be read silently as false.
require_bool() {
  local name
  for name in "$@"; do
    [[ "${!name:-}" == "true" || "${!name:-}" == "false" ]] ||
      die "Setting ${name} must be true or false (got '${!name:-}')"
  done
}

require_var() {
  local name
  for name in "$@"; do
    [[ -n "${!name:-}" ]] || die "Required setting is empty or missing: ${name}"
  done
}

# Load lab.env (user settings) and, when present, infra.env (facts generated
# from the Terraform outputs). Every variable is exported so that templates
# can be rendered with envsubst.
load_config() {
  [[ -f "${LAB_ENV_FILE}" ]] || die "Missing ${LAB_ENV_FILE}. Copy config/lab.env.example to lab.env and adapt it."
  set -a
  # shellcheck source=/dev/null
  source "${LAB_ENV_FILE}"
  if [[ -f "${INFRA_ENV_FILE}" ]]; then
    # shellcheck source=/dev/null
    source "${INFRA_ENV_FILE}"
  fi
  set +a
  require_var CLUSTER_NAME BASE_DOMAIN OKD_VERSION
  BASTION_NTP_SERVER="${BASTION_NTP_SERVER:-false}"
  ISO_BLANK_SYSTEM_AREA="${ISO_BLANK_SYSTEM_AREA:-false}"
  require_bool BASTION_NTP_SERVER ISO_BLANK_SYSTEM_AREA
  CLUSTER_DOMAIN="${CLUSTER_NAME}.${BASE_DOMAIN}"
  # Optional settings: define them so that templates can always refer to them.
  HTTP_PROXY_URL="${HTTP_PROXY_URL:-}"
  NO_PROXY_EXTRA="${NO_PROXY_EXTRA:-}"
  # When the bastion is the lab time source, every node synchronises with it.
  if [[ "${BASTION_NTP_SERVER:-false}" == "true" && -n "${BASTION_IP:-}" ]]; then
    NTP_SERVER="${BASTION_IP}"
  fi
  NO_PROXY_LIST="$(no_proxy_list)"
  export CLUSTER_DOMAIN HTTP_PROXY_URL NO_PROXY_EXTRA NTP_SERVER NO_PROXY_LIST
  mkdir -p "${WORK_DIR}"
}

# --- Optional outbound HTTP proxy (HTTP_PROXY_URL in lab.env) -----------------

proxy_enabled() { [[ -n "${HTTP_PROXY_URL:-}" ]]; }

# Destinations that must never be sent to the proxy: the lab networks and the
# cluster's own names. OKD adds its pod and service networks by itself.
no_proxy_list() {
  local list="localhost,127.0.0.1,.svc,.cluster.local,.${CLUSTER_DOMAIN}" name
  for name in MACHINE_CIDR CTLPLANE_CIDR INTERNALAPI_CIDR TENANT_CIDR NO_PROXY_EXTRA; do
    if [[ -n "${!name:-}" ]]; then
      list+=",${!name}"
    fi
  done
  printf '%s' "${list}"
}

# Make the tools started by the calling script (curl, oc, openshift-install)
# use the proxy for external downloads. Requests to the cluster API are not
# affected: its name is in the exclusion list. Only bastion scripts call
# this; on the workstation the proxy is none of our business.
use_proxy() {
  proxy_enabled || return 0
  export http_proxy="${HTTP_PROXY_URL}" https_proxy="${HTTP_PROXY_URL}" no_proxy="${NO_PROXY_LIST}"
  export HTTP_PROXY="${HTTP_PROXY_URL}" HTTPS_PROXY="${HTTP_PROXY_URL}" NO_PROXY="${NO_PROXY_LIST}"
  info "Using the HTTP proxy ${HTTP_PROXY_URL} for external downloads"
}

# dnf runs through sudo, which drops the environment: pass the proxy as an option.
sudo_dnf() {
  sudo dnf ${HTTP_PROXY_URL:+"--setopt=proxy=${HTTP_PROXY_URL}"} "$@"
}

require_infra_config() {
  [[ -f "${INFRA_ENV_FILE}" ]] || die "Missing ${INFRA_ENV_FILE}. Run scripts/workstation/sync-to-bastion.sh from the workstation first."
}

# render_template <source> <destination>
# Substitutes ${VAR} and $VAR references to exported variables, and nothing
# else: other dollar signs (Jinja, shell snippets in manifests) are left
# untouched. A ${VAR} reference to a variable that is not exported is an error.
render_template() {
  local src="$1" dst="$2" exported names missing
  require_cmd envsubst
  exported="$(compgen -e)"
  # shellcheck disable=SC2016 # literal ${...} patterns are intended here
  missing="$( (grep -oE '\$\{[A-Z][A-Z0-9_]*\}' "${src}" || true) | sort -u | tr -d '${}' | while read -r name; do
    grep -qxF "${name}" <<<"${exported}" || printf '%s ' "${name}"
  done)"
  [[ -z "${missing}" ]] || die "Template ${src} references undefined settings: ${missing}"
  # shellcheck disable=SC2016,SC2001
  names="$(sed 's/.*/${&}/' <<<"${exported}" | tr '\n' ' ')"
  mkdir -p "$(dirname "${dst}")"
  envsubst "${names}" <"${src}" >"${dst}"
}

# wait_until <description> <timeout-seconds> <command...>
# Retries the command every 10 seconds until it succeeds. On timeout, the
# last error output of the command is shown: it usually names the cause.
wait_until() {
  local description="$1" timeout="$2" start errors
  shift 2
  errors="$(mktemp)"
  start="$(date +%s)"
  info "Waiting for: ${description} (timeout ${timeout}s)"
  until "$@" >/dev/null 2>"${errors}"; do
    if (($(date +%s) - start >= timeout)); then
      if [[ -s "${errors}" ]]; then
        warn "Last error: $(tail -n 5 "${errors}")"
      fi
      rm -f "${errors}"
      die "Timed out waiting for: ${description}"
    fi
    sleep 10
  done
  rm -f "${errors}"
  info "Done: ${description}"
}

# Prefix length of a CIDR, e.g. 192.168.0.0/24 -> 24.
cidr_prefix() { printf '%s' "${1#*/}"; }

# Host address inside a /24 or larger IPv4 CIDR: cidr_host 172.17.0.0/24 80.
cidr_host() {
  local network="${1%/*}"
  printf '%s.%s' "${network%.*}" "$2"
}
