---
title: Apply common changes (fluentd, cron, kolla_toolbox)
description: How -t common reconfigure reaches every host through the standalone common play in 2023.1, which runs bring common along, what restarts and how to verify.
tags: [fluentd, cron, kolla-toolbox, common, reconfigure, tags, loop-notify, kolla-set-configs]
impact: [restarts-on-drift]
---

# Apply `common` changes (fluentd, cron, kolla_toolbox)

How to push changes of the `common` role (fluentd, cron, kolla_toolbox) to hosts. In 2023.1 `common` is a play of its
own, tagged `common`, so `-t common reconfigure` reconfigures every host of the `common` group.

The page uses the definition of [drift](index.md#drift) of the Operations hub.

> [!NOTE]
> **Key answers**
>
> - **`-t common reconfigure` reconfigures every common host** [CODE] ([§2](#2-the-tag-does-nothing)). `common` reaches
>   a
>   host only through the "Apply role common" play: a run without tags, or a run whose tags include `common`
>   ([§3](#3-how-common-actually-reaches-hosts)). `-t nova` or `-t neutron` no longer bring it along.

> [!WARNING]
> [R2](../risk/risk-register.md#r2): fleet-wide restarts after an `enable_*` change — see "Hidden coupling" in
> [§3](#3-how-common-actually-reaches-hosts).

## 1. Commands

### 1.1 Apply `common` changes (fluentd, cron, kolla_toolbox)

```bash
# 2023.1: common is its own play, tagged common (site.yml:86-97)
kolla-ansible -i multinode -t common reconfigure
kolla-ansible -i multinode -t common reconfigure --limit 'compute[0:49]'
```

- The play targets the groups `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox`, all children of `common`
  (control, network, compute, storage, monitoring) in the shipped inventory [CODE] (`site.yml:86-97`;
  `inventory/multinode:48-53, :239-249`). It runs with `serial: kolla_serial` (`site.yml:93`), so `ANSIBLE_SERIAL`
  batches it.
- The `chrony` tag used for this in Ussuri no longer exists: there is no `chrony` role or play in 2023.1 (no
  `roles/chrony`, no `chrony` in `site.yml`).

## 2. The tag does nothing

No longer true in 2023.1. `roles/common/tasks/main.yml:1-2` is a bare `include_tasks: "{{ kolla_action }}.yml"` with no
tag and no `common_run` guard; the tag `common` is set on the play (`site.yml:86-97`). Tasks of a dynamic include get
the include's parent block (ansible-core 2.14.18 `lib/ansible/plugins/strategy/__init__.py:819-820`), and a block
extends its tags with those of its play (`lib/ansible/playbook/block.py:355-363`; `tags` is an `extend=True` field,
`lib/ansible/playbook/taggable.py:31`). The included `reconfigure.yml` tasks therefore carry `common` and run [CODE].
Tag semantics: [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code).

## 3. How `common` actually reaches hosts

- **Where it runs:** the `common` role (fluentd, cron, kolla_toolbox) runs only in the "Apply role common" play, on the
  hosts of `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` [CODE] (`site.yml:86-97`). No role declares `common` as
  a dependency any more (no `roles/*/meta` directory in 2023.1), and the `common_run` guard is gone.

  | Command | Hosts that get `common` |
  |---|---|
  | `reconfigure` (no tag) | all hosts of the `common` group, in the common play (the first service play after prechecks, `site.yml:86-97`) |
  | `-t nova` | none: the nova plays (`nova.yml:99-135`) do not include the `common` role [CODE] |
  | `-t neutron` | none (same reason) |
  | `-t chrony` | none: no play carries the tag in 2023.1, only the `always`-tagged plays (fact gathering, host grouping) run |
  | `-t haproxy` | none: the loadbalancer play (`site.yml:99-110`) does not include `common` |
  | `-t common` | all hosts of the `common` group (recommended way to push `common` changes) |
- **What it can change:**
  - `td-agent.conf` (fluentd inputs/outputs). It is built from `fluentd_input_openstack_services` (the `enable_*`
    flags of the OpenStack services, `roles/common/defaults/main.yml:138-202`) read by
    `conf/input/00-global.conf.j2:2-5`, the input files enabled by `enable_nova`/`enable_nova_libvirt_container` and
    `enable_prometheus_fluentd_integration`, the local syslog outputs of `syslog_facilities` (swift and haproxy, and
    the glance and neutron TLS proxies, each only on its own hosts, `roles/common/defaults/main.yml:82-102`), the
    Elasticsearch (`elasticsearch_address` defined) and OpenSearch (`enable_opensearch` or an external
    `opensearch_address`) outputs, and custom files under `{{ node_custom_config }}/fluentd/` [CODE]
    (`roles/common/tasks/config.yml:41-136`). The fluentd image label check and the Monasca output of Ussuri are gone;
  - `logrotate.conf` (cron, built from `cron_logrotate_services`, task at `roles/common/tasks/config.yml:138`);
  - the RabbitMQ Erlang cookie, `rabbitmq-env.conf` and `erl_inetrc` in kolla_toolbox (only with `enable_rabbitmq`);
  - container definitions of fluentd, cron and kolla_toolbox (image tag, volumes, environment, dimensions).
- **What restarts:** any drift restarts **all three** containers on that host (loop-notify in `check-containers.yml`)
  [CODE] (`roles/common/tasks/check-containers.yml:2-17`, `compare_container` with a looped
  `notify: "Restart {{ item.key }} container"`; ansible-core 2.14.18 `lib/ansible/plugins/strategy/__init__.py:614-631`;
  [Tags §2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)).
- **Impact:**
  - fluentd: log shipping gap. The Elasticsearch and OpenSearch outputs buffer to files under `/var/lib/fluentd/data`,
    the `fluentd_data` volume, which a restart or a recreate keeps (`roles/common/defaults/main.yml:123`;
    `roles/common/templates/conf/output/01-es.conf.j2:27-31`, `03-opensearch.conf.j2:27-31`). The tail read positions
    are in `/var/run/td-agent/`, on no volume (`roles/common/templates/conf/input/00-global.conf.j2:12`):
    [NOT AVAILABLE] whether they survive a config-only restart and whether they are lost when the container is recreated
    (e.g. an image or volume change) ([Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour)).
  - cron: log rotation is delayed.
  - kolla_toolbox: no service template references it (`roles/*/templates`); Kolla's own tasks use it [CODE].
  - **VM and API impact:** [NOT AVAILABLE]. None of the three is a container that [Tags
    §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) traces to running
    VMs [CODE].
- **Hidden coupling:** enabling a service that appears in either list (most OpenStack services, e.g. barbican) changes
  `td-agent.conf` and/or `logrotate.conf` on *every* host ([Repository architecture
  §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard)). In 2023.1 the common
  containers restart on every common host at the next run that includes the common play: any run without tags, or a
  run with `-t common`. A tagged run such as `-t nova` no longer triggers it
  ([Reconfigure Nova §3](reconfigure-nova.md#3-what-changes-per-type-of-change-code)).

## 4. Sequence, risks and verification

- **Sequence on each reached host**, from `roles/common/tasks/deploy.yml:1-9` (`reconfigure.yml` imports it):
  1. config: config directories; `config.json` ×3; custom fluentd files; `td-agent.conf`; cron `logrotate.conf`;
     RabbitMQ Erlang cookie, `rabbitmq-env.conf` and `erl_inetrc` for kolla_toolbox;
  2. check-containers: one looped `compare_container` over fluentd, kolla_toolbox and cron;
  3. bootstrap: `kolla_logs` volume and the `/var/log/kolla` link (`roles/common/tasks/bootstrap.yml:1-16`);
  4. flush handlers, in definition order: Restart fluentd → Restart kolla-toolbox (→ toolbox `ansible --version`
     init) → Restart cron (`roles/common/handlers/main.yml:2, :18, :37-40, :42`).
- **Hosts, parallelism:** all reached hosts at once, unless batched (`serial: kolla_serial`, `site.yml:93`).
- **Interruption:** one stop/start per container. The stop goes through the container's systemd unit, `docker stop -t
  <graceful_timeout>`, with `docker_graceful_timeout: 60` (`module_utils/kolla_docker_worker.py:436-452`,
  `module_utils/kolla_systemd_worker.py:33`, `group_vars/all.yml:140`; [Repository architecture
  §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_docker)). Log shipping
  pauses, cron rotation is delayed, and Kolla's own `kolla_toolbox` tasks wait. [NOT AVAILABLE] Whether VMs, APIs,
  networking or storage are affected ([§3](#3-how-common-actually-reaches-hosts)).
- **Risks:** [R2](../risk/risk-register.md#r2) (fleet-wide restarts after an `enable_*` change),
  [R25](../risk/risk-register.md#r25) (`-t common` mistaken for a reconfigure; in 2023.1 `-t common` does reconfigure,
  see [§2](#2-the-tag-does-nothing)).
- **Verification:**
  - before: `genconfig`, then `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check; echo $?` in each of
    `fluentd`, `cron` and `kolla_toolbox` (1 in any of them = all three will restart, by loop-notify; a
    `logrotate.conf`-only change, e.g. toggling `enable_mariadb`, shows up only in `cron`). The check does not cover
    image or volume changes;
  - after: `docker ps --filter name=fluentd --filter name=cron --filter name=kolla_toolbox` shows fresh start times;
    `docker logs fluentd` has no parse errors; logs still reach the configured output.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R2](../risk/risk-register.md#r2) (fleet-wide
  restarts after an `enable_*` change) and [R25](../risk/risk-register.md#r25) (`-t common` mistaken for a
  reconfigure)
- [Common: fluentd, cron, kolla_toolbox](../components/common.md) — service card and where to look
- [Chrony](../components/chrony.md) — the Ussuri tag used to push `common` changes; the role no longer exists in 2023.1
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) — dynamic `include_tasks` and tag
  inheritance: the tag semantics behind §2
- [Repository architecture §5.1](../concepts/repository-architecture.md#51-the-common-role-and-the-common_run-guard) —
  the `common` role and the `common_run` guard (gone in 2023.1)
- [Why a small change creates a large workload](../risk/small-change-large-workload.md) —
  `enable_<new service>: yes` changes fluentd/logrotate on every host
