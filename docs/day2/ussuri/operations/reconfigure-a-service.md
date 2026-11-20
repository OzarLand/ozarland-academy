---
title: Reconfigure a single service
description: What a single-service reconfigure such as -t keystone runs, what the tag also touches, what restarts on drift, the risks and the verification.
tags: [keystone, glance, placement, cinder, heat, haproxy, reconfigure, tags, loop-notify, one-shot, limit]
remember:
  - "A changed <code>services.d/&lt;svc&gt;*.cfg</code> restarts HAProxy on all haproxy hosts at once; add <code>--skip-tags haproxy</code> when frontends are not meant to change."
  - "On each drifted host all the service's containers restart, all such hosts in parallel unless <code>ANSIBLE_SERIAL</code> is set: a change common to all hosts then restarts the service on all its hosts at once."
  - "Even a narrow tag also touches the service's HAProxy frontends, Keystone registration, DB sync and <code>common</code> on every host of the service play."
  - "The service API is unavailable while its containers restart (up to 10 s stop, then start) on all its hosts at once."
  - "Before: <code>-t &lt;svc&gt; genconfig</code>, then <code>kolla_set_configs --check</code> with <code>-u root</code> in each container and a diff of the <code>services.d</code> file."
impact: [restarts-on-drift]
scenarios:
  - title: "A glance change during business hours"
    situation: "You changed an option in <code>glance-api.conf</code> that applies to every glance host. A user team is transferring large images to glance all afternoon. Your colleague suggests running <code>kolla-ansible -i multinode -t glance reconfigure</code> right now, since only one service is concerned."
    ask: "What would you do?"
    choices:
      - text: "Run it now with <code>--skip-tags haproxy</code>, so that the API stays up."
        verdict: "risky"
        why: "<code>--skip-tags haproxy</code> only drops the haproxy play (the frontends). The glance containers still restart on every drifted host, and the service API is unavailable while its containers restart (up to 10 s stop, then start) on all its hosts at once."
      - text: "Run it now: only drifted hosts restart, so the transfers are safe."
        verdict: "avoid"
        why: "Without <code>ANSIBLE_SERIAL</code>, drifted hosts restart in parallel, so a change common to all hosts restarts the service on all its hosts at once. In-flight glance or cinder transfers are SIGKILLed after 10 s (R24)."
      - text: "Run <code>kolla-ansible -t glance genconfig</code>, check each glance container with <code>docker exec -u root &lt;c&gt; /usr/local/bin/kolla_set_configs --check; echo $?</code>, diff <code>/etc/kolla/haproxy/services.d/glance*.cfg</code>, and run the <code>reconfigure</code> in a window with no transfers in flight."
        verdict: "best"
        why: "This is the \"before\" verification of §3 (genconfig, the check as root in each container, a diff of the HAProxy frontend), and it avoids R24: in-flight glance transfers are SIGKILLed after 10 s while the containers restart."
    see: "3-sequence-impact-risks-and-verification-of--t-svc-reconfigure"
quiz:
  - q: "During <code>-t keystone reconfigure</code>, one keystone container drifted on a host. What restarts on that host?"
    options: ["Only the container that drifted", "All the keystone containers of that host"]
    answer: 1
    explain: "This is loop-notify: a change that concerns one container restarts every container of that role on that host."
    see: "11-reconfigure-a-single-service"
  - q: "Do keystone hosts without drift restart?"
    options: ["Yes, every keystone host restarts", "No: only drifted hosts restart, in parallel"]
    answer: 1
    explain: "A change common to all hosts (globals, <code>keystone.conf</code>, a new image) therefore restarts keystone on all keystone hosts at once."
    see: "11-reconfigure-a-single-service"
  - q: "How do you keep HAProxy untouched during a service run?"
    options: ["With <code>--limit</code>", "With <code>--skip-tags haproxy</code>"]
    answer: 1
    explain: "<code>--skip-tags haproxy</code> drops the whole haproxy play, including the per-service frontend includes."
    see: "12-avoid-touching-haproxy-during-a-service-run"
---

# Reconfigure a single service

What `kolla-ansible -t <svc> reconfigure` does for one API service, with keystone as the command example: after the
gather-facts and group_by plays, which run on all hosts, the haproxy play runs on the haproxy hosts (the service's
frontend, and a HAProxy restart if the rendered frontend changed) and the service play on the service hosts (`common`,
then the service's containers, all of which restart on every drifted host). The page also says what a narrow tag touches
besides the service.

The scenario sections are written for the [assumed deployment](index.md#assumed-deployment); the page uses the
[conventions of the command sections](index.md#conventions-used-by-the-command-sections), the definition of
[drift](index.md#drift) and the notion of [code guarantees and environment
dependence](index.md#code-guarantees-and-environment-dependence).

> [!WARNING]
> [R8](../risk/risk-register.md#r8): a changed `services.d/<svc>*.cfg` restarts HAProxy on all haproxy hosts — see
> [§1.2](#12-avoid-touching-haproxy-during-a-service-run) and
> [§3](#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure).

## 1. Commands

### 1.1 Reconfigure a single service

```bash
kolla-ansible -i multinode -t keystone reconfigure
```

- **Scope:**
  - haproxy play: keystone frontend only, on haproxy hosts;
  - keystone play: `common` on keystone hosts, then config, check-containers, bootstrap (db sync), a handler flush
    (restarts happen here), Fernet key distribution, Keystone registration and the sanity check
    (`roles/keystone/tasks/deploy.yml`; the sanity check is off by default, `kolla_enable_sanity_checks`). Unlike
    glance, placement, neutron and nova, keystone registers last.
- **Restarts:**
  - haproxy, on all haproxy hosts, only if the frontend changed;
  - per host (loop-notify): on each keystone host where any keystone container drifted, all keystone containers of
    that host restart (`keystone`, plus `keystone_ssh` and `keystone_fernet` with Fernet tokens). Hosts without drift
    do not restart. Without `ANSIBLE_SERIAL`, drifted hosts restart in parallel, so a change common to all hosts
    (globals, `keystone.conf`, a
    new image) restarts keystone on all keystone hosts at once.
- **One-shot:** keystone db sync. Fernet keys are re-distributed.
- **Impact:** if restarted, keystone restarts on all drifted hosts at once; [NOT AVAILABLE] whether authentication fails
  meanwhile, and for how long ([Risk register R19](../risk/risk-register.md#r19)).

### 1.2 Avoid touching HAProxy during a service run

```bash
kolla-ansible -i multinode -t nova --skip-tags haproxy reconfigure
```

- `--skip-tags haproxy` drops the whole haproxy play, including the per-service frontend includes.
- Use it when frontends are not meant to change. Otherwise a changed `services.d/<svc>*.cfg` restarts HAProxy on all
  haproxy hosts.

## 2. Execute a service-specific tag: implicit effects

Even with a narrow tag, the code guarantees that the run also touches:

| Implicit effect | Mechanism | Evidence |
|---|---|---|
| **HAProxy frontends of the service, on all haproxy hosts**, and a HAProxy restart if the rendered frontend changed | haproxy play includes `<svc>/loadbalancer.yml` under the same tag; `haproxy-config` is `tags: always`; handlers ignore tags | `site.yml:126-392`; [fact sheet A §1.9](../reference/factsheets/a-infra-lb-ovn.md#19-what-exactly-happens-in-the-haproxy-play-for--t-service-and--t-haproxy); [Tags §2.2–2.3](../risk/tags.md#22-handlers-ignore-tags-code) |
| **`common` on every host of the service play** (fluentd/cron/toolbox config + container check, restarts if drift) | meta dependency inherits the tag; first-play rule | `roles/nova/meta/main.yml:3`, `roles/common/tasks/main.yml:1-10`; [Tags §2.1](../risk/tags.md#21-dynamic-include_tasks-and-tag-inheritance-code) |
| **Keystone registration** (service, endpoints, user, role) | `register.yml` in `deploy.yml`/`reconfigure.yml` | `service-ks-register` |
| **DB creation/grants and DB schema sync** for most services (Neutron's DB sync: `deploy` only by default, [Reconfigure Neutron §2](reconfigure-neutron.md#2-execution-and-targets)) | `bootstrap.yml` imported by `deploy.yml` | [CODE] 11 one-shot container runs on a no-change redeploy of this service set (cell0 mapped; MariaDB, RabbitMQ and Fernet keys already bootstrapped): 8 DB-sync bootstraps (keystone, glance, placement, nova API, nova cell, neutron, cinder, heat) + map_cell0 + 2× list_cells, counted from each role's `bootstrap_service.yml` (nova: [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table)) |
| **RabbitMQ user/vhost** (nova-cell only) | `service-rabbitmq` | `nova-cell/tasks/rabbitmq.yml` |
| **Global MariaDB variable toggle** (`-t glance`) | `log_bin_trust_function_creators` 1→0 | [fact sheet C §1](../reference/factsheets/c-glance-placement-cinder-horizon-heat.md#1-glance) |
| **Fernet key redistribution** (`-t keystone`) | `distribute_fernet.yml` | [fact sheet B §3.6](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#36-fernet-key-lifecycle-fact-unless-marked) (re-run on reconfigure: [§3.7](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#37-bootstrap-db-and-registration-what-re-runs-on-reconfigure)) |
| **Actions on hosts outside `--limit`** | `delegate_to` to `groups[...][0]`: Neutron DB bootstrap on neutron-server[0], cell list/discovery on conductor[0], RabbitMQ user creation on rabbitmq[0] | `roles/neutron/tasks/bootstrap.yml:12-13`, `bootstrap_service.yml:19-20`; `roles/nova-cell/tasks/discover_computes.yml:21`, `wait_discover_computes.yml:42`; `roles/nova-cell/tasks/rabbitmq.yml:12, :22`; [Add a compute node §2](add-a-compute-node.md#2-add-a-compute-node) |
| **SIGHUP to every nova-scheduler** (`-t nova`/`nova-api`) | refresh play | `nova.yml:140-156` |

What a service tag does **not** do: it never touches MariaDB, RabbitMQ or memcached *containers* (other plays), and it
never touches OVS (unless `-t openvswitch`). Under `-t haproxy` or a no-tag run, HAProxy and keepalived *containers*
are also checked; a service tag touches only its frontend file.

[CODE] `-t haproxy reconfigure` on an unchanged cloud: `common` + haproxy role on the 2 haproxy hosts
(`site.yml:126-136`, `inventory/multinode:91-92`). All 49 frontend `include_role` tasks are evaluated; 12 run
(placement's, which has no `when`, and the 11 whose `enable_<svc>` is true for this service set) and the other 37 are
skipped by `when: enable_<svc>` (`site.yml:138-389`). Restarts follow only a task that reports changed ([Tags
§2.4](../risk/tags.md#24-loop-notify-one-changed-item-notifies-the-handlers-of-all-items-code)); [NOT AVAILABLE] whether
any task does on an unchanged cloud.

## 3. Sequence, impact, risks and verification of `-t <svc> reconfigure`

For an API service such as keystone, glance, cinder, heat or placement:

1. The gather-facts and group_by plays run on all hosts (`tags: always`).
2. haproxy play, on the haproxy hosts: only the `<svc>` include runs and renders `services.d/<svc>*.cfg`. `common` (a
   meta dependency of the haproxy role) and the haproxy role's own tasks do not carry the `<svc>` tag, so they are
   skipped [CODE] ([Tags §2.3](../risk/tags.md#23-include_role--tags-always-inside-the-haproxy-play-code)). HAProxy
   restarts on all haproxy hosts at once if that file changed ([R8](../risk/risk-register.md#r8)).
3. Service play, on the service hosts: `common` → Keystone registration (`run_once`) → config → check-containers →
   DB/user creation and the DB-sync container on the first host → flush. Every drifted host restarts all of the
   service's containers (loop-notify), all such hosts in parallel unless `ANSIBLE_SERIAL` batches the play. Keystone is
   the exception: it registers last
   ([§1.1](#11-reconfigure-a-single-service)).

- **Interruption:** the service API is unavailable while its containers restart (up to 10 s stop, then start) on all
  its hosts at once. Add the HAProxy restart window if the frontend changed.
- **VM impact:** these services restart none of the containers that [Tags
  §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites) traces to running VMs
  [CODE]; any other effect on VMs is [NOT AVAILABLE]. In-flight glance or cinder transfers are SIGKILLed after 10 s
  ([R24](../risk/risk-register.md#r24)). Of the tags in Tags §3.1, the ones that can restart those containers are
  `nova`, `nova-cell`, `neutron`, `openvswitch`, `ovn`, `iscsi` and `baremetal` (run by `bootstrap-servers`, not
  `reconfigure`; Docker restart, [R14](../risk/risk-register.md#r14)) [CODE]; what those restarts do to running VMs is
  [NOT AVAILABLE]. Running on computes is not the test: `chrony` runs on every compute but restarts none of those
  containers.
- **Risks:** [R8](../risk/risk-register.md#r8) (HAProxy restart), [R19](../risk/risk-register.md#r19) (Keystone),
  [R20](../risk/risk-register.md#r20) (glance file backend), [R23](../risk/risk-register.md#r23) (`--limit` on a large
  inventory), [R24](../risk/risk-register.md#r24) (10 s SIGKILL).
- **Verification:**
  - before: `kolla-ansible -t <svc> genconfig`, then `docker exec -u root <c> /usr/local/bin/kolla_set_configs --check;
    echo $?` in each `<svc>` container (without `-u root` it exits 2 in images that run as a service user, e.g.
    glance-api; [Kolla images §3.4](../concepts/kolla-images.md#34-running-it-by-hand-needs-root)) and a diff of
    `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  - after: `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers (each
    `name` in `<svc>_ks_services`, e.g. `cinderv2` and `cinderv3` for cinder, `heat` and `heat-cfn` for heat), the API
    answers through the VIP, the container start times show which hosts restarted, and
    `docker ps --filter name=haproxy` shows whether HAProxy restarted.

## Related

- [Risk register](../risk/risk-register.md) — the risks this page names: [R8](../risk/risk-register.md#r8) (HAProxy
  restart), [R19](../risk/risk-register.md#r19) (Keystone), [R20](../risk/risk-register.md#r20) (glance file backend),
  [R23](../risk/risk-register.md#r23) (`--limit` on a large inventory), [R24](../risk/risk-register.md#r24) (10 s
  SIGKILL) and [R14](../risk/risk-register.md#r14) (Docker restart by `bootstrap-servers`)
- [Keystone](../components/keystone.md) — service card and where to look for the service of the §1.1 example
- [HAProxy + Keepalived](../components/haproxy-keepalived.md) — service card and where to look for HAProxy, including
  the haproxy play under a service tag
- [Pre-execution checklist](pre-execution-checklist.md) — the checks before every production run
- [Predict and inspect a run](predict-a-run.md) — `genconfig` and the exit codes of `kolla_set_configs --check`, used
  in the verification of §3
- [Tags §2](../risk/tags.md#2-ansible-29-semantics-that-kolla-relies-on) — the Ansible 2.9 semantics behind the
  implicit effects: tag inheritance, handlers that ignore tags, the haproxy play, loop-notify
- [Command quick lookup by tag](command-quick-lookup.md) — hosts touched, possible restarts and one-shot containers
  per tag
