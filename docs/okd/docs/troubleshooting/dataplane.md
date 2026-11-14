# Data plane problems

> Status: partially validated on the lab — validated on 2026-11-11 (OKD 4.22.0-okd-scos.10, operators 18-stable) for scenario A (two provoked failures, partial runs, a full second run), the read-only parts of scenario B and scenario C (service stopped and started); a key mismatch (scenario B) was not provoked and the emulation path of scenario D was not executed, because the lab compute node has KVM

## In short

- A data plane deployment is one Ansible run, recorded once: when it
  fails, fix the cause and create a new deployment under a new name.
- Read the `PLAY RECAP` and the summary line of the failed Job, not the
  first `fatal:` line.
- `True` on the NodeSet means "a deployment finished since the last
  change", not "every service was applied".
- `nova-compute` down is invisible to Kubernetes: only the OpenStack API
  and the smoke test show it.
- Problems that need two compute nodes are in the knowledge base (link
  below).

The data plane is where the lab feels most like Kolla-Ansible: an Ansible run
over SSH configures a host, and services run as containers under systemd.
The differences are that the run is started by creating a resource, executes
in pods, and its output is a pod log.

Names used below: NodeSet `openstack-edpm`, node `edpm-compute-0` at
192.168.122.100, Ansible user `cloud-admin`, key `.work/dataplane-ssh-key`
on the bastion.

Problems that only exist with two compute nodes (a node that is `up` but
not mapped to the cell, a live migration that fails with "address
resolution failed", a router gateway that is not taken over) were
provoked on 2026-11-12 and are described in
[Data plane scale-out, migration and scale-in](../knowledge-base/dataplane-scale-out-and-migration.md).

## Scenario A: a data plane deployment failed

### 1. Initial symptoms

- `oc get openstackdataplanedeployment` shows `STATUS=False` with a message
  about a failed service, or the deployment script ends with "Data plane
  deployment failed".
- An Ansible runner pod is in `Error`.

### 2. Read-only investigation

**[READ-ONLY]**

```bash
dep=edpm-deployment
oc get openstackdataplanedeployment ${dep}
oc get osdpd ${dep} -o json | jq -r '.status.conditions[] | select(.status != "True") | "\(.type): \(.reason) - \(.message)"'
oc get osdpd ${dep} -o json | jq '.status.nodeSetConditions'
oc get openstackdataplanenodeset openstack-edpm -o json | jq -r '.status.conditions[] | select(.status != "True") | "\(.type): \(.reason) - \(.message)"'

# One Job per service, in order. The first one that is not Complete is the failure.
oc get jobs -l openstackdataplanedeployment=${dep} --sort-by=.metadata.creationTimestamp
oc get pods -l openstackdataplanedeployment=${dep} --sort-by=.status.startTime

# The Ansible output of the failed service.
oc logs -l openstackdataplanedeployment=${dep},openstackdataplaneservice=<service> --tail=-1 | grep -n 'fatal:\|FAILED\|UNREACHABLE\|ERROR' | head
oc logs <failed-pod> | sed -n '/fatal:/,/PLAY RECAP/p'
oc logs <failed-pod> | tail -15
```

The pods carry four labels: `app=openstackansibleee`,
`openstackdataplanedeployment`, `openstackdataplanenodeset` and
`openstackdataplaneservice`.

### 3. Expected observations

- Jobs are named `<service>-<deployment>-<nodeset>` (only
  `ssh-known-hosts-<deployment>` has no NodeSet suffix). Services before the
  failure are `Complete`; the failed one has several pods in `Error`
  (retries, up to the Job's back-off limit, 6 by default, a new pod every
  ten to twenty seconds at first); later services have no Job.
- The log is standard Ansible: a `fatal:` line with the task name and
  message, and a `PLAY RECAP` with `failed=1` or `unreachable=1`. The last
  line is a summary: `EDPM AEE SUMMARY: status=failed rc=1`.
- A `fatal:` line is not always the failure. The log of a **successful**
  `bootstrap` contains one that Ansible ignores ("One or more supplied key
  could not be found in the database", followed by `...ignoring`). Trust
  the `PLAY RECAP` and the summary line.
- While a Job is retrying, the deployment and the NodeSet both show `False`,
  "Deployment in progress". Once the limit is reached the deployment shows
  `BackoffLimitExceeded` and the NodeSet `DeploymentReady: Error`.

Two failures provoked on the lab, and what they look like:

| Mistake | Where it shows | Message |
|---------|----------------|---------|
| Unknown name in `servicesOverride` | Deployment condition, at once; no Job is created | `Service error occurred OpenStackDataPlaneService.dataplane.openstack.org "no-such-service" not found` |
| `ansibleLimit` that matches no host | Pod log, then the deployment condition after the retries | `[ERROR]: Specified inventory, host pattern and/or --limit leaves us with no hosts to target.` then `Deployment error occurred nodeSet: openstack-edpm error: backoff limit reached for execution.name ...` |

Typical first failures, by service:

| Service | Typical failure | Cause |
|---------|-----------------|-------|
| any (first to run) | `UNREACHABLE! ... Permission denied (publickey)` | Key in the Secret does not match the node, or wrong `ansibleUser` |
| any | `UNREACHABLE! ... Connection timed out` | Runner pod has no path to 192.168.122.100: ctlplane attachment, port security ([network](network.md)) |
| `repo-setup`, `bootstrap`, `install-os` | Download or package errors | No outbound access or DNS from the node ([DNS](dns-and-routing.md), scenario D) |
| `configure-network` | Task fails or the node becomes unreachable right after | Network template does not match the node's interfaces |
| `validate-network` | Ping or DNS validation fails | Addresses, MTU or the data plane DNS |
| `install-certs` | Missing Secret | Certificates for the node were not issued: check `oc get certificates` |
| `ovn` | Container starts, cannot connect | OVN southbound database unreachable on internalapi |
| `libvirt`, `nova` | Service fails to start | See scenarios C and D |

### 4. Root cause

The operator runs services strictly in order and stops at the first failed
Job. Kubernetes retries a failed Job a few times, which is why one failure
shows up as several `Error` pods. Nothing is rolled back on the node: it is
left exactly where Ansible stopped, as with any Ansible run.

A deployment is a record of one run. Once failed it stays failed; it is not
retried when you fix the cause.

### 5. Resolution

1. Fix the cause: the NodeSet variables, a Secret, the network, the node.
   A deployment that is still running or retrying cannot be deleted
   directly. The admission webhook answers "deletion of a running deployment
   not allowed: set annotation dataplane.openstack.org/confirm-delete=true
   to confirm". Annotate, then delete:

   **[CHANGE]** Stops the retries. The node stays where Ansible left it.

   ```bash
   oc annotate openstackdataplanedeployment <name> dataplane.openstack.org/confirm-delete=true
   oc delete openstackdataplanedeployment <name>
   ```

   A deployment that has finished, successfully or not, is deleted without
   the annotation. After the deletion of a failed deployment the NodeSet
   returns to `True` if the previous deployment still matches its content.
2. Start a new run under a new name. Either everything:

   **[CHANGE]** Runs Ansible on the compute nodes.

   ```bash
   scripts/bastion/07-openstack-dataplane.sh edpm-deployment-2
   ```

   or only from the failed service onwards, to save time:

   **[CHANGE]**

   ```bash
   cat <<'YAML' | oc apply -f -
   apiVersion: dataplane.openstack.org/v1beta1
   kind: OpenStackDataPlaneDeployment
   metadata:
     name: edpm-deployment-retry-1
     namespace: openstack
   spec:
     nodeSets:
       - openstack-edpm
     servicesOverride:
       - install-certs
       - ovn
       - neutron-metadata
       - libvirt
       - nova
   YAML
   ```

3. Optionally remove the failed deployment once you have what you need from
   its logs:

   **[CHANGE]** Deletes the Jobs and pod logs of that run.

   ```bash
   oc delete openstackdataplanedeployment edpm-deployment
   ```

Careful with partial runs: the operator does not check which services ran.
On the lab, a deployment limited to `nova` by `servicesOverride` set
`deployedConfigHash` to the current `configHash` and the NodeSet to `True`,
although the changed variable concerned another service. `True` therefore
means "a deployment finished since the last change", not "every service
was applied". After a partial run, finish with a full run when convenient.

A full second run on the already deployed lab node took 13 minutes 43
seconds (21 minutes the first time). It restarted `ovn_controller` and
`nova_compute`, left `ovn_metadata_agent` running, and did not reboot the
node.

### 6. Verification

**[READ-ONLY]**

```bash
oc get openstackdataplanedeployment
oc get openstackdataplanenodeset openstack-edpm
oc rsh openstackclient openstack compute service list --service nova-compute
oc rsh openstackclient openstack network agent list
```

A node deployed for the first time must also be mapped to its cell:

**[CHANGE]**

```bash
oc rsh nova-cell0-conductor-0 nova-manage cell_v2 discover_hosts --verbose
```

### 7. Risks and precautions

- Do not edit a failed deployment or delete its Job pods hoping for a retry.
- Read the log before deleting the deployment; the logs live in its pods.
- `configure-network` on a node with running instances interrupts their
  networking. Skip it with `servicesOverride` when the network is fine.
- The `reboot-os` service may reboot the node. On the lab it never did (it
  ran for 13 seconds in the second full run), but it decides at run time.
- The script `07-openstack-dataplane.sh` applies the NodeSet from the
  repository template before it creates the deployment: a change made with
  `oc patch` on the NodeSet is reverted by it.

## Scenario B: SSH or key problems

### 1. Initial symptoms

- The first service fails with `UNREACHABLE`.
- The NodeSet stays not ready on `SetupReady` or `InputReady` with "Waiting
  for input ..., not yet ready".

### 2. Read-only investigation

**[READ-ONLY]**

```bash
oc get osdpns openstack-edpm -o jsonpath='{.spec.nodeTemplate.ansibleSSHPrivateKeySecret} {.spec.nodeTemplate.ansible.ansibleUser}{"\n"}'
oc get secret dataplane-ansible-ssh-private-key-secret -o json | jq -r '.data | keys[]'
oc get secret nova-migration-ssh-key -o json | jq -r '.data | keys[]'

# Does the key in the cluster match the key on the bastion and on the node?
oc get secret dataplane-ansible-ssh-private-key-secret -o jsonpath='{.data.ssh-publickey}' | base64 -d | ssh-keygen -lf -
ssh-keygen -lf .work/dataplane-ssh-key.pub
ssh -i .work/dataplane-ssh-key -o BatchMode=yes cloud-admin@192.168.122.100 'sudo -n true && echo SUDO_OK; ssh-keygen -lf ~/.ssh/authorized_keys'

# Can the cluster reach the node on ctlplane?
oc get network-attachment-definitions ctlplane
oc get osdpns openstack-edpm -o jsonpath='{.spec.networkAttachments}{"\n"}'
```

### 3. Expected observations

- The Secret has `ssh-privatekey`, `ssh-publickey` and `authorized_keys`;
  `nova-migration-ssh-key` has `ssh-privatekey` and `ssh-publickey`.
- The fingerprint of the Secret and of the file on the bastion are
  identical. The node prints `SUDO_OK` and one fingerprint per key it
  trusts: on the lab two, the key of the workstation and the data plane
  key. One of them must be the fingerprint of the Secret.
- Login from the bastion works and `sudo` needs no password.
- The NodeSet lists `ctlplane` in `networkAttachments`, and the NAD exists.

### 4. Root cause

The node must already trust the key: the public key is injected when the VM
is created, the private key is loaded into the Secret later. If the key pair
on the workstation was regenerated in between (or the Secret was created
from another file), they no longer match. The other cause is reachability:
the runner pod reaches the node through a macvlan interface on ctlplane,
which depends on the NAD and on the host cloud letting that traffic through.

### 5. Resolution

Mismatch: the simplest consistent fix is to make the Secret match what the
node trusts.

**[CHANGE]**

```bash
oc delete secret dataplane-ansible-ssh-private-key-secret
scripts/bastion/07-openstack-dataplane.sh edpm-deployment-2
```

The script creates the Secret from `.work/dataplane-ssh-key` only when it
does not exist, which is why it is deleted first. If that file
itself is not the key the node trusts, the node must be given the right
public key (through an existing access path) or be recreated with Terraform.

Reachability: see [network](network.md), scenarios B and C.

### 6. Verification

**[READ-ONLY]**

```bash
oc get openstackdataplanenodeset openstack-edpm -o json | jq -r '.status.conditions[] | "\(.type) \(.status)"'
```

### 7. Risks and precautions

- The private key Secret gives root on every compute node. Do not export it.
- Do not loosen `edpm_sshd_allowed_ranges` beyond the lab networks.

## Scenario C: nova-compute down on the node

### 1. Initial symptoms

- `openstack compute service list` shows `nova-compute` `down`, or the host
  is missing.
- Instances fail to schedule ("No valid host").

### 2. Read-only investigation

On the bastion:

**[READ-ONLY]**

```bash
oc rsh openstackclient openstack compute service list
oc rsh openstackclient openstack hypervisor list
oc get pods | grep -E 'nova-cell1-conductor|rabbitmq-cell1'
```

On the compute node:

**[READ-ONLY]**

```bash
sudo systemctl status edpm_nova_compute --no-pager
sudo podman ps -a --format '{{.Names}}\t{{.Status}}'
sudo journalctl -u edpm_nova_compute --since "30 min ago" --no-pager | tail -40
sudo podman logs --tail 60 nova_compute
sudo ls -la /var/lib/openstack/
nc -vz 172.17.0.86 5671
chronyc tracking | head -5
df -h /var/lib/nova
```

### 3. Expected observations

On the healthy lab:

- The compute service is listed under the host name
  `edpm-compute-0.ctlplane.<cluster domain>`. The hypervisor is listed under
  the name the VM gives itself (the host cloud's instance name with its
  default domain), because libvirt reports the kernel host name. The two
  names differ and that is harmless; use `openstack hypervisor list` rather
  than `hypervisor show <name>`.
- The unit `edpm_nova_compute` is active; it only runs `podman start
  nova_compute`. The containers are `nova_compute`, `ovn_controller` and
  `ovn_metadata_agent`, plus `nova_compute_init`, which is `Exited (0)` by
  design. The other units are `edpm_ovn_controller`,
  `edpm_ovn_metadata_agent` and `edpm_libvirt.target`.
- `/var/lib/openstack/` holds the generated configuration, certificates and
  CA bundles.
- `nc` reports `Connected to 172.17.0.86:5671`.
- `chronyc tracking` names the time source (the bastion, 192.168.130.5,
  when `BASTION_NTP_SERVER=true`) with an offset far below a second.

When something is wrong:

| Observation | Cause |
|-------------|-------|
| Unit inactive or failed, container exited | Stopped by hand (`Exited (0)`), or a start-up error: read the container log (configuration, libvirt connection) |
| Container running, log shows AMQP connection errors | RabbitMQ of cell1 unreachable: 172.17.0.86 on internalapi ([network](network.md), [RabbitMQ](galera-and-rabbitmq.md)) |
| Container running and connected, service `down` | Clock skew between node and control plane, or the cell conductor is down |
| Service absent from the list, no hypervisor | Host never registered or not discovered: run `discover_hosts` |
| Log shows libvirt errors | See scenario D |

### 4. Root cause

`nova-compute` reports through RabbitMQ of its cell to the cell conductor.
"Down" means no report for a minute: either the process is not running, or
its messages do not arrive. Nothing on the Kubernetes side notices: with
the service stopped on the lab, the control plane resource and the NodeSet
both stayed `True`. Only the OpenStack API (and the smoke test, "FAIL  Data
plane: nova-compute services up") shows it. Because the compute node sits outside the
cluster, it depends on the MetalLB address of `rabbitmq-cell1` being
reachable on the internalapi network.

### 5. Resolution

Process problem on a correct configuration:

**[CHANGE]**

```bash
sudo systemctl restart edpm_nova_compute
```

Configuration problem: fix it in the NodeSet or in `nova-extra-config` and
run the `nova` service again
([guide](../operations/08-dataplane-changes.md)). Do not edit files under
`/var/lib/openstack/` on the node.

Host not registered:

**[CHANGE]**

```bash
oc rsh nova-cell0-conductor-0 nova-manage cell_v2 discover_hosts --verbose
```

OVN metadata agent shown as not alive (`XXX` in
`openstack network agent list`, "FAIL  Data plane: OVN agents alive" in the
smoke test) while `nova-compute` is up. Observed on the lab after the
reboot of the OKD node: the agent had stopped trying to reach the OVN
southbound database and did not come back by itself, although its systemd
unit was `active` and its container `healthy`
([details](node-and-okd.md#scenario-b-planned-node-reboot)).

**[CHANGE]** Restarts the metadata agent on the compute node. Running
instances keep their network; the metadata service is interrupted for a few
seconds.

```bash
sudo systemctl restart edpm_ovn_metadata_agent
```

The agent was reported alive ten seconds later.

On the two reboots of 2026-11-12 and on the start of the whole lab of
2026-11-14 the OVN controller was disconnected as well. On 2026-11-14
both agents were left alone and reconnected by themselves 15 and 16
minutes after their start; the restart saves that wait.
Check it with `sudo podman exec ovn_controller ovn-appctl
connection-status` and restart both units if it is `not connected`: see
[why the OVN agents are dead after a reboot](../knowledge-base/okd-node-maintenance.md#why-are-the-ovn-agents-of-the-compute-node-dead-after-a-reboot-of-the-okd-node-and-how-do-i-fix-them).

### 6. Verification

**[READ-ONLY]**

```bash
oc rsh openstackclient openstack compute service list --service nova-compute     # up
oc rsh openstackclient openstack hypervisor list
tests/smoke-test.sh
```

Measured on the lab: the service is reported `down` 55 seconds after
`systemctl stop edpm_nova_compute`, and `up` again 7 seconds after the
start.

### 7. Risks and precautions

- Restarting `nova-compute` does not touch running instances.
- Do not `podman rm` or `podman run` the containers by hand; systemd and
  Ansible own them.

### Reproduce it in the lab

**[CHANGE]** Stops `nova-compute`; running instances are not affected, new
ones cannot be scheduled.

```bash
ssh -i .work/dataplane-ssh-key cloud-admin@192.168.122.100 'sudo systemctl stop edpm_nova_compute'
sleep 60
oc rsh openstackclient openstack compute service list --service nova-compute
oc get openstackcontrolplane,openstackdataplanenodeset
tests/smoke-test.sh
```

Follow the investigation above, then restore:

**[CHANGE]**

```bash
ssh -i .work/dataplane-ssh-key cloud-admin@192.168.122.100 'sudo systemctl start edpm_nova_compute'
```

## Scenario D: instances fail to start without nested virtualization

### 1. Initial symptoms

- `nova-compute` is `up`, but every instance goes to `ERROR` with a fault
  mentioning libvirt, or `nova-compute` fails at start-up.
- Instances boot but are extremely slow (expected with emulation, not a
  fault).

### 2. Read-only investigation

On the compute node:

**[READ-ONLY]**

```bash
grep -cE 'vmx|svm' /proc/cpuinfo
ls -l /dev/kvm
sudo podman logs --tail 80 nova_compute 2>&1 | grep -i 'kvm\|virt_type\|libvirt' | tail
sudo podman exec nova_compute grep -rs 'virt_type\|cpu_mode' /etc/nova/ | sort -u
```

On the bastion:

**[READ-ONLY]**

```bash
oc get configmap nova-extra-config -o yaml
grep COMPUTE_VIRT_TYPE lab.env
oc rsh openstackclient openstack server show <server> -c fault -c status
oc rsh openstackclient openstack hypervisor list -c "Hypervisor Hostname" -c "Hypervisor Type" -c State
```

### 3. Expected observations

- `0` CPU flags and no `/dev/kvm`: the compute VM has no hardware
  virtualization. `virt_type` must be `qemu`.
- A positive count and `/dev/kvm` present: nested virtualization is
  available and the default (`kvm`) works. This is the case of the lab node
  (count `8`). The ConfigMap `nova-extra-config` then holds
  `virt_type = kvm` and `cpu_mode = host-model`, which are also the
  defaults of the operator.
- The hypervisor type column shows `QEMU` in both cases: it names the
  libvirt driver, not the acceleration. To know what an instance really
  uses, look at its domain on the node:
  `sudo podman exec nova_compute virsh -c qemu:///system dumpxml <domain> | head -1`
  prints `<domain type='kvm' ...>` or `type='qemu'`.
- The fault of a failed instance mentions that KVM is not available or that
  the domain type is not supported.

### 4. Root cause

The compute node is itself a virtual machine. KVM inside a VM needs the host
cloud to expose the virtualization extensions (nested virtualization). When
it does not, libvirt cannot start `kvm` domains, and nova's default
`virt_type` is `kvm`. Software emulation (`qemu`) always works, at a large
performance cost. The lab chooses automatically at deployment time
(`COMPUTE_VIRT_TYPE=auto`), so this fault appears when the setting was
forced, when the ConfigMap was removed, or when a node was moved to a host
without the extensions.

### 5. Resolution

Set the hypervisor type explicitly and run the `nova` service again:

**[CHANGE]**

```bash
sed -i 's/^COMPUTE_VIRT_TYPE=.*/COMPUTE_VIRT_TYPE=qemu/' lab.env
scripts/bastion/07-openstack-dataplane.sh edpm-deployment-qemu-1
```

Existing instances in `ERROR` must be deleted and recreated, or hard
rebooted.

### 6. Verification

**[READ-ONLY]**

```bash
ssh -i .work/dataplane-ssh-key cloud-admin@192.168.122.100 "sudo podman exec nova_compute grep -rs virt_type /etc/nova/"
tests/smoke-test.sh
```

Expected with emulation: a `virt_type = qemu` line in
`/etc/nova/nova.conf.d/25-nova-extra.conf`. With KVM the same file says
`virt_type = kvm`.

**[CHANGE]** Boots and deletes a test instance.

```bash
tests/smoke-test.sh --functional
```

### 7. Risks and precautions

- With `qemu`, use tiny images and flavors (CirrOS, 256 MB). Booting a
  general-purpose cloud image takes many minutes.
- Changing `virt_type` on a node with running instances makes them
  unmanageable until they are recreated. Decide the type before creating
  workloads.
- The lab template sets `cpu_mode = none` together with `qemu`. That path
  was not executed: the lab compute node has KVM.
