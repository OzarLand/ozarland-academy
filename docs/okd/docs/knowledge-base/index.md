# Operations knowledge base

Short, tested answers to the questions an OpenStack administrator asks on
a cloud managed by operators on OKD, and about OKD itself. The rest of
the documentation explains how the lab is built and how the operators
work; this directory records **how each day-to-day task is done here**,
with the output that was really observed, for people who know OpenStack
from a Kolla-Ansible deployment.

Every command was run on the lab (single-node OKD 4.22,
openstack-k8s-operators 18-stable, OpenStack 2023.1 Antelope, one KVM
compute node) on 2026-11-12; the gateway test with three compute nodes
and the etcd restore were run on 2026-11-13. What could not be tested is
listed in [open questions](open-questions.md), not guessed.

## Start here

- **You have a task**: find it in [find by task](#find-by-task), or in
  the [index](#index) of all 149 entries with their one-line answers.
- **You only need the command**: open the [cheat sheet](cheat-sheet.md).
- **Something is broken**: go to the
  [troubleshooting runbooks](../troubleshooting/README.md); this
  knowledge base explains normal operation, the runbooks start from a
  symptom.
- **You are new to the lab**: follow the
  [suggested reading order](#suggested-reading-order).

Every page longer than a screen starts with an "In short" block: read it
first, it says what the page covers and what is worth remembering.

## Pages

| Page | Entries | Content |
| --- | --- | --- |
| [openstack-identity-and-tenants.md](openstack-identity-and-tenants.md) | 8 | Admin client, endpoints, CA, project and user setup, quotas, flavors, images |
| [openstack-networking-ovn.md](openstack-networking-ovn.md) | 10 | Provider and project networks, floating IPs, OVN databases, tracing, gateway, metadata |
| [openstack-compute.md](openstack-compute.md) | 13 | Instance lifecycle, compute node layout, Placement, allocation ratios, maintenance |
| [openstack-service-administration.md](openstack-service-administration.md) | 13 | Configuration and policy overrides, Fernet keys, catalog, RabbitMQ, Galera, memcached |
| [openstack-capacity-and-observability.md](openstack-capacity-and-observability.md) | 9 | Usage per service, limits, OOM and restarts, events, metrics, logs, request tracing |
| [okd-cluster-health-and-etcd.md](okd-cluster-health-and-etcd.md) | 11 | Version, cluster operators, static pods and revisions, etcd, API health, platform certificates |
| [okd-node-and-host.md](okd-node-and-host.md) | 11 | Shell on the node, CoreOS, MachineConfig, kubelet, CRI-O, disk, systemd units, time, log retention, cordon and drain |
| [okd-node-maintenance.md](okd-node-maintenance.md) | 5 | MachineConfig roll with timings, paused pool, drain dry run, tools during a partial API, OVN agents after a node restart |
| [okd-workloads-and-resources.md](okd-workloads-and-resources.md) | 6 | QoS classes and OOM order, requests and limits, PodDisruptionBudgets, quotas |
| [okd-networking.md](okd-networking.md) | 10 | Cluster OVN versus OpenStack OVN, node interfaces, routes and ingress, DNS, NetworkPolicy, whereabouts, MetalLB |
| [okd-storage.md](okd-storage.md) | 5 | Local volumes, claim binding, data location, recycling a volume, shared disk risks, image registry |
| [okd-access-and-security.md](okd-access-and-security.md) | 8 | Credentials, named users, read-only access, operator permissions, security contexts, audit log |
| [okd-monitoring-and-alerting.md](okd-monitoring-and-alerting.md) | 7 | Platform Prometheus and Alertmanager, queries, firing alerts, silences, events, console access |
| [okd-olm-and-operators.md](okd-olm-and-operators.md) | 7 | Catalog, Subscription, InstallPlan, CSV, operator logs and restart, `operatorOverrides`, CRDs, garbage |
| [backup-and-restore-drills.md](backup-and-restore-drills.md) | 12 | Database restore drills on both Galera instances, repairs afterwards, manual restore, etcd restore |
| [dataplane-scale-out-and-migration.md](dataplane-scale-out-and-migration.md) | 13 | Second compute node, host discovery, scheduling, live and cold migration, evacuation, gateway failover, clean removal of a node |
| [lab-state.md](lab-state.md) | 1 | What the campaigns left on the lab, with the commands to list and remove each item |
| [cheat-sheet.md](cheat-sheet.md) | - | One-liners grouped by task |
| [open-questions.md](open-questions.md) | - | What is not explained, not decided or not tested yet, and what has been settled since |

## Find by task

| I want to... | Go to |
| --- | --- |
| Give a new team a project, users, quotas and a working CLI | [Identity and tenants](openstack-identity-and-tenants.md) |
| Find out why an instance has no network, or test a security group | [Connectivity from inside an instance](openstack-networking-ovn.md#how-do-i-check-connectivity-mtu-dns-and-metadata-from-inside-an-instance), [ovn-trace](openstack-networking-ovn.md#how-do-i-trace-a-packet-through-ovn-without-sending-it) |
| Understand why a boot was refused | [Quota or scheduler refusal](openstack-compute.md#what-does-a-user-see-when-a-quota-or-the-scheduler-refuses-a-boot), [following a request in the logs](openstack-capacity-and-observability.md#where-are-the-logs-and-how-do-i-follow-one-request-across-services) |
| Change an option or a policy of a control plane service | [Service administration](openstack-service-administration.md) |
| Change an option of `nova-compute` on the node | [Allocation ratio entry](openstack-compute.md#how-do-i-change-an-allocation-ratio-or-any-nova-compute-option-the-supported-way) |
| Add or remove a compute node, migrate or evacuate instances | [Data plane scale-out, migration and scale-in](dataplane-scale-out-and-migration.md) |
| Take a safety net before a risky change | [What do I put aside](backup-and-restore-drills.md#what-do-i-put-aside-before-touching-the-databases) |
| Restore a database, or etcd | [Backup and restore drills](backup-and-restore-drills.md) |
| Change the host configuration or reboot the OKD node | [OKD node maintenance](okd-node-maintenance.md) |
| Check that the cluster under OpenStack is healthy | [Cluster health and etcd](okd-cluster-health-and-etcd.md) |
| Know what uses memory and what dies first | [Workloads and resources](okd-workloads-and-resources.md), [usage per service](openstack-capacity-and-observability.md#how-much-cpu-and-memory-does-each-openstack-service-use-right-now) |
| Find where the disk space goes, or reuse a `Released` volume | [Disk usage](okd-node-and-host.md#where-does-the-disk-space-go-on-the-node), [recycling a volume](okd-storage.md#what-happens-to-the-data-when-a-claim-is-deleted-and-how-do-i-reuse-the-volume) |
| Follow a request from a client to an API pod | [Request path](okd-networking.md#how-does-a-request-reach-an-openstack-api-end-to-end) |
| Give a colleague access, or find who changed something | [Access and security](okd-access-and-security.md) |
| Query metrics, read or silence alerts | [Monitoring and alerting](okd-monitoring-and-alerting.md) |
| Read the logs of an operator, restart it or switch it off | [OLM and the OpenStack operators](okd-olm-and-operators.md) |
| Know what is baseline and what is residue on the lab | [State of the lab](lab-state.md) |

## Suggested reading order

**30 minutes** (orientation):

1. [Conventions](#conventions) below: labels, helpers, address plan.
2. The "In short" block of each page of the [table above](#pages), in
   the order of the table.
3. [State of the lab](lab-state.md): what exists on the lab today.
4. [Open questions](open-questions.md): what is not known.

**Half a day** (in this order, with a terminal on the bastion):

1. The OpenStack side, as a tenant then as an administrator:
   [identity](openstack-identity-and-tenants.md),
   [networking with OVN](openstack-networking-ovn.md),
   [compute](openstack-compute.md),
   [service administration](openstack-service-administration.md),
   [capacity and observability](openstack-capacity-and-observability.md).
2. The platform under it:
   [cluster health and etcd](okd-cluster-health-and-etcd.md),
   [node and host](okd-node-and-host.md),
   [networking](okd-networking.md), [storage](okd-storage.md),
   [workloads and resources](okd-workloads-and-resources.md).
3. The drills, which change the lab and are best read before being
   replayed: [node maintenance](okd-node-maintenance.md),
   [backup and restore](backup-and-restore-drills.md),
   [scale-out and migration](dataplane-scale-out-and-migration.md).
4. As needed: [access and security](okd-access-and-security.md),
   [monitoring](okd-monitoring-and-alerting.md),
   [OLM and operators](okd-olm-and-operators.md).

## Structure of an entry

Each entry is a third-level heading written as the operator would ask the
question, followed by the same six parts:

- **Context**: when you need it.
- **How**: the commands, each block labelled with its effect (see below).
- **Observed on the lab**: real output or timing, shortened and dated.
- **Why / how it works**: the mechanism, and the Kolla-Ansible equivalent
  in one line.
- **Pitfalls**: what surprised us or can hurt.
- **See also**: links to the concept, operation and troubleshooting pages.

## Conventions

- Labels: **[READ-ONLY]** changes nothing; **[CHANGE]** modifies the lab
  and is followed by its revert when there is one; **[DESTRUCTIVE]**
  loses data or breaks a service until repaired.
- Commands run on the bastion with the `openstack` namespace selected
  (`oc project openstack`), unless the entry says otherwise.
- The `okd-*` files are about the platform under OpenStack: their
  commands name the namespace explicitly and use `node`, a shell on the
  OKD node (`node() { ssh core@192.168.130.10 "$@"; }`).
- Helpers used everywhere:

  ```bash
  os() { oc exec openstackclient -c openstackclient -- openstack "$@"; }
  export OS_CLIENT_CONFIG_FILE=~/kb-demo/clouds.yaml OS_CLOUD=kb-demo
  o=~/kb-demo/venv/bin/openstack
  compute() { ssh -i ~/okd-openstack-lab/.work/dataplane-ssh-key cloud-admin@192.168.122.100 "$@"; }
  ```

  `os` is the admin client in its pod, `$o` the client of the demo
  project member on the bastion, `compute` a shell on the compute node.
- Addresses are the lab defaults (192.168.130.0/24 machine network,
  192.168.122.0/24 control plane, 172.17.0.0/24 internal API,
  172.19.0.0/24 tenant, `lab.example.com`). Identifiers are replaced by
  placeholders such as `<network-id>`.
- No password or key value appears anywhere. Commands that would print
  one are written with a mask or a precise `grep`.
- The entries use a small demo tenant, `kb-demo` (domain, project, two
  users, one network, one router). It is left in place without any
  running instance so that the commands can be replayed.
- Before a **[CHANGE]** on a service, read the
  [safe change checklist](../operations/09-safe-change-checklist.md) and
  finish with `tests/smoke-test.sh`.

## Index

All entries, page by page, with the answer in one line.

### Identity and tenants

| Entry | One-line answer |
| --- | --- |
| [Where is the admin client and which credentials does it use?](openstack-identity-and-tenants.md#where-is-the-admin-client-and-which-credentials-does-it-use) | In the `openstackclient` pod, with a `clouds.yaml` rendered by the operator; use `oc exec`. |
| [Which endpoint do I use from where?](openstack-identity-and-tenants.md#which-endpoint-do-i-use-from-where-public-route-or-internal-service) | Public Routes on 443 from outside, `*-internal.openstack.svc` only from pods. |
| [Where is the TLS certificate authority and how do I export it?](openstack-identity-and-tenants.md#where-is-the-tls-certificate-authority-and-how-do-i-export-it) | Secret `rootca-public`, key `ca.crt`; clients need it. |
| [How do I create a domain, a project and users for a new team?](openstack-identity-and-tenants.md#how-do-i-create-a-domain-a-project-and-users-for-a-new-team) | Standard `openstack` commands through `os`; `reader` and `member` are enforced strictly. |
| [How do I set and check the quotas of a project?](openstack-identity-and-tenants.md#how-do-i-set-and-check-the-quotas-of-a-project) | `os quota set` by project ID, compute and network in separate calls. |
| [How does a non-admin user get a working CLI?](openstack-identity-and-tenants.md#how-does-a-non-admin-user-get-a-working-cli) | A virtual environment, a `clouds.yaml` with the public URL and the exported CA. |
| [How do I add flavors, an image, a keypair and a security group?](openstack-identity-and-tenants.md#how-do-i-add-flavors-an-image-a-keypair-and-a-security-group) | Pipe the image through `oc exec -i`; the rest is standard. |
| [Where does Glance store an uploaded image on the node?](openstack-identity-and-tenants.md#where-does-glance-store-an-uploaded-image-on-the-node) | File store on a local PersistentVolume, a directory of the node. |

### Networking with OVN

| Entry | One-line answer |
| --- | --- |
| [How do I create the external provider network for floating IPs?](openstack-networking-ovn.md#how-do-i-create-the-external-provider-network-for-floating-ips) | Flat network on physical network `datacentre` (bridge `br-ex`), pool .150 to .199, no DHCP. |
| [How does a project build its network, router and floating IP?](openstack-networking-ovn.md#how-does-a-project-build-its-network-router-and-floating-ip) | Standard commands; Geneve network with MTU 1384, router and NAT are OVN objects. |
| [How do I check connectivity, MTU, DNS and metadata from inside an instance?](openstack-networking-ovn.md#how-do-i-check-connectivity-mtu-dns-and-metadata-from-inside-an-instance) | Ping with `-M do`, `curl` 169.254.169.254, `nslookup`; OVN answers DHCP and local DNS. |
| [How do I run ovn-nbctl, ovn-sbctl and ovn-trace on this platform?](openstack-networking-ovn.md#how-do-i-run-ovn-nbctl-ovn-sbctl-and-ovn-trace-on-this-platform) | `oc exec` in `ovsdbserver-nb-0` and `ovsdbserver-sb-0` with `-c`. |
| [What do the OVN databases show for a project network?](openstack-networking-ovn.md#what-do-the-ovn-northbound-and-southbound-databases-show-for-a-project-network) | Switches, routers, NAT, DHCP options and port groups named after Neutron IDs. |
| [How do I trace a packet through OVN without sending it?](openstack-networking-ovn.md#how-do-i-trace-a-packet-through-ovn-without-sending-it) | `ovn-trace` in the southbound pod with port, MAC and IP of the flow. |
| [How do I check whether a security group lets a new connection in?](openstack-networking-ovn.md#how-do-i-check-whether-a-security-group-lets-a-new-connection-in) | `ovn-trace --ct new`: `output` means allowed, no output means dropped by `neutron_pg_drop`. |
| [Which chassis is the gateway and how is it scheduled?](openstack-networking-ovn.md#which-chassis-is-the-gateway-and-how-is-it-scheduled) | The compute node, through `edpm_enable_chassis_gw`; one chassis means no failover (failover with two and three chassis is in the scale-out page). |
| [What does the compute node look like from the Open vSwitch side?](openstack-networking-ovn.md#what-does-the-compute-node-look-like-from-the-open-vswitch-side) | Open vSwitch on the host, `ovn_controller` in a container, `br-int` patched to `br-ex`. |
| [How does the metadata service reach an instance?](openstack-networking-ovn.md#how-does-the-metadata-service-reach-an-instance) | An `ovnmeta-` namespace with haproxy per network, then the `nova-metadata` pod. |

### Compute

| Entry | One-line answer |
| --- | --- |
| [How do I boot an instance and follow what happens to it?](openstack-compute.md#how-do-i-boot-an-instance-and-follow-what-happens-to-it) | `server create --wait`, then `server event list` and the `fault` field. |
| [How do I get the console log or a graphical console?](openstack-compute.md#how-do-i-get-the-console-log-or-a-graphical-console) | `console log show`; noVNC URL through the proxy pod's Route. |
| [How do I stop, start, reboot, rebuild, rescue or snapshot an instance?](openstack-compute.md#how-do-i-stop-start-reboot-rebuild-rescue-or-snapshot-an-instance) | Standard commands; all worked on the lab; rebuild destroys the root disk. |
| [Can I resize an instance when there is only one compute node?](openstack-compute.md#can-i-resize-an-instance-when-there-is-only-one-compute-node) | Yes: `allow_resize_to_same_host` is set by the operator. |
| [Where are instance files, libvirt and the Nova containers?](openstack-compute.md#where-are-instance-files-libvirt-and-the-nova-containers-on-the-compute-node) | libvirt on the host, `nova_compute` under the unit `edpm_nova_compute`, files in `/var/lib/nova/instances`. |
| [How do I run nova-manage and nova-status?](openstack-compute.md#how-do-i-run-nova-manage-and-nova-status) | In the cell0 conductor pod; filter DEBUG lines and mask `list_cells`. |
| [How do I read capacity and allocations in Placement?](openstack-compute.md#how-do-i-read-capacity-and-allocations-in-placement) | `os resource provider inventory list` and `usage show`; ratios 4.0, 1.0 and 0.9. |
| [How do I change an allocation ratio the supported way?](openstack-compute.md#how-do-i-change-an-allocation-ratio-or-any-nova-compute-option-the-supported-way) | ConfigMap `nova-extra-config` plus a deployment limited to the `nova` service. |
| [How do I take a compute node out of scheduling?](openstack-compute.md#how-do-i-take-a-compute-node-out-of-scheduling-and-what-does-a-restart-of-nova_compute-do) | `compute service set --disable`; restarting the unit does not touch running instances. |
| [How do I create a host aggregate and an availability zone?](openstack-compute.md#how-do-i-create-a-host-aggregate-and-an-availability-zone) | Standard commands with the service host name. |
| [What does a user see when a quota or the scheduler refuses a boot?](openstack-compute.md#what-does-a-user-see-when-a-quota-or-the-scheduler-refuses-a-boot) | HTTP 403 at once for a quota; ERROR with `No valid host` otherwise, the filter is named in the scheduler log. |
| [How do I shelve an instance to free capacity without losing it?](openstack-compute.md#how-do-i-shelve-an-instance-to-free-capacity-without-losing-it) | `server shelve`: snapshot in Glance, capacity released, address kept. |
| [What happens if I ask for a migration with a single compute node?](openstack-compute.md#what-happens-if-i-ask-for-a-migration-with-a-single-compute-node) | Cold migration is accepted then fails silently; live migration is refused with HTTP 400. |

### Service administration

| Entry | One-line answer |
| --- | --- |
| [Where is the configuration of a service?](openstack-service-administration.md#where-is-the-configuration-of-a-service-and-what-did-the-operator-put-in-it) | Secret `<service>-config-data`, copied to `/etc/<service>/*.conf.d/` in the pod. |
| [How do I override one policy rule of a service?](openstack-service-administration.md#how-do-i-override-one-policy-rule-of-a-service) | `defaultConfigOverwrite` with a `policy.yaml` key in the control plane resource. |
| [How do I turn on debug logging for one service?](openstack-service-administration.md#how-do-i-turn-on-debug-logging-for-one-service-and-turn-it-off-again) | `customServiceConfig` with `debug = true`; the pods are rolled. |
| [Who rotates the Keystone Fernet keys?](openstack-service-administration.md#who-rotates-the-keystone-fernet-keys) | The keystone operator, in the Secret `keystone`; no CronJob and no manual step. |
| [How do I watch a Fernet rotation and check that issued tokens survive it?](openstack-service-administration.md#how-do-i-watch-a-fernet-rotation-and-check-that-issued-tokens-survive-it) | Fingerprints of the keys in the Secret and in the pod plus a token validation every 2 minutes; rotation observed 24 h 35 min after the previous one, without a pod restart. |
| [Who creates the catalog endpoints and what happens if one is deleted?](openstack-service-administration.md#who-creates-the-catalog-endpoints-and-what-happens-if-one-is-deleted) | `KeystoneEndpoint` resources; a deleted endpoint only comes back when the resource is reconciled, which you must force. |
| [How do I inspect RabbitMQ?](openstack-service-administration.md#how-do-i-inspect-rabbitmq-users-queues-connections-alarms) | `rabbitmqctl` and `rabbitmq-diagnostics` in each of the two broker pods. |
| [How do I look inside Galera?](openstack-service-administration.md#how-do-i-look-inside-galera-databases-sizes-connections-slow-queries) | `mysql -e` in the `galera` container of each of the two database pods. |
| [How do I take a database backup before a risky change?](openstack-service-administration.md#how-do-i-take-a-database-backup-before-a-risky-change) | `oc create job --from=cronjob/backup-openstack` for each Galera instance. |
| [How do I check memcached?](openstack-service-administration.md#how-do-i-check-memcached) | `memcached-tool 127.0.0.1:11211 stats` in the pod. |
| [How do I change the configuration of one Nova service only?](openstack-service-administration.md#how-do-i-change-the-configuration-of-one-nova-service-only-for-example-turn-off-its-debug-logging) | `customServiceConfig` under the service's own template, for example `apiServiceTemplate`. |
| [How do I give a service CPU and memory requests and limits?](openstack-service-administration.md#how-do-i-give-a-service-cpu-and-memory-requests-and-limits) | The `resources` field of the service template; it applies to each container. |
| [Why do the API pods log "AMQP server is unreachable"?](openstack-service-administration.md#why-do-the-api-pods-log-amqp-server-is-unreachable-every-few-minutes) | Idle `mod_wsgi` workers miss heartbeats, the broker closes the connection, the worker reconnects. |

### Backup and restore drills

| Entry | One-line answer |
| --- | --- |
| [What do I put aside before touching the databases?](backup-and-restore-drills.md#what-do-i-put-aside-before-touching-the-databases) | One extra `GaleraBackup` run, a `mysqldump --all-databases` of each instance, the resource and Secret export, an etcd snapshot: under a minute. |
| [What does GaleraRestore really do?](backup-and-restore-drills.md#what-does-galerarestore-really-do) | It starts a pod with the backup volume; the script you run there reloads the chosen dump table by table, with the services still connected. |
| [How do I restore the cell database, and what is the result?](backup-and-restore-drills.md#how-do-i-restore-the-cell-database-and-what-is-the-result) | 7 s, no failed API request; newer instances vanish from Nova, deleted ones come back. |
| [What is inconsistent after a cell database restore?](backup-and-restore-drills.md#what-is-inconsistent-after-a-cell-database-restore-and-how-do-i-repair-it) | Running domains unknown to Nova, allocations and ports without instance: `virsh`, `placement audit --delete`, `port delete`. |
| [How do I restore the main database instance, and what is the result?](backup-and-restore-drills.md#how-do-i-restore-the-main-database-instance-and-what-is-the-result) | 25 s, no failed API request; projects, flavors, images and networks go back to backup time, OVN and the store do not. |
| [How do I detect and repair Neutron and OVN after a restore?](backup-and-restore-drills.md#how-do-i-detect-and-repair-neutron-and-ovn-after-a-restore) | `neutron-ovn-db-sync-util` in `log` mode, then `repair` (deletes from OVN what Neutron no longer knows). |
| [How do I get rid of an instance that the API no longer finds?](backup-and-restore-drills.md#how-do-i-get-rid-of-an-instance-that-the-api-no-longer-finds) | Put its row back in `nova_api.instance_mappings`, then `server delete`. |
| [Which image files are left in the Glance store after a restore?](backup-and-restore-drills.md#which-image-files-are-left-in-the-glance-store-after-a-restore) | Files of images uploaded after the backup; compare the store with `glance.images`. |
| [What happens when a restore file fails to load?](backup-and-restore-drills.md#what-happens-when-a-restore-file-fails-to-load) | `FAILED` in the output, the script continues and exits with 0; the Service endpoint is put back. |
| [How do I restore by hand from a plain mysqldump?](backup-and-restore-drills.md#how-do-i-restore-by-hand-from-a-plain-mysqldump) | `mysql < dump` in the Galera pod with the endpoint removed; validated on a scratch server only. |
| [What can I verify about an etcd restore without doing it?](backup-and-restore-drills.md#what-can-i-verify-about-an-etcd-restore-without-doing-it) | Snapshot content and what `cluster-restore.sh` does, read on the node before the drill. |
| [How do I restore etcd on the single node, and what really happens?](backup-and-restore-drills.md#how-do-i-restore-etcd-on-the-single-node-and-what-really-happens) | Script 40 s, etcd down 9 minutes, restore pod left in place, forced revision (5 more minutes); OpenStack not interrupted. |

### Data plane scale-out, migration and scale-in

| Entry | One-line answer |
| --- | --- |
| [How do I add a second compute node?](dataplane-scale-out-and-migration.md#how-do-i-add-a-second-compute-node) | `compute_count = 2`, sync, the data plane script with a new deployment name: 21 minutes, no effect on running instances. |
| [Who maps a new compute node to the cell?](dataplane-scale-out-and-migration.md#who-maps-a-new-compute-node-to-the-cell) | Not the operator after a deployment: `nova-manage cell_v2 discover_hosts`, which the script runs. |
| [What does a node receive so that it can work with the others?](dataplane-scale-out-and-migration.md#what-does-a-node-receive-so-that-it-can-work-with-the-others) | SSH host keys of every node, the shared Nova migration key, its own libvirt certificates, DNS records. |
| [How does the scheduler choose between two nodes, and how do I force one?](dataplane-scale-out-and-migration.md#how-does-the-scheduler-choose-between-two-nodes-and-how-do-i-force-one) | Random among equal nodes; admin `--host` (microversion 2.74) or `--availability-zone nova:<host>`. |
| [How do I make an aggregate or an availability zone change the placement?](dataplane-scale-out-and-migration.md#how-do-i-make-an-aggregate-or-an-availability-zone-change-the-placement) | Aggregate with `--zone`, or aggregate metadata matched by a flavor property. |
| [Why does live migration fail with "address resolution failed"?](dataplane-scale-out-and-migration.md#why-does-live-migration-fail-with-address-resolution-failed) | The disk copy targets the node's own host name; set `live_migration_inbound_addr = $host` (now in the lab template). |
| [How long is an instance unreachable when it changes node?](dataplane-scale-out-and-migration.md#how-long-is-an-instance-unreachable-when-it-changes-node) | Live block migration 1.5 to 2.7 s; cold migration and resize about 25 s and a reboot. |
| [How do I empty a node for maintenance?](dataplane-scale-out-and-migration.md#how-do-i-empty-a-node-for-maintenance) | Disable the service, live-migrate each instance without destination, check each result. |
| [What happens to the instances when a compute node dies, and what does evacuate do?](dataplane-scale-out-and-migration.md#what-happens-to-the-instances-when-a-compute-node-dies-and-what-does-evacuate-do) | They stay `ACTIVE` and unreachable; `evacuate` rebuilds them elsewhere in 23 s, local disk lost. |
| [What happens to routers and floating IPs when the node hosting the gateway goes down?](dataplane-scale-out-and-migration.md#what-happens-to-routers-and-floating-ips-when-the-node-hosting-the-gateway-goes-down) | Floating IPs are distributed and survive; two chassis do not fail over, three do in about 3 s, and the returning node preempts. |
| [Why does the router address stop answering after a planned gateway move?](dataplane-scale-out-and-migration.md#why-does-the-router-address-stop-answering-after-a-planned-gateway-move) | The new gateway node sends with the chassis address mapping as source; the network keeps delivering to the old node. Remove the mapping on the gateway node. |
| [How do I remove a compute node cleanly?](dataplane-scale-out-and-migration.md#how-do-i-remove-a-compute-node-cleanly) | Drain, stop its services, delete agents and compute service, remove it from the NodeSet, then Terraform. |
| [What does the operator do when a node leaves the NodeSet?](dataplane-scale-out-and-migration.md#what-does-the-operator-do-when-a-node-leaves-the-nodeset) | Frees its addresses and DNS records; runs nothing on the node and deletes no OpenStack record. |

### Capacity and observability

| Entry | One-line answer |
| --- | --- |
| [How much CPU and memory does each service use?](openstack-capacity-and-observability.md#how-much-cpu-and-memory-does-each-openstack-service-use-right-now) | `oc adm top pods`, summed by the label `service`; under 4 Gi for the whole namespace. |
| [Do the pods have requests and limits?](openstack-capacity-and-observability.md#do-the-openstack-pods-have-requests-and-limits-and-what-protects-the-node) | No, except RabbitMQ: OpenStack pods are `BestEffort`. |
| [Has anything been OOM-killed or restarted?](openstack-capacity-and-observability.md#has-anything-been-oom-killed-or-restarted) | Container `lastState`, `OOMKilling` events and the kernel journal of the node. |
| [How do I read events, and how far back do they go?](openstack-capacity-and-observability.md#how-do-i-read-events-and-how-far-back-do-they-go) | `oc get events --sort-by=.lastTimestamp`; only the last two to three hours. |
| [What metrics can I query without deploying telemetry?](openstack-capacity-and-observability.md#what-metrics-can-i-query-without-deploying-telemetry) | Container metrics of every pod in the platform Prometheus, 15 days. |
| [Which exporters already exist in the pods?](openstack-capacity-and-observability.md#which-exporters-already-exist-in-the-openstack-pods) | RabbitMQ on 15692 and an OVN exporter on 1981; nobody scrapes them. |
| [Where are the logs and how do I follow one request?](openstack-capacity-and-observability.md#where-are-the-logs-and-how-do-i-follow-one-request-across-services) | `oc logs` per container, `podman logs` on the node; grep the request ID in each service. |
| [How do I find errors quickly across all pods?](openstack-capacity-and-observability.md#how-do-i-find-errors-quickly-across-all-pods-and-which-ones-are-noise) | A loop over `oc logs --since=1h` counting ` ERROR `; know the usual noise. |
| [How much room is left on the compute node?](openstack-capacity-and-observability.md#how-much-room-is-left-on-the-compute-node) | Placement inventory: 32 vCPU, about 15 GB of memory, 51 GB of disk; memory is the limit. |

### OKD cluster health and etcd

| Entry | One-line answer |
| --- | --- |
| [Which version runs, and is an update in progress or available?](okd-cluster-health-and-etcd.md#which-version-runs-and-is-an-update-in-progress-or-available) | `4.22.0-okd-scos.10`, channel `stable-scos-4`, one history line, no update available; nothing updates unless `spec.desiredUpdate` is set. |
| [What are the 34 cluster operators for, and which ones matter to OpenStack?](okd-cluster-health-and-etcd.md#what-are-the-34-cluster-operators-for-and-which-ones-matter-to-openstack) | 34, all `True False False`; etcd, API server, scheduler, network, DNS and ingress are the ones OpenStack depends on directly. |
| [How do I read the Degraded and Progressing messages of an operator?](okd-cluster-health-and-etcd.md#how-do-i-read-the-degraded-and-progressing-messages-of-an-operator) | The message is `<Controller><Type>: text`; go from `oc get co` to the operator resource's conditions, then the operator log. |
| [Where does the control plane itself run, and what are revisions?](okd-cluster-health-and-etcd.md#where-does-the-control-plane-itself-run-and-what-are-revisions) | Four static pods started by the kubelet from `/etc/kubernetes/manifests`; installer pods write each numbered revision. |
| [How do I check etcd: members, health, size, alarms and latency?](okd-cluster-health-and-etcd.md#how-do-i-check-etcd-members-health-size-alarms-and-latency) | `etcdctl` in the etcd pod: one member, 122 MB file for 46 MB in use, no alarm, WAL fsync p99 7 ms. |
| [Does etcd need defragmentation, and who does it here?](okd-cluster-health-and-etcd.md#does-etcd-need-defragmentation-and-who-does-it-here) | No: the defragmentation controller disables itself on a single node; the file is 1.4 % of the 8 GiB quota. |
| [Are there automatic etcd backups, and where is the backup script?](okd-cluster-health-and-etcd.md#are-there-automatic-etcd-backups-and-where-is-the-backup-script) | No automatic etcd backup; `cluster-backup.sh` is on the node and the only snapshot was taken by hand. |
| [Where are the logs of the API server, controller manager and scheduler, and what is normal in them?](okd-cluster-health-and-etcd.md#where-are-the-logs-of-the-api-server-controller-manager-and-scheduler-and-what-is-normal-in-them) | `oc logs` on the static pods; about 120 etcd handshake warnings per hour and a few `Trace[` lines are normal. |
| [Is the API healthy and fast right now?](okd-cluster-health-and-etcd.md#is-the-api-healthy-and-fast-right-now) | `/readyz?verbose`: 41 checks passing; p99 GET 22 ms, LIST 71 ms; rate of 5xx and 429 over the last hour is zero. |
| [Which certificates does the platform use, when do they expire and which rotate by themselves?](okd-cluster-health-and-etcd.md#which-certificates-does-the-platform-use-when-do-they-expire-and-which-rotate-by-themselves) | First signers and kubelet certificates 24 hours, API serving 30 days, all rotated while the cluster runs; `system:admin` (10 years) never. |
| [What happens during the first-day certificate rotation?](okd-cluster-health-and-etcd.md#what-happens-during-the-first-day-certificate-rotation) | Signers replaced at 80 % of their 24 hours, kubelet certificates renewed twice, four kube-apiserver revisions; no intervention. |

### OKD node and host

| Entry | One-line answer |
| --- | --- |
| [How do I get a shell on the node: `oc debug node` or SSH as `core`?](okd-node-and-host.md#how-do-i-get-a-shell-on-the-node-oc-debug-node-or-ssh-as-core) | `oc debug node/okd-0` needs API, scheduler and kubelet; SSH as `core` needs only sshd and is the only door when the API is down. |
| [What is the host operating system, and why can I not install a package?](okd-node-and-host.md#what-is-the-host-operating-system-and-why-can-i-not-install-a-package) | CentOS Stream CoreOS 10, image-based: `/usr` is read-only, only `/etc` and `/var` are writable; tools come from containers. |
| [What does a MachineConfig contain, and what would changing one do?](okd-node-and-host.md#what-does-a-machineconfig-contain-and-what-would-changing-one-do) | Files, systemd units and kernel arguments merged into `rendered-master-<hash>`; a change reboots the only node. |
| [How is kubelet configured, and where are its logs?](okd-node-and-host.md#how-is-kubelet-configured-and-where-are-its-logs) | A host systemd unit; effective values from `/configz` (`maxPods` 250, 1 GiB reserved); logs in the journal or `oc adm node-logs`. |
| [How much is reserved for the system, and when would kubelet evict pods?](okd-node-and-host.md#how-much-is-reserved-for-the-system-and-when-would-kubelet-evict-pods) | 1 GiB and 500m, static; eviction under 100 MiB of memory available or 10 % of disk free (15 % for the image filesystem). |
| [How do I inspect containers below Kubernetes with `crictl` and CRI-O?](okd-node-and-host.md#how-do-i-inspect-containers-below-kubernetes-with-crictl-and-cri-o) | `crictl` over SSH talks to the CRI-O socket and works without the API; 200 running containers, 150 images, runtime `crun`. |
| [Where does the disk space go on the node?](okd-node-and-host.md#where-does-the-disk-space-go-on-the-node) | 46 GiB of 150 used: 31 GiB images, 6.6 GiB emptyDir volumes, 2.3 GiB API audit log, 1.2 GiB OpenStack volumes. |
| [Which systemd units matter on the node, and how do I check them?](okd-node-and-host.md#which-systemd-units-matter-on-the-node-and-how-do-i-check-them) | NetworkManager, `ovs-configuration`, `nodeip-configuration`, `crio`, `kubelet`, plus `dnsmasq` and Open vSwitch; none failed. |
| [Is the node clock synchronised, and to what?](okd-node-and-host.md#is-the-node-clock-synchronised-and-to-what) | Yes: chrony follows the bastion (192.168.130.5) and four public pool servers; offset in microseconds. |
| [How long are host logs kept (journal, container logs, audit)?](okd-node-and-host.md#how-long-are-host-logs-kept-journal-container-logs-audit) | Journal about two weeks (4 GiB cap), container logs 50 MiB x 5 files, API audit about 10 hours, events 3 hours. |
| [What do cordon, uncordon and drain mean when there is only one node?](okd-node-and-host.md#what-do-cordon-uncordon-and-drain-mean-when-there-is-only-one-node) | Cordon only keeps new pods `Pending`; a drain would evict every pod with nowhere to go, a full outage with no benefit. |

### OKD node maintenance

| Entry | One-line answer |
| --- | --- |
| [How do I apply a MachineConfig on the single node, and what happens step by step?](okd-node-maintenance.md#how-do-i-apply-a-machineconfig-on-the-single-node-and-what-happens-step-by-step) | Reboot 10 to 15 s after the change, no cordon or drain; API away 3 min 35, OpenStack pods ready after 5 min 50, pool `Updated` after 7 min 10; removal is a second identical roll. |
| [How do I prepare a MachineConfig change without rebooting yet, and see what is pending?](okd-node-maintenance.md#how-do-i-prepare-a-machineconfig-change-without-rebooting-yet-and-see-what-is-pending) | Pause the pool, apply, compare `spec.configuration.name` with `status.configuration.name` and diff the two rendered configs; unpause to roll. |
| [What would a drain really evict here, and which PodDisruptionBudgets exist?](okd-node-maintenance.md#what-would-a-drain-really-evict-here-and-which-poddisruptionbudgets-exist) | Server-side dry run: 198 pods, 83 in `openstack`; four platform budgets, none blocking, none for OpenStack. |
| [Which tools work while the API is only partly back after a reboot?](okd-node-maintenance.md#which-tools-work-while-the-api-is-only-partly-back-after-a-reboot) | SSH first, `oc adm node-logs` within 10 s of the API, `oc debug node` only about 75 s later (needs the aggregated image API). |
| [Why are the OVN agents of the compute node dead after a reboot of the OKD node, and how do I fix them?](okd-node-maintenance.md#why-are-the-ovn-agents-of-the-compute-node-dead-after-a-reboot-of-the-okd-node-and-how-do-i-fix-them) | Controller and metadata agent do not reconnect to the southbound database (both MachineConfig rolls and one start of the whole lab; metadata agent 4 restarts of the OKD node out of 5); restart `edpm_ovn_controller` and `edpm_ovn_metadata_agent`. |

### OKD workloads and resources

| Entry | One-line answer |
| --- | --- |
| [Which pods die first if the node runs out of memory?](okd-workloads-and-resources.md#which-pods-die-first-if-the-node-runs-out-of-memory) | The OpenStack pods: 18 of 20 are BestEffort (`oom_score_adj` 1000, Galera included); RabbitMQ later, static pods last. |
| [How do I read the node's requests and limits accounting?](okd-workloads-and-resources.md#how-do-i-read-the-nodes-requests-and-limits-accounting) | Memory requests 72 % of allocatable, real use 62 %; the scheduler counts requests only, 8.5 GiB of requests are left. |
| [How do I give a control plane service requests and limits, and what does it change?](okd-workloads-and-resources.md#how-do-i-give-a-control-plane-service-requests-and-limits-and-what-does-it-change) | Patch `spec.<service>.template.resources` in the OpenStackControlPlane; the pod rolls (34 s for Keystone) and becomes Burstable. |
| [What does an out-of-memory kill look like, and how do I find it afterwards?](okd-workloads-and-resources.md#what-does-an-out-of-memory-kill-look-like-and-how-do-i-find-it-afterwards) | Reason `OOMKilled`, exit code 137, kernel line `oom-kill` with `CONSTRAINT_MEMCG`; none on the lab since installation. |
| [Do PodDisruptionBudgets protect the control plane here?](okd-workloads-and-resources.md#do-poddisruptionbudgets-protect-the-control-plane-here) | No: no budget exists in `openstack`, and a budget only filters evictions, not `oc delete pod` or a crash. |
| [How do ResourceQuota and LimitRange work, and are any in place?](okd-workloads-and-resources.md#how-do-resourcequota-and-limitrange-work-and-are-any-in-place) | Admission controls applied when a pod is created; none in `openstack` or `openstack-operators`, by design of the operators. |

### OKD networking

| Entry | One-line answer |
| --- | --- |
| [What is the cluster network made of, and what are its parameters?](okd-networking.md#what-is-the-cluster-network-made-of-and-what-are-its-parameters) | OVN-Kubernetes; pods 10.128.0.0/14 (a /23 for the node), Services 172.30.0.0/16, MTU 1342, `routingViaHost` true. |
| [There are two OVN deployments on the node: how do I tell them apart?](okd-networking.md#there-are-two-ovn-deployments-on-the-node-how-do-i-tell-them-apart) | Cluster OVN is inside the `ovnkube-node` pod (`GR_okd-0`, `join`); OpenStack OVN is the `ovsdbserver-*` pods (`neutron-<network-id>`). |
| [What are `br-ex` and the secondary interfaces of the node?](okd-networking.md#what-are-br-ex-and-the-secondary-interfaces-of-the-node) | `br-ex` holds `ens3` and the node address; `ens4`, `ens5`, `ens6` are ctlplane, internalapi and tenant, used through macvlan NADs. |
| [How does a pod without a secondary interface reach the OpenStack networks?](okd-networking.md#how-does-a-pod-without-a-secondary-interface-reach-the-openstack-networks) | Through `ovn-k8s-mp0` and the host routing table, masqueraded to the node's `.10` address on that network. |
| [How does a request reach an OpenStack API, end to end?](okd-networking.md#how-does-a-request-reach-an-openstack-api-end-to-end) | Public: `*.apps` DNS, HAProxy router on the node, pod IP. Internal: ClusterIP for pods, MetalLB VIP 172.17.0.80 for the compute node. |
| [What does the ingress router do with a route, and where does TLS end?](okd-networking.md#what-does-the-ingress-router-do-with-a-route-and-where-does-tls-end) | One HAProxy pod on the host network; the six routes are `reencrypt`: TLS ends with the Route's own certificate, then new TLS to the pod. |
| [How does name resolution work, from a pod to the bastion?](okd-networking.md#how-does-name-resolution-work-from-a-pod-to-the-bastion) | Pod to CoreDNS (172.30.0.10), to the node's dnsmasq, to the bastion's dnsmasq; data plane names do not resolve from pods. |
| [Which NetworkPolicies exist, and how do I add one safely?](okd-networking.md#which-networkpolicies-exist-and-how-do-i-add-one-safely) | 53 platform namespaces have policies, `openstack` has none; try default-deny plus an allow rule in a scratch namespace first. |
| [Which pod holds which address on the OpenStack networks, and how do I clean a leaked one?](okd-networking.md#which-pod-holds-which-address-on-the-openstack-networks-and-how-do-i-clean-a-leaked-one) | The whereabouts `IPPool` objects in `openshift-multus`; remove a leak with a JSON patch using `test`, then delete its reservation. |
| [Which virtual IPs does MetalLB announce, on which interface, and how do I verify from the compute node?](okd-networking.md#which-virtual-ips-does-metallb-announce-on-which-interface-and-how-do-i-verify-from-the-compute-node) | 172.17.0.80 (six internal APIs, shared), .85 and .86 (RabbitMQ) on `ens5`, 192.168.122.80 (DNS) on `ens4`; verify with `arping`. |

### OKD storage

| Entry | One-line answer |
| --- | --- |
| [How is persistent storage provided, and how does a claim find its volume?](okd-storage.md#how-is-persistent-storage-provided-and-how-does-a-claim-find-its-volume) | Twelve static 10Gi local PVs, class `local-storage` with no provisioner; a claim binds a whole volume when its first pod starts. |
| [Where is each claim's data on the node, and how big is it really?](okd-storage.md#where-is-each-claims-data-on-the-node-and-how-big-is-it-really) | In `/var/lib/openstack-lab-pv/pvNN`, mapping from `oc get pv`; 1.2 GiB in total, and the 10Gi capacity is not a limit. |
| [What happens to the data when a claim is deleted, and how do I reuse the volume?](okd-storage.md#what-happens-to-the-data-when-a-claim-is-deleted-and-how-do-i-reuse-the-volume) | Data stays (`Retain`); the volume becomes `Released` and is not reused until it is erased and its `claimRef` removed. |
| [etcd, images, logs and volumes share one disk: what are the risks and how do I watch it?](okd-storage.md#etcd-images-logs-and-volumes-share-one-disk-what-are-the-risks-and-how-do-i-watch-it) | One 150 GiB partition: a full disk evicts pods and stops etcd, heavy writers slow etcd; watch `df /var` and WAL fsync p99. |
| [The image registry is "Removed": what does that imply?](okd-storage.md#the-image-registry-is-removed-what-does-that-imply) | No internal registry: every image is pulled from external registries through the proxy; anything that pushes does not work. |

### OKD access and security

| Entry | One-line answer |
| --- | --- |
| [Which credentials does the bastion use, and when do they expire?](okd-access-and-security.md#which-credentials-does-the-bastion-use-and-when-do-they-expire) | The `system:admin` client certificate (group `system:masters`, valid until 2036) and the `kubeadmin` password; no identity provider. |
| [How do I add named users (a second administrator, a read-only user)?](okd-access-and-security.md#how-do-i-add-named-users-a-second-administrator-a-read-only-user) | An htpasswd Secret and identity provider in `oauth/cluster`, then role bindings; the OAuth pod rolls (about 30 s without logins). |
| [What can a read-only user really see?](okd-access-and-security.md#what-can-a-read-only-user-really-see) | Health, pods, logs and events; no Secrets, no exec, no OpenStack custom resources. Route TLS private keys are readable. |
| [How do I let read-only users see the OpenStack custom resources?](okd-access-and-security.md#how-do-i-let-read-only-users-see-the-openstack-custom-resources) | A ClusterRole on the 31 `.openstack.org` API groups, named exactly, with the `aggregate-to-view` and `-cluster-reader` labels. |
| [How do I remove a user or the identity provider cleanly?](okd-access-and-security.md#how-do-i-remove-a-user-or-the-identity-provider-cleanly) | Bindings first, then tokens, then User and Identity; deleting only the User revokes nothing while its token is valid. |
| [Which permissions do the OpenStack operators hold, and who can edit the OpenStackControlPlane?](okd-access-and-security.md#which-permissions-do-the-openstack-operators-hold-and-who-can-edit-the-openstackcontrolplane) | Operators: cluster-wide rights on Secrets and workloads; service pods: only the `anyuid` SCC; only cluster administrators edit it. |
| [Under which security context do the OpenStack pods run?](okd-access-and-security.md#under-which-security-context-do-the-openstack-pods-run) | 15 of 20 pods use `anyuid` with fixed Kolla UIDs, 4 `restricted-v2`, Glance `privileged`; the namespace enforces `privileged`. |
| [Who changed the OpenStackControlPlane (or logged in)?](okd-access-and-security.md#who-changed-the-openstackcontrolplane-or-logged-in-querying-the-audit-log) | `oc adm node-logs --path=kube-apiserver/` and a filter; metadata only, about 10 hours kept; a shared certificate reads `system:admin`. |

### OKD monitoring and alerting

| Entry | One-line answer |
| --- | --- |
| [Is the monitoring stack running, and what does it cost?](okd-monitoring-and-alerting.md#is-the-monitoring-stack-running-and-what-does-it-cost) | Yes, on defaults with one replica each: 11 pods, 3.2 GiB of memory, 15-day retention in an `emptyDir` (1.3 GiB after 16 hours). |
| [How do I query Prometheus from the command line?](okd-monitoring-and-alerting.md#how-do-i-query-prometheus-from-the-command-line) | `oc create token prometheus-k8s`, then `curl --data-urlencode` on the `thanos-querier` route, `/api/v1/query`. |
| [Which alerts are firing, and what do they mean?](okd-monitoring-and-alerting.md#which-alerts-are-firing-and-what-do-they-mean) | Six fire; only `HighOverallControlPlaneMemory` (64 % used) is a real signal, and no notification receiver is configured. |
| [How do I silence an alert during a maintenance?](okd-monitoring-and-alerting.md#how-do-i-silence-an-alert-during-a-maintenance) | `amtool silence add` in the `alertmanager-main-0` pod with matcher, duration and comment; the alert still fires in Prometheus. |
| [How far back do Kubernetes events go, and how do I use them?](okd-monitoring-and-alerting.md#how-far-back-do-kubernetes-events-go-and-how-do-i-use-them) | Three hours (time-to-live in etcd); sort by `.lastTimestamp`, filter `type=Warning`, capture them right after an incident. |
| [How do I reach the web console (and other `*.apps` pages) through an SSH tunnel?](okd-monitoring-and-alerting.md#how-do-i-reach-the-web-console-and-other-apps-pages-through-an-ssh-tunnel) | A SOCKS tunnel (`ssh -D`) to the bastion and a browser profile using it; a single-port forward fails on the OAuth redirect. |
| [What is monitored for OpenStack without the telemetry operator?](okd-monitoring-and-alerting.md#what-is-monitored-for-openstack-without-the-telemetry-operator) | Only the containers (CPU, memory, restarts, readiness); RabbitMQ and OVN exporters answer on 15691 and 1981 but nobody scrapes them. |

### OLM and the OpenStack operators

| Entry | One-line answer |
| --- | --- |
| [How are the OpenStack operators installed, and how do I check every link of the chain?](okd-olm-and-operators.md#how-are-the-openstack-operators-installed-and-how-do-i-check-every-link-of-the-chain) | CatalogSource, Subscription (`alpha`, Manual), InstallPlan, CSV `openstack-operator.v0.8.0`, `OpenStack` resource, 21 Deployments. |
| [Is the catalog pinned to a digest, and how do I move a running lab from a tag to a digest?](okd-olm-and-operators.md#is-the-catalog-pinned-to-a-digest-and-how-do-i-move-a-running-lab-from-a-tag-to-a-digest) | Compare `spec.image` with the running `imageID`; patch `spec.image` to the running digest and update `lab.env`: same CSV, READY after 19 s. |
| [How do I read an operator's logs, and when do operators actually reconcile?](okd-olm-and-operators.md#how-do-i-read-an-operators-logs-and-when-do-operators-actually-reconcile) | `oc logs deploy/<service>-operator-controller-manager`; they reconcile only when a watched object changes, idle operators log nothing. |
| [How do I restart a service operator safely, and what does leader election do?](okd-olm-and-operators.md#how-do-i-restart-a-service-operator-safely-and-what-does-leader-election-do) | Delete its pod: new pod Ready in 12 s, lease acquired 34 s after the deletion, then one full reconcile; services keep running. |
| [How do I switch off or resize individual operators (`operatorOverrides`)?](okd-olm-and-operators.md#how-do-i-switch-off-or-resize-individual-operators-operatoroverrides) | `spec.operatorOverrides` of the `OpenStack` resource (name, replicas, resources); a direct edit of the Deployment is reverted. |
| [Which resource types do the operators own, and which exist on this lab?](okd-olm-and-operators.md#which-resource-types-do-the-operators-own-and-which-exist-on-this-lab) | 104 CRDs in 31 API groups, 36 kinds with objects; the CSV owns only `OpenStack`, the initialisation operator creates the other 103. |
| [What garbage accumulates (old ReplicaSets, Jobs, completed pods), and what may I clean?](okd-olm-and-operators.md#what-garbage-accumulates-old-replicasets-jobs-completed-pods-and-what-may-i-clean) | 51 empty ReplicaSets in the cluster, 33 Completed pods in `openstack`; only old data plane deployments and manual Jobs are yours to delete. |

### State of the lab

| Entry | One-line answer |
| --- | --- |
| [What did the campaigns leave on the lab, and how do I list and remove each item?](lab-state.md#what-did-the-campaigns-leave-on-the-lab-and-how-do-i-list-and-remove-each-item) | Nine data plane deployments with 51 Jobs on 2026-11-12 (eleven deployments after the drills of 2026-11-13), two dumps per database instance, the `kb-demo` tenant, the `nova-extra-config` ConfigMap (now baseline); `/var` at 32 %. |
