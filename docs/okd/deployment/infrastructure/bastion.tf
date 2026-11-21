# The bastion is the operations host of the lab: it serves DNS for the
# cluster, holds the oc client and the kubeconfig, and is the only entry
# point from outside.

resource "openstack_compute_keypair_v2" "lab" {
  name       = "${var.name_prefix}-key"
  public_key = trimspace(file(pathexpand(var.ssh_public_key_file)))
}

data "openstack_images_image_v2" "bastion" {
  name        = var.bastion_image
  most_recent = true
}

resource "openstack_networking_port_v2" "bastion" {
  name               = "${var.name_prefix}-bastion"
  network_id         = openstack_networking_network_v2.machine.id
  security_group_ids = [openstack_networking_secgroup_v2.lab.id]

  fixed_ip {
    subnet_id  = openstack_networking_subnet_v2.machine.id
    ip_address = cidrhost(var.machine_cidr, local.host.bastion)
  }
}

data "openstack_networking_network_v2" "bastion_access" {
  count = var.bastion_access_network != "" ? 1 : 0
  name  = var.bastion_access_network
}

resource "openstack_networking_port_v2" "bastion_access" {
  count = var.bastion_access_network != "" ? 1 : 0

  name               = "${var.name_prefix}-bastion-access"
  network_id         = data.openstack_networking_network_v2.bastion_access[0].id
  security_group_ids = [openstack_networking_secgroup_v2.lab.id]
}

resource "openstack_compute_instance_v2" "bastion" {
  name        = "${var.name_prefix}-bastion"
  flavor_name = var.bastion_flavor
  key_pair    = openstack_compute_keypair_v2.lab.name

  block_device {
    uuid                  = data.openstack_images_image_v2.bastion.id
    source_type           = "image"
    destination_type      = "volume"
    volume_size           = 40
    volume_type           = var.volume_type
    boot_index            = 0
    delete_on_termination = true
  }

  network {
    port = openstack_networking_port_v2.bastion.id
  }

  dynamic "network" {
    for_each = openstack_networking_port_v2.bastion_access
    content {
      port = network.value.id
    }
  }

  # The access network must not install a second default route.
  user_data = templatefile("${path.module}/templates/bastion-cloud-init.yaml.tftpl", {
    has_access_network = var.bastion_access_network != ""
    access_mac         = lower(one(openstack_networking_port_v2.bastion_access[*].mac_address) == null ? "" : one(openstack_networking_port_v2.bastion_access[*].mac_address))
  })

  lifecycle {
    ignore_changes = [block_device, user_data]
  }

  depends_on = [openstack_networking_router_interface_v2.machine]
}

resource "openstack_networking_floatingip_v2" "bastion" {
  count = var.bastion_floating_ip ? 1 : 0

  pool        = var.external_network
  subnet_id   = var.floating_ip_subnet_id
  description = "${var.name_prefix} bastion"
}

resource "openstack_networking_floatingip_associate_v2" "bastion" {
  count = var.bastion_floating_ip ? 1 : 0

  floating_ip = openstack_networking_floatingip_v2.bastion[0].address
  port_id     = openstack_networking_port_v2.bastion.id

  depends_on = [openstack_networking_router_interface_v2.machine]
}
