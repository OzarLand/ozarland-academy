terraform {
  required_version = ">= 1.6.0"

  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = "~> 3.0"
    }
  }
}

# Credentials are never stored here. The provider reads them from the
# standard OpenStack client configuration: either the OS_CLOUD environment
# variable (pointing to an entry in clouds.yaml) or OS_* variables.
provider "openstack" {}
