---
title: Apply common changes (fluentd, cron, kolla_toolbox)
description: Why -t common reconfigure reconfigures no host, how common reaches hosts through another play such as -t chrony, what restarts and how to verify.
tags: [fluentd, cron, kolla-toolbox, chrony, reconfigure, tags, loop-notify, kolla-set-configs]
impact: [restarts-on-drift]
---

# Apply `common` changes (fluentd, cron, kolla_toolbox)

How to push changes of the `common` role (fluentd, cron, kolla_toolbox) to hosts. `-t common reconfigure` reconfigures
no host, so the commands use a play that reaches the hosts first, such as `-t chrony reconfigure`.

The page uses the definition of [drift](index.md#drift) of the Operations hub.

> [!NOTE]
> **Key answers**
>
> - **`-t common reconfigure` reconfigures no host** [CODE] ([§2](#2-the-tag-does-nothing)). `common` reaches a host in
>   the first matching play of a run; `-t chrony` is the recommended way to push its changes
>   ([§3](#3-how-common-actually-reaches-hosts)).

> [!WARNING]
> [R2](../risk/risk-register.md#r2): fleet-wide restarts after an `enable_*` change — see "Hidden coupling" in
> [§3](#3-how-common-actually-reaches-hosts).

## 1. Commands

### 1.1 Apply `common` changes (fluentd, cron, kolla_toolbox)

```bash
# -t common is a NO-OP in Ussuri (Tags §2.1). Use a play that reaches the hosts first:
kolla-ansible -i multinode -t chrony reconfigure            # chrony play includes all hosts by default
kolla-ansible -i multinode -t chrony reconfigure --limit 'compute[0:49]'
```

- This also reconfigures chrony on those hosts.
- If `enable_chrony` is `no`, use any service tag whose play covers the hosts, e.g. `-t openvswitch` for network and
  compute hosts.

## 2. The tag does nothing

`kolla-ansible -t common reconfigure` executes, per play, only the `include_tasks` statement and the `set_fact`. The
included `reconfigure.yml` tasks are filtered out because they do not carry the `common` tag [CODE]
(`roles/common/tasks/main.yml:1-10`; tag semantics in [Tags
§2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)). **No host is reconfigured.**

## 3. How `common` actually reaches hosts

- **Where it runs:** the `common` role (fluentd, cron, kolla_toolbox) runs on a host during the **first** play of the
  run that includes that host and whose tag matches, then never again in that run (`common_run`).

  | Command | Hosts that get `common` |
  |---|---|
  | `reconfigure` (no tag) | all hosts, in the chrony play (first play; chrony is enabled by default on all physical groups) |
  | `-t nova` | all nova hosts including every compute [CODE] (`nova.yml:117-135`, `roles/nova-cell/meta/main.yml:3`) |
  | `-t neutron` | network + compute + neutron-server hosts |
  | `-t chrony` | all hosts (recommended way to push `common` changes) |
  | `-t haproxy` | haproxy hosts |
- **What it can change:**
  - `td-agent.conf` (fluentd inputs/outputs). It is built from the `enable_*` flags of the services in
    `fluentd_input_openstack_services`, `enable_swift`/`enable_haproxy` (local outputs on swift and haproxy hosts
    only), `glance_enable_tls_backend` (glance-tls-proxy output on every host), the fluentd image's `fluentd_version`
    label (selects the rewrite filter, 0.12 if absent), custom files under `{{ node_custom_config }}/fluentd/` and the
    Elasticsearch/Monasca settings;
  - `logrotate.conf` (cron, built from `cron_logrotate_services`);
  - the RabbitMQ erlang cookie in kolla_toolbox;
  - container definitions of fluentd, cron and kolla_toolbox (image tag, volumes).
- **What restarts:** any drift restarts **all three** containers on that host (loop-notify in `check-containers.yml`)
  [CODE] (`roles/common/tasks/check-containers.yml:2-17`; [Tags
  §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
- **Impact:**
  - fluentd: log shipping gap. The Elasticsearch and Monasca outputs buffer to files under `/var/lib/fluentd/data`, the
    `fluentd_data` volume, which a restart or a recreate keeps (`roles/common/defaults/main.yml:93`;
    `roles/common/templates/conf/output/01-es.conf.j2:26-27`, `02-monasca.conf.j2:13-14`). The tail read positions are
    in `/var/run/<fluentd_binary>/`, on no volume (`roles/common/templates/conf/input/00-global.conf.j2:14`):
    [NOT AVAILABLE] whether they survive a config-only restart and whether they are lost when the container is recreated
    (e.g. an image or volume change) ([Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)).
  - cron: log rotation is delayed.
  - kolla_toolbox: no service template references it (`roles/*/templates`); Kolla's own tasks use it [CODE].
  - **VM and API impact:** [NOT AVAILABLE]. None of the three is a container that [Tags
    §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) traces to running
    VMs [CODE].
- **Hidden coupling:** enabling a service that appears in either list (most OpenStack services, e.g. barbican) changes
  `td-agent.conf` and/or `logrotate.conf` on *every* host ([Repository architecture
  §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard)). The common containers
  therefore restart on whatever hosts the *next* run reaches, which can be a seemingly unrelated `-t nova` run
  ([Reconfigure Nova §3](reconfigure-nova.md#3-what-changes-per-type-of-change-code)).

## 4. Sequence, risks and verification

- **Sequence on each reached host** (first matching play only), from `roles/common/tasks/deploy.yml`:
  1. config: config directories; fluentd image label check; `config.json` ×3; custom fluentd files; `td-agent.conf`;
     cron `logrotate.conf`; RabbitMQ Erlang cookie and env files for kolla_toolbox;
  2. check-containers: one looped `compare_container` over fluentd, kolla_toolbox and cron;
  3. bootstrap: `kolla_logs` volume and the `/var/log/kolla` link;
  4. flush handlers, in definition order: Restart fluentd → Restart kolla-toolbox (→ toolbox `ansible --version`
     init) → Restart cron.
- **Hosts, parallelism:** all reached hosts at once, unless batched.
- **Interruption:** one stop/start per container (stop up to 10 s, [Repository architecture
  §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker)). Log shipping
  pauses, cron rotation is delayed, and Kolla's own `kolla_toolbox` tasks wait. [NOT AVAILABLE] Whether VMs, APIs,
  networking or storage are affected ([§3](#3-how-common-actually-reaches-hosts)).
- **Risks:** [R2](../risk/risk-register.md#r2) (fleet-wide restarts after an `enable_*` change),
  [R25](../risk/risk-register.md#r25) (`-t common` mistaken for a reconfigure).
- **Verification:**
  - before: `genconfig`, then `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check; echo $?` in each of
    `fluentd`, `cron` and `kolla_toolbox` (1 in any of them = all three will restart, by loop-notify; a
    `logrotate.conf`-only change, e.g. toggling `enable_chrony` or `enable_mariadb`, shows up only in `cron`). The
    check does not cover image or volume changes;
  - after: `docker ps --filter name=fluentd --filter name=cron --filter name=kolla_toolbox` shows fresh start times;
    `docker logs fluentd` has no parse errors; logs still reach the configured output.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R2](../risk/risk-register.md#r2) (fleet-wide
  restarts after an `enable_*` change) and [R25](../risk/risk-register.md#r25) (`-t common` mistaken for a
  reconfigure)
- [Common: fluentd, cron, kolla_toolbox](../components/common.md) — service card and where to look
- [Chrony](../components/chrony.md) — service card and where to look for the tag used to push `common` changes
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) — dynamic `include_tasks` and tag
  inheritance: the tag semantics behind §2
- [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard) —
  the `common` role and the `common_run` guard
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) —
  `enable_<new service>: yes` changes fluentd/logrotate on every host
