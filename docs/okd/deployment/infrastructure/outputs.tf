output "bastion_ssh_host" {
  description = "Address the workstation uses to reach the bastion."
  value = (
    var.bastion_floating_ip
    ? openstack_networking_floatingip_v2.bastion[0].address
    : try(openstack_networking_port_v2.bastion_access[0].all_fixed_ips[0], openstack_networking_port_v2.bastion.all_fixed_ips[0])
  )
}

output "floating_ips" {
  description = "Floating IPs of the lab VMs: the source addresses an outbound proxy or firewall sees."
  value = {
    bastion  = openstack_networking_floatingip_v2.bastion[*].address
    okd      = openstack_networking_floatingip_v2.okd[*].address
    computes = openstack_networking_floatingip_v2.compute[*].address
  }
}

output "okd_node_created" {
  description = "Whether the OKD node exists yet (false until the agent ISO image is provided)."
  value       = length(openstack_compute_instance_v2.okd) > 0
}

# Everything the cluster-side scripts need to know about the infrastructure.
# scripts/workstation/sync-to-bastion.sh turns this into an environment file.
output "lab" {
  description = "Addressing facts consumed by the deployment scripts."
  value = {
    machine_cidr    = var.machine_cidr
    machine_gateway = openstack_networking_subnet_v2.machine.gateway_ip
    machine_mtu     = openstack_networking_network_v2.machine.mtu
    bastion_ip      = openstack_networking_port_v2.bastion.all_fixed_ips[0]
    upstream_dns    = join(",", var.upstream_dns)

    okd_ip  = openstack_networking_port_v2.okd_machine.all_fixed_ips[0]
    okd_mac = openstack_networking_port_v2.okd_machine.mac_address

    networks = {
      for net, cfg in local.isolated_networks : net => {
        cidr    = cfg.cidr
        mtu     = openstack_networking_network_v2.isolated[net].mtu
        gateway = cfg.routed ? cidrhost(cfg.cidr, 1) : ""
        okd_ip  = openstack_networking_port_v2.okd_isolated[net].all_fixed_ips[0]
        okd_mac = openstack_networking_port_v2.okd_isolated[net].mac_address
      }
    }

    dataplane_user = var.dataplane_user

    computes = [
      for i in range(var.compute_count) : {
        name = "${var.name_prefix}-compute-${i}"
        ips = {
          for net in keys(local.isolated_networks) :
          net => openstack_networking_port_v2.compute["${i}-${net}"].all_fixed_ips[0]
        }
      }
    ]
  }
}

output "name_prefix" {
  description = "Prefix of all lab resources."
  value       = var.name_prefix
}
