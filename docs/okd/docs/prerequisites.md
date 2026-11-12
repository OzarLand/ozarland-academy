# Prerequisites

What you need before starting, and how to check each item. Everything here
can be verified in a few minutes with a throw-away instance; doing so avoids
discovering a blocker halfway through the installation.

## Host cloud project

The lab runs in one project (tenant) of an existing OpenStack cloud. A
regular project member role is enough.

### Quota

| Resource | Needed (default lab) | Notes |
|---|---|---|
| Instances | 3 | bastion, OKD node, one compute node |
| vCPU | 26 | |
| RAM | 52 GB | |
| Volumes | 4 | three root volumes and the installer ISO |
| Volume storage | 255 GB | |
| Networks / subnets | 4 / 4 | |
| Routers | 1 | with a gateway on the external network |
| Ports | about 15 | |
| Security groups / rules | 1 / about 5 | one more rule per entry of `admin_cidrs` |
| Floating IPs | 0 to 3 | one for the bastion unless a shared access network is used; one more for the OKD node and for each compute node only on clouds where an instance needs one for outbound access |
| Images | 1 private image, about 1.5 GB | the installer ISO |

**[READ-ONLY]**

```bash
openstack quota show
openstack limits show --absolute
```

### Flavors

| VM | Minimum |
|---|---|
| bastion | 2 vCPU, 4 GB |
| OKD node | 16 vCPU, 32 GB |
| compute node | 8 vCPU, 16 GB (4 vCPU / 8 GB works for CirrOS-only tests) |

Flavor root disk size does not matter: all VMs boot from volumes.

### Images

A **CentOS Stream 9** cloud image must be available (bastion and compute
nodes). The data plane container images of the selected operator branch are
built for CentOS Stream 9; do not substitute another distribution or major
version for the compute node. The project must be allowed to upload a
private image (the OKD installer ISO).

### Network features

| Requirement | Why | Check |
|---|---|---|
| An external network usable as router gateway | Outbound access for all lab VMs | `openstack network list --external` |
| Project members may create networks with port security disabled | MetalLB and macvlan traffic on the OpenStack networks | see below |
| Tenant network MTU of at least 1400 | Two nested overlays must fit | `openstack network show <net> -c mtu` |

**[CHANGE]** — creates and deletes a test network:

```bash
openstack network create --disable-port-security lab-precheck
openstack network show lab-precheck -c port_security_enabled -c mtu
openstack network delete lab-precheck
```

If the first command is refused by policy, read the fallback discussion in
[architecture.md](architecture.md#networking) before going further.

### Outbound access

Lab VMs download from `quay.io`, `github.com` and
`raw.githubusercontent.com`, `mirror.openshift.com`-style content hosts used
by the OKD installer, `cloud.centos.org` / `mirror.stream.centos.org`,
`trunk.rdoproject.org`, and `download.cirros-cloud.net` (test image of the
functional smoke test). A cloud that filters
outbound traffic needs these destinations allowed; a disconnected
installation is out of scope.

Access through an HTTP proxy is supported as long as the proxy accepts HTTPS
(`CONNECT`) requests from the lab VMs: see
[Running behind a proxy](installation/README.md#running-behind-a-proxy).
The lab also needs an NTP server; when none is reachable, the bastion can
serve its own clock (`BASTION_NTP_SERVER` in `lab.env`).

## Checks on a test instance

Boot a small CentOS Stream 9 instance with the flavor family and volume type
you intend to use, then run the following.

### Nested virtualization

**[READ-ONLY]**

```bash
grep -cE 'vmx|svm' /proc/cpuinfo
ls -l /dev/kvm
```

A count of `0` means compute nodes will use emulation. The lab still works;
see [architecture.md](architecture.md#nested-virtualization).

### CPU level

The OKD node operating system (CentOS Stream CoreOS 10) requires the
x86-64-v3 instruction set.

**[READ-ONLY]**

```bash
/usr/lib64/ld-linux-x86-64.so.2 --help | grep -E 'x86-64-v[234]'
```

`x86-64-v3 (supported, searched)` must appear.

### Disk latency

This is the etcd suitability test recommended by the etcd project: small
sequential writes, each followed by `fdatasync`.

**[CHANGE]** — writes a 22 MB temporary file:

```bash
sudo dnf install -y fio
fio --rw=write --ioengine=sync --fdatasync=1 --directory=/var/tmp \
    --size=22m --bs=2300 --name=etcd-check
```

In the output, look at `fsync/fdatasync/sync_file_range` → `99.00th`. Below
10 ms is good. Between 10 and 20 ms the cluster installs but may show
occasional etcd warnings. Above that, choose a faster volume type or flavor.

## Workstation

The machine from which you drive the deployment. It holds the host cloud
credentials and never needs to reach the cluster directly.

| Tool | Purpose |
|---|---|
| `terraform` ≥ 1.6 | Creates the infrastructure. OpenTofu should work by setting `TERRAFORM=tofu` in `lab.env`; this was not tested |
| `openstack` client | Uploads the installer ISO |
| `ssh`, `scp`, `ssh-keygen`, `tar` | Access to the bastion |
| `python3` | Converts Terraform outputs for the scripts |
| An SSH key pair | Injected into the bastion |

Credentials are read from the standard OpenStack client configuration
(`clouds.yaml` selected with `OS_CLOUD`, or `OS_*` environment variables).
They are never copied to the bastion or into this repository.

**[READ-ONLY]**

```bash
openstack token issue -c expires   # proves the credentials work
terraform version
```

## Knowledge

The guides assume you operate OpenStack already (services, configuration
files, RabbitMQ, Galera, Neutron/OVN basics). No Kubernetes experience is
assumed; start with [concepts/](concepts/README.md).
