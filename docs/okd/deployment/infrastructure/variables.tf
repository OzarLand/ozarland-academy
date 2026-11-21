# ---------------------------------------------------------------------------
# Environment-specific inputs. Set them in terraform.tfvars (not committed).
# ---------------------------------------------------------------------------

variable "name_prefix" {
  description = "Prefix added to the name of every resource created for the lab."
  type        = string
  default     = "okdlab"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.name_prefix))
    error_message = "name_prefix must be 2-21 lowercase alphanumeric characters or dashes, starting with a letter."
  }
}

variable "external_network" {
  description = "Name of the external (provider) network used for the router gateway and floating IPs."
  type        = string
}

variable "ssh_public_key_file" {
  description = "Path to the SSH public key injected into the bastion and the compute node."
  type        = string
}

variable "admin_cidrs" {
  description = "Source CIDRs allowed to reach the bastion over SSH."
  type        = list(string)

  validation {
    condition     = length(var.admin_cidrs) > 0 && alltrue([for c in var.admin_cidrs : can(cidrhost(c, 0))])
    error_message = "admin_cidrs must be a non-empty list of valid CIDRs."
  }
}

variable "bastion_floating_ip" {
  description = "Allocate a floating IP for the bastion. Disable when the workstation reaches the bastion through bastion_access_network instead."
  type        = bool
  default     = true
}

variable "floating_ip_subnet_id" {
  description = "Optional ID of the external network subnet floating IPs are allocated from. Only needed on clouds whose external network has several subnets and where the default choice has no free address."
  type        = string
  default     = null
}

variable "okd_floating_ip" {
  description = "Also allocate a floating IP for the OKD node (machine network port). Only needed on clouds where instances have outbound access through a floating IP but not through the router's shared address."
  type        = bool
  default     = false
}

variable "compute_floating_ip" {
  description = "Also allocate a floating IP for each compute node (ctlplane port). Same use case as okd_floating_ip."
  type        = bool
  default     = false
}

variable "bastion_access_network" {
  description = "Optional name of an existing network on which the bastion gets an extra port (for a workstation living in the same cloud project). Empty to disable."
  type        = string
  default     = ""
}

variable "volume_type" {
  description = "Cinder volume type for all root volumes. etcd needs low fsync latency: pick the fastest type available."
  type        = string
  default     = null
}

variable "bastion_image" {
  description = "Image name for the bastion (CentOS Stream 9 expected)."
  type        = string
  default     = "CentOS Stream 9"
}

variable "bastion_flavor" {
  description = "Flavor for the bastion (2 vCPU / 4 GB is enough)."
  type        = string
}

variable "okd_flavor" {
  description = "Flavor for the single-node OKD cluster (16 vCPU / 32 GB minimum for OKD plus the OpenStack control plane)."
  type        = string
}

variable "okd_root_volume_size" {
  description = "Size in GB of the OKD node root volume. It also holds the persistent volumes of the OpenStack control plane."
  type        = number
  default     = 150

  validation {
    condition     = var.okd_root_volume_size >= 120
    error_message = "The OKD node needs at least 120 GB."
  }
}

variable "agent_iso_image_id" {
  description = "Glance image ID of the agent installer ISO. The OKD node is only created once this is set (second apply)."
  type        = string
  default     = ""
}

variable "compute_count" {
  description = "Number of OpenStack compute (data plane) nodes. 0 gives a control-plane-only lab."
  type        = number
  default     = 1

  validation {
    condition     = var.compute_count >= 0 && var.compute_count <= 5
    error_message = "compute_count must be between 0 and 5."
  }
}

variable "compute_image" {
  description = "Image name for compute nodes. Must match the OS expected by the data plane container images (CentOS Stream 9 for the 18-stable operators)."
  type        = string
  default     = "CentOS Stream 9"
}

variable "compute_flavor" {
  description = "Flavor for compute nodes (8 vCPU / 16 GB recommended)."
  type        = string
}

variable "compute_root_volume_size" {
  description = "Size in GB of each compute node root volume."
  type        = number
  default     = 60
}

# ---------------------------------------------------------------------------
# Lab addressing. The defaults mirror the upstream openstack-k8s-operators
# development environment so that upstream samples stay recognisable.
# Change them only if they collide with networks you must reach.
# ---------------------------------------------------------------------------

variable "machine_cidr" {
  description = "OKD machine network: bastion and OKD node primary interface."
  type        = string
  default     = "192.168.130.0/24"

  validation {
    condition     = can(cidrhost(var.machine_cidr, 250))
    error_message = "machine_cidr must be a valid IPv4 network of at least a /24."
  }
}

variable "ctlplane_cidr" {
  description = "OpenStack control plane (provisioning) network: Ansible/SSH and DNS to compute nodes."
  type        = string
  default     = "192.168.122.0/24"

  validation {
    condition     = can(cidrhost(var.ctlplane_cidr, 0)) && endswith(var.ctlplane_cidr, "/24")
    error_message = "ctlplane_cidr must be a valid /24 IPv4 network: the lab address plan uses fixed host numbers."
  }
}

variable "internalapi_cidr" {
  description = "OpenStack internal API network: RabbitMQ, OVN southbound DB, internal endpoints."
  type        = string
  default     = "172.17.0.0/24"

  validation {
    condition     = can(cidrhost(var.internalapi_cidr, 0)) && endswith(var.internalapi_cidr, "/24")
    error_message = "internalapi_cidr must be a valid /24 IPv4 network: the lab address plan uses fixed host numbers."
  }
}

variable "tenant_cidr" {
  description = "OpenStack tenant network: Geneve tunnels between OVN chassis."
  type        = string
  default     = "172.19.0.0/24"

  validation {
    condition     = can(cidrhost(var.tenant_cidr, 0)) && endswith(var.tenant_cidr, "/24")
    error_message = "tenant_cidr must be a valid /24 IPv4 network: the lab address plan uses fixed host numbers."
  }
}

variable "upstream_dns" {
  description = "Resolvers the bastion DNS forwards to, and that compute nodes use at first boot. They must be reachable from the lab networks. May be empty when the lab only reaches the outside through an HTTP proxy (HTTP_PROXY_URL in lab.env): the proxy then resolves external names."
  type        = list(string)
  default     = ["1.1.1.1", "9.9.9.9"]
}

variable "dataplane_ssh_public_key_file" {
  description = "Public key authorised for the data plane Ansible user on compute nodes (created by scripts/workstation/create-dataplane-key.sh). Defaults to .work/dataplane-ssh-key.pub at the repository root."
  type        = string
  default     = null
}

variable "dataplane_user" {
  description = "User created on compute nodes for the data plane Ansible jobs. The deployment scripts read it from the Terraform outputs."
  type        = string
  default     = "cloud-admin"
}
