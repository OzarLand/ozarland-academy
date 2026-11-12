# Installation guide

The installation is a sequence of seven steps. Each step has its own page
explaining what is deployed, why, how to verify it and what to look at when
it fails. Commands are run either on the **workstation** (has cloud
credentials) or on the **bastion** (has cluster access); every page says
which.

| Step | Page | Where | Duration (measured on the lab) |
|---|---|---|---|
| 1 | [Infrastructure](01-infrastructure.md) | workstation | 5 min (the `apply` itself: about 1 min) |
| 2 | [OKD cluster](02-okd.md) | bastion, workstation | 55 min (bastion 1 min, ISO 3 min, installation 46 min) |
| 3 | [Platform services](03-platform-services.md) | bastion | 2 min |
| 4 | [OpenStack operators](04-openstack-operators.md) | bastion | 3 min |
| 5 | [OpenStack control plane](05-openstack-control-plane.md) | bastion | 10–15 min |
| 6 | [OpenStack data plane](06-openstack-data-plane.md) | bastion | 21 min |
| 7 | [Verification](07-verification.md) | bastion | 2 min |

These figures come from one installation, behind a proxy, on fast volumes.
Count two hours for a first run, reading included. Running steps 3 to
6 again once they have finished takes a few seconds and changes nothing.
Steps 1 and 2 are different: the bastion setup restarts its DNS service,
and the ISO step refuses to overwrite an existing installation unless
`--force` is given.

Read [../architecture.md](../architecture.md) and check
[../prerequisites.md](../prerequisites.md) first.

## Quick reference

For readers who have been through the pages once:

```bash
# --- workstation ---
cp config/lab.env.example lab.env                       # then edit
cp deployment/infrastructure/terraform.tfvars.example \
   deployment/infrastructure/terraform.tfvars           # then edit
scripts/workstation/create-dataplane-key.sh
terraform -chdir=deployment/infrastructure init
terraform -chdir=deployment/infrastructure apply
scripts/workstation/sync-to-bastion.sh
scripts/workstation/ssh-bastion.sh scripts/bastion/01-setup-bastion.sh
scripts/workstation/ssh-bastion.sh scripts/bastion/02-create-agent-iso.sh
scripts/workstation/boot-okd-node.sh

# --- bastion (scripts/workstation/ssh-bastion.sh opens a shell there) ---
scripts/bastion/03-wait-for-okd.sh
scripts/bastion/04-platform-services.sh
scripts/bastion/05-openstack-operators.sh
scripts/bastion/06-openstack-controlplane.sh
scripts/bastion/07-openstack-dataplane.sh
tests/smoke-test.sh --functional
```

## How the automation is organised

```text
config/lab.env.example        settings you choose (names, versions)
deployment/infrastructure/    Terraform: networks, router, VMs
deployment/okd/               installer templates, storage and MetalLB manifests
deployment/openstack/         operator, control plane and data plane manifests
scripts/workstation/          steps that need cloud credentials
scripts/bastion/              steps that need cluster access (numbered)
scripts/lib/                  shared shell helpers and the address plan
tests/                        smoke test and offline template check
```

Principles:

- **Manifests are templates, scripts are glue.** Everything that ends up in
  the cluster is a readable YAML file under `deployment/`. Scripts only
  substitute values (`${VARIABLE}` placeholders), apply the result and wait.
  The rendered files are kept in `.work/rendered/` on the bastion so you can
  read exactly what was applied.
- **Two sources of values.** `lab.env` holds what you decide. `.work/infra.env`
  is generated from the Terraform outputs (addresses, MAC addresses, MTU) so
  that nothing about the infrastructure is typed twice.
- **Scripts are idempotent.** Re-running a step after a failure is the
  normal way to continue.
- **No secrets in files.** Cloud credentials stay in your OpenStack client
  configuration on the workstation. Service passwords are generated directly
  into a Kubernetes Secret. `lab.env`, `terraform.tfvars` and `.work/` are
  ignored by Git.

## Running behind a proxy

Some clouds give lab VMs no direct Internet access, only an HTTP proxy.
Set `HTTP_PROXY_URL` in `lab.env` before the first bastion step:

```bash
HTTP_PROXY_URL=http://proxy.example.com:3128
```

What this changes:

- the bastion downloads its packages, the OKD client tools and the release
  manifests of the platform services through the proxy, and no longer
  requires external names to resolve through its DNS;
- the OKD cluster is installed with a cluster-wide proxy (`proxy:` block of
  `install-config.yaml`), so the node pulls its images through it. The lab
  networks and the cluster names bypass the proxy; add your own exceptions
  with `NO_PROXY_EXTRA`;
- the data plane Ansible runs receive the proxy settings
  (`edpm_playbook_environment` in the NodeSet), so the compute nodes install
  packages and pull images through it;
- the functional test downloads its CirrOS image through it.

The proxy must accept HTTPS (`CONNECT`) requests from every lab VM address
it sees. Plain HTTP is not required: the lab's `repo-setup` service writes
the package repositories of the compute nodes with `https://` addresses.
Related optional settings, all neutral by default:

| Setting | Where | Purpose |
|---|---|---|
| `BASTION_NTP_SERVER=true` | `lab.env` | The lab VMs cannot reach an NTP server: the bastion serves its clock to the OKD node and the compute nodes |
| `ISO_BLANK_SYSTEM_AREA=true` | `lab.env` | The image service refuses hybrid ISO files |
| `okd_floating_ip`, `compute_floating_ip` | `terraform.tfvars` | Only instances with a floating IP have outbound access. **Exposure:** the compute node's floating IP sits on a port without port security or security group, so the node is reachable from the external network until the data plane deployment has installed its own firewall; use it only where the external network is trusted or filtered upstream |
| `floating_ip_subnet_id` | `terraform.tfvars` | The external network has several subnets |
| `upstream_dns` | `terraform.tfvars` | Resolvers reachable from the lab (may be empty behind a proxy) |

## Removing the lab

**[DESTRUCTIVE]** — deletes every lab VM, volume and network:

```bash
terraform -chdir=deployment/infrastructure destroy
openstack image list --private -f value -c ID -c Name | grep agent-iso   # then delete these images
```
