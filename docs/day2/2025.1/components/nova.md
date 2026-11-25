---
title: Nova
description: "Where the 2025.1 study covers Nova: the new nova_metadata container, restarts limited to changed containers, unbatchable reconfigure, open points."
tags: [nova, libvirt, reconfigure, serial, limit, one-shot, risk, dependencies, unknowns]
---

# Nova

This page is the starting point for Nova, which is split into two roles: `nova` (API level: `nova_api`, the new
`nova_metadata`, `nova_scheduler` and `nova_super_conductor`, on the control nodes of the example inventory) and
`nova-cell` (cell level: `nova_compute`, `nova_libvirt`, `nova_ssh`, `nova_conductor`, the three console proxies and
`nova_compute_ironic`, on the compute and control nodes) (`nova.yml:1-22`, `roles/nova/defaults/main.yml:2-77`,
`inventory/multinode:18-19`, `inventory/multinode:99-100`, `inventory/multinode:226-252`). The tag `nova` selects both;
`nova-api` does not touch computes and `nova-cell` touches every compute (`nova.yml:103-147`;
[Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)). `nova.yml` is the same file as in 2024.1, and
`site.yml` imports it after the Open vSwitch and OVN plays and before the neutron play (`site.yml:605-669`) [CODE].

**Changed in 2025.1** [CODE]:

- **The metadata API has its own container.** The nova role defines a `nova-metadata` service: container
  `nova_metadata`, group `nova-metadata`, the nova-api image, WSGI module `nova.wsgi.metadata:application`, and the
  HAProxy `nova_metadata` backend (`roles/nova/defaults/main.yml:33-61`). The example inventory adds
  `[nova-metadata:children]` with `nova` (`inventory/multinode:232-233`); a 2024.1 inventory has no such group, and a
  container is deployed only on hosts of its group (`kolla_ansible/filters.py:77-79`). The "Apply role nova" play does
  not list `nova-metadata` among its hosts (`nova.yml:103-108`), so `nova_metadata` runs only where that group overlaps
  `nova-api`, `nova-scheduler` or `nova-super-conductor`. The external metadata frontend is off by default
  (`nova_enable_external_metadata: "no"`, `roles/nova/defaults/main.yml:258`) ([Nova deep dive
  §1](nova-deep-dive.md#1-components-roles-containers-and-placement)).
- **`nova_api` runs under uWSGI** by default (`nova_wsgi_provider: "uwsgi"`, `roles/nova/defaults/main.yml:324`;
  command at `roles/nova/templates/nova-api.json.j2:3`).
- **Restarts follow the changed containers only.** The config tasks of both roles no longer notify, and
  `check-containers.yml` imports `service-check-containers` (`roles/nova/tasks/check-containers.yml:2-3`,
  `roles/nova-cell/tasks/check-containers.yml:2-3`), which notifies `Restart <service> container` for each container
  whose check reported a change. A nova-compute-only change restarts `nova_compute` only, a scheduler-only change
  `nova_scheduler` only ([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code);
  [F1](../reference/findings.md#f1) no longer holds).
- **No rolling `reconfigure` or `upgrade`:** both commands pass `kolla_serial=0` after your own `-e`
  (`kolla_ansible/cli/commands.py:136, :278`), so every Nova play takes all its hosts in one batch. A batched run is
  `kolla-ansible deploy -t nova -e kolla_serial=N`, which runs the same tasks ([F19](../reference/findings.md#f19);
  [Write config first, apply in controlled batches
  §1.2](../operations/controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure)).
- **Two new checks before the cell role runs**, imported first by `roles/nova-cell/tasks/deploy.yml:4`: a libvirt
  version check that fails the play on a downgrade of `nova_libvirt` (tag `nova-libvirt-version-check`), and a check
  that the `nova_libvirt` image contains `kolla_nova_libvirt_start` (tag `nova-libvirt-script-check`); both start
  one-shot containers from the new image, `run_once`, on the first compute
  (`roles/nova-cell/tasks/version-check.yml:2-73`, `roles/nova-cell/tasks/version-check.yml:79-120`).
- **virtlogd now runs inside `nova_libvirt`:** its command is `kolla_nova_libvirt_start`
  (`roles/nova-cell/templates/nova-libvirt.json.j2:2`), and `qemu.conf` sets `stdio_handler = "logd"`; `libvirtd.conf`
  adds `max_workers` and `max_client_requests` (`roles/nova-cell/templates/libvirtd.conf.j2:36-37`,
  `roles/nova-cell/defaults/main.yml:594-595`) ([Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences),
  item 20; [Q22](../troubleshooting/open-questions.md#q22)).
- **Every compute gets a `compute_id` from the Nova API:** the nova-cell `config.yml` lists all hypervisors through
  `kolla_toolbox` on the first conductor, for every compute, also in `genconfig` (`roles/nova-cell/tasks/config.yml:53-110`;
  [F20](../reference/findings.md#f20)).
- **Messaging and catalog:** the queue switches are gone; `use_queue_manager`, `rabbit_quorum_queue` and
  `rabbit_transient_quorum_queue` are always `true` in both `nova.conf` templates
  (`roles/nova-cell/templates/nova.conf.j2:191-206`, `roles/nova/templates/nova.conf.j2:141-157`;
  [F17](../reference/findings.md#f17)); `[cinder] catalog_info` names the `block-storage` service type
  (`roles/nova/templates/nova.conf.j2:67`, `roles/nova-cell/templates/nova.conf.j2:112`); the API-level
  `www_authenticate_uri` points to the public Keystone URL (`roles/nova/templates/nova.conf.j2:114`;
  [Keystone](keystone.md)). These
  change every Nova `nova.conf` at the first 2025.1 run ([Nova deep dive
  §2.3](nova-deep-dive.md#23-configuration-dependencies-inputs-that-change-novas-files)).
- **Ceph:** the libvirt secret usage names become `ceph-ephemeral-nova` and `ceph-persistent-cinder`, and the external
  Ceph tasks no longer notify ([Nova deep dive §5](nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special)).
- **Upgrade:** `roles/nova/tasks/rolling_upgrade.yml` and `roles/nova-cell/tasks/post-config.yml` are gone; the nova
  upgrade runs config, the upgrade checks, the safety stop and check-containers (`roles/nova/tasks/upgrade.yml:1-58`)
  ([Nova deep dive §7](nova-deep-dive.md#7-upgrade-path-specifics)).
- **Still holds in 2025.1:** the ten plays of `nova.yml` with their tags, `serial` from `kolla_serial` and
  `max_fail_percentage` (`nova.yml:29-302`, e.g. `nova.yml:140-144`); the handler order of the cell role, `nova_ssh`
  then `nova_libvirt` then `nova_compute` (`roles/nova-cell/handlers/main.yml:70-158`); the bootstrap containers
  running with `KOLLA_UPGRADE` (`roles/nova/tasks/bootstrap_service.yml:11`,
  `roles/nova-cell/tasks/bootstrap_service.yml:11`).

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the two service cards follow them.

## Where to look

### Operate

- **Scenario (`nova`):** [Reconfigure Nova](../operations/reconfigure-nova.md); batched apply: [Write config first,
  apply in controlled batches
  §2](../operations/controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern)
- **Command (`nova`):** [Reconfigure Nova
  §1.1](../operations/reconfigure-nova.md#11-reconfigure-nova-control-plane-and-computes), a batched run: [Reconfigure
  Nova §1.4](../operations/reconfigure-nova.md#14-a-batched-run-deploy-with-kolla_serial) and [Write config first,
  apply in controlled batches
  §1.2](../operations/controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure)
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
  rolling run on failures with `nova_cell_max_fail_percentage` or `kolla_max_fail_percentage`: [Write config first,
  apply in controlled batches §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)
- **Scenario (`nova-bootstrap`, `nova-reload`, `nova-online-data-migrations` (with their `-api-`/`-cell-` variants),
  `nova-refresh-scheduler-cell-cache`, and the new `nova-libvirt-version-check` and `nova-libvirt-script-check`):** the
  plays themselves: [Nova deep dive §4](nova-deep-dive.md#4-the-nova-plays-step-by-step-ansiblenovayml)
- **Add a compute:** [Add a compute node](../operations/add-a-compute-node.md)

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
- **First 2025.1 run after 2024.1:** [F16](../reference/findings.md#f16) (changed systemd unit text and `ulimits`),
  [F17](../reference/findings.md#f17) (queue settings), [F20](../reference/findings.md#f20) (`compute_id`), and the
  row "First 2025.1 run on a compute deployed by 2024.1" of [Nova deep dive
  §2.4](nova-deep-dive.md#24-operational-dependencies-what-restarts-what)
- **What the tag executes (`nova-bootstrap`, `nova-reload`, `nova-online-data-migrations` (with their `-api-`/`-cell-`
  variants) and `nova-refresh-scheduler-cell-cache`):** [Tags
  §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), one row each; use as narrower play tags: [Tags
  §4](../risk/tags.md#4-practical-consequences)

### Dependencies

- **Dependencies (role `nova`):** [Component dependencies §3](dependencies.md#3-control-plane-services)
- **Dependencies (role `nova-cell`):** [Component dependencies §3](dependencies.md#3-control-plane-services), [Component
  dependencies §5](dependencies.md#5-compute-node-dependency-summary)
- **In depth:** [Nova deep dive §2](nova-deep-dive.md#2-dependency-classification) and [Nova deep dive
  §3](nova-deep-dive.md#3-what-must-be-available-before-nova-can-operate)

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
  `nova-cell`: the API DB and cell0 mapping (`nova-api`/`nova`), RabbitMQ. In 2025.1 the Nova API must also answer for
  every compute, since `config.yml` reads the hypervisor list ([F20](../reference/findings.md#f20)).
- **Before an upgrade from 2024.1:** add the `nova-metadata` group to the inventory (in the example inventory,
  `[nova-metadata:children]` with `nova`), and run `kolla-ansible pull` first: no task of the Nova upgrade pulls
  images, and a restart handler pulls a missing image just before it stops the old container
  (`roles/nova/tasks/upgrade.yml:1-58`, `roles/nova-cell/tasks/upgrade.yml:1-16`,
  `module_utils/kolla_docker_worker.py:364-372`) [CODE]. A `nova_libvirt` image without `kolla_nova_libvirt_start`
  fails the script check ([Nova deep dive §7](nova-deep-dive.md#7-upgrade-path-specifics)).
- [Nova deep dive §3](nova-deep-dive.md#3-what-must-be-available-before-nova-can-operate), "What must be available
  before Nova can operate": what Kolla configures is [CODE]; upstream Nova behaviour is marked [NOT AVAILABLE].
- [Nova deep dive §2.1](nova-deep-dive.md#21-installation-deploy-time-dependencies), installation (deploy-time)
  dependencies: what must work while Kolla runs the nova plays, each with its failure mode.
- [Nova deep dive §2.2](nova-deep-dive.md#22-runtime-dependencies-what-nova-needs-to-operate), runtime dependencies:
  what each Nova component requires at runtime.
- [R1](../risk/risk-register.md#r1), precautions for any config change touching nova-compute: `genconfig` + `diff`, then
  `deploy-containers --limit` in batches, or `deploy -e kolla_serial=N`; drain live migrations first. In 2025.1 a
  nova-compute change restarts `nova_compute` only; `nova_libvirt` restarts when its own files, image or container
  definition changed, as at the first 2025.1 run (`roles/nova-cell/tasks/check-containers.yml:2-3`; [Tags
  §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)) [CODE].
- [R2](../risk/risk-register.md#r2), precautions for enabling or disabling a service that has a logrotate or fluentd
  input entry: treat `enable_*` changes as fleet-wide changes; roll out with `--limit` batches; apply the `common` side
  deliberately with `-t common`. A `-t nova` run does not run the `common` play, which is tagged `common` only
  (`site.yml:88-103`) [CODE].
- [R3](../risk/risk-register.md#r3), precautions for a change of RabbitMQ group membership, password or port: plan as a
  maintenance; batch with `--limit`; verify RabbitMQ cluster health first. The cell transport URLs list every host of
  the RPC and notification groups with user and password (`roles/nova-cell/defaults/main.yml:217-218`) and are written
  into every cell `nova.conf` (`roles/nova-cell/templates/nova.conf.j2:37`,
  `roles/nova-cell/templates/nova.conf.j2:183`) [CODE].
- [R24](../risk/risk-register.md#r24), container stop timeout: the stop goes through the container's systemd unit,
  whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:148`)
  ([F3](../reference/findings.md#f3)). Precautions: drain long operations before restarts; raise
  `docker_graceful_timeout` if needed (changing it changes the unit text, which the next check reports as drift,
  [F16](../reference/findings.md#f16)).
- [Reconfigure Nova §6](../operations/reconfigure-nova.md#6-operational-risks-and-verification), verification: before,
  `kolla-ansible -t nova genconfig` (restarts nothing: `genconfig` runs `config.yml` only, whose tasks no longer
  notify; `kolla_ansible/cli/commands.py:113-125`, `roles/nova-cell/tasks/main.yml:2`), then a diff of
  `/etc/kolla/nova-*/nova.conf` on one controller and one compute, `kolla_set_configs --check` in `nova_compute` on a
  few computes (exit 1 means that container will restart), and no active live migrations. After,
  `openstack compute service list` (all up), the `nova_*` containers' state, `virsh list --all` inside `nova_libvirt`
  on a sample of computes with guest pings, and a `nova-manage cell_v2 list_hosts` count equal to the number of
  computes. `genconfig` still calls the Nova API from the first conductor for every compute
  ([F20](../reference/findings.md#f20)).

### Known limits and open points

- [Q1](../troubleshooting/open-questions.md#q1): "Do running VMs survive a `nova_libvirt` restart or recreate?" Status:
  [NOT AVAILABLE].
- [Q22](../troubleshooting/open-questions.md#q22), new in 2025.1: what happens to the console output of running guests
  when `nova_libvirt`, which now runs virtlogd, restarts. Status: [NOT AVAILABLE].
- [Nova deep dive §5](nova-deep-dive.md#5-nova-libvirt-why-its-restart-is-special), "nova-libvirt: why its restart is
  special": what the code shows about the container is [CODE]: `pid_mode: host` and `cgroupns_mode: host`
  (`roles/nova-cell/defaults/main.yml:10-11`), state on named volumes (`roles/nova-cell/defaults/main.yml:380-394`), a
  start path that is passive towards running guests (kolla `docker/nova/nova-libvirt/extend_start.sh:1-11`), the 60 s
  stop timeout of its systemd unit, and the restart handler (`roles/nova-cell/handlers/main.yml:86-108`). What happens to
  running VMs is [NOT AVAILABLE].
- [Nova deep dive §6](nova-deep-dive.md#6-live-migration-resize-and-consoles), live migration, resize and consoles:
  whether a `nova_libvirt` or `nova_ssh` restart interrupts operations in progress is [NOT AVAILABLE].
- [Nova deep dive §7](nova-deep-dive.md#7-upgrade-path-specifics): with an inventory that lacks `nova-metadata`, the
  exact failure, and whether `nova_metadata` stays stopped after an upgrade with `nova_safety_upgrade`, since the
  reload play does not start it (`roles/nova/tasks/reload_api.yml:5-23`), are [NOT AVAILABLE].
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
  `KOLLA_UPGRADE` (`roles/nova/tasks/bootstrap_service.yml:11`, `roles/nova-cell/tasks/bootstrap_service.yml:11`),
  which runs the schema syncs and exits (kolla `docker/nova/nova-api/extend_start.sh:16-20`,
  `docker/nova/nova-conductor/extend_start.sh:9-12`); the online data migrations run only in the upgrade-only plays
  (`nova.yml:258-302`), and the images' `KOLLA_BOOTSTRAP` branches are not reached from the nova roles.
- [F1](../reference/findings.md#f1), "Loop-notify amplification": **no longer holds in 2025.1** [CODE]. A
  nova-compute-only change restarts `nova_compute` only, a scheduler-only change `nova_scheduler` only ([Tags
  §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)).
- [F3](../reference/findings.md#f3), "`docker_graceful_timeout` and `docker_client_timeout` are ignored": no longer
  holds [CODE]. Both values reach the module through `docker_common_options` (`group_vars/all.yml:151-162`), and the
  stop timeout is written into each container's systemd unit (`module_utils/kolla_systemd_worker.py:33`); for
  `nova_libvirt` this matters only if libvirtd has not exited by then.
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": still holds; `-t nova` starts the one-shot containers
  of the API and cell bootstraps, `map_cell0` and `list_cells` on `control01`, and in 2025.1 also the two version-check
  one-shots on the first compute ([Reconfigure Nova
  §1.1](../operations/reconfigure-nova.md#11-reconfigure-nova-control-plane-and-computes)) [CODE].
- [F6](../reference/findings.md#f6), "Global inputs are rendered into per-host files": `enable_*` flags,
  RabbitMQ/memcached membership, service passwords, the oslo.messaging options and the external FQDN end up in
  compute-side files (e.g. `roles/nova-cell/templates/nova.conf.j2:37`, `roles/nova-cell/templates/nova.conf.j2:191-206`)
  [CODE].
- [F8](../reference/findings.md#f8), "`--limit` does not confine actions": with `deploy --limit` set to a compute host,
  `control01` runs cell discovery and the hypervisor list, delegated to the first conductor, and the version checks
  run on the first compute (`roles/nova-cell/tasks/wait_discover_computes.yml:8-43`,
  `roles/nova-cell/tasks/discover_computes.yml:4-23`, `roles/nova-cell/tasks/config.yml:59-73`,
  `roles/nova-cell/tasks/version-check.yml:20-21`) [CODE].
- [F10](../reference/findings.md#f10), "`kolla_serial` makes `run_once` steps repeat per batch": for the commands that
  accept `kolla_serial` (not `reconfigure` or `upgrade`, [F19](../reference/findings.md#f19)), API DB sync ×3 with
  serial 1 and the three controllers of the `multinode` inventory, the version checks once per nova-cell batch, and
  restarts in host-pattern order, computes before conductors in the nova-cell play (`nova.yml:127-134`) [CODE].
- [F13](../reference/findings.md#f13), "The Nova deploy order": **partly no longer holds** [CODE]. Open vSwitch and OVN
  now come before the nova plays, the neutron play still after them (`site.yml:605-665`, `site.yml:667`,
  `site.yml:669`); [NOT AVAILABLE] whether instances can be scheduled on a new compute before the neutron play
  finishes.
- [F15](../reference/findings.md#f15), "What the bootstrap containers run differs per image": Nova's bootstrap
  containers run with `KOLLA_UPGRADE` (schema sync, no online data migrations outside `upgrade`) [CODE], as in Q14
  above.
- [F16](../reference/findings.md#f16), holds again in 2025.1: the first 2025.1 check of a Nova container whose unit
  2024.1 wrote reports drift, so on a compute `nova_compute`, `nova_libvirt` and `nova_ssh` all restart at that first
  run, each through its own check (`module_utils/kolla_systemd_worker.py:155-168`,
  `module_utils/kolla_container_worker.py:58-65`) [CODE].
- [F17](../reference/findings.md#f17): quorum queues, transient quorum queues and the queue manager are always on; what
  oslo.messaging does with existing classic queues is [NOT AVAILABLE].
- [F20](../reference/findings.md#f20), new in 2025.1: every compute lists all hypervisors through the first conductor;
  the run time and API load with many computes are [NOT AVAILABLE].
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `masakari`, which names
  nova-libvirt: with `libvirt_enable_sasl` (default `true`) the instancemonitor gets an `auth.conf` with the libvirt
  SASL credentials (`roles/masakari/defaults/main.yml:186`, `roles/masakari/templates/masakari-instancemonitor.json.j2:9-15`).
  Its `connection_uri` is still hard-coded `qemu+tcp` (`roles/masakari/templates/masakari-monitors.conf.j2:18`), while
  with `libvirt_tls` libvirtd listens on TLS only (`roles/nova-cell/templates/libvirtd.conf.j2:1-3`). Status: [CODE];
  effect on the instancemonitor [NOT AVAILABLE].
- Risk items whose VM impact refers to R1: [R12](../risk/risk-register.md#r12), changing `openstack_tag` / `*_tag` and
  running `deploy` instead of `upgrade`; [R13](../risk/risk-register.md#r13), a rebuilt image pushed under the same tag;
  [R14](../risk/risk-register.md#r14), a `bootstrap-servers` re-run on a live host: a Docker restart (`restarted` unless
  `docker_systemd_reload`, default `false`; ansible-collection-kolla `roles/docker/handlers/main.yml:10-15`,
  `roles/docker/defaults/main.yml:71`) stops every container, `nova_libvirt` and OVS included [CODE];
  [R15](../risk/risk-register.md#r15), `kolla-ansible stop`, stops the Nova cell containers on the targeted hosts
  through `service-stop` (`roles/nova-cell/tasks/stop.yml:2-6`) [CODE].
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), items 5, 10, 11, 18 and 20: Nova's online data
  migrations never run outside `upgrade` [CODE]; one `chown` per file of `/var/lib/nova` on computes on every
  `COPY_ALWAYS` start (`roles/nova-cell/templates/nova-compute.json.j2:108-112`; kolla
  `docker/base/set_configs.py:403-410`) [CODE]; nova-libvirt's start path is passive, and VM survival is decided on the
  stop path [CODE for the start path; NOT AVAILABLE for survival]; SSH host keys of `nova_ssh` change on every
  recreate, since `/etc/ssh` is on none of its volumes (`roles/nova-cell/defaults/main.yml:395-400`) [CODE]; virtlogd
  lives and dies with `nova_libvirt` [CODE].

## Service card

The rows of the two cards are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py nova nova-cell -->

### Nova (API level) — role `nova`

| Item | Value |
|---|---|
| Play | nova.yml (`import_playbook` at site.yml:667) |
| Tags | nova, nova-api(-*) |
| Play host patterns | nova-api, nova-scheduler, nova-super-conductor |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `nova_api`, `nova_metadata`, `nova_scheduler`, `nova_super_conductor` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | register → config → check-containers → flush handlers |
| Task files | bootstrap.yml, bootstrap_service.yml, bootstrap_upgrade.yml, check-containers.yml, check.yml, clone.yml, config.yml, config_bootstrap.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, loadbalancer.yml, main.yml, map_cell0.yml, online_data_migrations.yml, precheck.yml, pull.yml, reconfigure.yml, refresh_scheduler_cell_cache.yml, register.yml, reload_api.yml, reload_super_conductor.yml, stop.yml, upgrade.yml |
| Templates | `nova-api-bootstrap.json.j2`, `nova-api-wsgi.conf.j2`, `nova-api.json.j2`, `nova-metadata-wsgi.conf.j2`, `nova-metadata.json.j2`, `nova-scheduler.json.j2`, `nova-super-conductor.json.j2`, `nova.conf.j2` |
| Handlers (definition order) | Restart nova-super-conductor container; Restart nova-scheduler container; Restart nova-api container; Restart nova-metadata container |
| Key variables | `enable_nova`, `enable_cells`, `nova_safety_upgrade`, `nova_console` |
| Role dependencies | none |

### Nova (cell level) — role `nova-cell`

| Item | Value |
|---|---|
| Play | nova.yml (`import_playbook` at site.yml:667) |
| Tags | nova, nova-cell(-*) |
| Play host patterns | compute, nova-compute-ironic, nova-conductor, nova-novncproxy, nova-serialproxy, nova-spicehtml5proxy |
| Node types in play (example inventory) | compute, control |
| Node types running its containers | compute, control |
| Containers | `nova_libvirt`, `nova_ssh`, `nova_novncproxy`, `nova_spicehtml5proxy`, `nova_serialproxy`, `nova_conductor`, `nova_compute`, `nova_compute_ironic` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | clone (if) → version-check → config-host → config → check-containers → config-nova-fake (if) → flush handlers → wait_discover_computes (if) |
| Task files | bootstrap.yml, bootstrap_service.yml, bootstrap_upgrade.yml, cell_proxy_loadbalancer.yml, check-containers.yml, check.yml, clone.yml, config-host.yml, config-libvirt-tls.yml, config-nova-fake.yml, config.yml, config_bootstrap.yml, config_validate.yml, copy-certs.yml, create_cells.yml, deploy-containers.yml, deploy.yml, discover_computes.yml, external_ceph.yml, get_cell_settings.yml, libvirt-cleanup.yml, loadbalancer.yml, main.yml, online_data_migrations.yml, precheck.yml, proxy_loadbalancer.yml, pull.yml, rabbitmq.yml, reconfigure.yml, reload.yml, rolling_upgrade.yml, stop.yml, upgrade.yml, version-check.yml, wait_discover_computes.yml |
| Templates | `99-kolla-kvm.rules.j2`, `auth.conf.j2`, `hostnqn.j2`, `libvirt-secret.j2`, `libvirtd.conf.j2`, `multipath.conf.j2`, `nova-cell-bootstrap.json.j2`, `nova-compute-ironic.json.j2`, `nova-compute.json.j2`, `nova-conductor.json.j2`, `nova-libvirt.json.j2`, `nova-novncproxy.json.j2`, `nova-serialproxy.json.j2`, `nova-spicehtml5proxy.json.j2`, `nova-ssh.json.j2`, `nova.conf.d/libvirt.conf.j2`, `nova.conf.j2`, `qemu.conf.j2`, `sasl.conf.j2`, `secret.xml.j2`, `ssh_config.j2`, `sshd_config.j2` |
| Handlers (definition order) | Restart nova-conductor container; Restart nova-novncproxy container; Restart nova-spicehtml5proxy container; Restart nova-serialproxy container; Restart nova-ssh container; Restart nova-libvirt container; Checking libvirt container is ready; Create libvirt SASL user; Reload libvirtd; Restart nova-compute container; Restart nova-compute-ironic container; Restart nova-compute-fake containers; Wait for nova-compute services to update service versions |
| Key variables | `nova_compute_virt_type`, `nova_backend_ceph`, `libvirt_tls`, `libvirt_enable_sasl`, `nova_cell_*_group`, `migration_interface` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Nova deep dive](nova-deep-dive.md) — Nova in depth: the two roles and ten plays, the new `nova_metadata` container,
  the dependencies, what restarts what and the `nova_libvirt` restart
- [Reconfigure Nova](../operations/reconfigure-nova.md) — what `-t nova reconfigure` runs on controllers and on every
  compute, and how to batch it with `deploy`
- [Write config first, apply in controlled batches](../operations/controlled-batches.md) — `genconfig`, then
  `deploy-containers --limit` batch by batch
- [Add a compute node](../operations/add-a-compute-node.md) — what `deploy --limit` touches on the new compute and
  elsewhere
- [Neutron](neutron.md) — its metadata agents now reach the `nova_metadata` container through the internal VIP
- [RabbitMQ](rabbitmq.md) — a change of its group membership changes the transport URL everywhere; quorum queues always
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the eight checks before every production run
- [Components](index.md) — the other component pages
