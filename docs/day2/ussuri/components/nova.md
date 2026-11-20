---
title: Nova
description: Where the study covers Nova (roles nova and nova-cell), from the three reconfigure commands and the compute restart risk to dependencies and open points.
tags: [nova, libvirt, reconfigure, loop-notify, serial, limit, one-shot, risk, dependencies, unknowns]
---

# Nova

This page is the starting point for Nova, which is split into two roles: `nova` (API level: `nova_api`, `nova_scheduler`
and `nova_super_conductor`, on the control nodes of the example inventory) and `nova-cell` (cell level: `nova_compute`,
`nova_libvirt`, `nova_ssh`, `nova_conductor`, the three console proxies and `nova_compute_ironic`, on the compute and
control nodes). The tag `nova` selects both; `nova-api` does not touch computes and `nova-cell` touches every compute
([Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)). The lists below say where the study covers how
to operate it, its impact, its dependencies and the evidence, what to check around a run and what stays open; the two
service cards follow them.

## Where to look

### Operate

- **Scenario (`nova`):** [Reconfigure Nova](../operations/reconfigure-nova.md); batched apply: [Write config first,
  apply in controlled batches
  §2](../operations/controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)
- **Command (`nova`):** [Reconfigure Nova
  §1.1](../operations/reconfigure-nova.md#11-reconfigure-nova-control-plane-and-computes), [Write config first, apply in
  controlled batches §1.2](../operations/controlled-batches.md#12-rolling-reconfigure-with-ansible_serial), [Reconfigure
  a single service §1.2](../operations/reconfigure-a-service.md#12-avoid-touching-haproxy-during-a-service-run)
- **Scenario (`nova-api`):** [Reconfigure Nova
  §2](../operations/reconfigure-nova.md#2-execution-sequence-kolla-ansible--t-nova-reconfigure) (plays 1, 3 and 5)
- **Command (`nova-api`):** [Reconfigure Nova
  §1.2](../operations/reconfigure-nova.md#12-reconfigure-only-the-nova-control-plane-no-compute-impact)
- **Scenario (`nova-cell`):** [Reconfigure Nova
  §2](../operations/reconfigure-nova.md#2-execution-sequence-kolla-ansible--t-nova-reconfigure) (plays 2 and 4),
  [Reconfigure Nova
  §4](../operations/reconfigure-nova.md#4-are-all-compute-nodes-affected-does-nova-compute-restart-on-every-compute)
- **Command (`nova-cell`):** [Reconfigure Nova
  §1.3](../operations/reconfigure-nova.md#13-reconfigure-only-the-cell-part-conductors-consoles-computes), [Write config
  first, apply in controlled batches
  §1.1](../operations/controlled-batches.md#11-compute-changes-in-controlled-batches-recommended-pattern)
- **Scenario (`nova-bootstrap`, `nova-reload`, `nova-online-data-migrations` (with their `-api-`/`-cell-` variants) and
  `nova-refresh-scheduler-cell-cache`):** the plays themselves: [Nova deep dive
  §4](nova-deep-dive.md#4-the-nova-plays-step-by-step-ansiblenovayml)

### Impact and risk

- **What the tag executes (`nova`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `nova`
- **Risks (`nova`):** [R1](../risk/risk-register.md#r1), [R2](../risk/risk-register.md#r2),
  [R3](../risk/risk-register.md#r3), [R24](../risk/risk-register.md#r24)
- **What the tag executes (`nova-api`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `nova-api`
- **What the tag executes (`nova-cell`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and
  [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows
  `nova-cell`
- **Risks (`nova-cell`):** [R1](../risk/risk-register.md#r1)
- **What the tag executes (`nova-bootstrap`, `nova-reload`, `nova-online-data-migrations` (with their `-api-`/`-cell-`
  variants) and `nova-refresh-scheduler-cell-cache`):** [Tags
  §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), one row each; use as narrower play tags: [Tags
  §4](../risk/tags.md#4-practical-consequences) (item 4)

### Dependencies

- **Dependencies (role `nova`):** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Dependencies (role `nova-cell`):** [Component dependencies §3](dependencies.md#3-control-plane-services), [Component
  dependencies §5](dependencies.md#5-compute-node-dependency-summary)

### Evidence

- **Fact sheet (roles `nova` and `nova-cell`):** –
- **Image side (role `nova`):** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `nova-api`), [Kolla
  images §4.1](../concepts/kolla-images.md#41-one-shots-that-bypass-kolla_start), [Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Also (role `nova`):** **[Nova deep dive](nova-deep-dive.md)**; handlers: [Tags
  §5](../risk/tags.md#5-role--handler-map-core-services)
- **Image side (role `nova-cell`):** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `nova-conductor`),
  [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour), [Kolla images
  §5.1](../concepts/kolla-images.md#51-nova-libvirt-the-start-path-is-passive)
- **Also (role `nova-cell`):** **[Nova deep dive](nova-deep-dive.md)**, in particular [Nova deep dive
  §5](nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special); handlers: [Tags
  §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 5 (health gates): before the run, check
  `openstack compute service list` and `openstack network agent list` all up. Repeat after each batch.
- [Pre-execution checklist](../operations/pre-execution-checklist.md), step 6 (workload gates): no live migrations,
  resizes, image uploads or volume migrations in flight on the targeted hosts; check
  `openstack server list --all-projects --status MIGRATING|RESIZE` and `openstack volume list --status *ing`.
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows `nova`,
  `nova-api` and `nova-cell`: `nova` is safe on its own "only with batching and a window; prefer `genconfig` +
  `deploy-containers --limit`", `nova-cell` "as `nova`", `nova-api` "yes; does not touch computes". Prerequisites of
  `nova`: MariaDB, RabbitMQ, memcached, Keystone, Placement, Glance, Neutron registered; of `nova-api`: as `nova`; of
  `nova-cell`: the API DB and cell0 mapping (`nova-api`/`nova`), RabbitMQ.
- [Nova deep dive §3](nova-deep-dive.md#3-what-must-be-available-before-nova-can-operate), "What must be available
  before Nova can operate", eight items ordered by necessity: MariaDB (through HAProxy and the VIP); RabbitMQ;
  Keystone + memcached; Placement; cell mapping and host mapping; Neutron server + an L2 agent on the compute; Glance
  for image-backed boots and Cinder for volume-backed boots; libvirt (+ KVM, `br_netfilter`, udev rule) on the compute.
  What Kolla configures is [CODE]; upstream Nova behaviour is marked [NOT AVAILABLE].
- [Nova deep dive §2.1](nova-deep-dive.md#21-installation-deploy-time-dependencies), installation (deploy-time)
  dependencies: what must work while Kolla runs the nova plays, each with its failure mode.
- [Nova deep dive §2.2](nova-deep-dive.md#22-runtime-dependencies-what-nova-needs-to-operate), runtime dependencies:
  what each Nova component requires at runtime.
- [R1](../risk/risk-register.md#r1), precautions for any config change touching nova-compute: `genconfig` + `diff`, then
  `deploy-containers --limit` in batches, or `ANSIBLE_SERIAL`; drain live migrations first; validate libvirt restart
  behaviour in staging.
- [R2](../risk/risk-register.md#r2), precautions for enabling or disabling a service that has a logrotate or fluentd
  input entry: treat `enable_*` changes as fleet-wide changes; roll out with `--limit` batches.
- [R3](../risk/risk-register.md#r3), precautions for a change of RabbitMQ group membership, password or port: plan as a
  maintenance; batch with `--limit`; verify RabbitMQ cluster health first.
- [R24](../risk/risk-register.md#r24), precautions for the effective container stop timeout of 10 s: drain long
  operations before restarts; patch `kolla_docker` or pass `graceful_timeout` if needed.
- [Reconfigure Nova §6](../operations/reconfigure-nova.md#6-operational-risks-and-verification), verification: before,
  `kolla-ansible -t nova genconfig` (restarts nothing), then a diff of `/etc/kolla/nova-*/nova.conf` on one controller
  and one compute, `kolla_set_configs --check` in `nova_compute` on a few computes (exit 1 means the container will
  restart, and so will `nova_libvirt` and `nova_ssh`), and no active live migrations. After,
  `openstack compute service list` (all up), `docker ps --filter name=nova_ -a`, `virsh list --all` inside
  `nova_libvirt` on a sample of computes with guest pings, and a `nova-manage cell_v2 list_hosts` count equal to the
  number of computes.
- [Nova deep dive §7](nova-deep-dive.md#7-upgrade-path-specifics): the image pull is not part of `upgrade`; run
  `kolla-ansible pull` first.

### Known limits and open points

- [Q1](../troubleshooting/open-questions.md#q1): "Do running VMs survive a `nova_libvirt` restart or recreate?" Status:
  [NOT AVAILABLE].
- [Nova deep dive §5](nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special), "nova-libvirt: why its restart is
  special": what the code shows about the container is [CODE] (`pid_mode: host`, state on named volumes, a start path
  that is passive towards running guests, the 10 s stop timeout, the restart handler's retries); what happens to running
  VMs is [NOT AVAILABLE].
- [Nova deep dive §6](nova-deep-dive.md#6-live-migration-resize-and-consoles), live migration, resize and consoles:
  whether a `nova_libvirt` or `nova_ssh` restart interrupts operations in progress is [NOT AVAILABLE].
- [What is not known](../troubleshooting/what-is-not-known.md#running-vms-and-compute-hosts), group "Running VMs and
  compute hosts": what the sources do not establish about a `nova_libvirt` restart or recreate, a `nova_compute`
  restart, a `nova_ssh` restart, the restart of the nova API, scheduler and conductors, upstream Nova behaviour when a
  dependency is missing, scheduling on a fresh compute, and live migration to a new compute.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish whether the SSH clients accept the new `nova_ssh` and `keystone_ssh` host keys after a
  recreate without failing, or the cost of the recursive chown on large trees (the NFS instance directory among them).
- [Q13](../troubleshooting/open-questions.md#q13): "`bootstrap-servers` re-run effects on a live compute". Status:
  [NOT AVAILABLE].
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: Nova's bootstrap containers run with
  `KOLLA_UPGRADE`, so Nova's online data migrations never run outside `upgrade`; the images' `KOLLA_BOOTSTRAP` branches
  are unreachable.
- [F1](../reference/findings.md#f1), "Loop-notify amplification": a nova-compute-only change restarts `nova_libvirt` and
  `nova_ssh`; a scheduler-only change restarts `nova_api` [CODE].
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored" [CODE]: every
  stop sends SIGKILL to a container still running 10 s after SIGTERM; for `nova_libvirt` this matters only if libvirtd
  has not exited by then.
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": `-t nova` starts 5 one-shot containers on `control01`
  when cell0 is mapped and the cell is unchanged [CODE].
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords and the external FQDN end up in compute-side files [CODE].
- [F8](../reference/findings.md#f8), "`--limit` does not confine actions": with `deploy --limit` set to a compute host,
  `control01` runs cell discovery (`nova_list_cells`, `openstack compute service list`,
  `nova-manage cell_v2 discover_hosts`) [CODE].
- [F10](../reference/findings.md#f10), "`kolla_serial` makes `run_once` steps repeat per batch": API DB sync ×3 with
  serial 1 and the three controllers of the `multinode` inventory; a play's restarts follow host-pattern order, computes
  before conductors in the nova-cell play [CODE].
- [F13](../reference/findings.md#f13), "The Nova deploy order" puts nova-compute before OVS and the Neutron agents on
  new computes [CODE]; [NOT AVAILABLE] whether instances can be scheduled on such a compute before the later plays
  finish.
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": Nova's bootstrap
  containers run with `KOLLA_UPGRADE` (schema sync, no online data migrations outside `upgrade`) [CODE].
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md) has no row whose area is Nova; its row
  `masakari` names nova-libvirt: instancemonitor uses `qemu+tcp` without SASL while nova-libvirt enables SASL. Status:
  [CODE]; effect on the instancemonitor [NOT AVAILABLE].
- Risk items whose VM impact refers to R1: [R12](../risk/risk-register.md#r12), changing `openstack_tag` / `*_tag` and
  running `deploy` instead of `upgrade` ("as R1 + R7 + R8 together"); [R13](../risk/risk-register.md#r13), a rebuilt
  image pushed under the same tag ("as R1"); [R14](../risk/risk-register.md#r14), a `bootstrap-servers` re-run on a live
  host ("Docker restart = nova_libvirt + OVS restart"). [R15](../risk/risk-register.md#r15), `kolla-ansible stop`, stops
  the `nova_libvirt` and OVS containers on the targeted hosts.
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 5, 10, 11 and 18: Nova's online data
  migrations never run outside `upgrade` [CODE]; one `chown` per file of `/var/lib/nova` on computes on every
  `COPY_ALWAYS` start [CODE]; nova-libvirt's start path is passive, and VM survival is decided on the stop path [CODE
  for the start path; NOT AVAILABLE for survival]; SSH host keys of `nova_ssh` and `keystone_ssh` change on every
  recreate [CODE].

## Service card

The rows of the two cards are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py nova nova-cell -->

### Nova (API level) — role `nova`

| Item | Value |
|---|---|
| Play | nova.yml (`import_playbook` at site.yml:710) |
| Tags | nova, nova-api(-*) |
| Play host patterns | nova-api, nova-scheduler, nova-super-conductor |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `nova_api`, `nova_scheduler`, `nova_super_conductor` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, bootstrap_upgrade.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_bootstrap.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, map_cell0.yml, online_data_migrations.yml, precheck.yml, pull.yml, reconfigure.yml, refresh_scheduler_cell_cache.yml, register.yml, reload_api.yml, reload_super_conductor.yml, rolling_upgrade.yml, stop.yml, upgrade.yml |
| Templates | `nova-api-bootstrap.json.j2`, `nova-api.json.j2`, `nova-scheduler.json.j2`, `nova-super-conductor.json.j2`, `nova.conf.j2` |
| Handlers (definition order) | Restart nova-super-conductor container; Restart nova-scheduler container; Restart nova-api container |
| Key variables | `enable_nova`, `enable_cells`, `nova_safety_upgrade`, `nova_console` |
| Role dependencies | `common` (meta) |

### Nova (cell level) — role `nova-cell`

| Item | Value |
|---|---|
| Play | nova.yml (`import_playbook` at site.yml:710) |
| Tags | nova, nova-cell(-*) |
| Play host patterns | compute, nova-compute-ironic, nova-conductor, nova-novncproxy, nova-serialproxy, nova-spicehtml5proxy |
| Node types in play (example inventory) | compute, control |
| Node types running its containers | compute, control |
| Containers | `nova_libvirt`, `nova_ssh`, `nova_novncproxy`, `nova_spicehtml5proxy`, `nova_serialproxy`, `nova_conductor`, `nova_compute`, `nova_compute_ironic` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | bootstrap_xenapi (if) → clone (if) → config-host → config → check-containers → config-nova-fake (if) → flush handlers → wait_discover_computes (if) |
| Task files | bootstrap.yml, bootstrap_service.yml, bootstrap_upgrade.yml, bootstrap_xenapi.yml, cell_proxy_loadbalancer.yml, check-containers.yml, check.yml, clone.yml, config-host.yml, config-libvirt-tls.yml, config-nova-fake.yml, config.yml, config_bootstrap.yml, copy-certs.yml, create_cells.yml, deploy-containers.yml, deploy.yml, discover_computes.yml, external_ceph.yml, get_cell_settings.yml, loadbalancer.yml, main.yml, online_data_migrations.yml, precheck.yml, proxy_loadbalancer.yml, pull.yml, rabbitmq.yml, reconfigure.yml, reload.yml, rolling_upgrade.yml, stop.yml, upgrade.yml, wait_discover_computes.yml |
| Templates | `99-kolla-kvm.rules.j2`, `auth.conf.j2`, `libvirtd.conf.j2`, `nova-cell-bootstrap.json.j2`, `nova-compute-ironic.json.j2`, `nova-compute.json.j2`, `nova-conductor.json.j2`, `nova-libvirt.json.j2`, `nova-novncproxy.json.j2`, `nova-serialproxy.json.j2`, `nova-spicehtml5proxy.json.j2`, `nova-ssh.json.j2`, `nova.conf.d/libvirt.conf.j2`, `nova.conf.j2`, `qemu.conf.j2`, `sasl.conf.j2`, `secret.xml.j2`, `ssh_config.j2`, `sshd_config.j2` |
| Handlers (definition order) | Restart nova-conductor container; Restart nova-novncproxy container; Restart nova-spicehtml5proxy container; Restart nova-serialproxy container; Restart nova-ssh container; Restart nova-libvirt container; Create libvirt SASL user; Restart nova-compute container; Restart nova-compute-ironic container; Restart nova-compute-fake containers; Wait for nova-compute services to update service versions |
| Key variables | `nova_compute_virt_type`, `nova_backend_ceph`, `libvirt_tls`, `libvirt_enable_sasl`, `nova_cell_*_group`, `migration_interface` |
| Role dependencies | `common` (meta) |

<!-- END GENERATED -->

## Related

- [Nova deep dive](nova-deep-dive.md) — Nova in depth: the two roles and ten plays, the dependencies, what restarts what
  and the `nova_libvirt` restart
- [Reconfigure Nova](../operations/reconfigure-nova.md) — what `-t nova reconfigure` runs on controllers and on every
  compute
- [Write config first, apply in controlled batches](../operations/controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch
- [Add a compute node](../operations/add-a-compute-node.md) — what `deploy --limit` touches on the new compute and
  elsewhere
- [RabbitMQ](rabbitmq.md) — a change of its group membership changes the transport URL everywhere
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
