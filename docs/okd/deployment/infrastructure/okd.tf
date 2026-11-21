# Single-node OKD cluster.
#
# The node has one interface per network (the host cloud offers no VLAN
# trunking to instances). All addresses are static and are rendered into the
# agent installer configuration from the outputs of this module.

resource "openstack_networking_port_v2" "okd_machine" {
  name               = "${var.name_prefix}-okd-machine"
  network_id         = openstack_networking_network_v2.machine.id
  security_group_ids = [openstack_networking_secgroup_v2.lab.id]

  fixed_ip {
    subnet_id  = openstack_networking_subnet_v2.machine.id
    ip_address = cidrhost(var.machine_cidr, local.host.okd)
  }
}

resource "openstack_networking_port_v2" "okd_isolated" {
  for_each = local.isolated_networks

  name                  = "${var.name_prefix}-okd-${each.key}"
  network_id            = openstack_networking_network_v2.isolated[each.key].id
  port_security_enabled = false

  fixed_ip {
    subnet_id  = openstack_networking_subnet_v2.isolated[each.key].id
    ip_address = cidrhost(each.value.cidr, local.host.okd)
  }
}

resource "openstack_compute_instance_v2" "okd" {
  count = var.agent_iso_image_id != "" ? 1 : 0

  name        = "${var.name_prefix}-okd"
  flavor_name = var.okd_flavor

  # Boot order: the empty root volume first, the installer ISO second.
  # On first boot the empty disk is not bootable and the firmware falls
  # through to the ISO; once the installer has written the disk, every later
  # boot starts from the disk without any change to the instance.
  block_device {
    source_type           = "blank"
    destination_type      = "volume"
    volume_size           = var.okd_root_volume_size
    volume_type           = var.volume_type
    boot_index            = 0
    delete_on_termination = true
  }

  block_device {
    uuid                  = var.agent_iso_image_id
    source_type           = "image"
    destination_type      = "volume"
    volume_size           = 2
    volume_type           = var.volume_type
    device_type           = "cdrom"
    disk_bus              = "sata"
    boot_index            = 1
    delete_on_termination = true
  }

  # Interface order matters: it must match the order used in the agent
  # installer network configuration (machine, ctlplane, internalapi, tenant).
  network {
    port = openstack_networking_port_v2.okd_machine.id
  }
  network {
    port = openstack_networking_port_v2.okd_isolated["ctlplane"].id
  }
  network {
    port = openstack_networking_port_v2.okd_isolated["internalapi"].id
  }
  network {
    port = openstack_networking_port_v2.okd_isolated["tenant"].id
  }

  lifecycle {
    # The ISO is only needed for the first boot. Never rebuild the cluster
    # because the image was later removed or regenerated.
    ignore_changes = [block_device]
  }

  depends_on = [openstack_networking_router_interface_v2.machine]
}

# Optional floating IP, for clouds where only instances holding one have
# outbound access. The address is attached to the port, so it exists before
# the node and survives a reinstallation.
resource "openstack_networking_floatingip_v2" "okd" {
  count = var.okd_floating_ip ? 1 : 0

  pool        = var.external_network
  subnet_id   = var.floating_ip_subnet_id
  description = "${var.name_prefix} OKD node"
}

resource "openstack_networking_floatingip_associate_v2" "okd" {
  count = var.okd_floating_ip ? 1 : 0

  floating_ip = openstack_networking_floatingip_v2.okd[0].address
  port_id     = openstack_networking_port_v2.okd_machine.id

  depends_on = [openstack_networking_router_interface_v2.machine]
}
