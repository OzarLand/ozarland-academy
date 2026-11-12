# OpenStack compute operations

> Status: every command was run on the lab (OKD 4.22, operators 18-stable,
> OpenStack 2023.1 Antelope, one KVM compute node) on 2026-11-12

The Nova control services are pods; `nova_compute` is a podman container
on the compute node and libvirt runs on that host as systemd services.
With one compute node, live migration and evacuation cannot be exercised
(see [open questions](open-questions.md)). `os`, `$o` and `compute` are
the helpers defined in [networking with OVN](openstack-networking-ovn.md):
admin client, member client, SSH to the compute node.

## Entries

### How do I boot an instance and follow what happens to it?

**Context**: first boot in a new project, or a user says "my instance is
stuck".

**How**:

**[CHANGE]**

```bash
$o server create kb-vm1 --image kb-cirros-0.6.3 --flavor kb.tiny \
  --network kb-demo-net --key-name kb-demo-key --security-group kb-demo-ssh --wait
```

**[READ-ONLY]**

```bash
$o server list -c Name -c Status -c Networks
$o server event list kb-vm1
$o server show kb-vm1 -f value -c fault
os server show kb-vm1 -c OS-EXT-SRV-ATTR:host -c OS-EXT-SRV-ATTR:hypervisor_hostname -c OS-EXT-SRV-ATTR:instance_name
```

**Observed on the lab** (2026-11-12): first instance ACTIVE after 24 s
(image download to the node included), second one after 18 s (image
cached). The event list gives one line per action with its request ID:

```text
reboot 2026-11-12T06:48:20.000000
start 2026-11-12T06:47:53.000000
stop 2026-11-12T06:47:43.000000
create 2026-11-12T06:44:29.000000
```

**Why / how it works**: `nova-api` (pod) writes the request,
`nova-scheduler` asks Placement for candidates, the cell conductor sends
the build to `nova_compute` on the node through the cell RabbitMQ.
Kolla-Ansible equivalent: identical API; the services are containers on
the controllers.

**Pitfalls**:

- The host of an instance is the **service host**
  (`edpm-compute-0.ctlplane.okd.lab.example.com`), but the hypervisor
  hostname is the node's own operating-system hostname. They differ on the
  lab; use the service host in `compute service` and `aggregate` commands.
- A failed boot shows `No valid host was found` in `fault` and nothing
  more: the reason is in the scheduler and conductor logs (see
  [capacity and observability](openstack-capacity-and-observability.md)).
- Members do not see the `OS-EXT-SRV-ATTR` fields; use the admin client.

**See also**: [Verification](../installation/07-verification.md),
[Logs](../operations/02-logs.md),
[Data plane troubleshooting](../troubleshooting/dataplane.md)

### How do I get the console log or a graphical console?

**Context**: the instance is ACTIVE but does not answer on the network.

**How**:

**[READ-ONLY]**

```bash
$o console log show kb-vm1 --lines 12
$o console url show kb-vm1 --novnc
oc get route -n openstack | grep novnc
```

**Observed on the lab** (2026-11-12):

```text
=== cirros: current=0.6.3 uptime=15.00 ===
login as 'cirros' user. default password: 'gocubsgo'. use 'sudo' for root.
kb-vm1 login:
https://nova-novncproxy-cell1-public-openstack.apps.okd.lab.example.com/vnc_lite.html?path=<token>
```

From the bastion the page answered HTTP 200 and the WebSocket handshake
returned `101 Switching Protocols`.

**Why / how it works**: the console log is the file `console.log` of the
instance on the compute node, read through `nova_compute`. The noVNC proxy
is a pod per cell (`nova-cell1-novncproxy-0`) published by a Route; it
connects to the VNC port of QEMU on the node over the internal API
network. Kolla-Ansible equivalent: `nova_novncproxy` behind HAProxy, URL
built from `kolla_external_fqdn`.

**Pitfalls**:

- The URL uses the lab wildcard domain and the lab CA: your browser must
  resolve `*.apps.okd.lab.example.com` and trust (or accept) the
  certificate, otherwise the page stays blank.
- The token in the URL is valid for a few minutes and for one instance.
  Treat it as a secret.
- An empty console log does not mean a dead instance: some images log to
  the graphical console only.

**See also**: [DNS and routing](../troubleshooting/dns-and-routing.md),
[Architecture](../architecture.md)

### How do I stop, start, reboot, rebuild, rescue or snapshot an instance?

**Context**: day-to-day lifecycle requests, done by the project member.

**How**:

**[CHANGE]**

```bash
$o server stop kb-vm2
$o server start kb-vm2
$o server reboot --soft --wait kb-vm2
$o server reboot --hard --wait kb-vm2
$o server image create --name kb-vm2-snap --wait kb-vm2
$o server rescue kb-vm2
$o server unrescue kb-vm2
```

**[DESTRUCTIVE]** Rebuild replaces the root disk with the image content.

```bash
$o server rebuild --image kb-cirros-0.6.3 kb-vm2
```

**[READ-ONLY]**

```bash
$o image show kb-vm2-snap -c disk_format -c size -c visibility -c properties
compute sudo virsh domblklist instance-0000000e
```

**Observed on the lab** (2026-11-12): stop and start about 4 s each;
snapshot of a running CirrOS instance 8 s, giving a private `qcow2` image
of 54 MB with `image_type: snapshot` and `base_image_ref`; rebuild ACTIVE
after about 4 s; rescue after about 8 s. In rescue mode the disks are:

```text
 vda      /var/lib/nova/instances/<instance-id>/disk.rescue
 vdb      /var/lib/nova/instances/<instance-id>/disk
 sda      /var/lib/nova/instances/<instance-id>/disk.config.rescue
```

**Why / how it works**: all these actions are executed by `nova_compute`
through libvirt on the node. A snapshot is uploaded to Glance, which
stores it on its persistent volume. Rescue boots the instance from the
image it was created from and attaches the original disk as second disk.
Kolla-Ansible equivalent: identical.

**Pitfalls**:

- The snapshot is `private` and owned by the project; it counts in the
  Glance volume of the lab (local storage, no quota by default).
- A live snapshot is crash-consistent only. Stop the instance first when
  the content matters.
- Rebuild keeps addresses and the instance ID but **destroys the root
  disk**; rescue does not.
- Do not leave an instance in RESCUE: most other actions are refused in
  that state.

**See also**: [Storage troubleshooting](../troubleshooting/storage.md),
[Backup and restore](../lifecycle/05-backup-and-restore.md)

### Can I resize an instance when there is only one compute node?

**Context**: with Kolla-Ansible a single-node cloud refuses resize until
you set `allow_resize_to_same_host` yourself.

**How**:

**[READ-ONLY]**

```bash
oc exec nova-api-0 -c nova-api-api -- grep -n allow_resize /etc/nova/nova.conf.d/01-nova.conf
```

**[CHANGE]**

```bash
$o server resize --flavor kb.small kb-vm2
$o server show kb-vm2 -f value -c flavor -c status
$o server resize confirm kb-vm2
```

**Observed on the lab** (2026-11-12):

```text
6:allow_resize_to_same_host = true
kb.small (kb.small)
VERIFY_RESIZE
ACTIVE
confirmResize 2026-11-12T06:49:25.000000
resize 2026-11-12T06:48:31.000000
```

No configuration change was needed. `VERIFY_RESIZE` was reached within a
minute.

**Why / how it works**: the nova operator renders
`allow_resize_to_same_host = true` in the configuration of `nova-api` by
default. The scheduler then accepts the current host as target and the
compute service resizes the disk in place. Kolla-Ansible equivalent: add
the option under `[DEFAULT]` in `/etc/kolla/config/nova.conf` and
reconfigure.

**Pitfalls**:

- A resize stops the instance; it is not a live operation.
- The instance holds **both** allocations in Placement until you confirm
  or revert. Unconfirmed resizes eat capacity.
- A flavor with a smaller disk is refused.
- On a multi-node cloud, resize to another host needs the migration SSH
  key (`nova-migration-ssh-key`) deployed by the `nova` data plane
  service. This path could not be tested with one node.

**See also**: [Data plane changes](../operations/08-dataplane-changes.md),
[Change service configuration](../operations/04-change-service-configuration.md)

### Where are instance files, libvirt and the Nova containers on the compute node?

**Context**: you need to look at the hypervisor itself: disk usage, a
domain that will not start, leftovers.

**How**:

**[READ-ONLY]**

```bash
compute sudo virsh list --all
compute sudo ls -la /var/lib/nova/instances/ /var/lib/nova/instances/_base
compute 'systemctl list-units --type=service --no-pager | grep -E "edpm|virt"'
compute 'sudo podman ps --format "{{.Names}} {{.Status}}"'
compute sudo podman exec nova_compute ls /etc/nova/nova.conf.d/
compute 'sudo podman logs --since 10m nova_compute 2>&1 | tail -5'
compute 'sudo journalctl -u edpm_nova_compute --since "15 min ago" --no-pager | tail -5'
```

**Observed on the lab** (2026-11-12):

```text
 5    instance-0000000d   running
 13   instance-0000000e   running
edpm_nova_compute.service        loaded active running nova_compute container
virtlogd.service                 loaded active running libvirt logging daemon
virtnodedevd.service             loaded active running libvirt nodedev daemon
virtqemud.service                loaded active running libvirt QEMU daemon
01-nova.conf
02-nova-host-specific.conf
nova-blank.conf
```

Each instance has a directory `/var/lib/nova/instances/<instance-id>/`
with `console.log` (root, mode 600), `disk` (qcow2 overlay, 31 MB for
CirrOS), `disk.config` (config drive) and `disk.info`. `_base/` held 13
cached base images of 112 MB each (one per image booted since the
installation, test runs included), still there after all instances were
deleted.

**Why / how it works**: the data plane runs libvirt as modular systemd
daemons **on the host** and only `nova_compute` in a container, started by
the unit `edpm_nova_compute` with the Kolla entry point (the log shows
`Kolla config strategy set to: COPY_ALWAYS`). Its configuration comes from
`/var/lib/openstack/nova` on the host, written by Ansible and copied into
the container at each start.
Kolla-Ansible equivalent: `nova_libvirt` and `nova_compute` containers,
logs in `/var/log/kolla/nova/`.

**Pitfalls**:

- There is **no** `/var/log/containers/nova` or `/var/log/kolla`: logs are
  in `podman logs` and the journal only.
- `virsh` runs on the host with `sudo`, not inside a container.
- The image cache in `_base` is not emptied when instances are deleted;
  Nova removes unused base images later with a periodic task. A busy test
  day can fill the disk (58 GB on the lab).
- Files edited under `/var/lib/openstack/nova` are overwritten by the
  next `nova` deployment.

**See also**: [Data plane troubleshooting](../troubleshooting/dataplane.md),
[Logs](../operations/02-logs.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md)

### How do I run nova-manage and nova-status?

**Context**: cell mapping checks, host discovery, upgrade checks. With
Kolla-Ansible you `docker exec nova_api nova-manage ...`.

**How**:

**[READ-ONLY]** The output of `list_cells` contains connection URLs with
passwords: always mask it.

```bash
nm() { oc exec nova-cell0-conductor-0 -c nova-cell0-conductor-conductor -- "$@" 2>&1 | grep -v DEBUG; }
nm nova-manage cell_v2 list_cells | sed -E 's#://[^@]*@#://<user>:<password>@#g'
nm nova-manage cell_v2 list_hosts
nm nova-manage db version
nm nova-manage api_db version
nm nova-status upgrade check
oc get cronjob -n openstack | grep nova
```

**[CHANGE]** Maps new compute hosts to their cell; harmless when there is
none.

```bash
nm nova-manage cell_v2 discover_hosts --verbose
```

**Observed on the lab** (2026-11-12):

```text
| cell0 | <cell-id> | rabbit: | mysql+pymysql://<user>:<password>@openstack.openstack.svc/nova_cell0?... |
| cell1 | <cell-id> | rabbit://<user>:<password>@rabbitmq-cell1.openstack.svc:5671/?ssl=1 | mysql+pymysql://<user>:<password>@openstack-cell1.openstack.svc/nova_cell1?... |
|   cell1   | <cell-id> | edpm-compute-0.ctlplane.okd.lab.example.com |
Found 2 cell mappings.
Skipping cell0 since it does not contain hosts.
Found 0 unmapped computes in cell: <cell-id>
nova-cell0-db-purge      0 0 * * *
nova-cell1-db-purge      0 0 * * *
```

The database versions were `960aac0e09ea` (cell) and `b30f573d3377`
(API). `nova-status upgrade check` reports Success everywhere except a Warning
for the Cinder API (no `volumev3` endpoint: Cinder is not deployed) and
exits with code 1.

**Why / how it works**: the cell0 conductor pod has the API database and
cell0 credentials mounted, so `nova-manage` works there without options.
Cell1 has its own Galera and RabbitMQ instances. The compute node was
already mapped to cell1 without any manual step (the nova operator runs
the discovery itself: the status of the `NovaCell` resource records a
`nova-compute-discovery` hash), and database purge is done by
the two CronJobs.
Kolla-Ansible equivalent: `docker exec nova_api nova-manage ...` and
`kolla-ansible ... nova-cell` plays.

**Pitfalls**:

- `debug = true` is the default in the Nova configuration here: every
  `nova-manage` call prints dozens of DEBUG lines first, and the version
  commands add INFO lines from the migration library. Filter them.
- `list_cells` prints database and RabbitMQ passwords in clear. Never
  paste it unmasked.
- Exit code 1 of `nova-status` means "warnings", not failure; a script
  with `set -e` stops on it.
- Do not run schema commands (`db sync`, `archive_deleted_rows`) by hand:
  the operator runs them as jobs.

**See also**: [Inspect service status](../operations/01-inspect-service-status.md),
[Galera and RabbitMQ](../troubleshooting/galera-and-rabbitmq.md)

### How do I read capacity and allocations in Placement?

**Context**: "No valid host" or a capacity review: what does the scheduler
believe the node can take?

**How**:

**[READ-ONLY]** Admin only: a member gets HTTP 403 on these calls.

```bash
rp=$(os resource provider list -f value -c uuid | sed -n 1p)
os resource provider inventory list $rp
os resource provider usage show $rp
os resource provider show $rp --allocations -f json
os resource provider trait list $rp -f value | wc -l
os allocation candidate list --resource VCPU=1 --resource MEMORY_MB=256 -f value
os hypervisor stats show
```

**Observed on the lab** (2026-11-12), two instances running:

```text
| resource_class | allocation_ratio | min_unit | max_unit | reserved | step_size | total | used |
| VCPU           |              4.0 |        1 |        8 |        0 |         1 |     8 |    2 |
| MEMORY_MB      |              1.0 |        1 |    15729 |      512 |         1 | 15729 |  768 |
| DISK_GB        |              0.9 |        1 |       58 |        1 |         1 |    58 |    3 |
```

The candidate list shows the remaining room as
`VCPU=2/32,MEMORY_MB=768/15217,DISK_GB=3/51`; the provider has 75 traits.

**Why / how it works**: capacity is `(total - reserved) * allocation_ratio`.
`nova_compute` reports the inventory; the ratios come from
`initial_cpu_allocation_ratio = 4.0`, `initial_ram_allocation_ratio = 1.0`
and `initial_disk_allocation_ratio = 0.9` in the generated configuration.
The `openstackclient` pod already contains the Placement plugin.
Kolla-Ansible equivalent: same commands after installing
`osc-placement`; the initial ratios are the Nova defaults of the release
unless overridden in `nova.conf`.

**Pitfalls**:

- Memory is not overcommitted at all (ratio 1.0) and 10 % of the disk is
  held back (ratio 0.9): the node is "full" earlier than on an older
  cloud with 16.0 and 1.5.
- `hypervisor stats show` is deprecated and ignores ratios; trust
  Placement.
- The resource provider name is the hypervisor hostname, not the service
  host.

**See also**: [Resource exhaustion](../troubleshooting/resource-exhaustion.md),
[capacity and observability](openstack-capacity-and-observability.md)

### How do I change an allocation ratio (or any nova-compute option) the supported way?

**Context**: you want more vCPU overcommit. On Kolla-Ansible: edit
`/etc/kolla/config/nova/nova-compute.conf`, then
`kolla-ansible reconfigure -t nova`.

**How**:

**[CHANGE]** Extra configuration for the compute nodes, then a deployment
limited to the `nova` service.

```bash
cat <<'YAML' | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: nova-extra-config
  namespace: openstack
data:
  25-nova-extra.conf: |
    [DEFAULT]
    cpu_allocation_ratio = 8.0
---
apiVersion: dataplane.openstack.org/v1beta1
kind: OpenStackDataPlaneDeployment
metadata:
  name: kb1-nova-ratio-1
  namespace: openstack
spec:
  nodeSets:
    - openstack-edpm
  servicesOverride:
    - nova
YAML
oc wait openstackdataplanedeployment kb1-nova-ratio-1 --for=condition=Ready --timeout=900s
```

**[READ-ONLY]**

```bash
compute sudo podman exec nova_compute cat /etc/nova/nova.conf.d/25-nova-extra.conf
os resource provider inventory list $rp -f value
```

**[CHANGE]** Revert: delete the ConfigMap, run a second deployment
(`kb1-nova-ratio-2`, same content), then reset the ratio in Placement.

```bash
oc delete cm nova-extra-config
os resource provider inventory set $rp --amend --resource VCPU:allocation_ratio=4.0
```

**Observed on the lab** (2026-11-12): deployment Ready in 2 min 17 s
(Ansible recap `ok=140 changed=21 failed=0`); `nova_compute` restarted
once; both instances stayed `running`; a ping on the floating IP every
0.5 s lost 0 of 452 packets; Placement showed `VCPU 8.0` within 70 s.
After the revert deployment (2 min 22 s) the file was gone from the node
**but Placement still showed 8.0**; the `inventory set --amend` command
put it back to 4.0 and it stayed there.

**Why / how it works**: the data plane service `nova` lists the ConfigMap
`nova-extra-config` as an optional data source; its keys are copied to
`/etc/nova/nova.conf.d/` on the nodes of the NodeSet. Without an explicit
`cpu_allocation_ratio`, Nova only applies `initial_cpu_allocation_ratio`
when it **creates** the provider, so removing the option does not restore
the old value. Kolla-Ansible equivalent: same Nova behaviour after
removing the override and reconfiguring.

**Pitfalls**:

- The ConfigMap must be named `nova-extra-config` and the key must end in
  `.conf`; use a prefix above `01` so that it wins over the generated
  file.
- The commands above are those of the drill, when the ConfigMap did not
  exist on a lab with KVM. The deployment script now writes it with a
  `[libvirt]` section (hypervisor type and live migration address, see
  [why live migration failed](dataplane-scale-out-and-migration.md#why-does-live-migration-fail-with-address-resolution-failed)):
  add your options to it with `oc edit` and revert by removing your
  lines, not by deleting the ConfigMap.
- A deployment object is single use: a new change needs a new name. Old
  ones stay as history (`oc get openstackdataplanedeployment`).
- The NodeSet status keeps the hash of the deleted ConfigMap in
  `.status.configMapHashes`; it is not a sign that the file is still
  there.
- Control-plane Nova services (API, scheduler, conductor) do **not** read
  this ConfigMap: use `customServiceConfig` in the control plane resource
  for them.

**See also**: [Data plane changes](../operations/08-dataplane-changes.md),
[Change service configuration](../operations/04-change-service-configuration.md),
[Safe change checklist](../operations/09-safe-change-checklist.md)

### How do I take a compute node out of scheduling and what does a restart of nova_compute do?

**Context**: maintenance on a hypervisor: stop new instances from landing
there, restart the agent, put it back.

**How**:

**[CHANGE]**

```bash
os compute service set --disable --disable-reason "maintenance" \
  edpm-compute-0.ctlplane.okd.lab.example.com nova-compute
compute sudo systemctl restart edpm_nova_compute
os compute service set --enable edpm-compute-0.ctlplane.okd.lab.example.com nova-compute
```

**[READ-ONLY]**

```bash
os compute service list -c Binary -c Host -c Zone -c Status -c State
os compute service list --service nova-compute --long -c Host -c Status -c State -c "Disabled Reason"
os resource provider trait list $rp -f value | grep DISABLED
compute 'ps -eo pid,etimes,cmd | grep qemu-kvm | grep -v grep | cut -c1-80'
```

**Observed on the lab** (2026-11-12): with the service disabled the
provider gained the trait `COMPUTE_STATUS_DISABLED` and a new boot ended
in ERROR with `No valid host was found`; running instances were not
touched. Enabling removed the trait. The manual restart took 3 s; the
`qemu-kvm` processes kept their start time, a ping on the floating IP lost
0 of 120 packets and the service never showed `down` in the API.

```text
nova-conductor nova-cell0-conductor-0 internal enabled up
nova-scheduler nova-scheduler-0 internal enabled up
nova-conductor nova-cell1-conductor-0 internal enabled up
nova-compute edpm-compute-0.ctlplane.okd.lab.example.com nova enabled up
```

**Why / how it works**: disabling sets a trait that the scheduler's
Placement request forbids. Instances are QEMU processes supervised by
libvirt on the host, independent of the `nova_compute` container; the
container is a systemd unit, so `systemctl` is the right tool, not
`podman restart`. Kolla-Ansible equivalent: `docker restart nova_compute`.

**Pitfalls**:

- The control services are listed with the **pod name** as host
  (`nova-scheduler-0`), the compute service with its control-plane FQDN.
- Disabling does not move instances. With one node there is nowhere to
  migrate them; on a larger cloud, live-migrate before maintenance.
- A manual restart is not recorded anywhere in the cluster: prefer a data
  plane deployment when the reason is a configuration change.
- libvirt is not part of that unit: `virtqemud` is a separate host
  service (started with `--timeout 120`) and restarting `edpm_nova_compute`
  does not touch it.

**See also**: [Restart a service](../operations/03-restart-a-service.md),
[Data plane troubleshooting](../troubleshooting/dataplane.md),
[Scale a service](../operations/06-scale-a-service.md)

### How do I create a host aggregate and an availability zone?

**Context**: group hypervisors (hardware type, licence, site) and let
users pick a zone.

**How**:

**[CHANGE]**

```bash
os aggregate create --zone kb-az kb-agg
os aggregate add host kb-agg edpm-compute-0.ctlplane.okd.lab.example.com
os aggregate set --property kbtest=1 kb-agg
```

**[READ-ONLY]**

```bash
os availability zone list --compute -f value
os compute service list --service nova-compute -f value -c Host -c Zone -c Status -c State
os resource provider aggregate list $rp -f value | wc -l
```

**[CHANGE]** Clean up.

```bash
os aggregate remove host kb-agg edpm-compute-0.ctlplane.okd.lab.example.com
os aggregate delete kb-agg
```

**Observed on the lab** (2026-11-12):

```text
internal available
kb-az available
edpm-compute-0.ctlplane.okd.lab.example.com kb-az enabled up
1
{'kbtest': '1'}
```

After the cleanup the node was back in the default zone `nova`.

**Why / how it works**: an availability zone is only the
`availability_zone` metadata of an aggregate; Nova mirrors the aggregate
to Placement (one aggregate on the provider) so that the scheduler can
filter early. The scheduler configuration generated by the operator
already enables `AggregateInstanceExtraSpecsFilter`, so aggregate
properties can be matched by flavor extra specs without any change.
Kolla-Ansible equivalent: identical commands; the filter list is the
upstream default unless overridden.

**Pitfalls**:

- Use the service host name, not the hypervisor hostname, in
  `aggregate add host`.
- On the lab the node joined the zone with two instances running and no
  warning. Instances created with an explicit zone are pinned to it:
  do not move hosts between zones under them.
- `internal` is the zone of the control services; it is not selectable by
  users.

**See also**: [Inspect service status](../operations/01-inspect-service-status.md)

### What does a user see when a quota or the scheduler refuses a boot?

**Context**: "my instance does not start". Two very different refusals:
the API says no at once (quota), or the instance is created and ends in
ERROR (no host).

**How**:

**[CHANGE]** Two deliberate failures in the demo project (quota of 4
instances; one compute node).

```bash
BOOT="--image kb-cirros-0.6.3 --flavor kb.tiny --network kb-demo-net --key-name kb-demo-key --security-group kb-demo-ssh"
$o server create kb-vm-q $BOOT --min 5 --max 5
$o server group create --policy anti-affinity kb-anti
gid=$($o server group show kb-anti -f value -c id)
$o server create kb-vm-a $BOOT --hint group=$gid --wait
$o server create kb-vm-b $BOOT --hint group=$gid --wait
```

**[READ-ONLY]**

```bash
$o server show kb-vm-b -f value -c status -c fault
$o quota show --usage | grep -E 'instances|cores|ram'
oc logs nova-scheduler-0 --since=5m | grep -E 'Filter .* returned 0 hosts'
```

**[CHANGE]** Clean up.

```bash
$o server delete --wait kb-vm-a kb-vm-b
$o server group delete kb-anti
```

**Observed on the lab** (2026-11-12):

```text
Quota exceeded for cores, instances: Requested 5, 5, but already used 0, 0 of 4, 4 cores, instances (HTTP 403)
ERROR
{'code': 500, 'created': '2026-11-12T07:42:06Z', 'message': 'No valid host was found. There are not enough hosts available.'}
... INFO nova.filters [...] Filter ServerGroupAntiAffinityFilter returned 0 hosts
```

The quota refusal creates nothing. The second instance of the
anti-affinity group was created, went to ERROR after a few seconds and
stayed a member of the group until deleted. The first instance booted in
20 seconds.

**Why / how it works**: quotas are checked by `nova-api` before anything
is written; placement and filters are evaluated later by the scheduler,
which logs at INFO level the filter that removed the last host. The user
only ever sees the generic `No valid host`. Kolla-Ansible equivalent:
identical behaviour; the line is in
`/var/log/kolla/nova/nova-scheduler.log`.

**Pitfalls**:

- With `--wait`, the client printed `Error creating server` but the shell
  exit code observed was 0: test the status, not the exit code.
- The instance in ERROR is a real object: it stays in the server list
  and in the group until somebody deletes it.
- With one compute node, any anti-affinity group holds one instance at
  most. The `soft-anti-affinity` policy exists for that case; it was not
  tried here.
- The scheduler line carries the request ID; start from the instance's
  `server event list` to get it (see
  [capacity and observability](openstack-capacity-and-observability.md)).

**See also**: [Logs](../operations/02-logs.md),
[identity and tenants](openstack-identity-and-tenants.md),
[Resource exhaustion](../troubleshooting/resource-exhaustion.md)

### How do I shelve an instance to free capacity without losing it?

**Context**: a project wants to keep an instance but not pay for its
resources; or you need room on the node.

**How**:

**[CHANGE]**

```bash
$o server shelve --wait kb-vm-a
$o server unshelve --wait kb-vm-a
```

**[READ-ONLY]** Between the two commands (`rp` is the resource provider
ID, as in the Placement entry):

```bash
$o server show kb-vm-a -f value -c status
$o image list -f value -c Name -c Status
os port list --server "$($o server show kb-vm-a -f value -c id)" -f value -c Status -c "Fixed IP Addresses"
os resource provider usage show $rp -f value
compute sudo virsh list --all
```

**Observed on the lab** (2026-11-12): shelve took 12 seconds, unshelve
21 seconds.

```text
SHELVED_OFFLOADED
kb-vm-a-shelved active
DOWN [{'subnet_id': '<subnet-id>', 'ip_address': '10.20.0.121'}]
```

While shelved, the domain was gone from `virsh list`, the Placement usage
only counted the other instance, the port kept its address in state
`DOWN`, and an image `<name>-shelved` existed in the project. After
unshelve the instance was `ACTIVE` with the same address and the image
had been deleted.

**Why / how it works**: shelve snapshots the root disk to Glance and,
because `shelved_offload_time` is 0 by default, removes the instance from
the hypervisor at once. Unshelve goes through the scheduler again and
rebuilds the disk from the snapshot. Kolla-Ansible equivalent: identical.

**Pitfalls**:

- The snapshot uses Glance storage (the local volume of the node on the
  lab) for as long as the instance is shelved.
- Unshelve is a new scheduling: the capacity was released, so it can end
  in `No valid host` if the room has been taken in the meantime (not
  provoked here).
- The admin client answered `No Server found for kb-vm-a`: the admin
  works in another project and must use the instance ID (or
  `--all-projects` in lists), not the name.
- The first boot after unshelve is a cold boot: memory content is lost,
  as with stop and start.

**See also**: [identity and tenants](openstack-identity-and-tenants.md),
[Storage troubleshooting](../troubleshooting/storage.md)

### What happens if I ask for a migration with a single compute node?

**Context**: a maintenance procedure written for a multi-node cloud says
"migrate the instances away". The lab has one node.

**How**:

**[CHANGE]** Admin only. Both requests fail without harming the instance.

```bash
id=$($o server show kb-vm-a -f value -c id)
os server migrate $id
os server migrate --live-migration $id
```

**[READ-ONLY]**

```bash
os server show $id -f value -c status -c fault
os server event list $id -f value -c Action -c "Start Time"
os server migration list --server $id
```

**Observed on the lab** (2026-11-12):

```text
No valid host was found. There are not enough hosts available. (HTTP 400)
ACTIVE
migrate 2026-11-12T07:43:45.000000
```

The cold migration was **accepted** by the API (no error, exit code 0);
the instance stayed `ACTIVE` with no fault, and the only traces were a
`migrate` event and a migration record in status `error`. The live
migration was refused synchronously with HTTP 400 and also left a record
in status `error`.

**Why / how it works**: a cold migration is cast to the conductor, which
finds no other host and gives up; the instance is never stopped. A live
migration is checked by the conductor while the API waits, hence the
immediate error. `allow_resize_to_same_host` applies to resize only, not
to migration. Kolla-Ansible equivalent: identical.

**Pitfalls**:

- "The command returned 0" does not mean the instance moved: always read
  `server migration list`.
- Failed records stay in the list; they are history, not pending work.
- Real live migration, evacuation and the migration SSH key could not be
  tested here (see [open questions](open-questions.md)).

**See also**: [Data plane changes](../operations/08-dataplane-changes.md),
[Data plane troubleshooting](../troubleshooting/dataplane.md)
