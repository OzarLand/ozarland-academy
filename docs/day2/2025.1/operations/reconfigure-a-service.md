---
title: Reconfigure a single service
description: What a single-service reconfigure such as -t keystone runs in 2025.1, what the tag also touches, what restarts on drift, the risks and the verification.
tags: [keystone, glance, placement, cinder, heat, haproxy, reconfigure, tags, one-shot, limit, genconfig, serial]
remember:
  - "Changed in 2025.1: a service tag no longer restarts HAProxy. <code>-t &lt;svc&gt;</code> rewrites <code>services.d/&lt;svc&gt;*.cfg</code>, but only a run with <code>-t haproxy</code> (or no tag) applies it, with a staged HAProxy restart. <span class=\"ev ev-code\">CODE</span>"
  - "Changed in 2025.1: only the containers that drifted restart, not all the service's containers on the host; and <code>reconfigure</code> always runs every host at once (<code>kolla_serial=0</code>), so a change common to all hosts restarts the service on all its hosts together. <span class=\"ev ev-code\">CODE</span>"
  - "A service that <code>kolla-ansible upgrade</code> has not reached drifts on every host on its first 2025.1 reconfigure: its image tag changes (and the reconfigure skips the role's upgrade tasks), its systemd unit lacks <code>PartOf=kolla.target</code> (F16), and with Docker outside the Red Hat family its ulimits differ. Upgrade it first."
  - "The service API is unavailable while its containers restart, with up to <code>docker_graceful_timeout</code> (60 s by default) between SIGTERM and SIGKILL."
  - "To stage a service change host by host, use <code>deploy -e kolla_serial=1</code> or <code>--limit</code>: <code>reconfigure -e kolla_serial=1</code> is overridden. <span class=\"ev ev-code\">CODE</span>"
impact: [restarts-on-drift]
scenarios:
  - title: "A glance change during business hours"
    situation: "You changed an option in <code>glance-api.conf</code> that applies to every glance host. A user team is transferring large images to glance all afternoon. Your colleague suggests running <code>kolla-ansible reconfigure -i multinode -t glance -e kolla_serial=1</code> right now, since only one service is concerned and the batches keep glance up."
    ask: "What would you do?"
    choices:
      - text: "Run it now: <code>-e kolla_serial=1</code> restarts one glance host at a time."
        verdict: "avoid"
        why: "<code>reconfigure</code> always adds <code>kolla_serial=0</code> after your <code>-e</code>, and the later value wins, so every drifted glance host restarts at once <span class=\"ev ev-code\">CODE</span>. In-flight transfers are SIGKILLed if glance has not exited <code>docker_graceful_timeout</code> (60 s by default) after SIGTERM (R24)."
      - text: "Run it now with <code>--skip-tags haproxy</code>, so that the API stays up."
        verdict: "risky"
        why: "<code>--skip-tags haproxy</code> only drops the loadbalancer play (the frontend file); in 2025.1 a service tag does not restart HAProxy anyway. The glance containers still restart on every drifted host, all at once."
      - text: "Copy <code>/etc/kolla/haproxy/services.d/glance*.cfg</code>, run <code>kolla-ansible genconfig -i multinode -t glance</code>, check each glance container with <code>docker exec -u root &lt;c&gt; /usr/local/bin/kolla_set_configs --check; echo $?</code>, diff the frontend against the copy, then apply in a window with no transfers in flight, with <code>kolla-ansible deploy -t glance -e kolla_serial=1</code> if glance must stay up on some hosts."
        verdict: "best"
        why: "This is the \"before\" verification of §3 (a copy of the frontend, genconfig, the check as root in each container, a diff). <code>deploy</code> runs the same tasks as <code>reconfigure</code> and honours <code>kolla_serial</code>, and the window avoids R24."
    see: "3-sequence-impact-risks-and-verification-of--t-svc-reconfigure"
  - title: "The first keystone reconfigure after moving the deploy host to 2025.1"
    situation: "Your cloud was deployed with 2024.1 and the deploy host now runs 2025.1; <code>kolla-ansible upgrade</code> has not been run yet. You want to change one keystone option and plan <code>kolla-ansible reconfigure -i multinode -t keystone</code>, expecting nothing else to change because no other keystone setting moved."
    ask: "What would you do?"
    choices:
      - text: "Run it at any time: with no other change, only the keystone container restarts."
        verdict: "avoid"
        why: "The first 2025.1 check reports drift on every keystone container: its image (the 2025.1 tag), its unit that 2024.1 wrote, without <code>PartOf=kolla.target</code> (F16), and, with Docker outside the Red Hat family, its ulimits. Keystone would be recreated on all its hosts at once on the 2025.1 image, without its upgrade tasks."
      - text: "Run <code>kolla-ansible upgrade</code> (keystone included) first, in its own window; then plan the reconfigure, check the <code>services.d/keystone.cfg</code> diff, and apply a frontend change with <code>-t haproxy</code> afterwards."
        verdict: "best"
        why: "A <code>reconfigure</code> compares the image too, so it would move keystone to the 2025.1 image through the deploy path, without the database upgrade handlers of <code>roles/keystone/tasks/upgrade.yml</code> <span class=\"ev ev-code\">CODE</span>. The upgrade also writes the new units. A changed frontend is not applied by <code>-t keystone</code> in 2025.1, so it needs its own <code>-t haproxy</code> run (§3)."
      - text: "Add <code>--limit control01</code> to restart only one host."
        verdict: "risky"
        why: "<code>--limit</code> narrows every play to <code>control01</code>: the other keystone hosts keep the old configuration until a later run, and the loadbalancer hosts are not in the limit, so the frontend file waits too. It does not avoid the image change; it only splits the restarts over several runs."
    see: "11-reconfigure-a-single-service"
quiz:
  - q: "During <code>-t keystone reconfigure</code>, only the <code>keystone_fernet</code> container drifted on a host. What restarts on that host?"
    options: ["Only <code>keystone_fernet</code>", "All the keystone containers of that host"]
    answer: 0
    explain: "Changed in 2025.1: the shared check step notifies the restart handler of each changed container only; loop-notify is gone <span class=\"ev ev-code\">CODE</span>."
    see: "11-reconfigure-a-single-service"
  - q: "Can you restart keystone one host at a time with <code>kolla-ansible reconfigure -t keystone -e kolla_serial=1</code>?"
    options: ["Yes", "No: <code>reconfigure</code> always passes <code>kolla_serial=0</code> after your <code>-e</code>; use <code>deploy -e kolla_serial=1</code>"]
    answer: 1
    explain: "The 2025.1 CLI adds <code>kolla_serial=0</code> to <code>reconfigure</code> and <code>upgrade</code> after the user's extra vars, and the last value wins <span class=\"ev ev-code\">CODE</span>."
    see: "11-reconfigure-a-single-service"
  - q: "You changed a keystone frontend setting and ran <code>-t keystone reconfigure</code>. Does HAProxy now serve the new frontend?"
    options: ["Yes, handlers ignore tags", "No: the file is rewritten, but only a run with <code>-t haproxy</code> or no tag restarts HAProxy"]
    answer: 1
    explain: "The step that compares the HAProxy container carries only the loadbalancer play's tags, so it is skipped under <code>-t keystone</code>, and nothing notifies the HAProxy handlers <span class=\"ev ev-code\">CODE</span>."
    see: "3-sequence-impact-risks-and-verification-of--t-svc-reconfigure"
---

# Reconfigure a single service

What `kolla-ansible reconfigure -t <svc>` does in 2025.1 for one API service, with keystone as the command example:
after the gather-facts and group_by plays, which run on all hosts, the loadbalancer play runs on the loadbalancer hosts
(it rewrites the service's frontend file, and, **changed in 2025.1**, restarts nothing) and the service play on the
service hosts (the service's containers that drifted restart). As in 2024.1, `common` is its own play, tagged `common`
only, so a service tag does not run it. The page also says what a narrow tag touches besides the service, and what
changes on the first 2025.1 run of a cloud deployed by 2024.1.

The scenario sections are written for the [assumed deployment](index.md#assumed-deployment); the page uses the
[conventions of the command sections](index.md#conventions-used-by-the-command-sections), the definition of
[drift](index.md#drift) and the notion of [code guarantees and environment
dependence](index.md#code-guarantees-and-environment-dependence).

> [!NOTE]
> **Key answers**
>
> - **What restarts ([§1.1](#11-reconfigure-a-single-service)):** the service's containers that drifted, on every host
>   at once: **changed in 2025.1**, there is no loop-notify any more, and `reconfigure` always runs with
>   `kolla_serial=0`. To go host by host, use `deploy -e kolla_serial=N` or `--limit`.
> - **HAProxy ([§3](#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)):** changed in 2025.1, a service
>   tag rewrites the frontend file but never restarts HAProxy; the new frontend is applied by the next run with
>   `-t haproxy` (or no tag), backups first and the VIP holder last.
> - **First 2025.1 run on a 2024.1 cloud:** a service that `kolla-ansible upgrade` has not reached drifts on every
>   host: its image tag changes, and the reconfigure skips the role's upgrade tasks; the systemd unit text changed
>   ([F16](../reference/findings.md#f16)); with Docker outside the Red Hat family the default ulimits changed. Upgrade
>   it first.
> - **Keep the frontend file untouched:** `--skip-tags haproxy` ([§1.2](#12-avoid-touching-haproxy-during-a-service-run)).

> [!WARNING]
> [R8](../risk/risk-register.md#r8): a changed `services.d/<svc>*.cfg` restarts HAProxy on every loadbalancer host
> (backups together, then the VIP holder) at the next `-t haproxy` or untagged run, not during the `-t <svc>` run that
> wrote it — see [§1.2](#12-avoid-touching-haproxy-during-a-service-run) and
> [§3](#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure).

## 1. Commands

### 1.1 Reconfigure a single service

```bash
kolla-ansible reconfigure -i multinode -t keystone
```

`reconfigure` sets `kolla_action=reconfigure` and `kolla_serial=0` (`kolla_ansible/cli/commands.py:128-140`).

- **Scope:**
  - loadbalancer play: keystone frontend only, on the loadbalancer hosts (`site.yml:105-120`; keystone include
    `site.yml:203-207`, inside a block that runs only when `enable_haproxy` is set and `kolla_action` is `deploy`,
    `reconfigure`, `upgrade` or `config`, `site.yml:325-327`); the final loadbalancer check step is skipped under a
    service tag (`site.yml:319-324`);
  - keystone play (`site.yml:498-510`): config, check-containers, bootstrap (db sync), a handler flush (restarts happen
    here), Fernet key distribution, Keystone registration, and identity-provider registration when
    `enable_keystone_federation` is true (`roles/keystone/tasks/deploy.yml:2-21`; `reconfigure.yml` only imports
    `deploy.yml`). **New in 2025.1:** the role has a `check.yml`, used only by the new `kolla-ansible check` command.
    `common` does not run: it is its own play, tagged `common` only (`site.yml:88-103`). Unlike glance, placement,
    cinder, heat and neutron, which register first (e.g. `roles/glance/tasks/deploy.yml:2`), keystone registers last.
- **Restarts:**
  - not haproxy: changed in 2025.1 ([§3](#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure));
  - per container: **changed in 2025.1**, the shared check step (`roles/keystone/tasks/check-containers.yml:2-3`,
    `roles/service-check-containers/tasks/main.yml:4-41`) notifies the restart handler of each keystone container that
    drifted, and only of those (`keystone`, `keystone_ssh` and `keystone_fernet`, all three `enabled: true`
    unconditionally, `roles/keystone/defaults/main.yml:6, :36, :49`). Hosts without drift do not restart. Drifted
    hosts restart in parallel: the keystone play reads `serial: '{{ kolla_serial|default("0") }}'` (`site.yml:503`),
    and `reconfigure` always passes `kolla_serial=0` after the user's `-e` (`kolla_ansible/cli/commands.py:20-22,
    :136`; [F19](../reference/findings.md#f19)), so a change common to all hosts (globals, `keystone.conf`, a new
    image) restarts the changed keystone containers on all keystone hosts at once. To stage it, run `kolla-ansible
    deploy -t keystone -e kolla_serial=1`, which runs the same tasks, or split the hosts with `--limit`.
- **One-shot:** the `bootstrap_keystone` db sync container, once (`run_once`,
  `roles/keystone/tasks/bootstrap_service.yml:34-52`); the Fernet bootstrap container only when no host runs
  `keystone_fernet` (`:53-76`). Fernet keys are re-distributed (`roles/keystone/tasks/deploy.yml:15`).
- **Impact:** if restarted, keystone restarts on all drifted hosts at once; [NOT AVAILABLE] whether authentication fails
  meanwhile, and for how long ([Risk register R19](../risk/risk-register.md#r19)).

### 1.2 Avoid touching HAProxy during a service run

```bash
kolla-ansible reconfigure -i multinode -t nova --skip-tags haproxy
```

- `--skip-tags haproxy` drops the whole loadbalancer play, including the per-service frontend includes: `haproxy` is
  a play tag (`site.yml:115-118`), inherited by every task of the play ([Tags
  §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)).
- **Changed in 2025.1:** a service tag no longer restarts HAProxy in any case ([Tags
  §2.2](../risk/tags.md#22-handlers-ignore-tags-code)), so `--skip-tags haproxy` now only keeps the frontend file as
  it is. Use it when frontends are not meant to change, so that a later `-t haproxy` run does not pick up a frontend
  change you did not intend.

## 2. Execute a service-specific tag: implicit effects

Even with a narrow tag, the code guarantees that the run also touches:

| Implicit effect | Mechanism | Evidence |
|---|---|---|
| **HAProxy frontend files of the service, on all loadbalancer hosts**; **no** HAProxy restart (changed in 2025.1) | loadbalancer play includes `<svc>/loadbalancer.yml` under the same tag; that file imports `loadbalancer-config` with `tags: always`, which imports `haproxy-config` (and `proxysql-config` when `enable_proxysql`). With `haproxy_single_external_frontend` (default `false`), the service's block of `external-frontend-map` is also written. **Changed in 2025.1:** these tasks notify no handler; the restart comes from the loadbalancer `check-containers` step at the end of the play, which carries only the play tags | `site.yml:105-327`, `roles/keystone/tasks/loadbalancer.yml:2-7`, `roles/loadbalancer-config/tasks/main.yml:2-8`, `roles/haproxy-config/tasks/main.yml:2-21, :23-49`, `site.yml:319-324`; [fact sheet A §1.9](../reference/factsheets/a-infra-lb-ovn.md#19-what-exactly-happens-in-the-haproxy-play-for--t-service-and--t-haproxy); [Tags §2.2–2.3](../risk/tags.md#22-handlers-ignore-tags-code) |
| **`common` on every host of the service play**: **still not in 2025.1** | No role has a `meta/` directory (no meta dependency on `common`); `common` is a separate play on the `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` groups with `tags: common`, so it runs only under `-t common` or a run without tags | `site.yml:88-103`, `roles/common/tasks/main.yml:2`; [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) |
| **Keystone registration** (services, endpoints, projects, users, roles of those users, grants) | `register.yml` imports `service-ks-register` from `deploy.yml`, which `reconfigure.yml` imports | `roles/glance/tasks/register.yml:2-7`, `roles/service-ks-register/tasks/main.yml:3-129` |
| **DB creation/grants and DB schema sync** for most services, Neutron included (its `bootstrap_neutron` container has no `when`, [Reconfigure Neutron §2](reconfigure-neutron.md#2-execution-and-targets)) | `bootstrap.yml` imported by `deploy.yml` | [CODE] 14 one-shot container runs on a no-change redeploy of this service set (cell0 mapped; MariaDB, RabbitMQ and Fernet keys already bootstrapped): 8 DB-sync bootstraps (keystone, glance, placement, nova API, nova cell, neutron, cinder, heat) + map_cell0 + list_cells for cell0 (`roles/nova/tasks/map_cell0.yml:24-30`) + 2× list_cells, counted from each role's `bootstrap_service.yml` (`roles/keystone/tasks/bootstrap_service.yml:34-52`, `roles/glance/tasks/bootstrap_service.yml:19-37`, `roles/placement/tasks/bootstrap_service.yml:2-20`, `roles/neutron/tasks/bootstrap_service.yml:2-21`, `roles/cinder/tasks/bootstrap_service.yml:2-20`, `roles/heat/tasks/bootstrap_service.yml:2-30`; nova: [Reconfigure Nova §1.1](reconfigure-nova.md#11-reconfigure-nova-control-plane-and-computes), [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)), + **new in 2025.1**, the two libvirt image checks of nova-cell, `libvirt_version_check` and `nova_libvirt_script_check`, on the first compute (`roles/nova-cell/tasks/version-check.yml:3-21, :80-98`, run from `roles/nova-cell/tasks/deploy.yml:5` when `enable_nova_libvirt_container`) |
| **RabbitMQ user/vhost** (nova-cell only) | `service-rabbitmq`, imported from `nova-cell/tasks/bootstrap.yml` | `roles/nova-cell/tasks/bootstrap.yml:37`, `roles/nova-cell/tasks/rabbitmq.yml:3-29` |
| **Global MariaDB variable toggle** (`-t glance`) | `log_bin_trust_function_creators` 1→0 around the glance DB sync, unless `use_preconfigured_databases` | `roles/glance/tasks/bootstrap_service.yml:2-17, :39-54`; [fact sheet C §1](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#1-glance) |
| **Fernet key redistribution** (`-t keystone`) | `distribute_fernet.yml` | `roles/keystone/tasks/deploy.yml:15`; [fact sheet B §3.6](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#36-fernet-key-lifecycle-fact-unless-marked) (re-run on reconfigure: [§3.7](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#37-bootstrap-db-and-registration-what-re-runs-on-reconfigure)) |
| **Actions on hosts outside `--limit`** | `delegate_to` to `groups[...][0]`: Neutron DB bootstrap on neutron-server[0], cell discovery on conductor[0], RabbitMQ user creation on the first host of the cell's RPC (and notify) group, the libvirt image checks on the first compute | `roles/neutron/tasks/bootstrap.yml:13-14`, `bootstrap_service.yml:20-21`; `roles/nova-cell/tasks/discover_computes.yml:21`, `wait_discover_computes.yml:43`; `roles/nova-cell/tasks/rabbitmq.yml:12, :22`, `roles/service-rabbitmq/tasks/main.yml:42`; `roles/nova-cell/tasks/version-check.yml:21, :98`; [Add a compute node §2](add-a-compute-node.md#2-add-a-compute-node) |
| **SIGHUP to every nova-scheduler** (`-t nova`/`nova-api`) | refresh play, on `deploy` and `reconfigure` | `nova.yml:152-172` |

What a service tag does **not** do: it never touches MariaDB, RabbitMQ or memcached *containers* (other plays), never
the HAProxy, keepalived or ProxySQL containers (changed in 2025.1), and never OVS (unless `-t openvswitch`), nor the
`common` containers (fluentd, kolla_toolbox, cron). Under `-t haproxy` or a no-tag run, the loadbalancer role's
containers (HAProxy, keepalived, ProxySQL when enabled and `haproxy_ssh` when `enable_letsencrypt` is set,
`roles/loadbalancer/defaults/main.yml:29-36`) are checked, and that check also covers every frontend file written by
earlier service runs.

[CODE] `-t haproxy reconfigure` on an unchanged cloud: the loadbalancer role on the 2 loadbalancer hosts
(`site.yml:105-120`, `inventory/multinode:84-85`); `common` does not run (its play is tagged `common` only,
`site.yml:88-103`). **Changed in 2025.1:** the play holds 38 frontend `include_role` tasks, not 39 (swift is gone).
All 38 are evaluated; 12 run (placement's, which has no `when`, and the 11 whose condition is true for this service
set: cinder, glance, heat, horizon, keystone, mariadb, memcached, neutron, nova, nova-cell, rabbitmq) and the other 26
are skipped by their `when` (`site.yml:122-318`; defaults in `group_vars/all.yml`); then the loadbalancer
`check-containers` step runs (`site.yml:319-324`). Restarts follow only a container that the check reports changed
([Tags §2.4](../risk/tags.md#24-loop-notify-is-gone-in-20251-code)); [NOT AVAILABLE] whether any does on an unchanged
cloud.

## 3. Sequence, impact, risks and verification of `-t <svc> reconfigure`

For an API service such as keystone, glance, cinder, heat or placement:

1. The gather-facts and group_by plays run on all hosts (`tags: always`, `site.yml:2-75`).
2. loadbalancer play, on the loadbalancer hosts: only the `<svc>` include runs and renders `services.d/<svc>*.cfg`.
   The loadbalancer role's own tasks and the final `check-containers` step carry only the play tags (`haproxy`,
   `keepalived`, `loadbalancer`), not the `<svc>` tag, so they are skipped [CODE] (`site.yml:115-120, :319-324`;
   [Tags §2.3](../risk/tags.md#23-include_role--tags-always-inside-the-haproxy-play-code)). **Changed in 2025.1:**
   nothing in this run restarts HAProxy, even if the file changed; the next `-t haproxy` (or untagged) run finds the
   difference through `kolla_set_configs --check` (`services.d/` is copied into the container,
   `roles/loadbalancer/templates/haproxy/haproxy.json.j2:17-18`) and restarts HAProxy on every loadbalancer host,
   staged [CODE]: the hosts are grouped by whether they hold the VIP (`roles/loadbalancer/handlers/main.yml:9-34`);
   HAProxy stops and starts on all backups together and the play waits for `haproxy_monitor_port`
   (`:54-68`, `:90-119`); then it stops and starts on the VIP holder and waits again (`:181-195`, `:226-254`)
   ([R8](../risk/risk-register.md#r8); [HAProxy + Keepalived](../components/haproxy-keepalived.md#before-and-after-a-run)).
   Whether the VIP moves meanwhile is [NOT AVAILABLE].
3. Service play, on the service hosts: Keystone registration (`run_once`) → config → check-containers →
   DB/user creation and the DB-sync container on the first host → flush (e.g. `roles/glance/tasks/deploy.yml:2-15`;
   placement runs its clone step before config, `roles/placement/tasks/deploy.yml:2-14`). Every drifted container
   restarts, on all hosts at once (`kolla_serial=0`). Keystone is the exception in order: it registers last
   ([§1.1](#11-reconfigure-a-single-service)).

**First 2025.1 run on a cloud deployed by 2024.1** [CODE]:

- If `kolla-ansible upgrade` has not reached the service, its image changes: `openstack_release` defaults to `2025.1`
  (`group_vars/all.yml:795-797`), the check compares the image (`module_utils/kolla_container_worker.py:75`), and the
  handler recreates the container on the 2025.1 image (`module_utils/kolla_docker_worker.py:352-372`), through the
  deploy path, without the role's upgrade tasks (e.g. `roles/keystone/tasks/upgrade.yml:23-34`). Upgrade it first.
- Every container whose unit no 2025.1 run has recreated or restarted yet drifts: `compare_container` also compares
  the systemd unit text (`module_utils/kolla_container_worker.py:58-65`,
  `module_utils/kolla_systemd_worker.py:155-168`), and the 2025.1 template adds `PartOf=kolla.target`
  (`module_utils/kolla_systemd_worker.py:27`; [F16](../reference/findings.md#f16)). A `kolla-ansible upgrade` that
  recreated the service's containers already wrote the new units.
- With Docker on hosts outside the Red Hat family, `default_container_dimensions` now carries a `nofile` ulimit
  (`group_vars/all.yml:201-224`), which containers created by 2024.1 lack, so they differ and are recreated
  ([Repository architecture §6](../concepts/repository-architecture.md#6-custom-modules--container-lifecycle-via-kolla_container)).
  So the first run on a service not yet upgraded restarts or recreates it on all its hosts at once.
- Whether the frontend files of the services render differently under 2025.1 is [NOT AVAILABLE] (not rendered here);
  the diff of the verification below shows it.

- **Interruption:** the service API is unavailable while its drifted containers restart on all drifted hosts at once.
  A config drift goes through a systemd `RestartUnit` of the container's unit, a container drift (image, volumes,
  dimensions) through a stop, remove and start (`module_utils/kolla_docker_worker.py:352-374`, `:426-442`,
  `:450-470`; `module_utils/kolla_systemd_worker.py:107-126`). Either way the stop is the unit's
  `ExecStop=/usr/bin/<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:33`), with
  `docker_graceful_timeout`, 60 s by default, passed through `docker_common_options` (`group_vars/all.yml:148, :160`):
  up to 60 s between SIGTERM and SIGKILL, then the start.
- **VM impact:** these services restart none of the containers that [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) traces to running VMs
  [CODE]; any other effect on VMs is [NOT AVAILABLE]. In-flight glance or cinder transfers are SIGKILLed if still
  running `docker_graceful_timeout` (60 s by default) after SIGTERM ([R24](../risk/risk-register.md#r24)). Of the tags
  in Tags §3.1, the ones that can restart those containers are `nova`, `nova-cell`, `neutron`, `openvswitch`, `ovn`
  (with `ovn-controller` and `ovn-db`), `iscsi` and `baremetal` (run by `bootstrap-servers` through
  `openstack.kolla.baremetal`, `kolla-host.yml:3-14`, not `reconfigure`; Docker restart,
  [R14](../risk/risk-register.md#r14)) [CODE]; what those restarts do to running VMs is [NOT AVAILABLE]. Running on
  computes is not the test: `common` runs on every compute (`inventory/multinode:49-54, :202-212`) but restarts only
  fluentd, kolla_toolbox and cron. `chrony` still has no role or play.
- **Risks:** [R8](../risk/risk-register.md#r8) (HAProxy restart at the next `-t haproxy` run),
  [R19](../risk/risk-register.md#r19) (Keystone), [R20](../risk/risk-register.md#r20) (glance file backend),
  [R23](../risk/risk-register.md#r23) (`--limit` on a large inventory), [R24](../risk/risk-register.md#r24) (SIGKILL
  after `docker_graceful_timeout`).
- **Verification:**
  - before: copy `/etc/kolla/haproxy/services.d/<svc>*.cfg` from a loadbalancer host, run
    `kolla-ansible genconfig -i multinode -t <svc>`, then `docker exec -u root <c> /usr/local/bin/kolla_set_configs
    --check; echo $?` in each `<svc>` container (without `-u root` it exits 2 in images that run as a service user,
    e.g. glance-api; [Kolla images §3.4](../concepts/kolla-images.md#34-running-it-by-hand-needs-root)) and diff the
    frontend against the copy;
  - **`genconfig` and the frontend** [CODE]: `genconfig` runs with `kolla_action=config`
    (`kolla_ansible/cli/commands.py:113-125`), for which the loadbalancer block also runs (`site.yml:325-327`) and
    writes `services.d/<svc>*.cfg` (`roles/haproxy-config/tasks/main.yml:2-21`), while the loadbalancer check step is
    skipped (`site.yml:319-324`). In 2025.1 a `-t <svc> reconfigure` does not apply the frontend either, with or
    without `genconfig` first: the new frontend reaches HAProxy only through a `-t haproxy reconfigure` (or a run
    without tags). The service containers are not affected: their check step does run;
  - after: `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers (each
    `name` in `<svc>_ks_services`, e.g. `cinder` (type `block-storage`, new in 2025.1) and `cinderv3` for cinder (`roles/cinder/defaults/main.yml:346-359`), `heat`
    and `heat-cfn` for heat (`roles/heat/defaults/main.yml:224-236`)), the API answers through the VIP, and the
    container start times show which hosts restarted (`kolla_container_engine` defaults to `docker`,
    `group_vars/all.yml:100`; with Podman, use `podman`).

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R8](../risk/risk-register.md#r8) (HAProxy
  restart), [R19](../risk/risk-register.md#r19) (Keystone), [R20](../risk/risk-register.md#r20) (glance file backend),
  [R23](../risk/risk-register.md#r23) (`--limit` on a large inventory), [R24](../risk/risk-register.md#r24) (SIGKILL
  after `docker_graceful_timeout`) and [R14](../risk/risk-register.md#r14) (Docker restart by `bootstrap-servers`)
- [Technical findings](../reference/findings.md) — [F16](../reference/findings.md#f16) (the changed systemd unit
  template, a cause of drift on the first 2025.1 run) and [F19](../reference/findings.md#f19) (`reconfigure` cannot
  be batched)
- [Keystone](../components/keystone.md) — service card and where to look for the service of the §1.1 example
- [HAProxy + Keepalived](../components/haproxy-keepalived.md) — service card and where to look for HAProxy, including
  the staged restart order and the loadbalancer play under a service tag
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Predict and inspect a run](predict-a-run.md) — `genconfig` and the exit codes of `kolla_set_configs --check`, used
  in the verification of §3
- [Tags §2](../risk/tags.md#2-ansible-29-semantics-that-kolla-relies-on) — the semantics behind the implicit effects:
  tag inheritance, handlers that ignore tags, the haproxy play, the end of loop-notify
- [Command quick lookup by tag](command-quick-lookup.md) — hosts touched, possible restarts and one-shot containers
  per tag
- [2024.1 reconfigure a single service](../../2024.1/operations/reconfigure-a-service/) — the same page for 2024.1
