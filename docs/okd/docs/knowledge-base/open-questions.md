# Open questions

What the campaigns of 2026-11-12 (OpenStack administration, OKD
administration, restore and scale-out drills, node maintenance) observed without being able to explain, and what
they could not test. Each item says what is known, so that the next
person starts from facts.

## Observed but not explained

- **Catalog endpoint repair delay — mostly settled.** A deleted Keystone
  endpoint was not recreated until the `KeystoneEndpoint` resource was
  touched. The second campaign read the operator logs over 11 hours:
  operators reconcile on events only, four of them logged nothing at all
  after their start, and the hourly `KeystoneAPI` reconcile is triggered
  by the `keystone-cron` Job, not by a timer (see
  [when operators reconcile](okd-olm-and-operators.md#how-do-i-read-an-operators-logs-and-when-do-operators-actually-reconcile)).
  A restart of the operator is a full pass. What remains open: whether a
  resynchronisation longer than 11 hours exists.
- **Stale hash in the NodeSet status.** After the ConfigMap
  `nova-extra-config` was deleted and a new deployment had run,
  `.status.configMapHashes` of the NodeSet still listed it. Whether
  anything ever cleans it is unknown.
- **Notification queues without consumer.** `notifications.info` and
  `barbican_notifications.info` hold messages that nothing reads (270
  ready messages in the morning, 282 at 12:44 UTC, 141 in each queue:
  about two messages per hour on an idle lab). What emits them at that
  rate and the right fix (disable notifications in Keystone, or deploy a consumer)
  are open.
- **Queues left by replaced pods.** Each replaced Neutron pod leaves
  three empty quorum queues named after the old pod, with no expiry and
  no policy. The supported way to remove them (or to make Neutron use
  stable queue names) is not known.
- **Host discovery: settled.** The operator did not run discovery after
  a deployment that added a node; the mapping comes from the
  `discover_hosts` call at the end of the lab script. See
  [who maps a new compute node](dataplane-scale-out-and-migration.md#who-maps-a-new-compute-node-to-the-cell).
  What remains open: which change of the NodeSet or of Nova makes the
  operator create its own discovery Job again.
- **Hypervisor hostname versus service host: settled.** The difference
  breaks live migration without shared storage, because the disk copy
  targets the node's own host name; fixed with
  `live_migration_inbound_addr`. See
  [why live migration failed](dataplane-scale-out-and-migration.md#why-does-live-migration-fail-with-address-resolution-failed).
  What remains open: deploying nodes whose operating-system host name is
  already the control-plane FQDN, which would remove the difference, was
  not tried.
- **Gateway not taken over with two chassis.** When the node hosting the
  router gateway was stopped, the other chassis saw the tunnel down and
  did not claim the gateway port. This matches the isolation guard of
  `ovn-controller` (no working tunnel at all means "I am the one cut
  off"), read from its behaviour, not confirmed with a third chassis.
- **Certificates of a removed node.** The `Certificate` objects and
  Secrets of the node removed from the NodeSet were still present after
  the next deployment; they were deleted by hand. Whether the operator
  ever removes them is unknown.
- **`server migrate --live-migration --wait` reports "Complete"** for a
  migration that failed; not checked against a newer client.
- **Image files without a record in the Glance store**: three files of
  194 kB, older than the restore drills, match no active image. Probably
  left by images deleted while the file could not be removed, or by a
  test; not traced.
- **An instance that comes back after a cell restore stays `ACTIVE`**:
  no domain exists on the compute node, yet the periodic power-state
  synchronisation did not change its state in five minutes.
- **`restore_galera` exits with 0 after a failed file**, and its cleanup
  trap contains a malformed variable reference; whether this is fixed
  upstream after 18-stable was not checked.

- **OVN controller and metadata agent never reconnect after a restart
  of the OKD node.** Both log `connect: Address family not supported by
  protocol` for `ssl:ovsdbserver-sb.openstack.svc:6642` every 8 seconds,
  from the moment the DNS pod stops and for as long as they run, while
  `getent hosts` on the same node resolves the name. Reproduced on two
  reboots out of two (OVN 24.03, OVS library 3.3). Supposed cause: the
  asynchronous resolver of the OVS library keeps a failed state; not
  verified in the source, and not tried: an IP address instead of the
  name in `ovn-remote`. On the first reboot of the lab only the metadata
  agent was stuck; why the controller reconnected that time is unknown.
- **The node shutdown takes 2 min 30 with a silent gap of 84 seconds**,
  and the journal of the previous boot shows `kubepods-burstable.slice:
  A process of this unit has been killed by the OOM killer` near the
  end. Which scope holds the shutdown and why the OOM killer runs then
  was not traced.
- **The machine config controller waits about 2 min 30 for its leader
  lease** after each reboot although it is the only candidate; the
  lease is not released at shutdown. Harmless, but it delays the
  `Updated` status of the pool by more than a minute.
- **The kube-apiserver rolled a new static pod revision a few minutes
  after each reboot** (`configmap/kubelet-serving-ca has changed`),
  closing the API for some seconds. Whether this is tied to the reboot
  or to the certificate rotation of the first day was not established.

## Defaults that deserve a decision

- **No requests or limits on OpenStack pods** (all `BestEffort` except
  RabbitMQ). The `resources` field works (tried on Placement), but which
  values to set for each service on a single node is undecided.
- **memcached memory limit** of about 9.9 GB with no pod limit on a node
  of 31 GB.
- **Debug logging by default** in Nova and Placement, and DEBUG in the
  OVN metadata agent on the compute node. Turning it off works per
  service on the control plane (tried on the Nova API); whether to do it
  everywhere, and how on the data plane, is undecided.
- **Slow query log off and 128 MB InnoDB buffer pool** in Galera. The way
  to change them through the Galera resource was not tried.
- **512 MB of reserved host memory** on a compute node whose own
  processes use about 1.5 GB.
- **Local volumes do not enforce their size**: every claim reports the
  usage of the whole node filesystem, and the platform's volume alerts
  only cover the `openshift-*`, `kube-*` and `default` namespaces. One
  full claim fills the disk that etcd uses; which alert to add for
  `/var` is undecided.
- **System reservation of 1 GiB** for kubelet while the host services
  (`system.slice`) use about 4.4 GiB: the scheduler believes it has 3 GiB
  more than it has. The value to set (a MachineConfig-level change, one
  reboot) is undecided.
- **Memory requests far from real use**: the 22 operator pods request
  6 GiB and use 1.4, RabbitMQ requests 4 GiB and uses 0.3, while Galera
  requests nothing and is first in line for the OOM killer. Which
  operators can be switched off with `operatorOverrides` on this
  topology, and which requests to give Galera, are open.
- **No PodDisruptionBudget, ResourceQuota, LimitRange or NetworkPolicy**
  in the `openstack` namespace. Harmless with one node and one tenant of
  the cluster; to be decided before a multi-node or shared cluster.
- **Monitoring is not durable and nobody is told**: Prometheus keeps 15
  days in an `emptyDir` (lost with the pod), Alertmanager has no
  receiver, and no OpenStack target is scraped.
- **Read-only users can read Route TLS private keys** (`view` on Routes
  includes `spec.tls.key`), and no aggregated role exists for the
  OpenStack resource types (one was written and removed in the access
  file). Whether to ship such a role with the lab is undecided.
- **Audit log retention of about 10 hours** (2.3 GiB): too short to
  answer "who changed this yesterday". Forwarding or a larger size is
  undecided.
- **Node time follows the bastion and four public pool servers**; a
  production platform would list internal sources only.
- **`shutdownGracePeriod` is 0** on the node: pods are not stopped in
  order at node shutdown. Measured on two planned reboots
  ([entry](okd-node-maintenance.md#how-do-i-apply-a-machineconfig-on-the-single-node-and-what-happens-step-by-step)):
  RabbitMQ is killed in the first second, the shutdown still takes
  2 min 30 because systemd waits for container scopes, and Galera and
  RabbitMQ recovered alone both times. Whether to set a grace period
  (a `KubeletConfig`, one reboot) to make the stop ordered and shorter
  is undecided.
- **Nothing restarts the OVN agents of the compute nodes** after a
  restart of the OKD node, and nothing alerts on it. A habit (restart
  both services after any node restart) is documented; a systemd
  watchdog or a health check that restarts the container is undecided.
- **Data plane Jobs have no time-to-live** and each deployment object
  keeps its Jobs for ever; a retention habit (keep the last successful
  one per node set) is suggested, not enforced.
- **The community catalog is still enabled** and polled every four
  hours although nothing is installed from it.

## Not tested

- **Fernet rotation.** Still not observed: it was due on 2026-11-12 at
  about 20:25 UTC, after the end of the fourth campaign. A watcher was
  left running on the bastion until 20:50 UTC; its log
  (`.work/fernet-watch.log` in the working copy of the repository)
  holds key fingerprints, pod restarts and the validation status of two
  tokens every 2 minutes. Reading it and completing the
  [entry](openstack-service-administration.md#how-do-i-watch-a-fernet-rotation-and-check-that-issued-tokens-survive-it)
  closes this item. The resource has no supported manual trigger.
- **Live migration, evacuation, resize to another host**: executed on
  2026-11-12 with a temporary second node, see
  [Data plane scale-out, migration and scale-in](dataplane-scale-out-and-migration.md).
  Not covered: live migration under memory pressure (auto-converge,
  post-copy), instances with several disks or a config drive, a node
  lost without a clean shutdown, a larger disk than 1 GB.
- **`soft-anti-affinity` server groups** and **unshelve when the node is
  full**: mentioned in the entries, not provoked.
- **Volumes**: no Cinder on the lab; boot from volume, attach and volume
  snapshots are not covered.
- **Gateway failover with three chassis**: with two, the survivor does
  not take over (see above); the working failover was not observed.
  Source NAT traffic of an instance without floating IP was judged from
  the router's external address, not from inside an instance.
- **Outbound Internet access from instances**: not available on the lab;
  SNAT was verified up to the control-plane gateway only.
- **Database restore under real conditions**: the restore was executed
  on both instances
  ([drills](backup-and-restore-drills.md)), but on an idle lab with one
  Galera replica. Not known: the effect of API writes arriving during the
  restore (the services stay connected), the behaviour with three
  replicas, a restore after a database password rotation (the grants
  file brings old passwords back), and whether new ports become ACTIVE
  after a restore that follows a replacement of the Neutron pod.
- **Manual restore from a `mysqldump --all-databases` file**: imported
  on a scratch server only, never into a live instance.
- **Purge or deletion of RabbitMQ queues**: not executed.
- **Telemetry operator and user-workload monitoring**: resource types are
  present, nothing is deployed; the memory cost on a single node is
  unknown. Which of the two should scrape the RabbitMQ and OVN exporters
  is open.
- **MachineConfig roll**: executed twice on 2026-11-12 (apply and
  removal of one file), see
  [OKD node maintenance](okd-node-maintenance.md). Not covered: a
  change of kernel arguments or of the kubelet configuration
  (`KubeletConfig`), a change that the node disruption policies apply
  without reboot, a roll that fails half-way (pool `Degraded`), a
  restart of kubelet or CRI-O alone, and an unclean stop of the node.
- **etcd restore** and **a real node drain**: never executed (nothing
  irreversible on etcd; a drain of the only node is an outage). The
  drain was evaluated with a server-side dry run
  ([entry](okd-node-maintenance.md#what-would-a-drain-really-evict-here-and-which-poddisruptionbudgets-exist));
  the restore script and its single-member mode were read only
  ([entry](backup-and-restore-drills.md#what-can-i-verify-about-an-etcd-restore-without-doing-it)).
- **The whereabouts reconciler**: no CronJob or controller cleaning
  leaked addresses was found; a leak was cleaned by hand. Whether the
  node-level reconciler ever runs here was not observed.
- **An InstallPlan for a newer operator bundle**: the catalog is now
  pinned by digest, so no upgrade proposal was seen; approving one is
  covered by the lifecycle guide, not replayed here.
- **A real out-of-memory situation on the node** (node-level, not one
  container limit): the kill order is deduced from `oom_score_adj`, not
  provoked.
- **Other files in `defaultConfigOverwrite`**: only `policy.yaml` was
  tried, on Placement.
- **Setting quotas of block storage, load balancers or DNS**: services
  not deployed.

## How to close a question

Run the experiment on the lab, add or correct the entry in the topic
file with the observed output and its date, then remove the item here in
the same commit.
