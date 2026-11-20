---
title: Open vSwitch
description: Where the 2024.1 study covers Open vSwitch (role openvswitch), from what the tag runs on compute and network nodes to the vswitchd restart risk.
tags: [openvswitch, upgrade, serial, images, risk, dependencies, bugs, unknowns]
---

# Open vSwitch

This page is the starting point for Open vSwitch, the `openvswitch` role: the containers `openvswitch_db` and
`openvswitch_vswitchd`, on the compute and network nodes of the example inventory (`inventory/multinode:105-108`),
selected by the tag `openvswitch`. The play runs only while `enable_ovs_dpdk` is `no`; `ovs-dpdk` has its own play and
tag (`site.yml:611-639`). The risk register item on an `openvswitch_vswitchd` restart or recreate is
[R7](../risk/risk-register.md#r7). The lists below say where the study covers how to operate it, its impact, its
dependencies and the evidence, what to check around a run and what stays open; the service card follows them.

> [!NOTE]
> **Key answers**
>
> - **Bridges and ports, changed in 2024.1:** the external bridges and their ports are set by the `openvswitch_bridge`
>   (`fail_mode: standalone`) and `openvswitch_port` modules run inside `kolla_toolbox`, no longer by the image script
>   `kolla_ensure_openvswitch_configured`; neither task notifies a handler
>   (`roles/openvswitch/tasks/post-config.yml:25-53`) [CODE] ([Before and after a run](#before-and-after-a-run)).
> - **New `hostname` key, changed in 2024.1:** post-config also writes `external_ids:hostname` from
>   `ansible_facts.fqdn`, and a change of it, like one of `system-id` or `hw-offload`, notifies `Restart
>   openvswitch-vswitchd container` (`post-config.yml:3-23`, `roles/openvswitch/defaults/main.yml:106`) [CODE].
>   Whether the first 2024.1 run reports it changed, and so restarts `openvswitch_vswitchd`, is [NOT AVAILABLE].
> - **`conf.db` conversion at start, new in the 2024.1 image:** the `openvswitch-db-server` image converts `conf.db`
>   when `ovsdb-tool needs-conversion` says yes, before the Kolla-Ansible start script repeats the same test (kolla
>   `docker/openvswitch/openvswitch-db-server/extend_start.sh:8-10`,
>   `roles/openvswitch/templates/start-ovsdb-server.j2:5-7`) [CODE].
> - **Restart semantics still hold:** same handlers in the same order, now through `kolla_container`
>   (`roles/openvswitch/handlers/main.yml:1-44`); the play has `serial: kolla_serial`, default `0`
>   (`site.yml:616`) [CODE]. What a restart does to VM traffic is [NOT AVAILABLE].

## Where to look

### Operate

- **Scenario:** [Reconfigure Neutron §4](../operations/reconfigure-neutron.md#4-impact-on-networking) (row "Open
  vSwitch"), [Update container images §4](../operations/update-container-images.md#4-risks) (OVS image change)
- **Command:** [Reconfigure Neutron §1.1](../operations/reconfigure-neutron.md#11-neutron)
- [Command quick lookup by tag](../operations/command-quick-lookup.md), row `-t openvswitch reconfigure`: hosts touched
  with the default inventory: network and all computes (the `openvswitch` group, `inventory/multinode:105-108`); can
  restart `openvswitch_db` and `openvswitch_vswitchd` when the check detects drift, and `openvswitch_vswitchd` when
  post-config reports a change (`roles/openvswitch/tasks/check-containers.yml:2-18`, `post-config.yml:22-23`) [CODE].

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

- **The order inside the role still holds:** config-host, config, check-containers, a flush of the handlers, then
  post-config (`roles/openvswitch/tasks/deploy.yml:2-11`); `reconfigure` imports that file (`reconfigure.yml:2`) and
  `upgrade` lists the same five steps itself (`upgrade.yml:2-11`) [CODE]. The handlers are, in this order,
  `Restart openvswitch-db-server container` (which notifies `Waiting for openvswitch_db service to be ready`, an
  `ovs-vsctl --no-wait show` retried 30 times with a 2 s delay) and `Restart openvswitch-vswitchd container`, both
  `recreate_or_restart_container` and both skipped when `kolla_action` is `config`
  (`roles/openvswitch/handlers/main.yml:2-44`) [CODE]. A db restart does not notify the vswitchd handler (`:16-17`).
- **Post-config runs after the flush** (`deploy.yml:8-11`), so a change it reports notifies `Restart
  openvswitch-vswitchd container` again, and that restart runs at the end of the play [CODE]:
  - **Changed in 2024.1:** the first task, renamed `Set system-id, hostname and hw-offload`, sets three keys through
    the `openvswitch_db` module in `kolla_toolbox`: `external_ids:system-id` (`openvswitch_system_id`, default
    `ansible_facts.hostname`), the new `external_ids:hostname` (`openvswitch_hostname`, default `ansible_facts.fqdn`)
    and `other_config:hw-offload` (present or absent from `openvswitch_hw_offload`), on the hosts that run
    `openvswitch_vswitchd` (`post-config.yml:3-23`, `roles/openvswitch/defaults/main.yml:105-107`) [CODE]. 2023.1
    wrote only `system-id` and `hw-offload`. Whether the module reports *changed* when it adds the new key, or *ok*
    when a value is already set, is [NOT AVAILABLE]: its code is not in the studied sources (the kolla-toolbox image
    installs the `openvswitch.openvswitch` collection, `<3`, kolla `docker/kolla-toolbox/requirements.yml:13-14`).
    Nothing in the start scripts sets `hostname` (`roles/openvswitch/templates/start-ovsdb-server.j2:1-11`).
  - **Changed in 2024.1:** `Ensuring OVS bridge is properly setup` runs the `openvswitch_bridge` module with
    `fail_mode: standalone` for each name of `neutron_bridge_name`, and the new `Ensuring OVS ports are properly setup`
    runs the `openvswitch_port` module for each bridge and interface pair of `neutron_bridge_name` and
    `neutron_external_interface`, both through `kolla_toolbox`, on network hosts and on computes when
    `computes_need_external_bridge` (`post-config.yml:25-53`) [CODE]. Neither task has a `notify`. 2023.1 ran
    `docker exec openvswitch_db kolla_ensure_openvswitch_configured`, a script that fails when the interface does not
    exist (kolla `docker/openvswitch/openvswitch-db-server/ovs_ensure_configured.sh:7-10`); the image still ships it
    (`Dockerfile.j2:8`), but no task of `ansible/` calls it any more (grep). Whether the modules fail on a missing
    interface, and what setting `fail_mode` does to an existing bridge, is [NOT AVAILABLE].
- **Image changes and upgrade:** an OVS image change makes `Check openvswitch containers` report drift on every
  `openvswitch` host of the batch, and the handlers recreate the containers there; with the default `kolla_serial` of
  `0` the batch is the whole group (`check-containers.yml:2-18`, `site.yml:611-624`) [CODE]. `kolla-ansible upgrade`
  and `reconfigure` pass `ANSIBLE_SERIAL` as `kolla_serial` (`tools/kolla-ansible:296, :522, :531`), so
  `ANSIBLE_SERIAL=<n> kolla-ansible -t openvswitch upgrade`, or `--limit` batches, bound how many hosts are recreated in
  one batch [CODE]. Whether VM networking is interrupted on every compute at the same time is [NOT AVAILABLE] ([Update
  container images §4](../operations/update-container-images.md#4-risks), [R7](../risk/risk-register.md#r7)).
- **First 2024.1 check after an upgrade from 2023.1:** the check compares the systemd unit too, and its text changed,
  so an `openvswitch_db` or `openvswitch_vswitchd` whose unit 2023.1 wrote, and that no 2024.1 run has recreated or
  restarted yet, is
  restarted by the first 2024.1 check ([F16](../reference/findings.md#f16)) [CODE].
- **conf.db at start, new in the 2024.1 image:** `kolla_start` sources the image's extend_start chain before it runs
  the command (kolla `docker/base/start.sh:18-24`). In `openvswitch-db-server` that chain creates `conf.db` if absent,
  then runs `ovsdb-tool convert` when `ovsdb-tool needs-conversion` answers `yes` (kolla
  `docker/openvswitch/openvswitch-base/extend_start.sh:12`,
  `docker/openvswitch/openvswitch-db-server/Dockerfile.j2:9`, `extend_start.sh:3-10`). Kolla-Ansible's
  `start-ovsdb-server`, unchanged, repeats the test before it runs `ovsdb-server`
  (`roles/openvswitch/templates/start-ovsdb-server.j2:5-11`;
  command `start-ovsdb-server 127.0.0.1`, `openvswitch-db-server.json.j2:2`) [CODE]. What a failed conversion does
  to the start is [NOT AVAILABLE].
- **Log ownership, new in the 2024.1 image:** every OVS container start runs `chown -R openvswitch:openvswitch
  /var/log/kolla/openvswitch` (kolla `docker/openvswitch/openvswitch-base/extend_start.sh:10`), and the db and
  vswitchd images create their log file owned by `openvswitch` (`openvswitch-db-server/extend_start.sh:12-15`,
  `openvswitch-vswitchd/extend_start.sh:3-6`) [CODE]. kolla marks the `openvswitch` user "unused"
  (`kolla/common/users.py:280-283`); whether the image has that user is [NOT AVAILABLE] ([Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour), row `openvswitch-base`).
- **Podman only, new in 2024.1:** config-host creates `/run/openvswitch` on the host when `kolla_container_engine` is
  `podman` (`roles/openvswitch/tasks/config-host.yml:12-20`); the optional `ovs-vsctl` host wrapper
  (`openvswitch_ovs_vsctl_wrapper_enabled`, default `false`) now execs through `kolla_container_engine`
  (`roles/openvswitch/templates/ovs-vsctl.j2:3`, `tasks/config.yml:56-67`, `defaults/main.yml:99`) [CODE].
- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `openvswitch`: safe on its own "yes if unchanged"; prerequisite: the `openvswitch` kernel module, loaded and
  persisted by config-host (`config-host.yml:2-7`) [CODE].
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
  `roles/ovs-dpdk/files/ovs-dpdkctl.sh:350-353`). **Changed in 2024.1:** the notify is now spelled `Wait for dpdk tunnel
  ip`, like the handler (`roles/ovs-dpdk/handlers/main.yml:21, :88`), so a restart of `ovsdpdk_db` reaches it; the
  handler still has no port (`:88-92`), and ansible-core 2.16.20 `wait_for` with neither `port` nor `path` sleeps for
  the whole `timeout`, here 300 s (`modules/wait_for.py:541-542`) [CODE]. See [fact sheet A
  §6](../reference/factsheets/a-infra-lb-ovn.md#6-ovs-dpdk-role).
- [Q3](../troubleshooting/open-questions.md#q3): "Data-plane loss during an `openvswitch_vswitchd` restart or recreate".
  Status: [NOT AVAILABLE].
- [What is not known](../troubleshooting/what-is-not-known.md#network-data-plane), row "`openvswitch_vswitchd` restart
  or recreate": the sources do not establish whether the OpenFlow tables are lost, whether the OVS agent or
  `ovn-controller` reprograms them, and whether all VM traffic on the host is interrupted, and for how long. Same table:
  whether VM network traffic stops under `kolla-ansible stop`.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  whether services started by a shell wrapper that does not `exec` them receive SIGTERM before the container stops is
  [NOT AVAILABLE]; `start-ovs` runs `ovs-vswitchd` and `start-ovsdb-server` runs `ovsdb-server` without `exec`
  (`roles/openvswitch/templates/start-ovs.j2:2`, `start-ovsdb-server.j2:11`) [CODE]. The image's new `ovs_wrapper`,
  which traps TERM and QUIT, is not used by any Kolla-Ansible template (kolla
  `docker/openvswitch/openvswitch-base/ovs_wrapper.sh:3-19`, `Dockerfile.j2:36`; grep of `ansible/`) ([Kolla images
  §2.6](../concepts/kolla-images.md#26-signals-and-pid-1)).
- [Q14](../troubleshooting/open-questions.md#q14), answered from the source [CODE]: the OVS images have no one-shot
  branch (no `KOLLA_BOOTSTRAP`/`KOLLA_UPGRADE` in kolla `docker/openvswitch/*`, grep).
- [F13](../reference/findings.md#f13), "The Nova deploy order" still puts nova-compute before OVS and the Neutron
  agents on new computes (`site.yml:609` imports `nova.yml` before the openvswitch play at `:611`) [CODE]; [NOT
  AVAILABLE] whether instances can be scheduled on such a compute before the later plays finish.
- [fact sheet A §6.8](../reference/factsheets/a-infra-lb-ovn.md#68-operationally-notable), "Operationally notable" for
  the `ovs-dpdk` role (no fact sheet covers `openvswitch`): a restart of `ovsdpdk_db` notifies, among others, `Restart
  ovsdpdk-vswitchd container` (`roles/ovs-dpdk/handlers/main.yml:16-22`) [CODE].
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 13: an `openvswitch_vswitchd` restart
  replaces only the userspace daemon; the kernel module stays loaded and `conf.db`, on the `openvswitch_db` volume,
  keeps bridges and ports (`roles/openvswitch/defaults/main.yml:86`) [CODE]. [NOT AVAILABLE] Whether the OpenFlow
  tables are lost and must be reprogrammed by the OVS agent or `ovn-controller`.

## Service card

The rows of the card are explained in [How to read a service card](index.md#how-to-read-a-service-card).

<!-- BEGIN GENERATED: tools/service_cards.py openvswitch -->

| Item | Value |
|---|---|
| Play | site.yml:611 |
| Tags | openvswitch |
| Play host patterns | openvswitch |
| Node types in play (example inventory) | compute, network |
| Node types running its containers | compute, network |
| Containers | `openvswitch_db`, `openvswitch_vswitchd` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config-host → config → check-containers → flush handlers → post-config |
| Task files | check-containers.yml, check.yml, config-host.yml, config.yml, config_validate.yml, deploy-containers.yml, deploy.yml, main.yml, post-config.yml, precheck.yml, pull.yml, reconfigure.yml, stop.yml, upgrade.yml |
| Templates | `openvswitch-db-server.json.j2`, `openvswitch-vswitchd.json.j2`, `ovs-vsctl.j2`, `start-ovs.j2`, `start-ovsdb-server.j2` |
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
