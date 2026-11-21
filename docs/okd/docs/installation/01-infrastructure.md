# Step 1 — Infrastructure

**Where:** workstation.

## In short

- Terraform creates the networks, the router, the bastion and the compute
  VM, plus the network ports of the future OKD node. The OKD node itself
  comes in step 2.
- Two files hold your choices: `lab.env` (lab settings) and
  `terraform.tfvars` (your host cloud).
- `sync-to-bastion.sh` copies the repository to the bastion. Run it again
  after every change made on the workstation.
- Done when the bastion answers over SSH and `.work/infra.env` lists four
  MAC addresses for the OKD node.

## What we deploy

The virtual infrastructure described in
[../architecture.md](../architecture.md): four networks, a router, a
security group, the bastion, the compute node(s), and the network ports of
the future OKD node. The OKD node itself is created in step 2, once its
installer image exists.

## Why Terraform

The infrastructure is a set of interdependent objects with fixed
addresses. The MAC addresses of the OKD node, for example, are needed
before the node exists, to prepare its network configuration. A declarative
tool handles that naturally, and `terraform destroy` removes everything it
created and nothing else.

## Procedure

1. Choose the lab settings.

   **[CHANGE]**

   ```bash
   cp config/lab.env.example lab.env
   ```

   The defaults work as they are. `CLUSTER_NAME` and `BASE_DOMAIN` only need
   to be changed if they collide with real names you must resolve.

2. Describe your host cloud.

   **[CHANGE]**

   ```bash
   cp deployment/infrastructure/terraform.tfvars.example \
      deployment/infrastructure/terraform.tfvars
   ```

   | Variable | Meaning |
   |---|---|
   | `external_network` | Name of the external network (router gateway, floating IP pool) |
   | `ssh_public_key_file` | Your public key; the public half of `SSH_PRIVATE_KEY_FILE` in `lab.env` |
   | `admin_cidrs` | Addresses allowed to SSH to the bastion |
   | `volume_type` | Fastest volume type available |
   | `bastion_flavor`, `okd_flavor`, `compute_flavor` | Flavor names matching the sizes in the architecture |
   | `bastion_image`, `compute_image` | Name of the CentOS Stream 9 image in your cloud (`openstack image list`) |
   | `compute_count` | `0` for a control-plane-only lab |
   | `bastion_floating_ip`, `bastion_access_network` | How the workstation reaches the bastion |

3. Create the SSH key used later by the data plane Ansible jobs. Terraform
   injects its public half into the compute nodes.

   **[CHANGE]**

   ```bash
   scripts/workstation/create-dataplane-key.sh
   ```

4. Create the infrastructure.

   **[CHANGE]**

   ```bash
   export OS_CLOUD=<your cloud entry>
   terraform -chdir=deployment/infrastructure init
   terraform -chdir=deployment/infrastructure apply
   ```

5. Copy the repository and the generated infrastructure facts to the bastion.

   **[CHANGE]**

   ```bash
   scripts/workstation/sync-to-bastion.sh
   ```

   Re-run this script whenever you change `lab.env`, a manifest or a script
   on the workstation.

## Concepts worth understanding here

- **Port security.** Compare the machine network and the others:

  **[READ-ONLY]**

  ```bash
  openstack network list --long -c Name -c "Port Security Enabled"   # may need: openstack network show
  ```

  The OKD node will answer for addresses that Neutron never assigned to its
  ports. With port security on, the host cloud would silently drop that
  traffic. Remember this when an address "does not answer" later.
- **Pre-created ports.** The OKD node's ports exist before the node. Their
  MAC and IP addresses flow into `.work/infra.env`, then into the installer
  configuration. This is how a statically addressed node is described before
  its first boot.

## Verify

**[READ-ONLY]**

```bash
terraform -chdir=deployment/infrastructure output
cat .work/infra.env
scripts/workstation/ssh-bastion.sh 'hostname && ip -br address'
```

Expected: the bastion answers, has an address on the machine network, and
`.work/infra.env` lists four MAC addresses for the OKD node.

## If something fails

| Symptom | Look at |
|---|---|
| `terraform apply` fails with a quota error | [../prerequisites.md](../prerequisites.md#quota) |
| Policy error on `port_security_enabled` | Port security cannot be disabled by project members; see [../architecture.md](../architecture.md#networking) |
| No floating IP available | Set `bastion_floating_ip = false` and `bastion_access_network` if the workstation shares a network with the lab project |
| SSH to the bastion times out | `admin_cidrs` does not include your source address as seen by the cloud; check with `openstack security group rule list <prefix>-machine` |
| SSH works but `sync-to-bastion.sh` cannot log in | `BASTION_USER` in `lab.env` does not match the image's default user |

---

**Previous:** [Installation guide](README.md) · **Next:** [Step 2 — OKD cluster](02-okd.md)
