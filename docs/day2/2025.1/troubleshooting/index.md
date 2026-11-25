---
title: Troubleshooting
description: Index of the surprising behaviours of kolla-ansible 2025.1 runs that the study documents, by symptom, with the section that explains each one.
tags: [tags, handlers, serial, limit, check-mode, kolla-set-configs, one-shot, images, upgrade, pull, podman, haproxy, rabbitmq, ovn, bugs, unknowns, risk]
---

# Troubleshooting

Where to look when a `kolla-ansible` run did something unexpected, or did nothing. Each row of the [symptom
index](#symptom-index) names what an operator sees, restates in one or two sentences what the study says the 2025.1
code does, and links to the section that establishes it. The page also says where to look for one component, what is
already known as a bug or as an open point, and which checks the study names.

<img src="../assets/images/S3-what-is-not-known.webp" width="1536" height="1024" loading="lazy" alt="LUMO and Ilyan lean over a map whose centre is still blank, marked at its edge by a small navy pennant.">

> [!IMPORTANT]
> The study rests only on reading source code: kolla-ansible `2025.1-eom`, the kolla image repository `2025.1-eom`,
> ansible-collection-kolla `2025.1-eom` and the ansible-core 2.18.20 source. Nothing was run against a host, there are
> no timings, and every statement about data-plane or VM impact is [NOT AVAILABLE] ([Limits of this
> study](../reference/method-and-limits.md#limits-of-this-study)). All conclusions come from the 2025.1 implementation.
> Where a row says "no longer", "fixed" or "changed in 2025.1", it keeps a symptom that the 2024.1 code produced and
> says what the 2025.1 code does instead; "new in 2025.1" marks a symptom that the 2024.1 code did not produce. Docker
> is the default engine; the Podman paths were read in the code only. What a lab run has not confirmed is left for the
> community to confirm.
>
> During an incident, the portal can tell what Kolla will do given the inputs: tasks and restarts. What that does to VMs
> and APIs depends on the environment and is mostly [NOT AVAILABLE] in these sources ([Code guarantees and environment
> dependence](../operations/index.md#code-guarantees-and-environment-dependence)).
>
> This page is an index. It adds no diagnosis and no procedure of its own. The detailed 2024.1 rows are in the [2024.1
> troubleshooting index](../../2024.1/troubleshooting/).

## Symptom index

Three mechanisms explain almost every surprise on the operation pages: config drift means a full container stop/start,
never a reload; changed in 2025.1, one shared check step decides the restarts and notifies only the containers that
changed (loop-notify is gone); and global inputs are rendered into per-host files on every host ([Three mechanisms that
explain almost every surprise](../operations/index.md#three-mechanisms-that-explain-almost-every-surprise)).

In the tables, "What the code does" restates what the sections linked under "Read" say, and keeps their evidence labels
([Evidence labels](../start/conventions.md#evidence-labels)). A sentence without a label restates a sentence that
carries none.

### Containers restarted that should not have

| What you see | What the code does | Read |
|---|---|---|
| A container was stopped and started for a config change; nothing was reloaded | A config change is applied only by stopping and starting the container through its systemd unit; `kolla_container` has no reload action. The stop timeout is the 60 s of `docker_graceful_timeout` [CODE]. | [Repository architecture §4.3](../concepts/repository-architecture.md#43-the-config--check--handler-pattern); [R24](../risk/risk-register.md#r24) |
| Every container of a role restarted on a host although only one of them changed | **No longer in 2025.1** [CODE]: the config tasks no longer notify; the shared `service-check-containers` step notifies only the containers it found changed ([F1](../reference/findings.md#f1)). If siblings restarted, each of them drifted: look for a shared input (an image tag, a global flag, a membership change). | [Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code); [Reconfigure Nova §4](../operations/reconfigure-nova.md#4-are-all-compute-nodes-affected-does-nova-compute-restart-on-every-compute) |
| `nova_compute` restarted on every compute after a change meant for the control plane | A change that reaches the compute `nova.conf` (a global flag, a RabbitMQ or memcached membership change, a password) restarts `nova_compute` on every compute; with no loop-notify, `nova_libvirt` and `nova_ssh` restart only if their own files or parameters changed [CODE]. | [Reconfigure Nova §3](../operations/reconfigure-nova.md#3-what-changes-per-type-of-change-code); [R1](../risk/risk-register.md#r1); [Nova deep dive §2.4](../components/nova-deep-dive.md#24-operational-dependencies-what-restarts-what) |
| HAProxy restarted during a run with a service tag such as `-t keystone` | **No longer in 2025.1** [CODE] ([F18](../reference/findings.md#f18)): the `haproxy-config` tasks no longer notify, and the restart comes only from the loadbalancer play's final check (`site.yml:319-324`), which runs with `-t haproxy`, `-t loadbalancer`, `-t keepalived` or no tag. A service tag writes the frontend file and leaves it pending. | [Reconfigure a single service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure); [R8](../risk/risk-register.md#r8); [R29](../risk/risk-register.md#r29) |
| HAProxy was restarted, not reloaded, on all haproxy hosts | Still restart instead of reload [CODE]: the backup hosts first, all at once, then the host that holds the VIP. In 2025.1 the restart can carry frontend changes written earlier by any tagged run or `genconfig`. | [Known bugs and limitations](known-bugs-and-limitations.md) (rows `haproxy`); [HAProxy + Keepalived](../components/haproxy-keepalived.md); [R29](../risk/risk-register.md#r29) |
| `fluentd`, `cron` and `kolla_toolbox` restarted during an unrelated run | Not from a service-tagged run: `common` is its own play, tagged `common` only [CODE]. Enabling a service with a fluentd or logrotate entry changes the common files on every host of the `common` group; the containers restart at the next `-t common` or untagged run. Changed in 2025.1: only the common container whose files changed restarts. | [Apply `common` changes §3](../operations/apply-common-changes.md#3-how-common-actually-reaches-hosts); [R2](../risk/risk-register.md#r2) |
| `neutron_openvswitch_agent` restarted on all computes after an `ml2_conf.ini` override meant for the server | No longer, as in 2023.1 and 2024.1 [CODE]: `ml2_conf.ini` is rendered only for `neutron-server` and `neutron-infoblox-ipam-agent` ([F11](../reference/findings.md#f11)). | [Reconfigure Neutron §3](../operations/reconfigure-neutron.md#3-what-restarts-code); [R5](../risk/risk-register.md#r5) |
| Nova and Neutron containers restarted on all computes after a controller was added, removed or replaced | A `rabbitmq` membership change changes the transport URL everywhere, a `memcached` change the memcache server lists; in the default inventory both follow `control` [CODE]. | [Change control-plane membership §2](../operations/change-control-plane-membership.md#2-change-control-plane-membership-add-or-remove-a-controller); [R3](../risk/risk-register.md#r3); [R4](../risk/risk-register.md#r4) |
| Fleet-wide restarts after an `enable_*` flag changed | A global flag is rendered into per-host files on every host that uses it ([F6](../reference/findings.md#f6)) [CODE]. | [Why a small change creates a large workload](../risk/small-change-large-workload.md); [R2](../risk/risk-register.md#r2) |
| A container restarts on every `deploy`/`reconfigure` | **New in 2025.1** ([F21](../reference/findings.md#f21)) [CODE]: once an entry is dropped from a container's `config.json`, `kolla_set_configs --check` reports drift on every run, because nothing removes the recorded destination from the container's state; it stops only when the container is recreated. | [Known bugs and limitations](known-bugs-and-limitations.md) (rows `kolla images`); [Kolla images §3](../concepts/kolla-images.md#3-kolla_set_configs---check-what-it-compares-and-its-exit-codes) |
| A container restarted on a run where nothing was changed | A restart needs drift: a missing container, a compared parameter, a systemd unit text or a `kolla_set_configs --check` change ([Drift](../operations/index.md#drift)) [CODE]. [NOT AVAILABLE] Whether, on an unchanged cloud, every check reports ok. | [Repository architecture §4.3](../concepts/repository-architecture.md#43-the-config--check--handler-pattern); [What is not known, "Predicting a run"](what-is-not-known.md#predicting-a-run) |
| The first `deploy` or `reconfigure` after the upgrade restarted containers whose config had not changed | **Holds again in 2025.1** ([F16](../reference/findings.md#f16)) [CODE]: the unit text changed (`PartOf=kolla.target`), and with Docker outside the Red Hat family the default `ulimits` changed. A service that `kolla-ansible upgrade` has not reached also moves to its 2025.1 image. | [Predict and inspect a run §2](../operations/predict-a-run.md#2-the-first-20251-run-on-a-cloud-deployed-by-20241); [Pre-execution checklist §2](../operations/pre-execution-checklist.md#2-first-20251-run-on-a-cloud-deployed-by-20241); [R26](../risk/risk-register.md#r26) |
| `ovn_controller` restarted on every chassis on the first 2025.1 run | **New in 2025.1** [CODE]: the Southbound relays are on by default, so the chassis are pointed at the relays and their config changes. | [R33](../risk/risk-register.md#r33); [OVN](../components/ovn.md) |
| A container that was stopped, or that keeps exiting, was restarted by the run | With Docker, exit code 137 of the check or a client error is drift; with Podman a container that is not `running` is drift before any exec, and other codes fail the task [CODE]. | [Drift](../operations/index.md#drift); [Kolla images §3.3](../concepts/kolla-images.md#33-exit-codes) |
| A config change written earlier by `genconfig`, or by hand, was applied by a later, unrelated run | Any later run that reaches those hosts and compares the containers applies the pending drift [CODE]. | [Controlled batches §2](../operations/controlled-batches.md#2-separate-write-config-from-apply-recommended-pattern) (caveats) |
| A container picked up new config after a Docker restart or a reboot, without a Kolla run | Under `COPY_ALWAYS` the files are copied at every container start [CODE]. | [Kolla images §3.5](../concepts/kolla-images.md#35-what-a-restart-applies); [fact sheet E §2](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#2-docker-daemon-configuration-and-restart-the-exact-trigger) |
| `genconfig` restarted a container | **Changed in 2025.1** [CODE]: `genconfig` compares no container; only two config tasks still notify, for `placement-api` with `placement_wsgi_provider: apache` and for `cinder-volume` with Huawei XML files. | [Execution flow §4](../concepts/deployment-execution-flow.md#4-action-matrix-what-each-kolla_action-does) (row `genconfig`) |
| `openvswitch_vswitchd` restarted, or Open vSwitch did not stop cleanly | **New in 2025.1** ([F22](../reference/findings.md#f22)) [CODE]: `ovs_wrapper`'s TERM handler does not stop the daemons cleanly. | [Known bugs and limitations](known-bugs-and-limitations.md) (rows `openvswitch`); [R7](../risk/risk-register.md#r7); [Open vSwitch](../components/openvswitch.md) |
| `mariadb_clustercheck` disappeared after the upgrade | **Changed in 2025.1** [CODE]: ProxySQL is on by default, clustercheck follows the HAProxy loadbalancer only, and the upgrade removes the container. | [MariaDB/Galera](../components/mariadb.md); [R9](../risk/risk-register.md#r9) |
| All DB nodes or all RabbitMQ brokers restarted one by one | MariaDB and RabbitMQ restarts run in their own plays, `serial: "33%"`; each RabbitMQ broker is drained first [CODE]. | [fact sheet B §1.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#18-operationally-notable-behaviour-risks-and-oddities); [fact sheet B §2.8](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#28-operationally-notable-behaviour-risks-and-oddities); [R9](../risk/risk-register.md#r9) |
| `keepalived` restarted after the haproxy group was reordered | keepalived `priority` follows the host's index in the group: reordering changes `keepalived.conf` and moves the VIP [CODE]. | [R22](../risk/risk-register.md#r22); [HAProxy + Keepalived](../components/haproxy-keepalived.md) |
| The Docker daemon restarted during `bootstrap-servers` | `Restart docker` is a handler of ansible-collection-kolla, flushed at the same moment on every host of the batch, all hosts by default [CODE]. | [fact sheet E §2](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#2-docker-daemon-configuration-and-restart-the-exact-trigger); [R14](../risk/risk-register.md#r14) |
| A service restarted on every host at once instead of one host at a time | Without batching, a service restarts on every host of the play at once. Changed in 2025.1: `reconfigure` and `upgrade` cannot be batched ([F19](../reference/findings.md#f19)); `deploy -e kolla_serial=N` can [CODE]. | [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order); [Controlled batches §1.2](../operations/controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure); [R32](../risk/risk-register.md#r32) |
| Containers restarted in an order that is not the order of the changes | Within a role, restart order is handler definition order [CODE]. | [Execution flow §7](../concepts/deployment-execution-flow.md#7-dependencies-introduced-by-handlers); [Tags §5](../risk/tags.md#5-role--handler-map-core-services) |

### Nothing happened, or the change was not applied

| What you see | What the code does | Read |
|---|---|---|
| A HAProxy frontend change made with `-t <svc>` is not live | **New in 2025.1** ([F18](../reference/findings.md#f18)) [CODE]: the frontend file is written, HAProxy is not restarted; run `-t haproxy` (or an untagged run). | [Reconfigure a single service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure); [R29](../risk/risk-register.md#r29) |
| `-t common reconfigure` changed nothing | Does not hold in 2025.1 [CODE] ([F2](../reference/findings.md#f2)): the tag runs the common play. Check that the change is in the rendered files. | [Apply `common` changes §2](../operations/apply-common-changes.md#2-the-tag-does-nothing); [R25](../risk/risk-register.md#r25) |
| `kolla_set_configs --check` returns 0 after a change to a container's permissions | Narrower in 2025.1 ([F14](../reference/findings.md#f14)) [CODE]: the check now compares the command and the list of files, but a change confined to `permissions` is still not detected. | [Kolla images §3.2](../concepts/kolla-images.md#32-what-is-still-not-compared) |
| A file removed from the config is still in the container | Removal waits for a restart, with exceptions (glob sources, `COPY_ONCE`) [CODE]; in 2025.1 the dropped entry itself counts as drift ([F21](../reference/findings.md#f21)). | [Kolla images §3.5](../concepts/kolla-images.md#35-what-a-restart-applies) |
| The HAProxy frontend of a disabled service is still loaded | Stale `services.d` files are never removed [CODE]; the only removal is `mariadb.cfg` when ProxySQL is enabled, now the default. | [Known bugs and limitations](known-bugs-and-limitations.md) (rows `haproxy`) |
| Swift is still running after the upgrade, or its frontend and Keystone service are still there | **New in 2025.1** [CODE]: the role is removed and no task stops or removes the Swift containers, frontends or Keystone entries of a 2024.1 cloud. | [Swift](../components/swift.md); [Known bugs and limitations](known-bugs-and-limitations.md) (row `swift`) |
| A changed `heat_domain_admin_password` or `rabbitmq_cluster_cookie` was not applied | Both still hold [CODE]: the Heat domain admin is created only when absent; the Erlang cookie is written only by the bootstrap container. | [Known bugs and limitations](known-bugs-and-limitations.md) (rows `heat`, `rabbitmq`) |
| An expired certificate was not renewed by the certificates playbook | Test CA only; every step is `creates:`-guarded (still) [CODE]. | [Known bugs and limitations](known-bugs-and-limitations.md) (row `certificates`) |
| `/etc/hosts` on the existing hosts does not list a new compute after a run with `--limit` | `bootstrap-servers` writes the block only on the hosts the run reaches [CODE]. | [Add a compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node); [R23](../risk/risk-register.md#r23); [fact sheet E §3](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#3-etchosts-generation) |
| The `nova-reload` tags did nothing | The reload plays act only when `kolla_action == upgrade` [CODE]. | [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) |
| A service tag did not touch MariaDB, RabbitMQ, memcached or Open vSwitch | A service tag never runs those plays [CODE]. | [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) |

### The run failed or a task failed

| What you see | What the code does | Read |
|---|---|---|
| The check-containers task failed; `kolla_set_configs --check` exit code 2, or with Podman "Failed to compare container configuration" | Codes other than 0 and 1 (and 137 with Docker) fail the task [CODE]. | [Drift](../operations/index.md#drift); [Kolla images §3.3](../concepts/kolla-images.md#33-exit-codes) |
| `prechecks` or `deploy` failed on RabbitMQ queue types | **Changed in 2025.1** ([F17](../reference/findings.md#f17)) [CODE]: quorum queues are the only choice; classic queues must be migrated first. | [R27](../risk/risk-register.md#r27); [RabbitMQ](../components/rabbitmq.md) |
| The RabbitMQ version check failed and told you to run `kolla-ansible rabbitmq-upgrade` | **New in 2025.1** [CODE]: the message names a command that the 2025.1 CLI no longer has. | [R28](../risk/risk-register.md#r28); [Known bugs and limitations](known-bugs-and-limitations.md) (rows `rabbitmq`) |
| `prechecks` failed on the Octavia jobboard | With the amphora provider the jobboard is on by default and needs Redis or Valkey [CODE]. | [R30](../risk/risk-register.md#r30); [Octavia](../components/octavia.md) |
| The ML2 plugin check failed or skipped with OVN | **New in 2025.1** [CODE]: the check reads a volume result that the module no longer returns. | [Known bugs and limitations](known-bugs-and-limitations.md) (rows `neutron`) |
| The nova-cell config step is slow or fails on a large fleet | **New in 2025.1** ([F20](../reference/findings.md#f20)) [CODE]: every compute lists all hypervisors through the first conductor. | [Known bugs and limitations](known-bugs-and-limitations.md) (row `nova`); [Compute scaling and performance](../concepts/compute-scaling-and-performance.md) |
| A batch with failed hosts did not stop the run | Every play sets `max_fail_percentage`, default 100, which stops nothing early [CODE]. | [Controlled batches §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage) |
| A run with `--limit` failed because a host outside the limit is unreachable | Delegated steps and fact gathering reach hosts outside the limit ([F8](../reference/findings.md#f8), [F9](../reference/findings.md#f9)) [CODE]. | [R23](../risk/risk-register.md#r23) |
| A bootstrap or registration task failed on the first host of a group | Those tasks run once, on the first host [CODE]. | [Tags §2.5](../risk/tags.md#25-run_once-with-serial-code) |

### The run is slow

| What you see | What the code does | Read |
|---|---|---|
| A run with `--limit` spends a long time gathering facts | All hosts' facts are gathered by default ([F9](../reference/findings.md#f9)); the list can now be narrowed [CODE]. | [Compute scaling and performance](../concepts/compute-scaling-and-performance.md); [R23](../risk/risk-register.md#r23) |
| A run with no change is still slow on a large fleet, or slower with `kolla_serial` | Every run executes its tasks on every host; `run_once` steps repeat per batch ([F10](../reference/findings.md#f10)) [CODE]. | [Compute scaling and performance](../concepts/compute-scaling-and-performance.md) |
| How long a run should take | No timings are given [NOT AVAILABLE]. | [What is not known, "Timings, counts and scale"](what-is-not-known.md#timings-counts-and-scale) |

### `--limit` seems ignored

| What you see | What the code does | Read |
|---|---|---|
| Tasks ran on a controller although `--limit` named only a compute | `--limit` does not confine delegated and `run_once` steps ([F8](../reference/findings.md#f8)) [CODE]. | [R23](../risk/risk-register.md#r23); [Add a compute node §2](../operations/add-a-compute-node.md#2-add-a-compute-node) |

### Scope surprises: hosts or services touched outside what was asked

| What you see | What the code does | Read |
|---|---|---|
| DB-sync containers and Keystone registration ran on a `reconfigure` | `reconfigure` = `deploy` ([F5](../reference/findings.md#f5)) [CODE]. | [Execution flow §6](../concepts/deployment-execution-flow.md#6-initial-deployment-vs-reconfiguration-what-actually-differs) |
| `migrate-container-engine` touched every container | **New in 2025.1** [CODE]: it moves every container to the other engine and asks for no confirmation. | [R31](../risk/risk-register.md#r31) |
| `destroy` removed an inventory kept under `/etc/kolla` | **Changed in 2025.1** [CODE]: the kept entries are Ansible's absolute inventory sources, so an inventory in a subdirectory is removed. | [Known bugs and limitations](known-bugs-and-limitations.md) (row `destroy`); [R16](../risk/risk-register.md#r16) |
| A tag ran tasks on every compute | `nova`, `nova-cell`, `neutron`, `openvswitch` and `ovn` reach every compute [CODE]. | [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) |
| After the inventory was reordered: keepalived priorities, restart waves, the bootstrap host | Several choices follow the order of a group [CODE]. | [R22](../risk/risk-register.md#r22) |

### Images

| What you see | What the code does | Read |
|---|---|---|
| `deploy` or `reconfigure` did not pick up a rebuilt image pushed under the same tag | Still holds ([F4](../reference/findings.md#f4)) [CODE]: pull first. | [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code); [R13](../risk/risk-register.md#r13) |
| A new `openstack_tag` applied with `deploy` recreated every container | An image change recreates the container, on every host of the play at once [CODE]. | [R12](../risk/risk-register.md#r12) |
| `pull` did not change the running containers | `pull` never changes running containers [CODE]. | [Update container images §2](../operations/update-container-images.md#2-how-image-pulling-and-recreation-work-code); [R11](../risk/risk-register.md#r11) |
| `genconfig` pulled an image | **No longer in 2025.1** [CODE]: the fluentd image tasks of the common config step are gone. | [Apply `common` changes §1.1](../operations/apply-common-changes.md#11-apply-common-changes-fluentd-cron-kolla_toolbox) |
| `prune-images` did not remove the images of the previous release | Unchanged from 2024.1: with Docker it prunes images filtered on the `kolla_version` label [CODE]; whether only dangling images are removed is [NOT AVAILABLE]. | [R17](../risk/risk-register.md#r17); [fact sheet E §7](../reference/factsheets/e-host-bootstrap-ops-playbooks.md#7-prune-images-ansibleprune-imagesyml-role-prune-images) |

### Settings that are ignored

| What you see | What the code does | Read |
|---|---|---|
| `-e kolla_serial=N` is ignored by `reconfigure` and `upgrade` | **New in 2025.1** ([F19](../reference/findings.md#f19)) [CODE]: the CLI adds `kolla_serial=0` after your options. `ANSIBLE_SERIAL` no longer exists. | [Controlled batches §1.2](../operations/controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure); [R32](../risk/risk-register.md#r32) |
| The cyborg play is not batched by `kolla_serial` | It still reads `serial` [CODE]. | [Known bugs and limitations](known-bugs-and-limitations.md) (rows `site.yml`) |
| `docker_graceful_timeout` (60 s) is ignored | Does not hold ([F3](../reference/findings.md#f3)) [CODE]. | [R24](../risk/risk-register.md#r24) |

### Listings, check mode and prechecks

| What you see | What the code does | Read |
|---|---|---|
| `--list-tasks` shows only `include_tasks` placeholders; the CLI cannot pass `--list-tags` or `--list-hosts` | [F7](../reference/findings.md#f7) still holds; **changed in 2025.1**, the CLI keeps only `--list-tasks`; call `ansible-playbook` for the others [CODE]. | [Predict and inspect a run §1](../operations/predict-a-run.md#1-commands-and-what-they-show); [Tags §2.6](../risk/tags.md#26---list-tasks-is-not-usable-for-kolla-code) |
| A `--check --diff` run skipped the `kolla_container` tasks | Modules without check-mode support are skipped [CODE]. | [Predict and inspect a run §1](../operations/predict-a-run.md#1-commands-and-what-they-show) |
| The tag name did not predict what the run did | A tag name does not describe the work a run performs [CODE]. | [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) |

### Batching with `serial`

| What you see | What the code does | Read |
|---|---|---|
| With `kolla_serial`, the DB sync or Keystone registration ran several times | `run_once` steps repeat per batch ([F10](../reference/findings.md#f10)) [CODE]. | [Tags §2.5](../risk/tags.md#25-run_once-with-serial-code); [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order) |
| A fully failed batch ended the playbook | ansible-core ends the playbook when every host of a batch failed [CODE]. | [Execution flow §5](../concepts/deployment-execution-flow.md#5-batching-serial-and-its-interaction-with-order) |

### Upgrades and database migrations

| What you see | What the code does | Read |
|---|---|---|
| A schema migration ran during a `reconfigure` | A reconfigure with a new image tag runs the bootstrap (DB sync) containers [CODE]. | [Execution flow §6](../concepts/deployment-execution-flow.md#6-initial-deployment-vs-reconfiguration-what-actually-differs); [R12](../risk/risk-register.md#r12) |
| The RabbitMQ `upgrade` was refused | The version check refuses some version steps ([R28](../risk/risk-register.md#r28)) [CODE]. | [RabbitMQ](../components/rabbitmq.md) |
| Anything else about an upgrade | See the list of points the sources do not establish. | [What is not known, "Upgrades and database migrations"](what-is-not-known.md#upgrades-and-database-migrations) |

### Services, VMs and traffic during and after a restart

| What you see | What the code does | Read |
|---|---|---|
| Running VMs after a `nova_libvirt` restart or recreate | [NOT AVAILABLE] | [What is not known, "Running VMs and compute hosts"](what-is-not-known.md#running-vms-and-compute-hosts); [Q1](open-questions.md#q1) |
| VM network traffic after a restart of the OVS agent, of `openvswitch_vswitchd` or of the L3 agent | [NOT AVAILABLE]; the L3 wrapper still runs `neutron-netns-cleanup` with agent HA ([F12](../reference/findings.md#f12)) [CODE]. | [What is not known, "Network data plane"](what-is-not-known.md#network-data-plane); [R6](../risk/risk-register.md#r6); [R7](../risk/risk-register.md#r7) |
| APIs, DB traffic and the VIP while HAProxy, MariaDB, RabbitMQ or Keystone restart | Restart sequences are in the code; their effect is [NOT AVAILABLE]. | [What is not known, "Control plane"](what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat) |

### Other bugs and oddities, by service

The full list, by area, is [Known bugs and limitations](known-bugs-and-limitations.md). For any other role, the fact
sheets list the notable behaviour; the component pages say, item by item, which of them still hold in 2025.1.

## Investigate a component

Each of the component pages says where the study covers the component and ends with its service card ([How to read a
component page](../components/index.md#how-to-read-a-component-page)).

| Component | Role and tag | Risks |
|---|---|---|
| [Keystone](../components/keystone.md) | role `keystone`, tag `keystone` | [R19](../risk/risk-register.md#r19), [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24) |
| [Glance](../components/glance.md) | role `glance`, tag `glance` | [R20](../risk/risk-register.md#r20), [R21](../risk/risk-register.md#r21) |
| [Placement](../components/placement.md) | role `placement`, tag `placement` | [R8](../risk/risk-register.md#r8) |
| [Nova](../components/nova.md) | roles `nova` and `nova-cell` | [R1](../risk/risk-register.md#r1), [R2](../risk/risk-register.md#r2), [R3](../risk/risk-register.md#r3) |
| [Neutron](../components/neutron.md) | role `neutron`, tag `neutron` | [R5](../risk/risk-register.md#r5), [R6](../risk/risk-register.md#r6), [R7](../risk/risk-register.md#r7) |
| [Cinder](../components/cinder.md) | role `cinder`, tag `cinder` | [R8](../risk/risk-register.md#r8) |
| [Horizon](../components/horizon.md) | role `horizon`, tag `horizon` | [R8](../risk/risk-register.md#r8) |
| [Heat](../components/heat.md) | role `heat`, tag `heat` | [R8](../risk/risk-register.md#r8) |
| [Barbican](../components/barbican.md) | role `barbican`, tag `barbican` | – |
| [Octavia](../components/octavia.md) | role `octavia`, tag `octavia` | [R30](../risk/risk-register.md#r30) |
| [Swift](../components/swift.md) | removed in 2025.1 | [R21](../risk/risk-register.md#r21) |
| [Manila](../components/manila.md) | role `manila`, tag `manila` | – |
| [MariaDB/Galera](../components/mariadb.md) | role `mariadb`, tag `mariadb` | [R9](../risk/risk-register.md#r9), [R18](../risk/risk-register.md#r18) |
| [RabbitMQ](../components/rabbitmq.md) | role `rabbitmq`, tag `rabbitmq` | [R3](../risk/risk-register.md#r3), [R10](../risk/risk-register.md#r10), [R27](../risk/risk-register.md#r27), [R28](../risk/risk-register.md#r28) |
| [Memcached](../components/memcached.md) | role `memcached`, tags `memcache`, `memcached` | [R4](../risk/risk-register.md#r4) |
| [HAProxy + Keepalived](../components/haproxy-keepalived.md) | role `loadbalancer`; tags `haproxy`, `keepalived`, `loadbalancer` | [R8](../risk/risk-register.md#r8), [R29](../risk/risk-register.md#r29) |
| [Common: fluentd, cron, kolla_toolbox](../components/common.md) | role `common`, tag `common` | [R2](../risk/risk-register.md#r2) |
| [Open vSwitch](../components/openvswitch.md) | role `openvswitch`, tag `openvswitch` | [R7](../risk/risk-register.md#r7) |
| [OVN](../components/ovn.md) | roles `ovn-controller` and `ovn-db` | [R33](../risk/risk-register.md#r33) |
| [Chrony](../components/chrony.md) | no role, play or tag | – |
| [iscsid / tgtd](../components/iscsi.md) | role `iscsi`, tag `iscsi` | – |

Two more pages cut across the components: [Component dependencies](../components/dependencies.md) and [Nova deep
dive](../components/nova-deep-dive.md).

### Cases the study does not solve

The study does not diagnose a runtime failure of OpenStack, such as a failed VM deployment: no container or VM behaviour
is used as evidence. For a failed boot, a compute that gets no instances, an instance without network, a failed live
migration, an authentication failure, a volume that cannot be attached or a Galera cluster that is down, start from
[Nova deep dive §3](../components/nova-deep-dive.md#3-what-must-be-available-before-nova-can-operate), [Component
dependencies](../components/dependencies.md) and [Database operations](../operations/database-operations.md), and from
[What is not known](what-is-not-known.md) for what the sources do not establish.

## Is it known?

- [Known bugs and limitations](known-bugs-and-limitations.md) — the limitations and bugs found in `2025.1-eom`, by
  area, with their status against 2024.1
- [Findings](../reference/findings.md) — the headline findings [F1–F22](../reference/findings.md#f1); [F18 to
  F22](../reference/findings.md#f18) are new in 2025.1, and [F1](../reference/findings.md#f1) (loop-notify) no longer
  holds
- [Open questions](open-questions.md) — [Q1–Q21](open-questions.md#q1), with their status in 2025.1
- [What is not known](what-is-not-known.md) — what the sources do not establish, grouped by topic
- [Fact sheet corrections](../reference/factsheets/index.md#verification-and-errata) — the corrections to the Ussuri
  fact sheets
- [Risk register](../risk/risk-register.md) — the risks [R1–R33](../risk/risk-register.md#r1), with their status in
  2025.1

## Checks the corpus names

The checks that the study names before and after a run, as links. This page adds none.

| Page | What it lists |
|---|---|
| [Pre-execution checklist](../operations/pre-execution-checklist.md) | Know the diff, health gates, workload gates, scope and rollback material, before every production run. |
| [Pre-execution checklist §2](../operations/pre-execution-checklist.md#2-first-20251-run-on-a-cloud-deployed-by-20241) | What to settle and check before the first 2025.1 run on a cloud deployed by 2024.1. |
| [Predict and inspect a run](../operations/predict-a-run.md) | The commands that show what a run would target, render and restart. |
| [Reconfigure a single service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure) | Verification before and after a service run. |
| [Reconfigure Nova §6](../operations/reconfigure-nova.md#6-operational-risks-and-verification) | Verification before and after a Nova run. |
| [Reconfigure Neutron §5](../operations/reconfigure-neutron.md#5-risks-and-verification) | Verification before and after a Neutron run. |
| [Apply `common` changes §4](../operations/apply-common-changes.md#4-sequence-risks-and-verification) | Verification before and after a common run. |
| [Update container images §5](../operations/update-container-images.md#5-verification) | Verification of a pull and of the running image. |
| [Risk register](../risk/risk-register.md) | The precautions of each risk. |
| [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) | Per tag: whether it is safe on its own, and its prerequisites. |

## Related

- [Find it fast](../start/find-it-fast.md) — typical operator questions and the section that answers each one
- [Ten things to know before a production run](../start/ten-things-to-know.md) — the mechanisms behind most rows of the
  symptom index
- [Operations](../operations/index.md) — the operation pages, with their commands, impact classes and risks
- [Tags](../risk/tags.md) — what a tag really executes, on which hosts, and which containers can restart
- [Risk register](../risk/risk-register.md) — the risks, with their likelihood, severity and precautions
- [Method and limits of the study](../reference/method-and-limits.md) — how the sources were read, and what a
  source-only study cannot establish
- [2024.1 troubleshooting index](../../2024.1/troubleshooting/) — the same index for the previous release
