---
title: Reconfigure a single service
description: What a single-service reconfigure such as -t keystone runs in 2024.1, what the tag also touches, what restarts on drift, the risks and the verification.
tags: [keystone, glance, placement, cinder, heat, haproxy, reconfigure, tags, loop-notify, one-shot, limit, genconfig]
remember:
  - "A changed <code>services.d/&lt;svc&gt;*.cfg</code> restarts HAProxy on every loadbalancer host, the backups together and then the VIP holder; add <code>--skip-tags haproxy</code> when frontends are not meant to change."
  - "On each drifted host all the service's containers restart, all such hosts in parallel unless <code>ANSIBLE_SERIAL</code> is set: without it, a change common to all hosts restarts the service on all its hosts at once."
  - "A service that <code>kolla-ansible upgrade</code> has not reached drifts on every host on its first 2024.1 reconfigure: its image tag changes (and the reconfigure skips the role's upgrade tasks), its systemd unit text changed (F16) and quorum queues are on by default (F17). Upgrade it first."
  - "The service API is unavailable while its containers restart, with up to <code>docker_graceful_timeout</code> (60 s by default) between SIGTERM and SIGKILL."
  - "<code>genconfig</code> also re-renders <code>services.d</code>: copy the file first, and after it a <code>-t &lt;svc&gt;</code> run no longer notifies the HAProxy restart."
impact: [restarts-on-drift]
scenarios:
  - title: "A glance change during business hours"
    situation: "You changed an option in <code>glance-api.conf</code> that applies to every glance host. A user team is transferring large images to glance all afternoon. Your colleague suggests running <code>kolla-ansible -i multinode -t glance reconfigure</code> right now, since only one service is concerned."
    ask: "What would you do?"
    choices:
      - text: "Run it now with <code>--skip-tags haproxy</code>, so that the API stays up."
        verdict: "risky"
        why: "<code>--skip-tags haproxy</code> only drops the loadbalancer play (the frontends). The glance containers still restart on every drifted host, all such hosts in parallel when <code>ANSIBLE_SERIAL</code> is not set, so the glance API is unavailable on all its hosts at once."
      - text: "Run it now: only drifted hosts restart, so the transfers are safe."
        verdict: "avoid"
        why: "Without <code>ANSIBLE_SERIAL</code>, drifted hosts restart in parallel, so a change common to all hosts restarts glance on all its hosts at once. In-flight transfers are SIGKILLed if glance has not exited <code>docker_graceful_timeout</code> (60 s by default) after SIGTERM (R24)."
      - text: "Copy <code>/etc/kolla/haproxy/services.d/glance*.cfg</code>, run <code>kolla-ansible -t glance genconfig</code>, check each glance container with <code>docker exec -u root &lt;c&gt; /usr/local/bin/kolla_set_configs --check; echo $?</code>, diff the frontend against the copy, and run the <code>reconfigure</code> in a window with no transfers in flight, with <code>ANSIBLE_SERIAL</code> set if glance must stay up on some hosts."
        verdict: "best"
        why: "This is the \"before\" verification of §3 (a copy of the frontend, genconfig, the check as root in each container, a diff), and it avoids R24: in-flight glance transfers are SIGKILLed after <code>docker_graceful_timeout</code> while the containers restart."
    see: "3-sequence-impact-risks-and-verification-of--t-svc-reconfigure"
  - title: "The first keystone reconfigure after moving the deploy host to 2024.1"
    situation: "Your cloud was deployed with 2023.1 and the deploy host now runs 2024.1; <code>kolla-ansible upgrade</code> has not been run yet. You want to change one keystone option and plan <code>kolla-ansible -i multinode -t keystone reconfigure</code>, expecting nothing else to change because no other keystone setting moved."
    ask: "What would you do?"
    choices:
      - text: "Run it at any time: with no other change, only the host where you changed something restarts."
        verdict: "avoid"
        why: "The option is common to all hosts, and in any case the first 2024.1 check reports drift on every keystone container: its image (the 2024.1 tag), its unit that 2023.1 wrote (F16) and the rendered <code>keystone.conf</code> (quorum queues, F17). Keystone would be recreated on all its hosts at once on the 2024.1 image, without its upgrade tasks."
      - text: "Run <code>kolla-ansible upgrade</code> (keystone included) first, in its own window; then plan the reconfigure, check the <code>services.d/keystone.cfg</code> diff first, and expect keystone and, if the rendered frontend changed, HAProxy to restart."
        verdict: "best"
        why: "A <code>reconfigure</code> compares the image too, so it would move keystone to the 2024.1 image through the deploy path, without the database upgrade handlers of <code>roles/keystone/tasks/upgrade.yml</code> <span class=\"ev ev-code\">CODE</span>. The upgrade also writes the new units and the quorum setting. The <code>balance</code> line of the keystone frontend is written differently by 2024.1, so the frontend file is expected to change (§3)."
      - text: "Add <code>--limit control01</code> to restart only one host."
        verdict: "risky"
        why: "<code>--limit</code> narrows every play to <code>control01</code>: the other keystone hosts keep the old configuration until a later run, and the loadbalancer hosts are not in the limit, so the frontend change waits too. It does not avoid the restarts or the image change; it only splits them over several runs."
    see: "11-reconfigure-a-single-service"
quiz:
  - q: "During <code>-t keystone reconfigure</code>, one keystone container drifted on a host. What restarts on that host?"
    options: ["Only the container that drifted", "All the keystone containers of that host"]
    answer: 1
    explain: "This is loop-notify: a change that concerns one container restarts every container of that role on that host (<code>keystone</code>, <code>keystone_ssh</code>, <code>keystone_fernet</code>)."
    see: "11-reconfigure-a-single-service"
  - q: "Do keystone hosts without drift restart?"
    options: ["Yes, every keystone host restarts", "No: only drifted hosts restart, in parallel unless <code>ANSIBLE_SERIAL</code> is set"]
    answer: 1
    explain: "Without <code>ANSIBLE_SERIAL</code>, a change common to all hosts (globals, <code>keystone.conf</code>, a new image, the first 2024.1 run of a service not yet upgraded) therefore restarts keystone on all keystone hosts at once."
    see: "11-reconfigure-a-single-service"
  - q: "How do you keep HAProxy untouched during a service run?"
    options: ["With <code>--limit</code>", "With <code>--skip-tags haproxy</code>"]
    answer: 1
    explain: "<code>--skip-tags haproxy</code> drops the whole loadbalancer play, including the per-service frontend includes."
    see: "12-avoid-touching-haproxy-during-a-service-run"
  - q: "You ran <code>-t keystone genconfig</code>, which changed <code>services.d/keystone.cfg</code>. Does the following <code>-t keystone reconfigure</code> restart HAProxy?"
    options: ["Yes, the frontend changed", "No: the file is already written, so nothing notifies the restart"]
    answer: 1
    explain: "<code>genconfig</code> writes the frontend and skips every restart handler; the later template task reports no change, and the loadbalancer check-containers task does not run under <code>-t keystone</code>."
    see: "3-sequence-impact-risks-and-verification-of--t-svc-reconfigure"
---

# Reconfigure a single service

What `kolla-ansible -t <svc> reconfigure` does in 2024.1 for one API service, with keystone as the command example:
after the gather-facts and group_by plays, which run on all hosts, the loadbalancer play runs on the loadbalancer hosts
(the service's frontend, and a staged HAProxy restart if the rendered frontend changed) and the service play on the
service hosts (the service's containers, all of which restart on every drifted host). As in 2023.1, `common` is its
own play, tagged `common` only, so a service tag does not run it. The page also says what a narrow tag touches
besides the service, and what changes on the first 2024.1 run of a cloud deployed by 2023.1.

The scenario sections are written for the [assumed deployment](index.md#assumed-deployment); the page uses the
[conventions of the command sections](index.md#conventions-used-by-the-command-sections), the definition of
[drift](index.md#drift) and the notion of [code guarantees and environment
dependence](index.md#code-guarantees-and-environment-dependence).

> [!NOTE]
> **Key answers**
>
> - **What restarts ([§1.1](#11-reconfigure-a-single-service)):** on each host where any container of the service
>   drifted, all its containers; all such hosts in parallel, unless `ANSIBLE_SERIAL` is set. HAProxy restarts only if
> the service's rendered frontend
>   changed, backups first and the VIP holder last
> ([§3](#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)).
> - **First 2024.1 run on a 2023.1 cloud:** a service that `kolla-ansible upgrade` has not reached drifts on every
>   host: its image tag changes, and the reconfigure skips the role's upgrade tasks; the systemd unit text changed
>   ([F16](../reference/findings.md#f16)); quorum queues are on by default in every service that talks to RabbitMQ
>   ([F17](../reference/findings.md#f17)). Upgrade it first. For keystone the frontend text changes too
>   ([§3](#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)).
> - **Keep HAProxy out:** `--skip-tags haproxy` ([§1.2](#12-avoid-touching-haproxy-during-a-service-run)).
> - **`genconfig` first:** it re-renders `services.d` too, so a later `-t <svc>` run no longer restarts HAProxy for
>   that change ([§3](#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)).

> [!WARNING]
> [R8](../risk/risk-register.md#r8): a changed `services.d/<svc>*.cfg` restarts HAProxy on every loadbalancer host
> (backups together, then the VIP holder) — see [§1.2](#12-avoid-touching-haproxy-during-a-service-run) and
> [§3](#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure).

## 1. Commands

### 1.1 Reconfigure a single service

```bash
kolla-ansible -i multinode -t keystone reconfigure
```

`reconfigure` sets `kolla_action=reconfigure` and `kolla_serial` (`tools/kolla-ansible:529-531`).

- **Scope:**
  - loadbalancer play: keystone frontend only, on the loadbalancer hosts (`site.yml:105-120`; keystone include
    `site.yml:203-207`, inside a block that runs only when `enable_haproxy` is set and `kolla_action` is `deploy`,
    `reconfigure`, `upgrade` or `config`, `site.yml:324-326`);
  - keystone play (`site.yml:483-495`): config, check-containers, bootstrap (db sync), a handler flush (restarts happen
    here), Fernet key distribution, Keystone registration, and identity-provider registration when
    `enable_keystone_federation` is true (`roles/keystone/tasks/deploy.yml:2-21`; `reconfigure.yml` only imports
    `deploy.yml`). **Still holds in 2024.1:** there is no `check.yml` in the role. `common` does not run: it is its own
    play, tagged `common` only (`site.yml:88-103`). Unlike glance, placement, cinder, heat and neutron, which register
    first (e.g. `roles/glance/tasks/deploy.yml:2`), keystone registers last.
  - **Changed in 2024.1:** keystone's registration no longer passes a list of roles to create
    (`roles/keystone/tasks/register.yml:14-19`; 2023.1 passed `keystone_ks_roles`, which no longer exists), and the
    `admin` endpoint is no longer listed for removal (`roles/keystone/defaults/main.yml:200-202`).
- **Restarts:**
  - haproxy, on all loadbalancer hosts, only if the frontend changed (staged, see
    [§3](#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure));
  - per host (loop-notify): on each keystone host where any keystone container drifted, all keystone containers of
    that host restart (`keystone`, `keystone_ssh` and `keystone_fernet`, all three `enabled: true` unconditionally,
    `roles/keystone/defaults/main.yml:6, :34, :47`; `roles/keystone/tasks/check-containers.yml:2-17`). Hosts without
    drift do not restart. Drifted hosts restart in parallel, unless `ANSIBLE_SERIAL` is set (default 0,
    `tools/kolla-ansible:296, :531`; the keystone play reads `serial: '{{ kolla_serial|default("0") }}'`,
    `site.yml:486`), so without it a change common to all hosts (globals, `keystone.conf`, a new image) restarts
    keystone on all keystone hosts at once.
- **One-shot:** the `bootstrap_keystone` db sync container, once (`run_once`,
  `roles/keystone/tasks/bootstrap_service.yml:33-50`); the Fernet bootstrap container only when no host runs
  `keystone_fernet` (`:52-75`). Fernet keys are re-distributed (`roles/keystone/tasks/deploy.yml:15`).
- **Impact:** if restarted, keystone restarts on all drifted hosts at once; [NOT AVAILABLE] whether authentication fails
  meanwhile, and for how long ([Risk register R19](../risk/risk-register.md#r19)).

### 1.2 Avoid touching HAProxy during a service run

```bash
kolla-ansible -i multinode -t nova --skip-tags haproxy reconfigure
```

- `--skip-tags haproxy` drops the whole loadbalancer play, including the per-service frontend includes: `haproxy` is
  a play tag (`site.yml:115-118`), inherited by every task of the play ([Tags
  §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code)).
- Use it when frontends are not meant to change. Otherwise a changed `services.d/<svc>*.cfg` restarts HAProxy on all
  loadbalancer hosts.

## 2. Execute a service-specific tag: implicit effects

Even with a narrow tag, the code guarantees that the run also touches:

| Implicit effect | Mechanism | Evidence |
|---|---|---|
| **HAProxy frontends of the service, on all loadbalancer hosts**, and a HAProxy restart if the rendered frontend changed | loadbalancer play includes `<svc>/loadbalancer.yml` under the same tag; that file imports `loadbalancer-config` with `tags: always`, which imports `haproxy-config` (and `proxysql-config` when `enable_proxysql`); handlers ignore tags. **New in 2024.1:** with `haproxy_single_external_frontend` (default `false`), the service's block of `external-frontend-map` is also written and also notifies the restart | `site.yml:105-326`, `roles/keystone/tasks/loadbalancer.yml:2-7`, `roles/loadbalancer-config/tasks/main.yml:2-8`, `roles/haproxy-config/tasks/main.yml:2-23, :25-53`, `group_vars/all.yml:931`; [fact sheet A §1.9](../reference/factsheets/a-infra-lb-ovn.md#19-what-exactly-happens-in-the-haproxy-play-for--t-service-and--t-haproxy); [Tags §2.2–2.3](../risk/tags.md#22-handlers-ignore-tags-code) |
| **`common` on every host of the service play**: **still not in 2024.1** | No role has a `meta/` directory (no meta dependency on `common`); `common` is a separate play on the `cron`, `fluentd`, `kolla-logs` and `kolla-toolbox` groups with `tags: common`, so it runs only under `-t common` or a run without tags | `site.yml:88-103`, `roles/common/tasks/main.yml:2`; [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) |
| **Keystone registration** (services, endpoints, projects, users, roles of those users, grants) | `register.yml` imports `service-ks-register` from `deploy.yml`, which `reconfigure.yml` imports | `roles/glance/tasks/register.yml:2-7`, `roles/service-ks-register/tasks/main.yml:3-126` |
| **DB creation/grants and DB schema sync** for most services, Neutron included (its `bootstrap_neutron` container has no `when`, [Reconfigure Neutron §2](reconfigure-neutron.md#2-execution-and-targets)) | `bootstrap.yml` imported by `deploy.yml` | [CODE] 12 one-shot container runs on a no-change redeploy of this service set (cell0 mapped; MariaDB, RabbitMQ and Fernet keys already bootstrapped): 8 DB-sync bootstraps (keystone, glance, placement, nova API, nova cell, neutron, cinder, heat) + map_cell0 + list_cells for cell0 (`roles/nova/tasks/map_cell0.yml:24-30`) + 2× list_cells, counted from each role's `bootstrap_service.yml` (`roles/keystone/tasks/bootstrap_service.yml:33-50`, `roles/glance/tasks/bootstrap_service.yml:19-37`, `roles/placement/tasks/bootstrap_service.yml:2-20`, `roles/neutron/tasks/bootstrap_service.yml:2-21`, `roles/cinder/tasks/bootstrap_service.yml:2-20`, `roles/heat/tasks/bootstrap_service.yml:2-30`; nova: [Reconfigure Nova §1.1](reconfigure-nova.md#11-reconfigure-nova-control-plane-and-computes), [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)) |
| **RabbitMQ user/vhost** (nova-cell only) | `service-rabbitmq`, imported from `nova-cell/tasks/bootstrap.yml` | `roles/nova-cell/tasks/bootstrap.yml:37`, `roles/nova-cell/tasks/rabbitmq.yml:3-29` |
| **Global MariaDB variable toggle** (`-t glance`) | `log_bin_trust_function_creators` 1→0 around the glance DB sync, unless `use_preconfigured_databases` | `roles/glance/tasks/bootstrap_service.yml:2-17, :39-54`; [fact sheet C §1](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#1-glance) |
| **Fernet key redistribution** (`-t keystone`) | `distribute_fernet.yml` | `roles/keystone/tasks/deploy.yml:15`; [fact sheet B §3.6](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#36-fernet-key-lifecycle-fact-unless-marked) (re-run on reconfigure: [§3.7](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#37-bootstrap-db-and-registration-what-re-runs-on-reconfigure)) |
| **Actions on hosts outside `--limit`** | `delegate_to` to `groups[...][0]`: Neutron DB bootstrap on neutron-server[0], cell discovery on conductor[0], RabbitMQ user creation on the first host of the cell's RPC (and notify) group | `roles/neutron/tasks/bootstrap.yml:13-14`, `bootstrap_service.yml:20-21`; `roles/nova-cell/tasks/discover_computes.yml:21`, `wait_discover_computes.yml:43`; `roles/nova-cell/tasks/rabbitmq.yml:12, :22`, `roles/service-rabbitmq/tasks/main.yml:42`; [Add a compute node §2](add-a-compute-node.md#2-add-a-compute-node) |
| **SIGHUP to every nova-scheduler** (`-t nova`/`nova-api`) | refresh play, on `deploy` and `reconfigure` | `nova.yml:152-172` |

What a service tag does **not** do: it never touches MariaDB, RabbitMQ or memcached *containers* (other plays), and it
never touches OVS (unless `-t openvswitch`), nor the `common` containers (fluentd, kolla_toolbox, cron). Under
`-t haproxy` or a no-tag run, the loadbalancer role's containers (HAProxy, keepalived, ProxySQL when enabled and, new
in 2024.1, `haproxy_ssh` when `enable_letsencrypt` is set, `roles/loadbalancer/defaults/main.yml:30-32`) are also
checked; a service tag touches only its frontend file (and, with the single external frontend, its block of the map).

[CODE] `-t haproxy reconfigure` on an unchanged cloud: the loadbalancer role on the 2 loadbalancer hosts
(`site.yml:105-120`, `inventory/multinode:84-85`); `common` does not run (its play is tagged `common` only,
`site.yml:88-103`). **Changed in 2024.1:** the play holds 39 frontend `include_role` tasks, not 44 (freezer, murano,
sahara, senlin, solum and vitrage are gone; letsencrypt is new). All 39 are evaluated; 12 run (placement's, which has
no `when`, and the 11 whose condition is true for this service set: cinder, glance, heat, horizon, keystone, mariadb,
memcached, neutron, nova, nova-cell, rabbitmq) and the other 27 are skipped by their `when`
(`site.yml:122-323`; defaults in `group_vars/all.yml`). Restarts follow only a task that reports changed ([Tags
§2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)); [NOT AVAILABLE] whether
any task does on an unchanged cloud.

## 3. Sequence, impact, risks and verification of `-t <svc> reconfigure`

For an API service such as keystone, glance, cinder, heat or placement:

1. The gather-facts and group_by plays run on all hosts (`tags: always`, `site.yml:2-75`).
2. loadbalancer play, on the loadbalancer hosts: only the `<svc>` include runs and renders `services.d/<svc>*.cfg`.
   The loadbalancer role's own tasks carry only the play tags (`haproxy`, `keepalived`, `loadbalancer`), not the
   `<svc>` tag, so they are skipped [CODE] (`site.yml:115-120`; [Tags
   §2.3](../risk/tags.md#23-include_role--tags-always-inside-the-haproxy-play-code)). If that file changed, HAProxy
   restarts on every loadbalancer host, staged [CODE]: the hosts are grouped by whether they hold the VIP
   (`roles/loadbalancer/handlers/main.yml:9-34`); HAProxy stops and starts on all backups together and the play waits
   for `haproxy_monitor_port` (`:54-68`, `:90-118`); then it stops and starts on the VIP holder and waits again
   (`:179-193`, `:224-252`) ([R8](../risk/risk-register.md#r8); [HAProxy +
   Keepalived](../components/haproxy-keepalived.md#before-and-after-a-run)). **Corrected in 2024.1:** the 2023.1 page
   said "on
   all loadbalancer hosts at once"; the handlers stage it, and this order is unchanged from 2023.1 apart from the
   module rename. Whether the VIP moves meanwhile is [NOT AVAILABLE].
3. Service play, on the service hosts: Keystone registration (`run_once`) → config → check-containers →
   DB/user creation and the DB-sync container on the first host → flush (e.g. `roles/glance/tasks/deploy.yml:2-15`;
   placement runs its clone step before config, `roles/placement/tasks/deploy.yml:2-14`). Every drifted host restarts
   all of the service's containers (loop-notify), all such hosts in parallel unless `ANSIBLE_SERIAL` is set. Keystone
   is the exception: it registers
   last ([§1.1](#11-reconfigure-a-single-service)).

**First 2024.1 run on a cloud deployed by 2023.1** [CODE]:

- If `kolla-ansible upgrade` has not reached the service, its image changes: `openstack_release` defaults to `2024.1`
  (`group_vars/all.yml:679-681`), the check compares the image (`module_utils/kolla_container_worker.py:75`), and the
  handler recreates the container on the 2024.1 image (`module_utils/kolla_docker_worker.py:353-361`), through the
  deploy path, without the role's upgrade tasks (e.g. `roles/keystone/tasks/upgrade.yml:23-31`). Upgrade it first.
- Every container whose unit no 2024.1 run has recreated or restarted yet drifts: `compare_container` also compares
  the systemd unit text (`module_utils/kolla_container_worker.py:58-65`,
  `module_utils/kolla_systemd_worker.py:154-167`),
  and the 2024.1 unit template differs from the one 2023.1 wrote; with Docker only the start-limit line differs
  ([F16](../reference/findings.md#f16)). A `kolla-ansible upgrade` that recreated the service's containers already
  wrote the new units. The services that talk to RabbitMQ
  also render `rabbit_quorum_queue = true` by default (`group_vars/all.yml:268`; e.g.
  `roles/keystone/templates/keystone.conf.j2:77-78`, `roles/glance/templates/glance-api.conf.j2:139-140`,
  `roles/cinder/templates/cinder.conf.j2:90-91`, `roles/heat/templates/heat.conf.j2:89-90`;
  [F17](../reference/findings.md#f17)). So the first run on a service not yet upgraded restarts it on all its hosts
  at once, unless `ANSIBLE_SERIAL` is set.
- For keystone, the `balance` line of both frontends is now written `balance roundrobin` instead of
  `balance "roundrobin"` (`roles/keystone/defaults/main.yml:20, :30`), and the template copies it as is
  (`roles/haproxy-config/templates/haproxy_single_service_split.cfg.j2:77-79`): the rendered
  `services.d/keystone.cfg` changes and HAProxy restarts. With TLS on, every frontend's `bind` line also gains
  `alpn h2,http/1.1` (`haproxy_enable_http2: "yes"`, `group_vars/all.yml:920-921`; template `:2-5`). Whether the
  frontends of the other services render differently is [NOT AVAILABLE] (not rendered here); the diff of the
  verification below shows it.

- **Interruption:** the service API is unavailable while its containers restart on all drifted hosts at once. A config
  drift goes through a systemd `RestartUnit` of the container's unit, a container drift (image, volumes) through a
  stop, remove and start (`module_utils/kolla_docker_worker.py:341-363`, `:415-431`, `:439-459`;
  `module_utils/kolla_systemd_worker.py:106-125`). Either way the stop is the unit's
  `ExecStop=/usr/bin/<engine> stop <name> -t <graceful_timeout>` (`module_utils/kolla_systemd_worker.py:32`), with
  `docker_graceful_timeout`, 60 s by default, passed through `docker_common_options` (`group_vars/all.yml:139, :151`):
  up to 60 s between SIGTERM and SIGKILL, then the start. Add the HAProxy restart window if the frontend changed.
- **VM impact:** these services restart none of the containers that [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) traces to running VMs
  [CODE]; any other effect on VMs is [NOT AVAILABLE]. In-flight glance or cinder transfers are SIGKILLed if still
  running `docker_graceful_timeout` (60 s by default) after SIGTERM ([R24](../risk/risk-register.md#r24)). Of the tags
  in
  Tags §3.1, the ones that can restart those containers are `nova`, `nova-cell`, `neutron`, `openvswitch`, `ovn` (with
  `ovn-controller` and `ovn-db`, `site.yml:653, :669`), `iscsi` and `baremetal` (run by `bootstrap-servers` through
  `openstack.kolla.baremetal`, `kolla-host.yml:4-14`, not `reconfigure`; Docker restart,
  [R14](../risk/risk-register.md#r14)) [CODE]; what those restarts do to running VMs is [NOT AVAILABLE]. Running on
  computes is not the test: `common` runs on every compute (`inventory/multinode:49-54, :202-213`) but restarts only
  fluentd, kolla_toolbox and cron (`roles/common/defaults/main.yml:4, :13, :25`). `chrony` still has no role or play.
- **Risks:** [R8](../risk/risk-register.md#r8) (HAProxy restart), [R19](../risk/risk-register.md#r19) (Keystone),
  [R20](../risk/risk-register.md#r20) (glance file backend), [R23](../risk/risk-register.md#r23) (`--limit` on a large
  inventory), [R24](../risk/risk-register.md#r24) (SIGKILL after `docker_graceful_timeout`).
- **Verification:**
  - before: copy `/etc/kolla/haproxy/services.d/<svc>*.cfg` from a loadbalancer host, run
    `kolla-ansible -t <svc> genconfig`, then `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check;
    echo $?` in each `<svc>` container (without `-u root` it exits 2 in images that run as a service user, e.g.
    glance-api; [Kolla images §3.4](../concepts/kolla-images.md#34-running-it-by-hand-needs-root)) and diff the frontend
    against the copy;
  - **caveat on `genconfig`** [CODE]: `genconfig` runs with `kolla_action=config` (`tools/kolla-ansible:557-559`), for
    which the loadbalancer block also runs (`site.yml:326`) and writes `services.d/<svc>*.cfg`
    (`roles/haproxy-config/tasks/main.yml:2-23`), while every loadbalancer restart handler is skipped
    (`roles/loadbalancer/handlers/main.yml:16-17` and the same condition on each handler). In the following `-t <svc>
    reconfigure` the template task finds the file already written and notifies nothing, and the loadbalancer
    check-containers task, which would see the difference through `kolla_set_configs --check`
    (`roles/loadbalancer/tasks/check-containers.yml:2-18`; `services.d/` is copied into the container,
    `roles/loadbalancer/templates/haproxy/haproxy.json.j2:17-18`), does not run under a service tag. So the new
    frontend reaches HAProxy only through a `-t haproxy reconfigure` (or a run without tags). The service containers
    are not affected: their check-containers task does run;
  - after: `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers (each
    `name` in `<svc>_ks_services`, e.g. `cinderv3` only for cinder (`roles/cinder/defaults/main.yml:335-341`), `heat`
    and `heat-cfn` for heat (`roles/heat/defaults/main.yml:218-230`)), the API answers through the VIP, the container
    start times show which hosts restarted, and `docker ps --filter name=haproxy` shows whether HAProxy restarted
    (`kolla_container_engine` defaults to `docker`, `group_vars/all.yml:92`; with Podman, use `podman`).

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R8](../risk/risk-register.md#r8) (HAProxy
  restart), [R19](../risk/risk-register.md#r19) (Keystone), [R20](../risk/risk-register.md#r20) (glance file backend),
  [R23](../risk/risk-register.md#r23) (`--limit` on a large inventory), [R24](../risk/risk-register.md#r24) (SIGKILL
  after `docker_graceful_timeout`) and [R14](../risk/risk-register.md#r14) (Docker restart by `bootstrap-servers`)
- [Technical findings](../reference/findings.md) — [F16](../reference/findings.md#f16) (the changed systemd unit
  template) and [F17](../reference/findings.md#f17) (quorum queues on by default), the two causes of drift on the first
  2024.1 run
- [Keystone](../components/keystone.md) — service card and where to look for the service of the §1.1 example
- [HAProxy + Keepalived](../components/haproxy-keepalived.md) — service card and where to look for HAProxy, including
  the staged restart order and the loadbalancer play under a service tag
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Predict and inspect a run](predict-a-run.md) — `genconfig` and the exit codes of `kolla_set_configs --check`, used
  in the verification of §3
- [Tags §2](../risk/tags.md#2-ansible-29-semantics-that-kolla-relies-on) — the semantics behind the implicit effects:
  tag inheritance, handlers that ignore tags, the haproxy play, loop-notify
- [Command quick lookup by tag](command-quick-lookup.md) — hosts touched, possible restarts and one-shot containers
  per tag
