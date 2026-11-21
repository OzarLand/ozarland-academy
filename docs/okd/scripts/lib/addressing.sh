#!/usr/bin/env bash
# Address plan inside each OpenStack network. Source after load_config.
#
#   .10        OKD node
#   .30 - .70  pod addresses (NetworkAttachmentDefinition, whereabouts IPAM)
#   .80 - .90  service addresses (MetalLB)
#   .100+      compute nodes
#   .150-.199  ctlplane only: floating IP range of the lab provider network
#
# The host numbers follow the upstream development environment so that
# upstream samples and documentation remain directly comparable.
# shellcheck shell=bash

_network=""
for _network in CTLPLANE INTERNALAPI TENANT; do
  _cidr_var="${_network}_CIDR"
  [[ "$(cidr_prefix "${!_cidr_var}")" == "24" ]] || die "${_cidr_var} must be a /24 network"
  printf -v "${_network}_POD_START" '%s' "$(cidr_host "${!_cidr_var}" 30)"
  printf -v "${_network}_POD_END" '%s' "$(cidr_host "${!_cidr_var}" 70)"
  printf -v "${_network}_LB_START" '%s' "$(cidr_host "${!_cidr_var}" 80)"
  printf -v "${_network}_LB_END" '%s' "$(cidr_host "${!_cidr_var}" 90)"
  export "${_network}_POD_START" "${_network}_POD_END" "${_network}_LB_START" "${_network}_LB_END"
done
unset _network _cidr_var

# Well-known service addresses referenced by the control plane manifest.
DNS_VIP="$(cidr_host "${CTLPLANE_CIDR}" 80)"
INTERNALAPI_VIP="$(cidr_host "${INTERNALAPI_CIDR}" 80)"
RABBITMQ_VIP="$(cidr_host "${INTERNALAPI_CIDR}" 85)"
RABBITMQ_CELL1_VIP="$(cidr_host "${INTERNALAPI_CIDR}" 86)"
export DNS_VIP INTERNALAPI_VIP RABBITMQ_VIP RABBITMQ_CELL1_VIP

# Ranges the operator allocates compute node addresses from (NetConfig).
for _network in CTLPLANE INTERNALAPI TENANT; do
  _cidr_var="${_network}_CIDR"
  printf -v "${_network}_NODE_START" '%s' "$(cidr_host "${!_cidr_var}" 100)"
  printf -v "${_network}_NODE_END" '%s' "$(cidr_host "${!_cidr_var}" 120)"
  export "${_network}_NODE_START" "${_network}_NODE_END"
done
unset _network _cidr_var
