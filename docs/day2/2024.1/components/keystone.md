---
title: Keystone
description: Where the 2024.1 study covers Keystone (role keystone), from the reconfigure and its restart risk to the removed admin endpoint, Fernet keys and open points.
tags: [keystone, reconfigure, serial, one-shot, risk, dependencies, bugs, unknowns]
---

# Keystone

This page is the starting point for Keystone, the `keystone` role: the containers `keystone`, `keystone_ssh` and
`keystone_fernet` (`roles/keystone/defaults/main.yml:2-56`), on the control nodes of the example inventory
(`inventory/multinode:93-94`), selected by the tag `keystone` (`site.yml:483-495`). Keystone is a hard deploy-time
dependency of the 31 roles whose tasks use `service-ks-register` (keystone itself included; grep of `roles/*/tasks`;
2023.1 had 37, the difference being the removed roles freezer, murano, sahara, senlin, solum and vitrage): registration
runs `run_once` (`roles/service-ks-register/tasks/main.yml:125-126`) with `openstack_interface` (`internal`) and
authenticates against `keystone_internal_url` (`roles/service-ks-register/defaults/main.yml:5`,
`group_vars/all.yml:710`, `group_vars/all.yml:990-991`) [CODE] ([Component
dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses)). The lists below say where
the study covers how to operate it, its impact, its dependencies and the evidence, what to check around a run and what
stays open; the service card follows them.

## What changed in 2024.1

- **The admin port and admin endpoint code is gone** [CODE]. 2024.1 defines no `keystone_admin_port`,
  `keystone_admin_listen_port`, `keystone_admin_url` or `admin_protocol` (no match under `ansible/`). The Keystone ports
  are now `keystone_public_port`, `keystone_public_listen_port: "5000"`, `keystone_internal_port: "5000"` and
  `keystone_internal_listen_port` (`group_vars/all.yml:444-447`). The `keystone_admin` HAProxy entry that 2023.1 kept
  for upgrades is removed: the role defines only `keystone_internal` and `keystone_external`
  (`roles/keystone/defaults/main.yml:11-30`), and Apache listens on `keystone_public_listen_port` only, with one
  virtual host (`roles/keystone/templates/wsgi-keystone.conf.j2:10`,
  `roles/keystone/templates/wsgi-keystone.conf.j2:36`).
- **No step removes an admin endpoint any more** [CODE]. `keystone_service_endpoints` lists only `internal` and
  `public` (`roles/keystone/defaults/main.yml:200-202`); the 2023.1 `admin` entry with `state: absent` is gone, and
  `service-ks-register` no longer passes a `state` to `os_keystone_endpoint`
  (`roles/service-ks-register/tasks/main.yml:24-46`). `upgrade.yml` ends with the database steps
  (`roles/keystone/tasks/upgrade.yml:1-50`): the 2023.1 import of `service-ks-register` that removed the admin endpoint
  during an upgrade is not there. An `admin` endpoint still present in the catalogue is therefore left as it is by
  2024.1 code; whether one is present on a given platform is [NOT AVAILABLE]. The bootstrap wrapper is called with seven
  arguments, without an admin URL (`roles/keystone/tasks/register.yml:4-7`), which the kolla script treats as its
  "modern mode" (kolla `docker/keystone/keystone/keystone_bootstrap.sh:19-30`).
- **URLs are built with the `kolla_url` filter** [CODE]. `keystone_internal_url` and `keystone_public_url` are
  `<fqdn> | kolla_url(<protocol>, <port>)` (`group_vars/all.yml:960-961`); the filter is registered in
  `filter_plugins/address.py:25-30`. It puts the address in URL context (IPv6 in brackets) and omits the port for `http`
  on 80 and `https` on 443 (`kolla_ansible/kolla_url.py:20-41`). The internal URL now uses `keystone_internal_port`;
  2023.1 used `keystone_public_port` for both URLs.
- **`keystone_public_port` follows the single external frontend option** [CODE]: with
  `haproxy_single_external_frontend` (default `false`) it becomes 443 or 80 (`group_vars/all.yml:444`,
  `group_vars/all.yml:931-932`), so `keystone_public_url` then carries no port; `keystone_public_listen_port` stays
  `5000` (`group_vars/all.yml:445`). With the option on, the `haproxy-config` role also writes an
  `external-frontend-map` block per service, which notifies the HAProxy restart
  (`roles/haproxy-config/tasks/main.yml:25-53`).
- **Port pairing to keep in mind** [CODE]: the internal frontend sends to `keystone_internal_listen_port`
  (`roles/keystone/defaults/main.yml:17-18`) while Apache listens on `keystone_public_listen_port`
  (`roles/keystone/templates/wsgi-keystone.conf.j2:10`). Both are 5000 by default (`group_vars/all.yml:445-447`); an
  override of one without the other would make the backend port differ from the listening port. What a platform has
  overridden is [NOT AVAILABLE].
- **New messaging options in `keystone.conf`** [CODE]: with the default quorum queues, `rabbit_quorum_queue = true` is
  rendered (`roles/keystone/templates/keystone.conf.j2:77-86`, `group_vars/all.yml:268`; see
  [F17](../reference/findings.md#f17)). With `om_enable_queue_manager` (default `false`, `group_vars/all.yml:269`) the
  `keystone` container also mounts `/dev/shm` (`roles/keystone/defaults/main.yml:159`) and `keystone.conf` gets
  `use_queue_manager` (`roles/keystone/templates/keystone.conf.j2:63-68`) and a `[oslo_concurrency]` lock path
  (`roles/keystone/templates/keystone.conf.j2:116-119`). The
  `processname` line of that block is guarded by `service_name == 'keystone-api'`, but the file is rendered with
  `service_name` set to the `keystone_services` keys `keystone` and `keystone-fernet`
  (`roles/keystone/tasks/config.yml:60-74`), so that line is never rendered [CODE].
- **Role assignments**: `service-ks-register` now grants a role on a project, a domain or the system
  (`roles/service-ks-register/tasks/main.yml:103-119`), and the keystone role no longer passes a list of extra roles to
  register (`roles/keystone/tasks/register.yml:14-19`) [CODE].
- **Still holds in 2024.1** [CODE]: the handlers are the same five, in the same order, with the module renamed
  `kolla_container` (`roles/keystone/handlers/main.yml:5-98`); the play still takes `serial` from `kolla_serial`,
  default `0` (`site.yml:488`), and now also sets `max_fail_percentage`, default 100 (`site.yml:489-492`), which never
  stops the play early
  ([Controlled batches §1.3](../operations/controlled-batches.md#13-stop-a-rolling-run-on-failures-max_fail_percentage)).

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Command:** [Reconfigure a single service
  §1.1](../operations/reconfigure-a-service.md#11-reconfigure-a-single-service)
- **Membership:** [Change control-plane membership](../operations/change-control-plane-membership.md): adding or
  removing a keystone host changes the Fernet rotation schedule and the push targets on every keystone host.

### Impact and risk

- **What the tag executes (`keystone`):** [Tags §3](../risk/tags.md#3-what-a-tag-really-executes-master-table), row
  `<svc>`; [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row
  `<svc>` API service
- **Risks:** [R19](../risk/risk-register.md#r19), [R8](../risk/risk-register.md#r8), [R24](../risk/risk-register.md#r24)

### Dependencies

- **Dependencies:** [Component dependencies
  §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses), [Component dependencies
  §3](dependencies.md#3-control-plane-services)

### Evidence

- **Fact sheet:** [fact sheet B
  §3](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#3-keystone-ansibleroleskeystone)
- **Image side:** [Kolla images
  §4](../concepts/kolla-images.md#4-one-shot-containers-what-the-environment-variables-run) (row `keystone`), [Kolla
  images §4.1](../concepts/kolla-images.md#41-one-shots-that-bypass-kolla_start), [Kolla images
  §5](../concepts/kolla-images.md#5-per-image-start-behaviour)
- **Also:** handlers: [Tags §5](../risk/tags.md#5-role--handler-map-core-services)

### Before and after a run

- [Tags §3.1](../risk/tags.md#31-per-tag-answers-files-vms-apis-networkingstorage-safety-prerequisites), row `<svc>` API
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync"; batch with
  `ANSIBLE_SERIAL`. Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP.
- [R19](../risk/risk-register.md#r19), precautions for a Keystone `reconfigure`: `ANSIBLE_SERIAL`; verify fernet key
  consistency before and after.
- With the default serial 0, a reconfigure with a config change restarts `keystone_ssh`, then `keystone_fernet`, then
  `keystone`, in the handler definition order (`roles/keystone/handlers/main.yml:29-75`), each on all keystone hosts of
  the play at once (`site.yml:488`) [CODE]. Set `ANSIBLE_SERIAL` for a rolling reconfigure. The details are in [fact
  sheet B
  §3.9](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#39-operationally-notable-behaviour-risks-and-oddities).
- `ANSIBLE_SERIAL` has a limit on a first deployment: when no host of the run so far was found with a running
  `keystone_fernet` container and some keystone hosts are outside the current batch, the role fails on purpose rather
  than bootstrap the Fernet keys
  (`roles/keystone/tasks/bootstrap_service.yml:22-31`) [CODE].
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `ANSIBLE_SERIAL=1` for haproxy changes;
  `--skip-tags haproxy` when you don't intend to change frontends.
- [R24](../risk/risk-register.md#r24), container stop timeout: in 2024.1 the stop goes through the container's systemd
  unit, whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:32`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:139`)
  ([F3](../reference/findings.md#f3)). Precautions: drain long operations before restarts; raise
  `docker_graceful_timeout` if needed. The first 2024.1 check of a container whose unit 2023.1 wrote reports drift
  ([F16](../reference/findings.md#f16)).
- [R22](../risk/risk-register.md#r22), precautions for an inventory reordering (the keystone group is one of the groups
  it names): treat inventory order as configuration; never reorder casually. For Keystone the order matters because the
  Fernet rotation schedule of each host is computed from its index in `groups['keystone']`
  (`roles/keystone/tasks/config.yml:195-200`) [CODE].
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible -t <svc> genconfig`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, the API
  answers through the VIP, the container start times show which hosts restarted, and the haproxy container's start time
  shows whether HAProxy restarted. For Keystone, the endpoint list has an `internal` and a `public` endpoint only
  (`roles/keystone/defaults/main.yml:200-208`); an `admin` endpoint left from an older release is not removed by 2024.1
  code (see [What changed in 2024.1](#what-changed-in-20241)).

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `keystone`: fernet cron generator
  hour calculation; precheck vs generator expiry limits; push script stops at the first unreachable peer. Status: all
  three still hold in 2024.1 [CODE], and the files involved are unchanged from 2023.1: the generator computes
  `hour = time % HOUR_SPAN` (`roles/keystone/files/fernet_rotate_cron_generator.py:69`); the precheck asserts
  `fernet_token_expiry <= 604800` (`roles/keystone/tasks/precheck.yml:43-53`) while the generator is fed
  `fernet_key_rotation_interval` (`roles/keystone/tasks/config.yml:195-200`); `fernet-push.sh` runs under
  `set -o errexit` and rsyncs to each peer in turn (`roles/keystone/templates/fernet-push.sh.j2:3-4`,
  `roles/keystone/templates/fernet-push.sh.j2:17-22`).
- The key distribution after a deploy or reconfigure is one `fernet-push.sh` run, `run_once`, on the first host where
  `keystone_fernet` was found running, or on the first keystone host when none was
  (`roles/keystone/tasks/distribute_fernet.yml:12-18`) [CODE].
- [Q11](../troubleshooting/open-questions.md#q11): "Fernet key distribution failure modes". Status: [NOT AVAILABLE].
- [What is not
  known](../troubleshooting/what-is-not-known.md#control-plane-haproxy-mariadb-rabbitmq-keystone-memcached-heat), row
  "Keystone": the sources do not establish whether authentication, and so the other services' API requests, fails while
  keystone restarts or is down ([R19](../risk/risk-register.md#r19)); Fernet key distribution failure modes
  ([Q11](../troubleshooting/open-questions.md#q11)); whether Keystone still reads a removed policy file after the
  restart; the upstream semantics of `keystone-manage bootstrap`; whether the `keystone_fernet` container restarts when
  key 0 is missing.
- [What is not known](../troubleshooting/what-is-not-known.md#signals-the-container-runtime-and-image-start-behaviour):
  the sources do not establish whether the SSH clients accept the new `nova_ssh` and `keystone_ssh` host keys after a
  recreate without failing.
- [F5](../reference/findings.md#f5), "`reconfigure` = `deploy`": a reconfigure re-runs Keystone registration, DB
  creation/grants and the DB-sync bootstrap containers of most services [CODE]. For Keystone, the deploy flow runs
  config, check-containers, bootstrap, the handlers, key distribution, then registration
  (`roles/keystone/tasks/deploy.yml:1-21`).
- [fact sheet B
  §3.9](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#39-operationally-notable-behaviour-risks-and-oddities),
  "Operationally notable behaviour, risks and oddities" of the keystone role.
- [fact sheet B §3.10][sheet-b-310]: NOT AVAILABLE: whether the API services whose `[keystone_authtoken]` sections point
  keystonemiddleware at Keystone fail to authenticate requests while Keystone or memcached is unavailable.
- [Kolla images §5](../concepts/kolla-images.md#5-per-image-start-behaviour), row `keystone-fernet`: without key 0 on
  the node the start waits up to 10 × 60 s and the script exits 1 before the cron command is exec'd, so no rotation cron
  runs there meanwhile (`roles/keystone/templates/fernet-node-sync.sh.j2:15-28`) [CODE]; whether the container then
  restarts is [NOT AVAILABLE].
- [Kolla images §6](../concepts/kolla-images.md#6-day-2-consequences), item 18: SSH host keys of `nova_ssh` and
  `keystone_ssh` change on every recreate, because `/etc/ssh` is on no volume
  (`roles/keystone/defaults/main.yml:36-41`);
  the keystone SSH client sets `StrictHostKeyChecking no` and `UserKnownHostsFile /dev/null`
  (`roles/keystone/templates/ssh_config.j2:2-3`) [CODE]; whether the SSH client then accepts the new keys without
  failing is [NOT AVAILABLE: OpenSSH semantics].
- [Kolla images §7](../concepts/kolla-images.md#7-what-is-not-available-from-the-sources): not available from the
  sources: the upstream semantics of `keystone-manage bootstrap`, in particular whether it resets the admin password to
  `keystone_admin_password`.

## Service card

The rows of the card are explained on the [Components](index.md#how-to-read-a-service-card) page.

<!-- BEGIN GENERATED: tools/service_cards.py keystone -->

| Item | Value |
|---|---|
| Play | site.yml:483 |
| Tags | keystone |
| Play host patterns | keystone |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `keystone`, `keystone_ssh`, `keystone_fernet` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → clone (if) → bootstrap → flush handlers → distribute_fernet → register → register_identity_providers (if) |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, clone.yml, config-federation-oidc.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, distribute_fernet.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, register_identity_providers.yml, stop.yml, upgrade.yml |
| Templates | `crontab.j2`, `fernet-healthcheck.sh.j2`, `fernet-node-sync.sh.j2`, `fernet-push.sh.j2`, `fernet-rotate.sh.j2`, `keystone-fernet.json.j2`, `keystone-ssh.json.j2`, `keystone-startup.sh.j2`, `keystone.conf.j2`, `keystone.json.j2`, `ssh_config.j2`, `sshd_config.j2`, `wsgi-keystone.conf.j2` |
| Handlers (definition order) | Init keystone database upgrade; Restart keystone-ssh container; Restart keystone-fernet container; Restart keystone container; Finish keystone database upgrade |
| Key variables | `enable_keystone`, `keystone_token_provider`, `fernet_token_expiry`, `fernet_key_rotation_interval` |
| Role dependencies | none |

<!-- END GENERATED -->

## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — `-t keystone reconfigure`, the command
  example of the page: scope, restarts and one-shot
- [Change control-plane membership](../operations/change-control-plane-membership.md) — what adding or removing a
  controller changes, Keystone's Fernet schedule included
- [HAProxy + Keepalived](haproxy-keepalived.md) — the loadbalancer play renders the keystone frontends under
  `-t keystone` (`site.yml:203-207`), and HAProxy restarts if they changed
- [Memcached](memcached.md) — Keystone's token cache (`roles/keystone/templates/keystone.conf.j2:48-51`)
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — Keystone in
  the shared substrate that every OpenStack service uses
- [fact sheet B §3.10][sheet-b-310] — the runtime dependency of other services on Keystone, counted by role
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages

[sheet-b-310]: ../reference/factsheets/b-mariadb-rabbitmq-keystone.md#310-runtime-dependency-of-other-services-on-keystone-grep-across-ansiblerolestemplates
