---
title: Keystone
description: "The 2025.1 study of Keystone: a reconfigure that can no longer be batched, its restart risk, Fernet keys, the public authentication URL and open points."
tags: [keystone, reconfigure, serial, one-shot, risk, dependencies, bugs, unknowns]
---

# Keystone

This page is the starting point for Keystone, the `keystone` role: the containers `keystone`, `keystone_ssh` and
`keystone_fernet` (`roles/keystone/defaults/main.yml:2-58`), on the control nodes of the example inventory
(`inventory/multinode:93-94`), selected by the tag `keystone` (`site.yml:498-510`). Keystone is a hard deploy-time
dependency of the 30 roles whose tasks use `service-ks-register` (keystone itself included; grep of `roles/*/tasks`;
2024.1 had 31, the difference being the removed role swift): registration runs `run_once`
(`roles/service-ks-register/tasks/main.yml:129`) with `openstack_interface` (`internal`) and authenticates against
`keystone_internal_url` (`roles/service-ks-register/defaults/main.yml:5`, `group_vars/all.yml:823`,
`group_vars/all.yml:1126-1132`) [CODE] ([Component
dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses)).

**Changed in 2025.1** [CODE]:
- **No rolling reconfigure or upgrade:** `kolla-ansible reconfigure` and `kolla-ansible upgrade` always pass
  `kolla_serial=0` after the user's `-e`, so the keystone play (`serial` from `kolla_serial`, `site.yml:503`) runs on
  every keystone host at once for these two actions ([F19](../reference/findings.md#f19)). A batched run is now
  `kolla-ansible deploy -t keystone -e kolla_serial=N`, which runs the same tasks ([F5](../reference/findings.md#f5)).
- **Restarts:** no config task notifies; `check-containers.yml` imports `service-check-containers`, which notifies
  `Restart <service> container` for each container whose configuration or definition changed (fact sheet B
  [§3.5](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#35-handlers-ansibleroleskeystonehandlersmainyml-order-is-load-bearing-comment-2-3)).
  `kolla-ansible check` now fails when one of the three containers is missing, stopped or unhealthy
  (`roles/keystone/tasks/check.yml:2-4`).
- **Other services authenticate users against the public URL:** `www_authenticate_uri` is now `keystone_public_url`
  in 25 template lines of 23 roles (2024.1 used `keystone_internal_url`), so the first 2025.1 run changes the
  configuration of every API service that has a `[keystone_authtoken]` section ([fact sheet B §3.10][sheet-b-310]).
- **Messaging:** `keystone.conf` always renders `use_queue_manager = true`, `rabbit_quorum_queue = true` and
  `rabbit_transient_quorum_queue = true` (`roles/keystone/templates/keystone.conf.j2:63,72,77`), and the `keystone`
  container always mounts `/dev/shm` (`roles/keystone/defaults/main.yml:161`)
  ([F17](../reference/findings.md#f17)).
- **HAProxy health checks:** both keystone backends add `option httpchk` (`roles/keystone/defaults/main.yml:21,32`).
- **Domain files:** a file added to `/etc/kolla/config/keystone/domains` once `keystone.conf` already has the domain
  settings now restarts `keystone` instead of failing the 2024.1 "Check keystone containers" task ([fact sheet B
  §3.4](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#34-config-files-ansibleroleskeystonetasksconfigyml)).
- **Still holds:** no admin port and no admin endpoint (the Keystone ports are `keystone_public_port`,
  `keystone_public_listen_port: "5000"`, `keystone_internal_port: "5000"` and `keystone_internal_listen_port`,
  `group_vars/all.yml:508-511`); `keystone_service_endpoints` lists `internal` and `public` only
  (`roles/keystone/defaults/main.yml:202-204`); URLs are built with the `kolla_url` filter
  (`group_vars/all.yml:1096-1097`; `filter_plugins/address.py:25-30`; `kolla_ansible/kolla_url.py:20-41`); the
  bootstrap wrapper is called with seven arguments (`roles/keystone/tasks/register.yml:4-7`); the Fernet templates and
  the cron generator are unchanged.

The lists below say where the study covers how to operate it, its impact, its dependencies and the evidence, what to
check around a run and what stays open; the service card follows them.

## Where to look

### Operate

- **Scenario:** [Reconfigure a single service
  §2](../operations/reconfigure-a-service.md#2-execute-a-service-specific-tag-implicit-effects), [Reconfigure a single
  service §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure)
- **Command:** [Reconfigure a single service
  §1.1](../operations/reconfigure-a-service.md#11-reconfigure-a-single-service)
- **Batches:** [Write config first, apply in controlled batches
  §1.2](../operations/controlled-batches.md#12-rolling-runs-with-kolla_serial-not-with-reconfigure): why a rolling
  Keystone change goes through `deploy -e kolla_serial=N`
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
  service: safe on its own "yes, it is the intended unit; it still runs Keystone registration and DB sync".
  Prerequisites: MariaDB, RabbitMQ, memcached, Keystone (registration), HAProxy VIP.
- [R19](../risk/risk-register.md#r19), precautions for a Keystone `reconfigure`: verify Fernet key consistency before
  and after; for batches, use `deploy -t keystone -e kolla_serial=N`, since `reconfigure` ignores `kolla_serial`
  ([F19](../reference/findings.md#f19)).
- A `reconfigure` with a config change restarts `keystone_ssh`, then `keystone_fernet`, then `keystone`, in the handler
  definition order (`roles/keystone/handlers/main.yml:29-69`), each on all keystone hosts at once [CODE]. Nothing waits
  for the API or the healthcheck before registration runs. The details are in [fact sheet B
  §3.9](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#39-operationally-notable-behaviour-risks-and-oddities).
- The first 2025.1 run after an upgrade from 2024.1 changes `keystone.conf` (messaging options) and the container
  units ([F16](../reference/findings.md#f16)), and the `www_authenticate_uri` change touches every API service: expect
  all keystone containers, and the API containers of the other services, to restart once [CODE]. [NOT AVAILABLE] What
  clients see in the `WWW-Authenticate` header after the change; to be confirmed by the community.
- A batched `deploy` has a limit on a first deployment: when no host of the run so far has a listed `keystone_fernet`
  container and some keystone hosts are outside the current batch, the role fails on purpose rather than bootstrap the
  Fernet keys (`roles/keystone/tasks/bootstrap_service.yml:22-31`) [CODE].
- [R8](../risk/risk-register.md#r8), precautions for a HAProxy config change: `--skip-tags haproxy` when you don't
  intend to change frontends. The `-t keystone` run renders the keystone frontends through the loadbalancer play
  (`site.yml:203-207`), and the new `option httpchk` lines change them on the first 2025.1 run, but changed in 2025.1
  it no longer restarts HAProxy: the new frontends apply at the next run with `-t haproxy`, `-t loadbalancer` or no tag
  ([F18](../reference/findings.md#f18)) [CODE].
- [R24](../risk/risk-register.md#r24), container stop timeout: the stop goes through the container's systemd unit,
  whose `ExecStop` is `/usr/bin/<engine> stop <name> -t <graceful_timeout>`
  (`module_utils/kolla_systemd_worker.py:33`), with `docker_graceful_timeout` 60 s (`group_vars/all.yml:148`)
  ([F3](../reference/findings.md#f3)). Precautions: drain long operations before restarts; raise
  `docker_graceful_timeout` if needed.
- [R22](../risk/risk-register.md#r22), precautions for an inventory reordering (the keystone group is one of the groups
  it names): treat inventory order as configuration; never reorder casually. For Keystone the order matters because the
  Fernet rotation schedule of each host is computed from its index in `groups['keystone']`
  (`roles/keystone/tasks/config.yml:163-174`) [CODE].
- [Reconfigure a single service
  §3](../operations/reconfigure-a-service.md#3-sequence-impact-risks-and-verification-of--t-svc-reconfigure),
  verification of `-t <svc> reconfigure`: before, `kolla-ansible genconfig -t <svc>`, then `kolla_set_configs --check`
  in each `<svc>` container and a diff of `/etc/kolla/haproxy/services.d/<svc>*.cfg` against the previous version;
  after, `openstack endpoint list --service <name>` is unchanged for each Keystone service the role registers, the API
  answers through the VIP, the container start times show which hosts restarted, and the haproxy container's start time
  shows whether HAProxy restarted. For Keystone, the endpoint list has an `internal` and a `public` endpoint only
  (`roles/keystone/defaults/main.yml:202-210`). New in 2025.1: `kolla-ansible check -t keystone` fails if a keystone
  container is unhealthy, which includes a failed `fernet-push.sh --check` dry run in `keystone_fernet`
  (`roles/keystone/templates/fernet-healthcheck.sh.j2:6`) [CODE].

### Known limits and open points

- [Known bugs and limitations](../troubleshooting/known-bugs-and-limitations.md), row `keystone`: fernet cron generator
  hour calculation; precheck vs generator expiry limits; push script stops at the first unreachable peer. Status: all
  three still hold in 2025.1 [CODE], and the files involved are unchanged from 2024.1: the generator computes
  `hour = time % HOUR_SPAN` (`roles/keystone/files/fernet_rotate_cron_generator.py:69`); the precheck asserts
  `fernet_token_expiry <= 604800` (`roles/keystone/tasks/precheck.yml:44-61`) while the generator is fed
  `fernet_key_rotation_interval` (`roles/keystone/tasks/config.yml:163-168`); `fernet-push.sh` runs under
  `set -o errexit` and rsyncs to each peer in turn (`roles/keystone/templates/fernet-push.sh.j2:3`,
  `roles/keystone/templates/fernet-push.sh.j2:17-22`).
- The key distribution after a deploy or reconfigure is one `fernet-push.sh` run, `run_once`, on the first host where a
  `keystone_fernet` container was listed, or on the first keystone host when none was
  (`roles/keystone/tasks/distribute_fernet.yml:12-16`) [CODE]. Changed in 2025.1: the role now groups hosts by whether
  the container is listed, not by its state (`roles/keystone/tasks/bootstrap_service.yml:2-19`); whether the Docker and
  Podman clients list a stopped container there is [NOT AVAILABLE].
- The keystone role still writes `processname` only for a service named `keystone-api`, which it never renders, while
  `use_queue_manager = true` is now always set (`roles/keystone/templates/keystone.conf.j2:63-65`) [CODE]; what
  oslo.messaging's queue manager does without it is [NOT AVAILABLE] ([fact sheet B
  §3.9](../reference/factsheets/b-mariadb-rabbitmq-keystone.md#39-operationally-notable-behaviour-risks-and-oddities),
  item 11).
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
  (`roles/keystone/defaults/main.yml:38-43`);
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
| Play | site.yml:498 |
| Tags | keystone |
| Play host patterns | keystone |
| Node types in play (example inventory) | control |
| Node types running its containers | control |
| Containers | `keystone`, `keystone_ssh`, `keystone_fernet` |
| deploy/reconfigure flow (`tasks/deploy.yml`) | config → check-containers → clone (if) → bootstrap → flush handlers → distribute_fernet → register → register_identity_providers (if) |
| Task files | bootstrap.yml, bootstrap_service.yml, check-containers.yml, check.yml, clone.yml, config-federation-oidc.yml, config.yml, config_validate.yml, copy-certs.yml, deploy-containers.yml, deploy.yml, distribute_fernet.yml, loadbalancer.yml, main.yml, precheck.yml, pull.yml, reconfigure.yml, register.yml, register_identity_providers.yml, stop.yml, upgrade.yml |
| Templates | `crontab.j2`, `fernet-healthcheck.sh.j2`, `fernet-node-sync.sh.j2`, `fernet-push.sh.j2`, `fernet-rotate.sh.j2`, `keystone-fernet.json.j2`, `keystone-ssh.json.j2`, `keystone-startup.sh.j2`, `keystone.conf.j2`, `keystone.json.j2`, `ssh_config.j2`, `sshd_config.j2`, `wsgi-keystone.conf.j2` |
| Handlers (definition order) | Init keystone database upgrade; Restart keystone-ssh container; Restart keystone-fernet container; Restart keystone container; Finish keystone database upgrade |
| Key variables | `enable_keystone`, `keystone_token_provider`, `fernet_token_expiry`, `fernet_key_rotation_interval` |
| Role dependencies | none |

<!-- END GENERATED -->

The card's tool lists `keystone_token_provider` as a key variable for every release; 2025.1 defines no such variable,
and `keystone.conf` sets `provider = fernet` unconditionally (`roles/keystone/templates/keystone.conf.j2:32`) [CODE].


## Related

- [Reconfigure a single service](../operations/reconfigure-a-service.md) — `-t keystone reconfigure`, the command
  example of the page: scope, restarts and one-shot
- [Change control-plane membership](../operations/change-control-plane-membership.md) — what adding or removing a
  controller changes, Keystone's Fernet schedule included
- [HAProxy + Keepalived](haproxy-keepalived.md) — the loadbalancer play renders the keystone frontends under
  `-t keystone` (`site.yml:203-207`); HAProxy picks them up only at its next own run
  ([F18](../reference/findings.md#f18))
- [Memcached](memcached.md) — Keystone's token cache (`roles/keystone/templates/keystone.conf.j2:48-51`)
- [Component dependencies §1](dependencies.md#1-the-shared-substrate-what-every-openstack-service-uses) — Keystone in
  the shared substrate that every OpenStack service uses
- [fact sheet B §3.10][sheet-b-310] — the runtime dependency of other services on Keystone, counted by role
- [Pre-execution checklist](../operations/pre-execution-checklist.md) — the checks before every production run
- [Components](index.md) — the other component pages

[sheet-b-310]: ../reference/factsheets/b-mariadb-rabbitmq-keystone.md#310-runtime-dependency-of-other-services-on-keystone-grep-across-ansiblerolestemplates
