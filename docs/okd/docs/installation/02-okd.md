# Step 2 — OKD cluster

**Where:** bastion, with one command on the workstation.

## What we deploy

A single-node OKD cluster: one VM that is at the same time the Kubernetes
control plane (API server, etcd, controllers) and the only worker.

OKD is the community distribution of Kubernetes that Red Hat OpenShift is
built from. The OpenStack operators are developed and tested against
OpenShift, and they rely on things plain Kubernetes does not ship: the
Operator Lifecycle Manager (OLM), Routes, Multus, a certificate authority
for webhooks. OKD provides all of them.

## How the installation works

We use the **agent-based installer** with `platform: none`:

```text
 bastion                              workstation                 host cloud
 -------                              -----------                 ----------
 install-config.yaml  \
 agent-config.yaml     >  openshift-install agent create image
                      /        |
                               v
                        agent.x86_64.iso  ---- scp ---->  image upload ---> boot the VM
                                                                               |
 openshift-install agent wait-for ...  <------- cluster API comes up ----------+
```

- `install-config.yaml` describes the cluster (name, domain, networks).
- `agent-config.yaml` describes the machine: its interfaces by MAC address
  and their static configuration.
- The resulting ISO is self-contained. The VM boots it, validates its own
  environment (DNS, disk, connectivity), writes CentOS Stream CoreOS to its
  disk, reboots and assembles the cluster. No external bootstrap machine or
  load balancer is involved.
- `platform: none` tells OKD not to integrate with the host cloud at all.
  The cluster does not know it runs on OpenStack, which keeps the lab
  independent of the provider — and avoids confusing the host cloud with the
  cloud we are about to build.

The VM is created with two disks in a specific boot order: the empty root
volume first, the ISO second. On first boot the empty disk is skipped and
the ISO starts; after installation the disk is bootable and the ISO is
never used again.

## Procedure

1. Prepare the bastion (client tools, DNS, and the time service when
   `BASTION_NTP_SERVER=true`).

   **[CHANGE]** — workstation:

   ```bash
   scripts/workstation/ssh-bastion.sh scripts/bastion/01-setup-bastion.sh
   ```

2. Build the installer ISO.

   **[CHANGE]** — workstation:

   ```bash
   scripts/workstation/ssh-bastion.sh scripts/bastion/02-create-agent-iso.sh
   ```

   The rendered `install-config.yaml` and `agent-config.yaml` are kept in
   `.work/okd/rendered/` on the bastion. Read them once: they are short.

3. Upload the ISO and create the node. The ISO embeds certificates valid
   for 24 hours, so do this right after step 2.

   **[CHANGE]** — workstation:

   ```bash
   scripts/workstation/boot-okd-node.sh
   ```

4. Follow the installation.

   **[CHANGE]** — bastion (changes nothing in the cluster, but replaces
   `~/.kube/config` on the bastion):

   ```bash
   scripts/bastion/03-wait-for-okd.sh
   ```

   The script only waits and reports; interrupting and re-running it is
   harmless. It finishes by installing the cluster credentials in
   `~/.kube/config` on the bastion.

   Measured on the lab: the node answers ping about 90 seconds after its
   creation, the installer reports "Cluster is ready for install" after
   about five minutes, and "Install complete" 46 minutes after the creation
   of the node.

## Concepts worth understanding here

- **DNS is a hard dependency.** `api.<cluster>.<domain>` (clients),
  `api-int.<cluster>.<domain>` (the node itself) and
  `*.apps.<cluster>.<domain>` (every Route) must resolve before and after
  installation. On this lab they all point to the single node and are served
  by dnsmasq on the bastion. If the bastion DNS stops, `oc` stops working —
  see [../troubleshooting/dns-and-routing.md](../troubleshooting/dns-and-routing.md).
- **The node OS is managed by the cluster.** You do not `dnf install` on
  CentOS Stream CoreOS, and configuration changes are applied through
  cluster resources (MachineConfig). SSH access (`ssh core@<node>` from the
  bastion) exists for emergencies; day-to-day host access goes through
  `oc debug node/<name>`.
- **Cluster operators.** OKD itself is run by operators. `oc get
  clusteroperators` is the OKD equivalent of what `oc get
  openstackcontrolplane` will be for OpenStack: one line per component with
  Available / Progressing / Degraded.

## Verify

**[READ-ONLY]** — bastion:

```bash
oc get clusterversion
oc get nodes -o wide
oc get clusteroperators
```

Expected: one node `Ready` with roles `control-plane,master,worker`; every
cluster operator `AVAILABLE=True`, `PROGRESSING=False`, `DEGRADED=False`.

Check the MTU chain described in the architecture:

**[READ-ONLY]**

```bash
oc get network.config cluster -o jsonpath='{.status.clusterNetworkMTU}{"\n"}'
```

The value must be the host network MTU minus 100 (1342 on a host network
at 1442).

## If something fails

| Symptom | Look at |
|---|---|
| `02-create-agent-iso.sh` fails on network configuration | `nmstatectl` rejects the rendered `agent-config.yaml`; read the message, check `.work/infra.env` |
| The node never contacts the installer (`wait-for` shows no host) | The VM did not boot the ISO, or its static network is wrong. Read the console: `openstack console log show <prefix>-okd`, or open the graphical console; the agent prints validation failures on the login screen |
| Validation "DNS resolution" failing on the console | dnsmasq on the bastion: `dig api-int.<cluster domain> @<bastion ip>`; security group between node and bastion |
| Host status `insufficient`, "Host couldn't synchronize with any NTP server" | Normal for the first two minutes: it clears when the node has selected a time source. If it stays, no NTP server is reachable: set `BASTION_NTP_SERVER=true` and rebuild the ISO |
| Stuck pulling images | Outbound access through the router or the proxy; `curl -I https://quay.io/v2/` from the bastion (add `--proxy <url>` behind a proxy; HTTP 401 is the expected answer) |
| `bootstrap-complete` reached, `install-complete` times out | `oc get clusteroperators` and read the message of the ones not Available. A slow disk (etcd) is the usual cause of widespread flapping: [../prerequisites.md](../prerequisites.md#disk-latency) |
| ISO older than 24 hours | Rebuild: `scripts/bastion/02-create-agent-iso.sh --force`, then boot a new node |

Collecting installer diagnostics:

**[READ-ONLY]** — bastion:

```bash
ssh core@<okd node ip> 'sudo journalctl -b -u agent -u assisted-service --no-pager | tail -100'
```

## Reinstalling the cluster

**[DESTRUCTIVE]** — destroys the cluster and all OpenStack data in it.
Workstation:

```bash
rm deployment/infrastructure/agent-iso.auto.tfvars
terraform -chdir=deployment/infrastructure apply     # removes the OKD node, keeps its ports
```

Then repeat this page from step 2 with `02-create-agent-iso.sh --force`.
