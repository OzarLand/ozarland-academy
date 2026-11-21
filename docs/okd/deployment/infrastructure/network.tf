# Host numbers used on every lab network. Keeping them identical across
# networks makes addresses easy to recognise during troubleshooting.
locals {
  host = {
    bastion       = 5
    okd           = 10
    compute_first = 100
  }

  # The three OpenStack networks. Neutron port security is disabled on them:
  # the OKD node answers for extra IPs (MetalLB) and extra MACs (macvlan pods)
  # that Neutron anti-spoofing would otherwise drop.
  isolated_networks = {
    ctlplane    = { cidr = var.ctlplane_cidr, routed = true }
    internalapi = { cidr = var.internalapi_cidr, routed = false }
    tenant      = { cidr = var.tenant_cidr, routed = false }
  }
}

data "openstack_networking_network_v2" "external" {
  name = var.external_network
}

resource "openstack_networking_router_v2" "lab" {
  name                = "${var.name_prefix}-router"
  external_network_id = data.openstack_networking_network_v2.external.id
}

# --- Machine network (port security enabled, protected by a security group) --

resource "openstack_networking_network_v2" "machine" {
  name = "${var.name_prefix}-machine"
}

resource "openstack_networking_subnet_v2" "machine" {
  name            = "${var.name_prefix}-machine"
  network_id      = openstack_networking_network_v2.machine.id
  cidr            = var.machine_cidr
  ip_version      = 4
  dns_nameservers = var.upstream_dns

  allocation_pool {
    start = cidrhost(var.machine_cidr, 200)
    end   = cidrhost(var.machine_cidr, 250)
  }
}

resource "openstack_networking_router_interface_v2" "machine" {
  router_id = openstack_networking_router_v2.lab.id
  subnet_id = openstack_networking_subnet_v2.machine.id
}

# --- OpenStack networks (port security disabled) ----------------------------

resource "openstack_networking_network_v2" "isolated" {
  for_each = local.isolated_networks

  name                  = "${var.name_prefix}-${each.key}"
  port_security_enabled = false
}

resource "openstack_networking_subnet_v2" "isolated" {
  for_each = local.isolated_networks

  name       = "${var.name_prefix}-${each.key}"
  network_id = openstack_networking_network_v2.isolated[each.key].id
  cidr       = each.value.cidr
  ip_version = 4

  # Only ctlplane is routed: compute nodes boot on it (DHCP) and pull packages
  # and container images through it. The others are flat, isolated segments.
  enable_dhcp     = each.value.routed
  no_gateway      = each.value.routed ? null : true
  gateway_ip      = each.value.routed ? cidrhost(each.value.cidr, 1) : null
  dns_nameservers = each.value.routed ? var.upstream_dns : []

  allocation_pool {
    start = cidrhost(each.value.cidr, 200)
    end   = cidrhost(each.value.cidr, 250)
  }
}

resource "openstack_networking_router_interface_v2" "ctlplane" {
  router_id = openstack_networking_router_v2.lab.id
  subnet_id = openstack_networking_subnet_v2.isolated["ctlplane"].id
}

# --- Security group for the machine network ---------------------------------

resource "openstack_networking_secgroup_v2" "lab" {
  name        = "${var.name_prefix}-machine"
  description = "OKD lab machine network: SSH to the bastion, free traffic inside the lab"
}

resource "openstack_networking_secgroup_rule_v2" "intra_lab" {
  security_group_id = openstack_networking_secgroup_v2.lab.id
  description       = "Any traffic between lab members"
  direction         = "ingress"
  ethertype         = "IPv4"
  remote_group_id   = openstack_networking_secgroup_v2.lab.id
}

# Compute nodes sit on networks without port security, so they are not
# members of the security group. They still need the bastion (time, DNS).
resource "openstack_networking_secgroup_rule_v2" "ctlplane" {
  security_group_id = openstack_networking_secgroup_v2.lab.id
  description       = "Any traffic from the OpenStack ctlplane network"
  direction         = "ingress"
  ethertype         = "IPv4"
  remote_ip_prefix  = var.ctlplane_cidr
}

resource "openstack_networking_secgroup_rule_v2" "ssh" {
  for_each = toset(var.admin_cidrs)

  security_group_id = openstack_networking_secgroup_v2.lab.id
  description       = "SSH to the bastion"
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = each.value
}
