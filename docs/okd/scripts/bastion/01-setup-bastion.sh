#!/usr/bin/env bash
# Bastion step 1: install the client tools and configure the lab DNS.
#
# The cluster needs three DNS names before it can even install:
#   api.<cluster domain>      Kubernetes API (clients, kubelet)
#   api-int.<cluster domain>  same API, name used by the node itself
#   *.apps.<cluster domain>   every Route (console, OpenStack public APIs)
# With a single node they all point to that node. dnsmasq serves them and
# forwards everything else to the upstream resolvers.
#
# Optionally (BASTION_NTP_SERVER=true) the bastion also becomes the time
# source of the lab, for clouds where no NTP server is reachable.

# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/../lib/common.sh"

load_config
require_infra_config
require_cmd sudo curl
use_proxy

info "Installing packages"
sudo_dnf install -y -q dnsmasq nmstate jq tar gettext bind-utils openssl chrony

install_okd_clients() {
  local base="https://github.com/okd-project/okd/releases/download/${OKD_VERSION}"
  local tmp file
  if openshift-install version 2>/dev/null | grep -qF "${OKD_VERSION}" && command -v oc >/dev/null; then
    info "OKD client tools ${OKD_VERSION} already installed"
    return
  fi
  tmp="$(mktemp -d)"
  info "Downloading openshift-install and oc ${OKD_VERSION}"
  for file in sha256sum.txt "openshift-install-linux-${OKD_VERSION}.tar.gz" "openshift-client-linux-${OKD_VERSION}.tar.gz"; do
    curl -fsSL -o "${tmp}/${file}" "${base}/${file}"
  done
  # The release publishes the checksums of its files: refuse anything else.
  (cd "${tmp}" && grep -F -e "  openshift-install-linux-${OKD_VERSION}.tar.gz" \
    -e "  openshift-client-linux-${OKD_VERSION}.tar.gz" sha256sum.txt | sha256sum --check --quiet --strict -) ||
    die "Checksum verification of the OKD client tools failed"
  tar -C "${tmp}" -xzf "${tmp}/openshift-install-linux-${OKD_VERSION}.tar.gz" openshift-install
  tar -C "${tmp}" -xzf "${tmp}/openshift-client-linux-${OKD_VERSION}.tar.gz" oc kubectl
  sudo install -m 0755 "${tmp}/openshift-install" "${tmp}/oc" "${tmp}/kubectl" /usr/local/bin/
  rm -rf "${tmp}"
}

configure_dns() {
  local conf=/etc/dnsmasq.d/okd-lab.conf server
  info "Configuring dnsmasq for ${CLUSTER_DOMAIN}"
  {
    printf '# Managed by scripts/bastion/01-setup-bastion.sh\n'
    printf 'listen-address=127.0.0.1,%s\n' "${BASTION_IP}"
    printf 'bind-interfaces\n'
    printf 'no-resolv\n'
    printf 'domain-needed\n'
    for server in ${UPSTREAM_DNS//,/ }; do
      printf 'server=%s\n' "${server}"
    done
    printf 'host-record=api.%s,%s\n' "${CLUSTER_DOMAIN}" "${OKD_IP}"
    printf 'host-record=api-int.%s,%s\n' "${CLUSTER_DOMAIN}" "${OKD_IP}"
    printf 'host-record=%s.%s,%s\n' "${OKD_NODE_NAME}" "${CLUSTER_DOMAIN}" "${OKD_IP}"
    # A leading dot-less "address" entry is a wildcard for the whole subtree.
    printf 'address=/apps.%s/%s\n' "${CLUSTER_DOMAIN}" "${OKD_IP}"
  } | sudo tee "${conf}" >/dev/null
  # With bind-interfaces (also set by the distribution's dnsmasq.conf),
  # dnsmasq fails to start while its listen address is not configured yet:
  # at boot, start it after the network and retry if it still loses the race.
  sudo mkdir -p /etc/systemd/system/dnsmasq.service.d
  printf '[Unit]\nWants=network-online.target\nAfter=network-online.target\n\n[Service]\nRestart=on-failure\nRestartSec=5\n' |
    sudo tee /etc/systemd/system/dnsmasq.service.d/okd-lab.conf >/dev/null
  sudo systemctl daemon-reload
  sudo dnsmasq --test
  sudo systemctl enable dnsmasq
  sudo systemctl restart dnsmasq

  # The bastion itself must use its own dnsmasq, otherwise oc cannot resolve
  # the cluster names.
  local connection
  connection="$(nmcli -t -f NAME,DEVICE connection show --active | awk -F: -v dev="$(ip -o route get "${MACHINE_GATEWAY}" | sed -n 's/.* dev \([^ ]*\).*/\1/p')" '$2 == dev {print $1; exit}')"
  [[ -n "${connection}" ]] || die "Could not find the NetworkManager connection of the machine network interface"
  sudo nmcli connection modify "${connection}" ipv4.ignore-auto-dns yes ipv4.dns 127.0.0.1
  sudo nmcli connection up "${connection}" >/dev/null
}

verify_dns() {
  local name answer
  for name in "api.${CLUSTER_DOMAIN}" "api-int.${CLUSTER_DOMAIN}" "console-openshift-console.apps.${CLUSTER_DOMAIN}"; do
    answer="$(dig +short "${name}" @127.0.0.1)"
    [[ "${answer}" == "${OKD_IP}" ]] || die "DNS check failed: ${name} resolved to '${answer}', expected ${OKD_IP}"
  done
  # Behind a proxy, external names are resolved by the proxy, not by the lab.
  if ! proxy_enabled; then
    [[ -n "$(dig +short quay.io @127.0.0.1)" ]] || die "DNS check failed: external names do not resolve through dnsmasq"
  fi
  info "DNS answers are correct"
}

# Serve the bastion clock to the lab networks. "local" keeps chrony answering
# even though the bastion itself has no upstream server: the nodes then agree
# with each other, which is what the cluster needs.
configure_time_server() {
  local conf=/etc/chrony.d/okd-lab.conf
  [[ "${BASTION_NTP_SERVER:-false}" == "true" ]] || return 0
  info "Configuring chrony to serve time to the lab networks"
  sudo mkdir -p /etc/chrony.d
  {
    printf '# Managed by scripts/bastion/01-setup-bastion.sh\n'
    printf 'local stratum 10 orphan\n'
    printf 'allow %s\n' "${MACHINE_CIDR}" "${CTLPLANE_CIDR}"
  } | sudo tee "${conf}" >/dev/null
  if ! grep -qE '^confdir[[:space:]]+/etc/chrony\.d' /etc/chrony.conf; then
    printf '\n# Added by scripts/bastion/01-setup-bastion.sh\nconfdir /etc/chrony.d\n' | sudo tee -a /etc/chrony.conf >/dev/null
  fi
  sudo systemctl enable chronyd
  sudo systemctl restart chronyd
  wait_until "chrony answering on ${BASTION_IP}" 60 \
    sudo chronyd -Q -t 3 "server ${BASTION_IP} iburst maxsamples 1"
}

install_okd_clients
configure_dns
verify_dns
configure_time_server
info "Bastion ready: $(openshift-install version | head -1)"
