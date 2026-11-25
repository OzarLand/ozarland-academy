---
title: Open vSwitch
description: Where the 2025.1 study covers Open vSwitch (role openvswitch), from what the tag runs on compute and network nodes to the vswitchd restart risk.
tags: [openvswitch, upgrade, serial, images, risk, dependencies, bugs, unknowns]
---

# Open vSwitch

This page is the starting point for Open vSwitch, the `openvswitch` role: the containers `openvswitch_db` and
`openvswitch_vswitchd`, on the compute and network nodes of the example inventory (`inventory/multinode:105-108`),
selected by the tag `openvswitch`. The play runs only while `enable_ovs_dpdk` is `no`; `ovs-dpdk` has its own play and
tag (`site.yml:605-633`). The risk register item on an `openvswitch_vswitchd` restart or recreate is
[R7](../risk/risk-register.md#r7). The lists below say where the study covers how to operate it, its impact, its
dependencies and the evidence, what to check around a run and what stays open; the service card follows them.

> [!NOTE]
> **Key answers**
>
> - **Start scripts gone, changed in 2025.1:** Kolla-Ansible no longer renders `start-ovs` and `start-ovsdb-server`.
>   Both containers run the daemon directly under kolla's `ovs_wrapper`, with every option in the `command` of
>   `config.json` and an empty `config_files` list (`roles/openvswitch/templates/openvswitch-vswitchd.json.j2:2-3`,
>   `openvswitch-db-server.json.j2:2-3`) [CODE]. The wrapper's stop handler does not reach the daemon
>   ([F22](../reference/findings.md#f22)).
> - **Restart decision, changed in 2025.1:** the config tasks notify nothing; `check-containers.yml` imports
>   `service-check-containers` (`roles/openvswitch/tasks/check-containers.yml:2-3`), which restarts only the container
>   that differs. Post-config still notifies `Restart openvswitch-vswitchd container` on a change of `system-id`,
>   `hostname` or `hw-offload` (`roles/openvswitch/tasks/post-config.yml:3-23`) [CODE].
> - **Bridges and ports, since 2024.1:** set by the `openvswitch_bridge` (`fail_mode: standalone`) and
>   `openvswitch_port` modules inside `kolla_toolbox`; neither task notifies a handler
>   (`roles/openvswitch/tasks/post-config.yml:25-53`) [CODE].
> - **Restart semantics:** same two handlers in the same order (`roles/openvswitch/handlers/main.yml:1-40`), without
>   the `kolla_action != "config"` guard; the play has `serial: kolla_serial`, default `0` (`site.yml:610`), and
>   `reconfigure` and `upgrade` force it to `0` ([F19](../reference/findings.md#f19)) [CODE]. What a restart does to
>   VM traffic is [NOT AVAILABLE].

## Where to look

### Operate

- **Scenario:** [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) (row "Open
  vSwitch"), [Update container images §4](../operations/update-container-images.md#4-risks) (OVS image change)
- **Command:** [Reconfigure Neutron §1.1](../operations/reconfigure-neutron.md#11-neutron)
- [Command quick lookup by tag](../operations/command-quick-lookup.md), row `-t openvswitch reconfigure`: hosts touched
  with the default inventory: network and all computes (the `openvswitch` group, `inventory/multinode:105-108`); can
  restart `openvswitch_db` or `openvswitch_vswitchd`, each only when the check finds it different, and
  `openvswitch_vswitchd` when post-config reports a change (`roles/openvswitch/tasks/check-containers.yml:2-3`,
  `roles/openvswitch/tasks/post-config.yml:22-23`) [CODE].

### Impact and risk

- **What the tag executes (`openvswitch`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table) and
  [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), rows
  `openvswitch`
- **Risks:** [R7](../risk/risk-register.md#r7)

### Dependencies

- **Dependencies:** [Component dependencies §2](dependencies.md#2-infrastructure-components), [Component dependencies
  §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional)

### Evidence

- **Fact sheet:** – (`ovs-dpdk`: [fact sheet A §6](../reference/factsheets/a-infra-lb-ovn.md#6-ovs-dpdk-role))
- **Image side:** [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour) (rows `openvswitch-*`),
  [Kolla images §2.5](../concepts/kolla-images.md#25-the-extend_start-chain)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services); the container module:
  [Repository architecture §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)

### Before and after a run

- **The order inside the role still holds in 2025.1:** config-host, config, check-containers, a flush of the handlers, then
  post-config (`roles/openvswitch/tasks/deploy.yml:2-11`); `reconfigure` imports that file (`reconfigure.yml:2`) and
  `upgrade` lists the same five steps itself (`upgrade.yml:2-11`) [CODE]. The handlers are, in this order,
  `Restart openvswitch-db-server container` (which notifies `Waiting for openvswitch_db service to be ready`, an
  `ovs-vsctl --no-wait show` retried 30 times with a 2 s delay) and `Restart openvswitch-vswitchd container`, both
  `recreate_or_restart_container` (`roles/openvswitch/handlers/main.yml:2-40`) [CODE]. They lost their
  `kolla_action != "config"` guard in 2025.1; `genconfig` runs no check and no post-config, so nothing notifies them
  there. A db restart does not notify the vswitchd handler (`:14-15`).
- **Post-config runs after the flush** (`roles/openvswitch/tasks/deploy.yml:8-11`), so a change it reports notifies `Restart
  openvswitch-vswitchd container` again, and that restart runs at the end of the play [CODE]:
  - **Since 2024.1:** the first task, `Set system-id, hostname and hw-offload`, sets three keys through
    the `openvswitch_db` module in `kolla_toolbox`: `external_ids:system-id` (`openvswitch_system_id`, default
    `ansible_facts.hostname`), the new `external_ids:hostname` (`openvswitch_hostname`, default `ansible_facts.fqdn`)
    and `other_config:hw-offload` (present or absent from `openvswitch_hw_offload`), on the hosts that run
    `openvswitch_vswitchd` (`roles/openvswitch/tasks/post-config.yml:3-23`, `roles/openvswitch/defaults/main.yml:105-107`) [CODE], unchanged in
  2025.1. Whether the module reports *changed* when it adds the new key, or *ok*
    when a value is already set, is [NOT AVAILABLE]: its code is not in the studied sources (the kolla-toolbox image
    installs the `openvswitch.openvswitch` collection, `<3`, kolla `docker/kolla-toolbox/requirements.yml:13-14`).
    Nothing in the container commands sets `hostname` (`roles/openvswitch/templates/openvswitch-db-server.json.j2:2`).
  - **Since 2024.1:** `Ensuring OVS bridge is properly setup` runs the `openvswitch_bridge` module with
    `fail_mode: standalone` for each name of `neutron_bridge_name`, and the new `Ensuring OVS ports are properly setup`
    runs the `openvswitch_port` module for each bridge and interface pair of `neutron_bridge_name` and
    `neutron_external_interface`, both through `kolla_toolbox`, on network hosts and on computes when
    `computes_need_external_bridge` (`roles/openvswitch/tasks/post-config.yml:25-53`) [CODE]. Neither task has a
  `notify`. The image script `kolla_ensure_openvswitch_configured` that 2023.1 called is gone from kolla 2025.1. Whether the modules fail on a missing
    interface, and what setting `fail_mode` does to an existing bridge, is [NOT AVAILABLE].
- **Image changes and upgrade:** an OVS image change makes the check report drift on every `openvswitch` host of the
  batch, and the handlers recreate the containers there; with the default `kolla_serial` of `0` the batch is the whole
  group (`roles/openvswitch/tasks/check-containers.yml:2-3`, `site.yml:605-618`) [CODE]. **Changed in 2025.1:**
  `upgrade` and `reconfigure` always pass `kolla_serial=0` (`kolla_ansible/cli/commands.py:128-141`, `:270-283`;
  [F19](../reference/findings.md#f19)), so `ANSIBLE_SERIAL` no longer batches them; bound the recreated hosts with
  `--limit` batches, or pull the image and apply it with `deploy -e kolla_serial=<n> -t openvswitch`. Whether VM
  networking is interrupted on every compute at the same time is [NOT AVAILABLE] ([Update container images
  §4](../operations/update-container-images.md#4-risks), [R7](../risk/risk-register.md#r7)).
- **First 2025.1 run after an upgrade from 2024.1** [CODE]: the `config.json` of both containers changes (new command,
  no `config_files`), the systemd unit text changed ([F16](../reference/findings.md#f16)), and the image changes with
  the release, so both containers are recreated by the first 2025.1 `upgrade` or `deploy`. Recreating gives them a
  fresh defaults state, so the dropped `start-ovs` entries do not trigger [F21](../reference/findings.md#f21).
- **conf.db at start:** `kolla_start` sources the image's extend_start chain before it runs the command (kolla
  `docker/base/start.sh:21-27`). In `openvswitch-db-server` that chain creates `conf.db` if absent, then runs
  `ovsdb-tool convert` when `ovsdb-tool needs-conversion` answers `yes` (kolla
  `docker/openvswitch/openvswitch-db-server/extend_start.sh:3-10`). **Changed in 2025.1:** no Kolla-Ansible script
  repeats the test afterwards; the command starts `ovsdb-server` on `/var/lib/openvswitch/conf.db` directly, on the
  unix socket and on `ptcp:<ovsdb_port>:127.0.0.1` (`roles/openvswitch/templates/openvswitch-db-server.json.j2:2`)
  [CODE]. What a failed conversion does to the start is [NOT AVAILABLE].
- **Log ownership, since 2024.1:** every OVS container start runs `chown -R openvswitch:openvswitch
  /var/log/kolla/openvswitch` (kolla `docker/openvswitch/openvswitch-base/extend_start.sh:10`), and the db and
  vswitchd images create their log file owned by `openvswitch`
  (kolla `docker/openvswitch/openvswitch-db-server/extend_start.sh:12-15`,
  `docker/openvswitch/openvswitch-vswitchd/extend_start.sh:3-6`) [CODE]. kolla marks the `openvswitch` user "unused"
  (kolla `kolla/common/users.py:280-283`); whether the image has that user is [NOT AVAILABLE] ([Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour), row `openvswitch-base`).
- **Podman only, since 2024.1:** config-host creates `/run/openvswitch` on the host when `kolla_container_engine` is
  `podman` (`roles/openvswitch/tasks/config-host.yml:12-20`); the optional `ovs-vsctl` host wrapper
  (`openvswitch_ovs_vsctl_wrapper_enabled`, default `false`) now execs through `kolla_container_engine`
  (`roles/openvswitch/templates/ovs-vsctl.j2:3`, `roles/openvswitch/tasks/config.yml:20-30`,
  `roles/openvswitch/defaults/main.yml:99`) [CODE].
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `openvswitch`: safe on its own "yes if unchanged"; prerequisite: the `openvswitch` kernel module, loaded and
  persisted by config-host (`roles/openvswitch/tasks/config-host.yml:2-7`) [CODE].
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure):
  `openvswitch` is one of the tags that can restart the containers that Tags §3.1 traces to running VMs [CODE]; what
  those restarts do to running VMs is [NOT AVAILABLE].

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `openvswitch`: post-config
  restarts `openvswitch_vswitchd` when the `openvswitch_db` module reports changed, now for three keys
  (`roles/openvswitch/tasks/post-config.yml:3-23`) [CODE]. Whether it reports changed on an unchanged host: [NOT
  AVAILABLE].
- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `ovs-dpdk`: `pull` imports
  `service-images-pull`, which reads `ovsdpdk_services` through `kolla_role_name: "ovsdpdk"`
  (`roles/ovs-dpdk/tasks/pull.yml:2-3`, `vars/main.yml:4`, `roles/service-images-pull/tasks/main.yml:14`); the NIC
  mapping file is still written once (`gen_config` only if the file is absent,
  `roles/ovs-dpdk/files/ovs-dpdkctl.sh:350-353`). Since 2024.1 the notify is spelled `Wait for dpdk tunnel
  ip`, like the handler (`roles/ovs-dpdk/handlers/main.yml:19, :84`), so a restart of `ovsdpdk_db` reaches it; the
  handler still has no port (`:84-88`), and ansible-core 2.18.20 `wait_for` with neither `port` nor `path` sleeps for
  the whole `timeout`, here 300 s (`lib/ansible/modules/wait_for.py:542-543`) [CODE]. **Changed in 2025.1:** the
  bridge and port mappings now take the physical network names from `neutron_physical_networks`
  (`roles/ovs-dpdk/defaults/main.yml:40-43`). See [fact sheet A
  §6](../reference/factsheets/a-infra-lb-ovn.md#6-ovs-dpdk-role).
- [Q3](../troubleshooting/open-questions.md#q3): "Data-plane loss during an `openvswitch_vswitchd` restart or recreate".
  Status: [NOT AVAILABLE].
- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane), row "`openvswitch_vswitchd` restart
  or recreate": the sources do not establish whether the OpenFlow tables are lost, whether the OVS agent or
  `ovn-controller` reprograms them, and whether all VM traffic on the host is interrupted, and for how long. Same table:
  whether VM network traffic stops under `kolla-ansible stop`.
- [F22](../reference/findings.md#f22) and [What is not
  known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour): **changed in
  2025.1**, both daemons run under `ovs_wrapper`, which traps TERM and QUIT but builds the `ovs-appctl` control path
  from an empty `$1`, so the daemon is not asked to exit before the wrapper does (kolla
  `docker/openvswitch/openvswitch-base/ovs_wrapper.sh:3-19`) [CODE]. How the daemons then end, and whether that
  matters for flows and `conf.db`, is [NOT AVAILABLE] ([Kolla images §2.6](../concepts/kolla-images.md#26-signals-and-pid-1));
  to be confirmed by the community.
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: the OVS images have no one-shot
  branch (no `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` in kolla `docker/openvswitch/*`, grep).
- [F13](../reference/findings.md#f13), "The Nova deploy order" still puts nova-compute before OVS and the Neutron
  agents on new computes (`site.yml:667` imports `nova.yml` before the openvswitch play at `:605`) [CODE]; [NOT
  AVAILABLE] whether instances can be scheduled on such a compute before the later plays finish.
- [fact sheet A §6.8](../reference/factsheets/a-infra-lb-ovn.md#68-operationally-notable), "Operationally notable" for
  the `ovs-dpdk` role (no fact sheet covers `openvswitch`): a restart of `ovsdpdk_db` notifies, among others, `Restart
  ovsdpdk-vswitchd container` (`roles/ovs-dpdk/handlers/main.yml:14-20`) [CODE].
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 13: an `openvswitch_vswitchd` restart
  replaces only the userspace daemon; the kernel module stays loaded and `conf.db`, on the `openvswitch_db` volume,
  keeps bridges and ports (`roles/openvswitch/defaults/main.yml:86`) [CODE]. [NOT AVAILABLE] Whether the OpenFlow
  tables are lost and must be reprogrammed by the OVS agent or `ovn-controller`.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py openvswitch -->

| Item | Value |
|---|---|
| Play | site.yml:605 |
| Tags | openvswitch |
| Play host patterns | openvswitch |
| Node types in play (example inventory) | compute, network |
| Node types running its containers | compute, network |
| Containers | `openvswitch_db`, `openvswitch_vswitchd` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers → flush handlers → post-config |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, main.yml, post-config.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `openvswitch-db-server.json.j2`, `openvswitch-vswitchd.json.j2`, `ovs-vsctl.j2` |
| Handlers (definition order) | Restart openvswitch-db-server container; Waiting for openvswitch_db service to be ready; Restart openvswitch-vswitchd container |
| Key variables | `enable_openvswitch`, `neutron_bridge_name`, `neutron_external_interface`, `computes_need_external_bridge` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure Neutron](../operations/reconfigure-neutron.md) — `-t neutron` does not touch Open vSwitch, which has a
  separate play and tag
- [Update container images](../operations/update-container-images.md) — what an OVS image change recreates, and how to
  batch it
- [Component dependencies §4](dependencies.md#4-networking-components-ml2ovs-default-ml2ovn-optional) — `openvswitch_db`
  and `openvswitch_vswitchd` forward all VM traffic
- [Neutron](neutron.md) — `neutron_openvswitch_agent` programs the OVS flows
- [OVN](ovn.md) — `ovn_controller` programs OVS from the SB DB
- [Components](index.md) — the other component pages
