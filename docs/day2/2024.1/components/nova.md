---
title: Nova
description: Where the 2024.1 study covers Nova (roles nova and nova-cell), from the three reconfigure commands and the compute restart risk to dependencies and open points.
tags: [nova, libvirt, reconfigure, loop-notify, serial, limit, one-shot, risk, dependencies, unknowns]
---

# Nova

This page is the starting point for Nova, which is split into two roles: `nova` (API level: `nova_api`, `nova_scheduler`
and `nova_super_conductor`, on the control nodes of the example inventory) and `nova-cell` (cell level: `nova_compute`,
`nova_libvirt`, `nova_ssh`, `nova_conductor`, the three console proxies and `nova_compute_ironic`, on the compute and
control nodes) (`nova.yml:1-22`, `inventory/multinode:18-19`, `inventory/multinode:99-100`,
`inventory/multinode:227-249`). The tag `nova` selects both; `nova-api` does not touch computes and `nova-cell` touches
every compute (`nova.yml:103-147`; [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)). The lists
below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to check around
a run and what stays open; the two service cards follow them.

## What changed in 2024.1

- **Every Nova play gets `max_fail_percentage`, and one more play gets `any_errors_fatal`** [CODE]. Seven of the ten
  plays of `nova.yml` now set `max_fail_percentage` from `nova_max_fail_percentage` (API-level plays) or
  `nova_cell_max_fail_percentage` (cell-level plays), then `kolla_max_fail_percentage`, then 100 (e.g.
  `nova.yml:40-43`, `nova.yml:141-144`). The three plays that carry `any_errors_fatal: true` instead are the cell DB
  bootstrap and the two online-data-migration plays; the API online-migration play is new to that list
  (`nova.yml:79`, `nova.yml:269-270`, `nova.yml:294-295`). With the default 100 a play is never stopped early by the
  share of failed hosts of a batch ([Controlled batches
  §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).
- **The default RabbitMQ quorum queues change every Nova `nova.conf`** [CODE]. `om_enable_rabbitmq_quorum_queues`
  now defaults to `true` (`group_vars/all.yml:268`), so both templates render `rabbit_quorum_queue = true`
  (`roles/nova/templates/nova.conf.j2:156-165`, `roles/nova-cell/templates/nova.conf.j2:207-216`). A cloud that kept the
  2023.1 default gets a changed `nova.conf` for every Nova service, computes included, on its first 2024.1 run that
  renders the Nova configs ([F17](../reference/findings.md#f17)). With `om_enable_queue_manager` (default `false`,
  `group_vars/all.yml:269`) the templates add `use_queue_manager` (`roles/nova/templates/nova.conf.j2:142-147`,
  `roles/nova-cell/templates/nova.conf.j2:193-198`) and the Nova service containers mount `/dev/shm`
  (e.g. `roles/nova/defaults/main.yml:169`, `roles/nova-cell/defaults/main.yml:397`).
- **New file for `nova_compute`: `hostnqn`** [CODE]. The nova-cell `config.yml` renders
  `/etc/kolla/nova-compute/hostnqn` from the host name and notifies the nova-compute restart
  (`roles/nova-cell/tasks/config.yml:203-216`); `config.json` copies it to `/etc/nvme/hostnqn`
  (`roles/nova-cell/templates/nova-compute.json.j2:59-64`). On a compute where it is not there yet, the file is new,
  and `kolla_set_configs --check` reports a missing destination as a difference (kolla
  `docker/base/set_configs.py:165-169`, `docker/base/set_configs.py:240-242`).
- **A per-host, per-service override for the cell role** [CODE]. The nova-cell `Copying over nova.conf` loop also
  merges `/etc/kolla/config/nova/<host>/<service>.conf`, last (`roles/nova-cell/tasks/config.yml:69-89`, source at
  `:80`). The nova role does not have this source (`roles/nova/tasks/config.yml:64-82`).
- **Container definitions that may differ from a 2023.1 container** [CODE]. The `nova_libvirt` bind of `/run` is now
  written `/run:/run:shared` with Docker (2023.1: `/run/:/run/:shared`), and `nova_libvirt` and `nova_compute` add the
  `run_default_volumes_<engine>` list, empty for Docker (`roles/nova-cell/defaults/main.yml:11`, `:62`, `:374`;
  `group_vars/all.yml:165-172`). The Docker worker compares the bind strings without normalising them
  (`module_utils/kolla_docker_worker.py:124-144`, `module_utils/kolla_container_worker.py:400-430`); whether Docker
  reports the 2023.1 bind as `/run/` or `/run` is [NOT AVAILABLE], so whether this alone makes `nova_libvirt` differ is
  [NOT AVAILABLE]. Independently of it, the first 2024.1 check of a container whose systemd unit 2023.1 wrote reports
  drift ([F16](../reference/findings.md#f16)).
- **Smaller changes** [CODE]: console base URLs and the Nova endpoints are built with the `kolla_url` filter and the new
  `*_public_port` variables, which follow `haproxy_single_external_frontend` (default `false`)
  (`roles/nova-cell/templates/nova.conf.j2:57`, `roles/nova/defaults/main.yml:204-205`, `group_vars/all.yml:512`,
  `group_vars/all.yml:520`, `group_vars/all.yml:931-932`); host discovery runs `exec -t`
  (`roles/nova-cell/tasks/discover_computes.yml:17`); `sshd_config` of `nova_ssh` gains an `sftp` subsystem line for
  Debian and Ubuntu images (`roles/nova-cell/templates/sshd_config.j2:9-13`); the external Ceph files are looked up per
  host first and named after `nova_ceph_cluster` (default `ceph`) (`roles/nova-cell/tasks/external_ceph.yml:1-130`,
  `roles/nova-cell/defaults/main.yml:536`); the nova role no longer registers an extra Keystone role
  (`roles/nova/tasks/register.yml:1-8`).
- **Still holds in 2024.1** [CODE]: the handlers of both roles are the same, in the same order, with the module renamed
  `kolla_container` (`roles/nova/handlers/main.yml:1-54`, `roles/nova-cell/handlers/main.yml:1-168`); the deploy flows
  are unchanged (`roles/nova/tasks/deploy.yml:1-9`, `roles/nova-cell/tasks/deploy.yml:1-39`); every play still takes
  `serial` from `kolla_serial`, default `0` (e.g. `nova.yml:140`).

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
  §1.1](../operations/controlled-batches.md#11-compute-changes-in-controlled-batches-recommended-pattern); stop a
  rolling
  run on failures with `nova_cell_max_fail_percentage` or `kolla_max_fail_percentage`: [Write config first, apply in
  controlled batches §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)
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
- **First 2024.1 run after 2023.1:** [F16](../reference/findings.md#f16) (changed systemd unit text) and
  [F17](../reference/findings.md#f17) (quorum queues on by default), see
  [What changed in 2024.1](#what-changed-in-20241)
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
  before Nova can operate": what Kolla configures is [CODE]; upstream Nova behaviour is marked [NOT AVAILABLE].
- [Nova deep dive §2.1](nova-deep-dive.md#21-installation-deploy-time-dependencies), installation (deploy-time)
  dependencies: what must work while Kolla runs the nova plays, each with its failure mode.
- [Nova deep dive §2.2](nova-deep-dive.md#22-runtime-dependencies-what-nova-needs-to-operate), runtime dependencies:
  what each Nova component requires at runtime.
- [R1](../risk/risk-register.md#r1), precautions for any config change touching nova-compute: `genconfig` + `diff`, then
  `deploy-containers --limit` in batches, or `ANSIBLE_SERIAL`; drain live migrations first. The code reason is
  loop-notify: on a compute the `Check nova-cell containers` loop covers `nova-libvirt`, `nova-ssh` and `nova-compute`
  and notifies the restart handler of each executed item (`roles/nova-cell/tasks/check-containers.yml:2-22`,
  `roles/nova-cell/defaults/main.yml:3-21`, `roles/nova-cell/defaults/main.yml:53-64`) [CODE].
- [R2](../risk/risk-register.md#r2), precautions for enabling or disabling a service that has a logrotate or fluentd
  input entry: treat `enable_*` changes as fleet-wide changes; roll out with `--limit` batches; apply the `common` side
  deliberately with `-t common`. A `-t nova` run does not run the `common` play, which is tagged `common` only
  (`site.yml:88-103`) [CODE].
- [R3](../risk/risk-register.md#r3), precautions for a change of RabbitMQ group membership, password or port: plan as a
  maintenance; batch with `--limit`; verify RabbitMQ cluster health first. The cell transport URLs list every host of
  the RPC and notification groups with user and password (`roles/nova-cell/defaults/main.yml:206-207`) and are written
  into every cell `nova.conf` (`roles/nova-cell/templates/nova.conf.j2:37`,
  `roles/nova-cell/templates/nova.conf.j2:184`)
  [CODE].
- [R24](../risk/risk-register.md#r24), container stop timeout: in 2024.1 the stop goes through the container's systemd
  unit, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:32`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:139`)
  ([F3](../reference/findings.md#f3)). Precautions: drain long operations before restarts; raise
  `docker_graceful_timeout` if needed (changing it changes the unit text, which the next check reports as drift,
  [F16](../reference/findings.md#f16)).
- [Reconfigure Nova §6](../operations/reconfigure-nova.md#6-operational-risks-and-verification), verification: before,
  `kolla-ansible -t nova genconfig` (restarts nothing: every Nova restart handler is skipped when `kolla_action` is
  `config`, `roles/nova/handlers/main.yml:16-17`, `roles/nova-cell/handlers/main.yml:167-168`), then a diff of
  `/etc/kolla/nova-*/nova.conf` on one controller and one compute, `kolla_set_configs --check` in `nova_compute` on a
  few computes (exit 1 means the container will restart, and so will `nova_libvirt` and `nova_ssh`), and no active live
  migrations. After, `openstack compute service list` (all up), the `nova_*` containers' state, `virsh list --all`
  inside `nova_libvirt` on a sample of computes with guest pings, and a `nova-manage cell_v2 list_hosts` count equal to
  the number of computes.
- [Nova deep dive §7](nova-deep-dive.md#7-upgrade-path-specifics): no task of the Nova upgrade pulls images
  (`roles/nova/tasks/upgrade.yml:1-53`, `roles/nova-cell/tasks/upgrade.yml:1-16`); a restart handler pulls a missing
  image just before it stops the old container (`module_utils/kolla_docker_worker.py:353-361`) [CODE]. Run
  `kolla-ansible pull` first.

### Known limits and open points

- [Q1](../troubleshooting/open-questions.md#q1): "Do running VMs survive a `nova_libvirt` restart or recreate?" Status:
  [NOT AVAILABLE].
- [Nova deep dive §5](nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special), "nova-libvirt: why its restart is
  special": what the code shows about the container is [CODE]: `pid_mode: host` and `cgroupns_mode: host`
  (`roles/nova-cell/defaults/main.yml:8-9`), state on named volumes (`roles/nova-cell/defaults/main.yml:379-382`), a
  start path that is passive towards running guests (kolla `docker/nova/nova-libvirt/extend_start.sh:1-16`), the 60 s
  stop timeout of its systemd unit, and the restart handler's 5 retries (`roles/nova-cell/handlers/main.yml:109-113`).
  What happens to running VMs is [NOT AVAILABLE].
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
  `KOLLA_UPGRADE` (`roles/nova/tasks/bootstrap_service.yml:10-12`, `roles/nova-cell/tasks/bootstrap_service.yml:10-12`),
  which runs the schema syncs and exits (kolla `docker/nova/nova-api/extend_start.sh:16-20`,
  `docker/nova/nova-conductor/extend_start.sh:9-12`); the online data migrations run only in the upgrade-only plays
  (`nova.yml:258-302`), and the images' `KOLLA_BOOTSTRAP` branches are not reached from the nova roles.
- [F1](../reference/findings.md#f1), "Loop-notify amplification": a nova-compute-only change restarts `nova_libvirt` and
  `nova_ssh`; a scheduler-only change restarts `nova_api` [CODE] (`roles/nova-cell/tasks/check-containers.yml:2-22`,
  `roles/nova/tasks/config.yml:64-82`; [Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": no longer
  holds in 2024.1 [CODE]. Both values reach the module through `docker_common_options` (`group_vars/all.yml:142-153`),
  and the stop timeout is written into each container's systemd unit (`module_utils/kolla_systemd_worker.py:32`); for
  `nova_libvirt` this matters only if libvirtd has not exited by then.
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": `-t nova` starts 6 one-shot containers on `control01`
  when cell0 is mapped with an unchanged connection and the cell is unchanged: `nova_api_bootstrap`, `map_cell0`, a
  `list_cells` for cell0, `nova_cell_bootstrap`, and a `list_cells` in each of `create_cells.yml` and
  `discover_computes.yml` (`roles/nova/tasks/bootstrap.yml:54-56`, `roles/nova/tasks/map_cell0.yml:2-30`,
  `roles/nova-cell/tasks/bootstrap.yml:41-43`, `roles/nova-cell/tasks/create_cells.yml:2-4`,
  `roles/nova-cell/tasks/discover_computes.yml:4-5`, `roles/nova-cell/tasks/get_cell_settings.yml:2-21`) [CODE].
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords, the oslo.messaging options and the external FQDN end up in
  compute-side files (e.g. `roles/nova-cell/templates/nova.conf.j2:37`, `:57`, `:207-216`) [CODE].
- [F8](../reference/findings.md#f8), "`--limit` does not confine actions": with `deploy --limit` set to a compute host,
  `control01` runs cell discovery (`nova_list_cells`, `openstack compute service list`,
  `nova-manage cell_v2 discover_hosts`), delegated to the first conductor
  (`roles/nova-cell/tasks/wait_discover_computes.yml:8-43`, `roles/nova-cell/tasks/discover_computes.yml:4-23`) [CODE].
- [F10](../reference/findings.md#f10), "`kolla_serial` makes `run_once` steps repeat per batch": API DB sync ×3 with
  serial 1 and the three controllers of the `multinode` inventory (`roles/nova/tasks/bootstrap_service.yml:2-21`,
  `nova.yml:39`); a play's restarts follow host-pattern order, computes before conductors in the nova-cell play
  (`nova.yml:127-134`) [CODE].
- [F13](../reference/findings.md#f13), "The Nova deploy order" puts nova-compute before OVS and the Neutron agents on
  new computes (`site.yml:609`, `site.yml:611-624`) [CODE]; [NOT AVAILABLE] whether instances can be scheduled on such a
  compute before the later plays finish.
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": Nova's bootstrap
  containers run with `KOLLA_UPGRADE` (schema sync, no online data migrations outside `upgrade`) [CODE], as in Q14
  above.
- [F16](../reference/findings.md#f16), new in 2024.1: the first 2024.1 check of a Nova container whose unit 2023.1 wrote
  reports drift, and on a compute loop-notify then restarts `nova_compute`, `nova_libvirt` and `nova_ssh` together
  (`module_utils/kolla_systemd_worker.py:154-167`, `module_utils/kolla_container_worker.py:58-65`,
  `roles/nova-cell/tasks/check-containers.yml:2-22`) [CODE].
- [F17](../reference/findings.md#f17), new in 2024.1: quorum queues on by default change every Nova `nova.conf` [CODE];
  what oslo.messaging does with existing classic queues is [NOT AVAILABLE].
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `masakari`, which names
  nova-libvirt: the Ussuri SASL mismatch does not hold in 2024.1, since with `libvirt_enable_sasl` (default `true`) the
  instancemonitor gets an `auth.conf` with the libvirt SASL credentials (`roles/masakari/defaults/main.yml:185`,
  `roles/masakari/templates/masakari-instancemonitor.json.j2:9-15`). Its `connection_uri` is still hard-coded
  `qemu+tcp` (`roles/masakari/templates/masakari-monitors.conf.j2:18`), while with `libvirt_tls` libvirtd listens on
  TLS only (`roles/nova-cell/templates/libvirtd.conf.j2:1-3`). Status: [CODE]; effect on the instancemonitor
  [NOT AVAILABLE].
- Risk items whose VM impact refers to R1: [R12](../risk/risk-register.md#r12), changing `openstack_tag` / `*_tag` and
  running `deploy` instead of `upgrade`; [R13](../risk/risk-register.md#r13), a rebuilt image pushed under the same tag;
  [R14](../risk/risk-register.md#r14), a `bootstrap-servers` re-run on a live host: a Docker restart (`restarted` unless
  `docker_systemd_reload`, default `false`; ansible-collection-kolla `roles/docker/handlers/main.yml:10-15`,
  `roles/docker/defaults/main.yml:65`) stops every container, `nova_libvirt` and OVS included [CODE];
  [R15](../risk/risk-register.md#r15), `kolla-ansible stop`, stops the Nova cell containers on the targeted hosts
  through `service-stop` (`roles/nova-cell/tasks/stop.yml:2-6`) [CODE].
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 5, 10, 11 and 18: Nova's online data
  migrations never run outside `upgrade` [CODE]; one `chown` per file of `/var/lib/nova` on computes on every
  `COPY_ALWAYS` start (`roles/nova-cell/templates/nova-compute.json.j2:90-94`; kolla
  `docker/base/set_configs.py:379-386`) [CODE]; nova-libvirt's start path is passive, and VM survival is decided on the
  stop path [CODE for the start path; NOT AVAILABLE for survival]; SSH host keys of `nova_ssh` change on every recreate,
  since `/etc/ssh` is on none of its volumes (`roles/nova-cell/defaults/main.yml:384-391`) [CODE].

## Service card

The rows of the two cards are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py nova nova-cell -->

### Nova (API level) — role `nova`

| Item | Value |
|---|---|
| Play | nova.yml (`import_playbook` at site.yml:609) |
| Tags | nova, nova-api(-*) |
| Play host patterns | nova-api, nova-scheduler, nova-super-conductor |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `nova_api`, `nova_scheduler`, `nova_super_conductor` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, bootstrap_upgrade.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_bootstrap.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, map_cell0.yml, online_data_migrations.yml, precheck.yml, pull.yml, reconfigure.yml, refresh_scheduler_cell_cache.yml, register.yml, reload_api.yml, reload_super_conductor.yml, rolling_upgrade.yml, stop.yml, upgrade.yml |
| Templates | `nova-api-bootstrap.json.j2`, `nova-api-wsgi.conf.j2`, `nova-api.json.j2`, `nova-scheduler.json.j2`, `nova-super-conductor.json.j2`, `nova.conf.j2` |
| Handlers (definition order) | Restart nova-super-conductor container; Restart nova-scheduler container; Restart nova-api container |
| Key variables | `enable_nova`, `enable_cells`, `nova_safety_upgrade`, `nova_console` |
| Role dependencies | none |

### Nova (cell level) — role `nova-cell`

| Item | Value |
|---|---|
| Play | nova.yml (`import_playbook` at site.yml:609) |
| Tags | nova, nova-cell(-*) |
| Play host patterns | compute, nova-compute-ironic, nova-conductor, nova-novncproxy, nova-serialproxy, nova-spicehtml5proxy |
| Node types in play (example inventory) | compute, control |
| Node types running its containers | compute, control |
| Containers | `nova_libvirt`, `nova_ssh`, `nova_novncproxy`, `nova_spicehtml5proxy`, `nova_serialproxy`, `nova_conductor`, `nova_compute`, `nova_compute_ironic` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | clone (if) → config-host → config → check-containers → config-nova-fake (if) → flush handlers → wait_discover_computes (if) → post-config |
| Task files | bootstrap.yml, bootstrap_service.yml, bootstrap_upgrade.yml, cell_proxy_loadbalancer.yml, check-containers.yml, check.yml, clone.yml, config-host.yml, config-libvirt-tls.yml, config-nova-fake.yml, config.yml, config_bootstrap.yml, config_validate.yml, copy-certs.yml, create_cells.yml, deploy-containers.yml, deploy.yml, discover_computes.yml, external_ceph.yml, get_cell_settings.yml, libvirt-cleanup.yml, loadbalancer.yml, main.yml, online_data_migrations.yml, post-config.yml, precheck.yml, proxy_loadbalancer.yml, pull.yml, rabbitmq.yml, reconfigure.yml, reload.yml, rolling_upgrade.yml, stop.yml, upgrade.yml, wait_discover_computes.yml |
| Templates | `99-kolla-kvm.rules.j2`, `auth.conf.j2`, `hostnqn.j2`, `libvirt-secret.j2`, `libvirtd.conf.j2`, `nova-cell-bootstrap.json.j2`, `nova-compute-ironic.json.j2`, `nova-compute.json.j2`, `nova-conductor.json.j2`, `nova-libvirt.json.j2`, `nova-novncproxy.json.j2`, `nova-serialproxy.json.j2`, `nova-spicehtml5proxy.json.j2`, `nova-ssh.json.j2`, `nova.conf.d/libvirt.conf.j2`, `nova.conf.j2`, `qemu.conf.j2`, `sasl.conf.j2`, `secret.xml.j2`, `ssh_config.j2`, `sshd_config.j2` |
| Handlers (definition order) | Restart nova-conductor container; Restart nova-novncproxy container; Restart nova-spicehtml5proxy container; Restart nova-serialproxy container; Restart nova-ssh container; Restart nova-libvirt container; Checking libvirt container is ready; Create libvirt SASL user; Reload libvirtd; Restart nova-compute container; Restart nova-compute-ironic container; Restart nova-compute-fake containers; Wait for nova-compute services to update service versions |
| Key variables | `nova_compute_virt_type`, `nova_backend_ceph`, `libvirt_tls`, `libvirt_enable_sasl`, `nova_cell_*_group`, `migration_interface` |
| Role dependencies | none |

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
- [RabbitMQ](rabbitmq.md) — a change of its group membership changes the transport URL everywhere; quorum queues by
  default
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
