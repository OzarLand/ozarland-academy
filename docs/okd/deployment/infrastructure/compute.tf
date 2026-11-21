# OpenStack compute (data plane) nodes: plain CentOS Stream VMs. They are
# "pre-provisioned" nodes from the operator's point of view: we provide a
# running OS with SSH access, Ansible jobs started by the operator do the rest.

data "openstack_images_image_v2" "compute" {
  count       = var.compute_count > 0 ? 1 : 0
  name        = var.compute_image
  most_recent = true
}

locals {
  dataplane_ssh_public_key_file = coalesce(var.dataplane_ssh_public_key_file, "${path.module}/../../.work/dataplane-ssh-key.pub")

  compute_ports = merge([
    for i in range(var.compute_count) : {
      for net, cfg in local.isolated_networks :
      "${i}-${net}" => { index = i, network = net, cidr = cfg.cidr }
    }
  ]...)
}

resource "openstack_networking_port_v2" "compute" {
  for_each = local.compute_ports

  name                  = "${var.name_prefix}-compute-${each.value.index}-${each.value.network}"
  network_id            = openstack_networking_network_v2.isolated[each.value.network].id
  port_security_enabled = false

  fixed_ip {
    subnet_id  = openstack_networking_subnet_v2.isolated[each.value.network].id
    ip_address = cidrhost(each.value.cidr, local.host.compute_first + each.value.index)
  }
}

resource "openstack_compute_instance_v2" "compute" {
  count = var.compute_count

  name        = "${var.name_prefix}-compute-${count.index}"
  flavor_name = var.compute_flavor
  key_pair    = openstack_compute_keypair_v2.lab.name

  block_device {
    uuid                  = data.openstack_images_image_v2.compute[0].id
    source_type           = "image"
    destination_type      = "volume"
    volume_size           = var.compute_root_volume_size
    volume_type           = var.volume_type
    boot_index            = 0
    delete_on_termination = true
  }

  # Interface order: ctlplane (DHCP at first boot), internalapi, tenant.
  network {
    port = openstack_networking_port_v2.compute["${count.index}-ctlplane"].id
  }
  network {
    port = openstack_networking_port_v2.compute["${count.index}-internalapi"].id
  }
  network {
    port = openstack_networking_port_v2.compute["${count.index}-tenant"].id
  }

  user_data = templatefile("${path.module}/templates/compute-cloud-init.yaml.tftpl", {
    dataplane_user       = var.dataplane_user
    dataplane_public_key = trimspace(file(local.dataplane_ssh_public_key_file))
    admin_public_key     = trimspace(file(pathexpand(var.ssh_public_key_file)))
  })

  lifecycle {
    ignore_changes = [block_device, user_data]
  }

  depends_on = [openstack_networking_router_interface_v2.ctlplane]
}

# Optional floating IPs (see okd_floating_ip). They sit on the ctlplane port
# because that is where the node's default route is.
resource "openstack_networking_floatingip_v2" "compute" {
  count = var.compute_floating_ip ? var.compute_count : 0

  pool        = var.external_network
  subnet_id   = var.floating_ip_subnet_id
  description = "${var.name_prefix} compute ${count.index}"
}

resource "openstack_networking_floatingip_associate_v2" "compute" {
  count = var.compute_floating_ip ? var.compute_count : 0

  floating_ip = openstack_networking_floatingip_v2.compute[count.index].address
  port_id     = openstack_networking_port_v2.compute["${count.index}-ctlplane"].id

  depends_on = [openstack_networking_router_interface_v2.ctlplane]
}
